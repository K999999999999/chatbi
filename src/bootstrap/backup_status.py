"""读取工具写出的安全投影；不访问备份、私钥或可信目录。"""

import json
import os
import stat
import re
from datetime import UTC, datetime
from pathlib import Path

FAILURE_CODES = frozenset(
    {
        "BACKUP_FAILED",
        "BACKUP_LOCKED",
        "BACKUP_KEY_UNAVAILABLE",
        "BACKUP_STORAGE_UNAVAILABLE",
        "BACKUP_TIMEOUT",
        "BACKUP_INVALID",
    }
)


def read_backup_status(path=Path("/opt/chatbi-operations/backup.json")):
    unknown = {"status": "unknown", "last_success": None, "overdue": True}
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return unknown
            data = stream.read(4097)
        if len(data) > 4096:
            return unknown
        value = json.loads(data)
        if not isinstance(value, dict) or value.get("version") != 1:
            return unknown
        failure = value.get("failure_code")
        timestamp = value.get("last_success")
        if timestamp is None and isinstance(failure, str) and failure in FAILURE_CODES:
            return dict(unknown, failure_code=failure)
        if not isinstance(timestamp, str) or not re.fullmatch(
            r"[0-9TZ:+.\-]{20,40}", timestamp
        ):
            return unknown
        success = datetime.fromisoformat(timestamp)
        if success.tzinfo is None:
            return unknown
        age = (datetime.now(UTC) - success).total_seconds()
        if age < -60:
            return unknown
        result = {"status": "known", "last_success": timestamp, "overdue": age > 86400}
        failure = value.get("failure_code")
        if isinstance(failure, str) and failure in FAILURE_CODES:
            result["failure_code"] = failure
        return result
    except (OSError, ValueError, TypeError):
        return unknown
