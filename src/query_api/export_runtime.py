"""受限独立文件 worker 与进程内并发额度。"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .export_assets import verify_runtime_manifest

MAX_EXPORT_BYTES = 20 * 1024 * 1024
EXPORT_DEADLINE_SECONDS = 60
MAX_SNAPSHOT_BYTES = 5 * 1024 * 1024
MAX_WORKER_INPUT_BYTES = MAX_SNAPSHOT_BYTES + 16 * 1024
_WORKER = Path(__file__).with_name("export_worker.py")
_PROCESS_ROOT_LOCK = threading.Lock()
_PROCESS_ROOTS: set[str] = set()


class ExportFailure(RuntimeError):
    def __init__(self, code: str, message: str, status: int):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass(frozen=True)
class ExportArtifact:
    path: Path
    size: int
    deadline: float


class ExportRuntime:
    def __init__(self, temp_root: Path | None = None, *, export_root: Path | None = None, source_root: Path | None = None):
        self._root = (
            Path(temp_root)
            if temp_root
            else Path(tempfile.gettempdir()) / "chatbi-result-exports"
        )
        self._lock = threading.Lock()
        self._startup_lock = threading.Lock()
        self._owner_active: set[int] = set()
        self._active: set[subprocess.Popen] = set()
        self._closing = False
        self._initialized = False
        self._root_lock_fd: int | None = None
        self._process_root_key: str | None = None
        self._export_root = Path(export_root or os.environ.get("CHATBI_EXPORT_ROOT", "/opt/chatbi-export"))
        configured_source = source_root or os.environ.get("CHATBI_EXPORT_SOURCE_DIR")
        self._source_root = Path(configured_source) if configured_source else None
        self._render_config: dict | None = None

    def startup(self) -> None:
        with self._startup_lock:
            if self._initialized:
                return
            with self._lock:
                if self._closing:
                    raise ExportFailure(
                        "EXPORT_UNAVAILABLE", "文件导出服务正在关闭", 503
                    )
            self._root.mkdir(mode=0o700, parents=True, exist_ok=True)
            info = self._root.lstat()
            if (
                not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o077
            ):
                raise RuntimeError("导出临时目录必须为当前服务用户独占")
            lock_path = self._root / ".runtime.lock"
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            try:
                os.fchmod(lock_fd, 0o600)
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(lock_fd)
                raise RuntimeError("成果导出仅支持单 API 进程") from None
            except BaseException:
                os.close(lock_fd)
                raise
            process_root_key = str(self._root.resolve())
            with _PROCESS_ROOT_LOCK:
                if process_root_key in _PROCESS_ROOTS:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                    os.close(lock_fd)
                    raise RuntimeError("成果导出仅支持单 API 进程")
                _PROCESS_ROOTS.add(process_root_key)
            try:
                for entry in self._root.iterdir():
                    if entry == lock_path:
                        continue
                    info = entry.lstat()
                    if (
                        not stat.S_ISDIR(info.st_mode)
                        or info.st_uid != os.geteuid()
                        or info.st_mode & 0o077
                    ):
                        raise RuntimeError("导出临时根含有不可安全回收的条目")
                    shutil.rmtree(entry)
            except BaseException:
                with _PROCESS_ROOT_LOCK:
                    _PROCESS_ROOTS.discard(process_root_key)
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
                raise
            self._root_lock_fd = lock_fd
            self._process_root_key = process_root_key
            try:
                self._render_config = verify_runtime_manifest(
                    self._export_root, self._source_root
                )
            except (OSError, ValueError, TypeError, ImportError, KeyError):
                # PNG asset drift never disables the existing XLSX renderer.
                self._render_config = None
            self._initialized = True

    def acquire(self, owner: int) -> bool:
        try:
            self.startup()
        except ExportFailure:
            raise
        except (OSError, RuntimeError):
            raise ExportFailure(
                "EXPORT_UNAVAILABLE", "文件导出运行环境不可用", 503
            ) from None
        with self._lock:
            if (
                self._closing
                or owner in self._owner_active
                or len(self._owner_active) >= 2
            ):
                return False
            self._owner_active.add(owner)
            return True

    def release(self, owner: int) -> None:
        with self._lock:
            self._owner_active.discard(owner)

    def generate(
        self,
        owner: int,
        document: dict,
        cancelled: threading.Event,
        *,
        format: str = "xlsx",
        selection: dict | None = None,
    ):
        if format not in {"xlsx", "png", "pdf"}:
            raise ExportFailure("EXPORT_FORMAT_UNAVAILABLE", "所选导出格式暂不可用", 422)
        if os.geteuid() == 0:
            raise ExportFailure("EXPORT_UNAVAILABLE", "文件导出运行账户配置无效", 503)
        if not self.acquire(owner):
            raise ExportFailure(
                "EXPORT_BUSY", "已有文件正在生成或下载，请稍后重试", 429
            )
        if format in {"png", "pdf"}:
            try:
                self._render_config = verify_runtime_manifest(
                    self._export_root, self._source_root
                )
            except (OSError, ValueError, TypeError, ImportError, KeyError):
                self._render_config = None
            if self._render_config is None:
                self.release(owner)
                raise ExportFailure("EXPORT_UNAVAILABLE", "离线 Chromium 渲染资源不可用", 503)
        if format == "png" and not selection:
            self.release(owner)
            raise ExportFailure("EXPORT_SELECTION_INVALID", "图表选择无效", 422)
        workdir = self._root / uuid.uuid4().hex
        deadline = time.monotonic() + EXPORT_DEADLINE_SECONDS
        try:
            return self._generate(
                workdir, document, cancelled, deadline, format, selection
            )
        except BaseException:
            try:
                _remove_workdir(workdir)
            except OSError:
                raise ExportFailure(
                    "EXPORT_STORAGE_UNAVAILABLE", "导出临时文件清理失败", 503
                ) from None
            self.release(owner)
            raise

    def _generate(
        self,
        workdir: Path,
        document: dict,
        cancelled: threading.Event,
        deadline: float,
        format: str,
        selection: dict | None,
    ):
        payload = json.dumps(
            {"format": format, "document": document, "selection": selection},
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        source_payload = json.dumps(
            {key: value for key, value in document.items() if key != "export_time"},
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if (
            len(source_payload) > MAX_SNAPSHOT_BYTES
            or len(payload) > MAX_WORKER_INPUT_BYTES
        ):
            raise ExportFailure(
                "EXPORT_INPUT_TOO_LARGE", "结果快照超过 5 MiB，无法导出", 413
            )
        if time.monotonic() >= deadline:
            raise ExportFailure("EXPORT_TIMEOUT", "文件生成超过 60 秒限制", 504)

        workdir.mkdir(mode=0o700)
        os.chmod(workdir, 0o700)
        output = workdir / {"xlsx": "result.xlsx", "png": "result.png", "pdf": "result.pdf"}[format]
        environment = {"PATH": os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
        if format in {"png", "pdf"}:
            assert self._render_config is not None
            environment.update(
                {
                    "HOME": str(workdir),
                    "CHATBI_EXPORT_ROOT": str(self._export_root),
                    "PLAYWRIGHT_BROWSERS_PATH": str(self._render_config["browser_root"]),
                }
            )
        process = subprocess.Popen(
            [sys.executable, "-I", str(_WORKER), str(output)],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=workdir,
            env=environment,
            close_fds=True,
            start_new_session=True,
        )
        with self._lock:
            if self._closing:
                process.kill()
                process.wait()
                raise ExportFailure("EXPORT_UNAVAILABLE", "文件导出服务正在关闭", 503)
            self._active.add(process)
        try:
            pending_input = payload
            while process.poll() is None:
                if cancelled.is_set():
                    self._stop_group(process)
                    raise ExportFailure("EXPORT_DISCONNECTED", "下载连接已中断", 499)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._stop_group(process)
                    raise ExportFailure("EXPORT_TIMEOUT", "文件生成超过 60 秒限制", 504)
                try:
                    process.communicate(
                        input=pending_input, timeout=min(0.05, remaining)
                    )
                    pending_input = None
                except subprocess.TimeoutExpired:
                    pending_input = None
            if time.monotonic() >= deadline:
                raise ExportFailure("EXPORT_TIMEOUT", "文件生成超过 60 秒限制", 504)
            if process.returncode != 0:
                if process.returncode == 8:
                    raise ExportFailure(
                        "EXPORT_SELECTION_INVALID", "所选图表不可用", 422
                    )
                if process.returncode == 9:
                    raise ExportFailure(
                        "EXPORT_UNAVAILABLE", "离线 Chromium 渲染资源不可用", 503
                    )
                if process.returncode == 10:
                    raise ExportFailure(
                        "EXPORT_TOO_LARGE", "导出文件超过 20 MiB 限制", 413
                    )
                raise ExportFailure(
                    "EXPORT_FAILED", "文件无法完整生成，请稍后重试", 422
                )
            try:
                output_fd = os.open(
                    output, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
                )
            except OSError:
                raise ExportFailure(
                    "EXPORT_FAILED", "文件无法完整生成，请稍后重试", 422
                ) from None
            try:
                info = os.fstat(output_fd)
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
                    raise ExportFailure(
                        "EXPORT_FAILED", "文件无法完整生成，请稍后重试", 422
                    )
                os.fchmod(output_fd, 0o600)
                size = os.fstat(output_fd).st_size
            finally:
                os.close(output_fd)
            if not 0 < size <= MAX_EXPORT_BYTES:
                raise ExportFailure("EXPORT_TOO_LARGE", "导出文件超过 20 MiB 限制", 413)
            return ExportArtifact(output, size, deadline)
        except BaseException:
            if process.poll() is None:
                self._stop_group(process)
            raise
        finally:
            with self._lock:
                self._active.discard(process)

    @staticmethod
    def _stop_group(process: subprocess.Popen) -> None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            if process.poll() is None:
                process.wait()
            return
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if process.poll() is None:
            process.wait()

    def finish(self, owner: int, path: Path) -> None:
        try:
            _remove_workdir(path.parent)
        except OSError:
            raise ExportFailure(
                "EXPORT_STORAGE_UNAVAILABLE", "导出临时文件清理失败", 503
            ) from None
        self.release(owner)

    def shutdown(self) -> None:
        with self._lock:
            self._closing = True
            processes = tuple(self._active)
        for process in processes:
            self._stop_group(process)
        with self._startup_lock:
            if not self._initialized:
                with self._lock:
                    self._closing = False
                return
            for path in self._root.iterdir():
                if path.name != ".runtime.lock" and path.is_dir():
                    _remove_workdir(path)
            with self._lock:
                self._active.clear()
                self._owner_active.clear()
                self._closing = False
            assert self._root_lock_fd is not None
            fcntl.flock(self._root_lock_fd, fcntl.LOCK_UN)
            os.close(self._root_lock_fd)
            self._root_lock_fd = None
            self._initialized = False
            with _PROCESS_ROOT_LOCK:
                if self._process_root_key is not None:
                    _PROCESS_ROOTS.discard(self._process_root_key)
            self._process_root_key = None
            self._render_config = None


def _remove_workdir(path: Path) -> None:
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass
