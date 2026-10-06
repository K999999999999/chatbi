"""凭证隔离的文件 worker 入口。父进程只交付公开快照 JSON。"""

from __future__ import annotations

import ctypes
import json
import os
import resource
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.query_api.export_xlsx import create_query_workbook

MAX_INPUT_BYTES = 5 * 1024 * 1024 + 16 * 1024


def _parent_liveness_guard() -> bool:
    parent_pid = os.getppid()
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        return False
    return os.getppid() == parent_pid


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    if not _parent_liveness_guard():
        return 7
    if os.geteuid() == 0:
        return 6
    os.umask(0o077)
    maximum = 20 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_FSIZE, (maximum, maximum))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    destination = sys.argv[1]
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        return 3
    try:
        source = json.loads(raw)
        if not isinstance(source, dict) or source.get("format") != "xlsx":
            return 4
        create_query_workbook(source["document"], destination)
    except Exception:  # noqa: BLE001 - worker stderr must not expose source data
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
