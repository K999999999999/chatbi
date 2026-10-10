"""在候选恢复环境中交互核验一次登录与历史只读端点。"""

from __future__ import annotations

import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _request(port, path, *, token=None, body=None, method=None):
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise RuntimeError("RESTORE_LOGIN_FAILED")
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers=headers,
        method=method or ("POST" if body is not None else "GET"),
    )
    try:
        # verify() supplies a validated port; this URL uses a fixed HTTP loopback host.
        with urlopen(request, timeout=8) as response:  # nosec B310
            payload = response.read(1024**2 + 1)
            if len(payload) > 1024**2:
                raise ValueError()
            return response.status, json.loads(payload) if payload else None
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        raise RuntimeError("RESTORE_LOGIN_FAILED") from None


def verify(port, credentials):
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise RuntimeError("RESTORE_LOGIN_FAILED")
    if (
        not isinstance(credentials, dict)
        or set(credentials) != {"username", "password", "password_hash"}
        or not isinstance(credentials["username"], str)
        or not isinstance(credentials["password"], str)
        or not isinstance(credentials["password_hash"], str)
    ):
        raise RuntimeError("RESTORE_LOGIN_FAILED")
    _, login = _request(
        port,
        "/auth/login",
        body={"username": credentials["username"], "password": credentials["password"]},
    )
    token = login.get("access_token") if isinstance(login, dict) else None
    if not isinstance(token, str) or not token:
        raise RuntimeError("RESTORE_LOGIN_FAILED")
    try:
        _, identity = _request(port, "/auth/me", token=token)
        if (
            not isinstance(identity, dict)
            or identity.get("username") != credentials["username"]
        ):
            raise RuntimeError("RESTORE_LOGIN_FAILED")
        _, histories = _request(port, "/api/v1/histories?limit=20", token=token)
        if (
            not isinstance(histories, dict)
            or not isinstance(histories.get("items"), list)
            or not histories["items"]
        ):
            raise RuntimeError("RESTORE_HISTORY_FAILED")
        found_success_snapshot = False
        for item in histories["items"]:
            history_id = item.get("id") if isinstance(item, dict) else None
            if not isinstance(history_id, str) or not re.fullmatch(r"[0-9a-f-]{36}", history_id):
                continue
            _, header = _request(port, "/api/v1/histories/" + history_id, token=token)
            if not isinstance(header, dict) or header.get("id") != history_id:
                raise RuntimeError("RESTORE_HISTORY_FAILED")
            _, turns = _request(port, "/api/v1/histories/" + history_id + "/turns?limit=100", token=token)
            if not isinstance(turns, dict) or not isinstance(turns.get("items"), list):
                raise TypeError("RESTORE_HISTORY_FAILED")
            for turn in turns["items"]:
                if not isinstance(turn, dict):
                    continue
                turn_id = turn.get("id") if isinstance(turn, dict) else None
                if turn.get("status") != "succeeded" or not isinstance(turn_id, str):
                    continue
                _, detail = _request(
                    port,
                    "/api/v1/histories/" + history_id + "/turns/" + turn_id,
                    token=token,
                )
                snapshot = detail.get("snapshot") if isinstance(detail, dict) else None
                if not isinstance(snapshot, dict):
                    raise TypeError("RESTORE_HISTORY_FAILED")
                found_success_snapshot = True
            if not found_success_snapshot:
                raise RuntimeError("RESTORE_HISTORY_FAILED")
        _, results = _request(port, "/api/v1/saved-results?limit=1", token=token)
        if (
            not isinstance(results, dict)
            or not isinstance(results.get("items"), list)
            or not results["items"]
        ):
            raise RuntimeError("RESTORE_HISTORY_FAILED")
        first_result = results["items"][0]
        result_id = first_result.get("id") if isinstance(first_result, dict) else None
        if not isinstance(result_id, str) or not re.fullmatch(r"[0-9a-f-]{36}", result_id):
            raise RuntimeError("RESTORE_HISTORY_FAILED")
        _, detail = _request(port, "/api/v1/saved-results/" + result_id, token=token)
        if not isinstance(detail, dict) or not isinstance(detail.get("snapshot"), dict):
            raise TypeError("RESTORE_HISTORY_FAILED")
    finally:
        _request(port, "/auth/logout", token=token, method="POST")
    return {"login": True, "history": True}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--credentials-stdin", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.buffer.read(8192)
        if len(raw) >= 8192:
            raise RuntimeError("RESTORE_LOGIN_FAILED")
        credentials = json.loads(raw)
        print(json.dumps(verify(args.port, credentials), sort_keys=True))
    except (RuntimeError, TypeError, EOFError, KeyboardInterrupt):
        print("隔离候选登录/历史只读核验未通过。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
