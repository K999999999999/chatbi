"""有界只读诊断；不装配模型、不发送LLM请求、不修改账号。"""

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .operations import ProcessReadinessProbe


def http_status(url, *, ready=False):
    try:
        if urlsplit(url).scheme not in {"http", "https"}:
            return "not_ready"
        # 仅HTTP(S)；标准urllib重定向处理器也拒绝file/custom协议。
        with urlopen(Request(url), timeout=3) as response:  # nosec B310
            if response.status != 200:
                return "not_ready"
            if ready and json.loads(response.read(4096)).get("status") != "ready":
                return "not_ready"
        return "ready"
    except Exception:  # noqa: BLE001 - 不输出网络或凭据详情
        return "not_ready"


def diagnose():
    result = ProcessReadinessProbe(timeout=12)()
    from scripts.check_dev_qdrant import _check

    try:
        _check(
            os.environ.get("RAG_QDRANT_URL", "http://qdrant:6333"),
            os.environ.get("QDRANT_API_KEY", ""),
        )
        result["qdrant_health"] = "ready"
    except Exception:  # noqa: BLE001 - 原探针异常可能含连接详情
        result["qdrant_health"] = "not_ready"
    result["api_health"] = http_status("http://api:8000/health")
    result["api_ready"] = http_status("http://api:8000/ready", ready=True)
    result["web"] = http_status(
        "http://web:" + os.environ.get("CHATBI_DEV_WEB_PORT", "5173")
    )
    result["model"] = (
        "ready"
        if (Path(os.environ.get("RAG_MODEL_DIR", "/missing")) / "config.json").is_file()
        else "not_ready"
    )
    return result


def main():
    if os.environ.get("CHATBI_MAINTENANCE_TARGET", "dev") != "dev":
        print("诊断目标无效；当前只支持 dev。", file=sys.stderr)
        return 2
    result = diagnose()
    print(json.dumps({"checks": result, "llm": "not_probed"}, ensure_ascii=False))
    return 0 if all(value == "ready" for value in result.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
