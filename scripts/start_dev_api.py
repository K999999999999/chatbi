"""开发 API 启动入口；在热重载父进程启动前等待控制库。"""

import os
import sys
import time

from src.bootstrap.operations import ProcessReadinessProbe


def wait_for_control_database(timeout: float = 120) -> bool:
    probe = ProcessReadinessProbe()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if probe()["control_database"] == "ready":
            return True
        time.sleep(2)
    return False


def main() -> int:
    print("等待控制库就绪后启动开发 API。", flush=True)
    if not wait_for_control_database():
        print(
            "控制库尚未就绪；开发 API 未启动，请检查基础设施与迁移。", file=sys.stderr
        )
        return 1
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "src.query_api.main:app",
            "--host",
            "0.0.0.0",  # nosec B104 - 容器内监听，Compose仅发布宿主回环。
            "--port",
            "8000",
            "--reload",
            "--reload-dir",
            "/workspace/src",
            "--reload-dir",
            "/workspace/scripts",
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
