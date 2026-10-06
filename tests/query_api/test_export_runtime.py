from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.query_api import export_runtime
from src.query_api.export_runtime import ExportFailure, ExportRuntime


def test_export_slots_enforce_owner_and_global_limits(tmp_path):
    runtime = ExportRuntime(tmp_path)
    assert runtime.acquire(1)
    assert not runtime.acquire(1)
    assert runtime.acquire(2)
    assert not runtime.acquire(3)
    runtime.release(1)
    assert runtime.acquire(3)
    runtime.release(2)
    runtime.release(3)
    runtime.shutdown()


def test_runtime_cleans_only_its_private_stale_workdirs_and_locks_process(tmp_path):
    root = tmp_path / "exports"
    stale = root / ("a" * 32)
    root.mkdir(mode=0o700)
    stale.mkdir(mode=0o700)
    (stale / "partial.xlsx").write_bytes(b"partial")
    runtime = ExportRuntime(root)
    runtime.startup()
    assert not stale.exists()
    assert (root / ".runtime.lock").stat().st_mode & 0o777 == 0o600
    with pytest.raises(RuntimeError, match="单 API 进程"):
        ExportRuntime(root).startup()
    runtime.shutdown()
    restarted = ExportRuntime(root)
    restarted.startup()
    restarted.shutdown()


def test_runtime_keeps_quota_until_temporary_directory_is_removed(
    tmp_path, monkeypatch
):
    runtime = ExportRuntime(tmp_path / "exports")
    assert runtime.acquire(7)
    workdir = runtime._root / ("b" * 32)
    workdir.mkdir(mode=0o700)
    (workdir / "partial.xlsx").write_bytes(b"partial")
    remove = export_runtime.shutil.rmtree

    def fail_remove(_path):
        raise PermissionError("cleanup failure")

    monkeypatch.setattr(export_runtime.shutil, "rmtree", fail_remove)
    with pytest.raises(ExportFailure, match="清理失败"):
        runtime.finish(7, workdir / "partial.xlsx")
    assert not runtime.acquire(7)

    monkeypatch.setattr(export_runtime.shutil, "rmtree", remove)
    runtime.finish(7, workdir / "partial.xlsx")
    assert not workdir.exists()
    assert runtime.acquire(7)
    runtime.release(7)
    runtime.shutdown()


