"""容器内仅同UID可读的运行状态socket；不给公开HTTP增加诊断详情。"""

import errno
import json
import os
import socket
import socketserver
import stat
from pathlib import Path
from threading import Thread

SOCKET_PATH = os.environ.get(
    "CHATBI_OPERATIONS_SOCKET_PATH", "/tmp/chatbi-operations.sock"
)


class OperationsSocket:
    def __init__(self, snapshot, *, path=None):
        self._path = Path(
            path or os.environ.get("CHATBI_OPERATIONS_SOCKET_PATH", SOCKET_PATH)
        )
        self._snapshot = snapshot
        self._server = None
        self._thread = None
        self._inode = None

    def start(self):
        if self._path.exists():
            info = self._path.lstat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                raise RuntimeError("运行状态socket归属未确认")
            with socket.socket(socket.AF_UNIX) as connection:
                connection.settimeout(0.5)
                try:
                    connection.connect(str(self._path))
                except OSError as exc:
                    if exc.errno != errno.ECONNREFUSED:
                        raise RuntimeError(
                            "运行状态socket仍在使用或归属未确认"
                        ) from None
                else:
                    raise RuntimeError("运行状态socket已有运行进程")
            self._path.unlink()
        snapshot = self._snapshot

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.settimeout(0.5)
                try:
                    self.request.sendall(
                        json.dumps(snapshot(), ensure_ascii=False).encode() + b"\n"
                    )
                except OSError:
                    return

        self._server = socketserver.UnixStreamServer(str(self._path), Handler)
        os.chmod(self._path, 0o600)
        self._inode = self._path.stat().st_ino
        self._thread = Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.1},
            daemon=True,
            name="chatbi-status-socket",
        )
        self._thread.start()

    def close(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=1)
        if self._path.exists() and self._path.lstat().st_ino == self._inode:
            self._path.unlink()


def runtime_snapshot(operations):
    """仅本机 socket 的实际发布资产证据；HTTP 不暴露此投影。"""
    import hashlib
    from datetime import UTC, datetime

    result = dict(
        operations.snapshot(detailed=True),
        source_commit=os.environ.get("CHATBI_SOURCE_COMMIT"),
    )
    result["observed_at"] = datetime.now(UTC).isoformat()
    result["asset_sha256"] = None
    try:
        root = Path(os.environ.get("RAG_OUTPUT_DIR", "/opt/chatbi-rag"))
        pointer = (root / "current.json").read_bytes()
        if len(pointer) > 1024**2:
            return result
        value = json.loads(pointer)
        ref = Path(value["manifest_path"])
        if ref.is_absolute() or ".." in ref.parts:
            return result
        target = root / ref
        if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
            return result
        manifest = target.read_bytes()
        if len(manifest) > 1024**2:
            return result
        result["asset_sha256"] = {
            "rag-current.json": hashlib.sha256(pointer).hexdigest(),
            "rag-manifest.json": hashlib.sha256(manifest).hexdigest(),
        }
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return result
