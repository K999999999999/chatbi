from datetime import timedelta
from unittest.mock import Mock

from fastapi.testclient import TestClient

from src.query_api.app import create_app
from tests.query_api.test_browser_auth import browser, login  # noqa: F401


def test_readiness_without_probe_evidence_fails_closed():
    with TestClient(create_app(Mock())) as client:
        assert client.get("/health").json() == {"status": "ok"}
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "unknown", "checked_at": None}


def test_status_requires_identity_and_never_renews_idle_session(browser):  # noqa: F811
    client, service, clock, _auth = browser
    assert client.get("/api/v1/operations/status").status_code == 401
    headers = login(client)
    clock[0] += timedelta(minutes=29)
    response = client.get("/api/v1/operations/status", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "unknown"
    assert "details" not in response.json()
    clock[0] += timedelta(minutes=2)
    assert client.get("/api/v1/operations/status", headers=headers).status_code == 401
    service.execute.assert_not_called()


def test_status_enforces_cookie_origin_and_expected_user(browser):  # noqa: F811
    client, _, _, _ = browser
    login(client)
    assert (
        client.get(
            "/api/v1/operations/status",
            headers={
                "Origin": "https://untrusted.example",
                "X-ChatBI-User-ID": "1",
            },
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/operations/status",
            headers={
                "X-ChatBI-User-ID": "999",
            },
        ).status_code
        == 401
    )


def test_admin_details_follow_current_permissions_and_revocation(browser):  # noqa: F811
    from sqlalchemy import select
    from src.chatbi_control.models import Role, User
    from src.query_api.operations import DEPENDENCIES, OperationsState

    client, _, _, auth = browser
    # 用真实角色关系准备管理员；HTTP入口不使用缓存权限。
    with auth._session_factory() as session:
        user = session.scalar(select(User).where(User.username == "analyst"))
        user.roles = [session.scalar(select(Role).where(Role.name == "admin"))]
        session.commit()
    headers = login(client)
    state = OperationsState()
    state.record_checks(dict.fromkeys(DEPENDENCIES, "ready"))
    client.app.state.operations = state
    response = client.get("/api/v1/operations/status", headers=headers)
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["details"]["dependencies"]["qdrant"] == "ready"
    with auth._session_factory() as session:
        user = session.scalar(select(User).where(User.username == "analyst"))
        user.is_active = False
        session.commit()
    assert client.get("/api/v1/operations/status", headers=headers).status_code == 401
