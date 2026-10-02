from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.authorization import (
    AuthService,
    InMemoryAuditSink,
    LocalSessionIdentityProvider,
    RoleAuthorizationPolicyStore,
    hash_password,
)
from src.chatbi_control.bootstrap import seed_rbac
from src.chatbi_control.models import Base, User
from src.online_query.contracts import QuerySuccess
from src.query_api.app import create_app
from src.query_api.browser import COOKIE_NAME, BrowserSettings


def test_browser_login_is_explicitly_unavailable_without_web_configuration():
    client = TestClient(create_app(Mock()))
    response = client.post(
        "/auth/browser/login", json={"username": "analyst", "password": "invalid"}
    )
    assert response.status_code == 503


ORIGIN = "http://127.0.0.1:5173"
HEADERS = {
    "Origin": ORIGIN,
    "X-ChatBI-Request": "browser",
    "Content-Type": "application/json",
}


@pytest.fixture
def browser():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as session:
        roles = seed_rbac(session)
        session.add_all(
            [
                User(
                    username="analyst",
                    password_hash=hash_password("test-password-123"),
                    is_active=True,
                    must_change_password=False,
                    roles=[roles["analyst"]],
                ),
                User(
                    username="new-user",
                    password_hash=hash_password("test-password-123"),
                    is_active=True,
                    must_change_password=True,
                    roles=[roles["analyst"]],
                ),
            ]
        )
        session.commit()
    clock = [datetime(2026, 10, 3, tzinfo=UTC)]
    auth = AuthService(sessions, clock=lambda: clock[0])
    service = Mock()
    service.execute.return_value = QuerySuccess(
        "req-browser", "SELECT 1", ("value",), ((1,),), 1, False
    )
    app = create_app(
        service,
        auth_service=auth,
        audit_sink=InMemoryAuditSink(),
        identity_provider=LocalSessionIdentityProvider(auth),
        policy_store=RoleAuthorizationPolicyStore(),
        browser_settings=BrowserSettings(ORIGIN, secure=False),
    )
    with TestClient(app) as client:
        yield client, service, clock, auth
    engine.dispose()


def login(client, username="analyst"):
    response = client.post(
        "/auth/browser/login",
        json={"username": username, "password": "test-password-123"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    return {**HEADERS, "X-ChatBI-User-ID": str(response.json()["user_id"])}


def test_cookie_login_refresh_query_and_logout(browser):
    client, service, _, _ = browser
    headers = login(client)
    assert "access_token" not in client.get("/auth/browser/me").json()
    assert client.get("/auth/browser/me").headers["cache-control"] == "no-store"
    response = client.post(
        "/api/v1/query", json={"question": "查询销售额"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["rows"] == [[1]]
    assert len(service.execute.call_args_list) == 1
    assert (
        client.post("/auth/browser/logout", json={}, headers=headers).status_code == 204
    )
    assert COOKIE_NAME not in client.cookies
    assert client.get("/auth/browser/me").status_code == 401


@pytest.mark.parametrize(
    "bad_headers",
    [
        {},
        {**HEADERS, "Origin": "null"},
        {**HEADERS, "Origin": "https://attacker.invalid"},
        {**HEADERS, "X-ChatBI-Request": ""},
        {**HEADERS, "Sec-Fetch-Site": "cross-site"},
    ],
)
def test_login_csrf_rejected(browser, bad_headers):
    client, _, _, _ = browser
    response = client.post(
        "/auth/browser/login",
        json={"username": "analyst", "password": "test-password-123"},
        headers=bad_headers,
    )
    assert response.status_code == 403
    assert COOKIE_NAME not in client.cookies


def test_cookie_csrf_and_wrong_user_are_rejected_before_query(browser):
    client, service, _, _ = browser
    headers = login(client)
    for supplied, expected in [
        ({}, 403),
        ({**headers, "X-ChatBI-User-ID": "999"}, 401),
        ({**headers, "Authorization": "Bearer invalid"}, 401),
    ]:
        response = client.post(
            "/api/v1/query", json={"question": "查询销售额"}, headers=supplied
        )
        assert response.status_code == expected
    assert not service.execute.called


def test_first_password_change_revokes_cookie_and_old_bearer(browser):
    client, service, _, auth = browser
    old = auth.login("new-user", "test-password-123").token
    headers = login(client, "new-user")
    assert (
        client.post(
            "/api/v1/query", json={"question": "查询销售额"}, headers=headers
        ).status_code
        == 403
    )
    changed = client.post(
        "/auth/browser/change-password",
        json={
            "current_password": "test-password-123",
            "new_password": "updated-password-123",
        },
        headers=headers,
    )
    assert changed.status_code == 204
    assert COOKIE_NAME not in client.cookies
    assert (
        client.get("/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code
        == 401
    )
    assert not service.execute.called


def test_session_idle_expiry_and_logout_cleanup(browser):
    client, _, clock, _ = browser
    headers = login(client)
    clock[0] += timedelta(minutes=31)
    assert client.get("/auth/browser/me").status_code == 401
    assert (
        client.post("/auth/browser/logout", json={}, headers=headers).status_code == 204
    )
    assert COOKIE_NAME not in client.cookies


def test_production_cookie_and_origin_configuration():
    settings = BrowserSettings.from_environment(
        {"CHATBI_ENV": "production", "CHATBI_WEB_ORIGIN": "https://chatbi.example"}
    )
    assert settings.secure
    with pytest.raises(ValueError):
        BrowserSettings.from_environment(
            {"CHATBI_ENV": "production", "CHATBI_WEB_ORIGIN": ORIGIN}
        )


def test_cookie_attributes(browser):
    client, _, _, _ = browser
    response = client.post(
        "/auth/browser/login",
        json={"username": "analyst", "password": "test-password-123"},
        headers=HEADERS,
    )
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/" in cookie
    assert "domain=" not in cookie and "max-age=" not in cookie


def test_logout_database_failure_does_not_claim_success(browser, monkeypatch):
    client, _, _, auth = browser
    headers = login(client)

    def failed_logout(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(auth, "logout", failed_logout)
    response = client.post("/auth/browser/logout", json={}, headers=headers)
    assert response.status_code == 503
    assert COOKIE_NAME in client.cookies
    assert client.get("/auth/browser/me").status_code == 200


def test_absolute_expiry_even_with_activity(browser):
    client, _, clock, _ = browser
    login(client)
    for _ in range(16):
        clock[0] += timedelta(minutes=29)
        assert client.get("/auth/browser/me").status_code == 200
    clock[0] += timedelta(minutes=16)
    assert client.get("/auth/browser/me").status_code == 401


def test_packaged_files_do_not_shadow_api_or_expose_source(tmp_path):
    (tmp_path / "index.html").write_text("<h1>ChatBI</h1>")
    (tmp_path / "assets").mkdir()
    client = TestClient(
        create_app(Mock(), browser_settings=BrowserSettings(ORIGIN, False, tmp_path))
    )
    assert client.get("/").text == "<h1>ChatBI</h1>"
    assert client.get("/api/missing").status_code == 404
    assert client.get("/assets/missing.js").status_code == 404
    assert client.get("/src/main.tsx").status_code == 404
    assert client.get("/health").json() == {"status": "ok"}
    with pytest.raises(ValueError):
        create_app(
            Mock(),
            browser_settings=BrowserSettings(ORIGIN, False, tmp_path / "missing"),
        )
