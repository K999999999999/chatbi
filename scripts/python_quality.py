"""在工具容器中复用CI固定版本的Python质量入口。"""

import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> int:
    with TemporaryDirectory(prefix="chatbi-quality-") as cache:
        environment = {
            **os.environ,
            "UV_CACHE_DIR": str(Path(cache) / "uv"),
            "RUFF_CACHE_DIR": str(Path(cache) / "ruff"),
        }
        return subprocess.call(
            ["bash", "scripts/check_python_quality.sh"],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
        )


if __name__ == "__main__":
    raise SystemExit(main())
