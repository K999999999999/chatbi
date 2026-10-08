"""生成一次性隔离恢复账号；输出只由调用方保留在内存中。"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore-id", required=True)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{32}", args.restore_id):
        print("恢复 ID 无效。", file=sys.stderr)
        return 1
    from src.authorization.passwords import hash_password

    password = secrets.token_urlsafe(32)
    value = {
        "username": "restore_test_" + args.restore_id[:12],
        "password": password,
        "password_hash": hash_password(password),
    }
    print(json.dumps(value, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