def test_timeout_kills_worker_group_and_releases_owner_slot(tmp_path, monkeypatch):
    script = tmp_path / "hang.py"
    pid_file = tmp_path / "worker.pid"
    script.write_text(
        "import os, sys, time\n"
        f"open({str(pid_file)!r}, 'w').write(str(os.getpid()))\n"
        "sys.stdin.buffer.read()\n"
        "time.sleep(30)\n"
    )
    monkeypatch.setattr(export_runtime, "_WORKER", script)
    monkeypatch.setattr(export_runtime, "EXPORT_DEADLINE_SECONDS", 0.3)
    runtime = ExportRuntime(tmp_path / "runtime")
    with pytest.raises(ExportFailure, match="60 秒"):
        runtime.generate(1, {"result": {"rows": []}}, threading.Event())
    pid = int(pid_file.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert runtime.acquire(1)
    runtime.release(1)
    runtime.shutdown()


def test_snapshot_size_limit_releases_slot_without_starting_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(export_runtime, "MAX_SNAPSHOT_BYTES", 16)
    runtime = ExportRuntime(tmp_path / "runtime")
    with pytest.raises(ExportFailure, match="5 MiB") as failure:
        runtime.generate(1, {"result": {"rows": ["x" * 32]}}, threading.Event())
    assert failure.value.code == "EXPORT_INPUT_TOO_LARGE"
    assert runtime.acquire(1)
    runtime.release(1)
    assert [path for path in runtime._root.iterdir() if path.is_dir()] == []
    runtime.shutdown()


def test_output_size_limit_releases_slot_and_removes_completed_file(
    tmp_path, monkeypatch
):
    script = tmp_path / "large-output.py"
    script.write_text(
        "import sys\n"
        "sys.stdin.buffer.read()\n"
        "with open(sys.argv[1], 'wb') as output: output.write(b'1234')\n"
    )
    monkeypatch.setattr(export_runtime, "_WORKER", script)
    monkeypatch.setattr(export_runtime, "MAX_EXPORT_BYTES", 3)
    runtime = ExportRuntime(tmp_path / "runtime")
    with pytest.raises(ExportFailure, match="超过 20 MiB") as failure:
        runtime.generate(1, {"result": {"rows": []}}, threading.Event())
    assert failure.value.code == "EXPORT_TOO_LARGE"
    assert runtime.acquire(1)
    runtime.release(1)
    assert [path for path in runtime._root.iterdir() if path.is_dir()] == []
    runtime.shutdown()


def test_worker_symlink_output_is_rejected_without_changing_target_permissions(
    tmp_path, monkeypatch
):
    target = tmp_path / "outside.xlsx"
    target.write_bytes(b"outside")
    target.chmod(0o644)
    script = tmp_path / "symlink-output.py"
    script.write_text(
        "import os, sys\n"
        "sys.stdin.buffer.read()\n"
        f"os.symlink({str(target)!r}, sys.argv[1])\n"
    )
    monkeypatch.setattr(export_runtime, "_WORKER", script)
    runtime = ExportRuntime(tmp_path / "runtime")
    with pytest.raises(ExportFailure) as failure:
        runtime.generate(1, {"result": {"rows": []}}, threading.Event())
    assert failure.value.code == "EXPORT_FAILED"
    assert target.stat().st_mode & 0o777 == 0o644
    assert runtime.acquire(1)
    runtime.release(1)
    runtime.shutdown()


def test_shutdown_kills_active_worker_and_cleans_its_workdir(tmp_path, monkeypatch):
    script = tmp_path / "shutdown.py"
    pid_file = tmp_path / "worker.pid"
    script.write_text(
        "import os, sys, time\n"
        f"open({str(pid_file)!r}, 'w').write(str(os.getpid()))\n"
        "sys.stdin.buffer.read()\n"
        "time.sleep(30)\n"
    )
    monkeypatch.setattr(export_runtime, "_WORKER", script)
    runtime = ExportRuntime(tmp_path / "runtime")
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(runtime.generate, 1, {"result": {"rows": []}}, threading.Event())
        deadline = time.monotonic() + 3
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert pid_file.exists()
        pid = int(pid_file.read_text())
        runtime.shutdown()
        with pytest.raises(ExportFailure):
            result.result(timeout=5)
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert runtime._owner_active == set()
    assert [path for path in runtime._root.iterdir() if path.is_dir()] == []


def test_cancellation_kills_worker_and_releases_owner_slot(tmp_path, monkeypatch):
    script = tmp_path / "cancel.py"
    pid_file = tmp_path / "worker.pid"
    child_pid_file = tmp_path / "child.pid"
    child_code = (
        "import os, signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"open({str(child_pid_file)!r}, 'w').write(str(os.getpid()))\n"
        "time.sleep(30)\n"
    )
    script.write_text(
        "import os, subprocess, sys, time\n"
        f"open({str(pid_file)!r}, 'w').write(str(os.getpid()))\n"
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}])\n"
        "sys.stdin.buffer.read()\n"
        "time.sleep(30)\n"
    )
    monkeypatch.setattr(export_runtime, "_WORKER", script)
    runtime = ExportRuntime(tmp_path / "runtime")
    cancelled = threading.Event()
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(runtime.generate, 1, {"result": {"rows": []}}, cancelled)
        deadline = time.monotonic() + 3
        while (
            (not pid_file.exists() or not child_pid_file.exists())
            and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        assert pid_file.exists() and child_pid_file.exists()
        pid = int(pid_file.read_text())
        child_pid = int(child_pid_file.read_text())
        cancelled.set()
        with pytest.raises(ExportFailure, match="连接已中断"):
            result.result(timeout=5)
    for stopped_pid in (pid, child_pid):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                os.kill(stopped_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.01)
        else:
            if stopped_pid == child_pid:
                os.kill(child_pid, 9)
            pytest.fail(f"worker process {stopped_pid} survived cancellation")
    assert runtime.acquire(1)
    runtime.release(1)
    runtime.shutdown()
