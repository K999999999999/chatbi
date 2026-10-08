"""在目标API容器内以本机操作者权限读取安全快照，不续期用户会话。"""

import json
import socket

from src.bootstrap.operations_socket import SOCKET_PATH


def read_status(path=SOCKET_PATH):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(3)
        connection.connect(path)
        with connection.makefile("rb") as stream:
            data = stream.readline(16385)
        if len(data) > 16384:
            raise ValueError("运行状态大小无效")
        return json.loads(data)


def main():
    try:
        snapshot = read_status()
    except (OSError, ValueError):
        snapshot = {"status": "unknown", "checked_at": None}
    print(json.dumps(snapshot, ensure_ascii=False))


if __name__ == "__main__":
    main()
