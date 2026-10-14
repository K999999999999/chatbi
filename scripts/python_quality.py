"""在工具容器中复用CI固定版本的Python质量入口。"""

import os
import subprocess
from pathlib import Path


def main() -> int:
    environment = {
        **os.environ,
        "UV_CACHE_DIR": "/tmp/chatbi-uv-cache",
        "RUFF_CACHE_DIR": "/tmp/chatbi-ruff-cache",
    }
    return subprocess.call(
        ["bash", "scripts/check_python_quality.sh"],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
    )


if __name__ == "__main__":
    raise SystemExit(main())
