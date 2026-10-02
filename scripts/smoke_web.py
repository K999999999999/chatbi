"""打包网页 + 正式 API 登录 Smoke；凭证仅从进程环境读取。"""

import argparse
import os
import secrets

import httpx


def run_smoke(base_url: str, username: str, password: str) -> None:
    origin = base_url.rstrip("/")
    headers = {"Origin": origin, "X-ChatBI-Request": "browser"}
    with httpx.Client(base_url=origin, timeout=10, trust_env=False) as client:
        assert client.get("/health").json() == {"status": "ok"}
        index = client.get("/")
        assert index.status_code == 200 and '<div id="root">' in index.text
        response = client.post(
            "/auth/browser/login",
            json={"username": username, "password": password},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" not in body
        assert "httponly" in response.headers["set-cookie"].lower()
        assert response.headers["cache-control"] == "no-store"
        headers["X-ChatBI-User-ID"] = str(body["user_id"])
        if body["must_change_password"]:
            new_password = secrets.token_urlsafe(32)
            changed = client.post(
                "/auth/browser/change-password",
                json={"current_password": password, "new_password": new_password},
                headers=headers,
            )
            assert changed.status_code == 204
            assert client.get("/auth/browser/me").status_code == 401
            response = client.post(
                "/auth/browser/login",
                json={"username": username, "password": new_password},
                headers=headers,
            )
            assert response.status_code == 200
        assert client.get("/auth/browser/me").status_code == 200
        # 故意缺少问题；只验证新默认入口 / 登录，不调用 CI 的假模型。
        assert client.post("/api/v1/query", json={}, headers=headers).status_code == 400
        assert (
            client.post("/auth/browser/logout", json={}, headers=headers).status_code
            == 204
        )
        assert client.get("/auth/browser/me").status_code == 401


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    password = os.environ.get("CHATBI_SMOKE_PASSWORD", "")
    if not password:
        print("Web smoke 缺少显式验收凭证")
        return 1
    try:
        run_smoke(
            args.base_url, os.environ.get("CHATBI_SMOKE_USERNAME", "admin-1"), password
        )
    except Exception as error:
        print(f"Web startup smoke: FAIL ({type(error).__name__})")
        return 1
    print("Web startup smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
