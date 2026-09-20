"""内置账号认证 HTTP API 测试。"""

from datetime import UTC, datetime
from unittest import TestCase
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.authorization import AuthService, hash_password
from src.chatbi_control.bootstrap import seed_rbac
from src.chatbi_control.models import Base, User
from src.query_api.app import create_app


class AuthApiTest(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)
        with self.session_factory() as session:
            roles = seed_rbac(session)
            user = User(
                username="analyst-1",
                password_hash=hash_password("analyst-password-123"),
                is_active=True,
                must_change_password=True,
                roles=[roles["analyst"]],
            )
            session.add(user)
            session.commit()
        self._token_number = 0
        self.auth_service = AuthService(
            self.session_factory,
            clock=lambda: datetime(2026, 9, 20, 12, tzinfo=UTC),
            token_factory=self._next_token,
        )
        self.client = TestClient(create_app(Mock(), auth_service=self.auth_service))

    def tearDown(self) -> None:
        self.engine.dispose()

    def _next_token(self) -> str:
        self._token_number += 1
        return f"auth-api-token-{self._token_number}"

    def test_login_returns_bearer_token_and_current_identity(self) -> None:
        response = self.client.post(
            "/auth/login",
            json={"username": "analyst-1", "password": "analyst-password-123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["access_token"], "auth-api-token-1")
        self.assertTrue(response.json()["must_change_password"])
        token = response.json()["access_token"]
        current = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json()["username"], "analyst-1")

    def test_invalid_login_does_not_reveal_account_state(self) -> None:
        response = self.client.post(
            "/auth/login",
            json={"username": "missing", "password": "wrong-password-123"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "用户名或密码错误")

    def test_logout_and_change_password_use_the_same_session_service(self) -> None:
        login = self.client.post(
            "/auth/login",
            json={"username": "analyst-1", "password": "analyst-password-123"},
        )
        token = login.json()["access_token"]
        changed = self.client.post(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "analyst-password-123",
                "new_password": "new-analyst-password-123",
            },
        )
        self.assertEqual(changed.status_code, 204)
        self.assertEqual(
            self.client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            ).status_code,
            401,
        )

        second = self.client.post(
            "/auth/login",
            json={"username": "analyst-1", "password": "new-analyst-password-123"},
        )
        self.assertEqual(second.status_code, 200)
        logged_out = self.client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {second.json()['access_token']}"},
        )
        self.assertEqual(logged_out.status_code, 204)

    def test_auth_endpoint_is_unavailable_when_service_is_not_configured(self) -> None:
        client = TestClient(create_app(Mock()))

        response = client.post(
            "/auth/login",
            json={"username": "analyst-1", "password": "analyst-password-123"},
        )

        self.assertEqual(response.status_code, 503)
