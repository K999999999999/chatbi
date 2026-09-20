"""Query API 使用内置账号 Session 和 RBAC 的集成测试。"""

from unittest import TestCase

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.authorization import (
    InMemoryAuditSink,
    AuthService,
    LocalSessionIdentityProvider,
    RoleAuthorizationPolicyStore,
    hash_password,
)
from src.chatbi_control.bootstrap import seed_rbac
from src.chatbi_control.models import Base, User
from src.online_query.contracts import QuerySuccess
from src.query_api.app import create_app


class _RecordingService:
    def __init__(self) -> None:
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return QuerySuccess(
            request_id=request.request_id or "generated-request-id",
            sql="SELECT 1",
            columns=("value",),
            rows=((1,),),
            row_count=1,
            truncated=False,
        )


class LocalQueryAuthTest(TestCase):
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
            session.add_all(
                [
                    User(
                        username="analyst-1",
                        password_hash=hash_password("analyst-password-123"),
                        is_active=True,
                        must_change_password=False,
                        roles=[roles["analyst"]],
                    ),
                    User(
                        username="first-login-1",
                        password_hash=hash_password("first-login-password-123"),
                        is_active=True,
                        must_change_password=True,
                        roles=[roles["analyst"]],
                    ),
                ]
            )
            session.commit()
        self.token_number = 0
        self.auth_service = AuthService(
            self.session_factory,
            token_factory=self._next_token,
        )
        self.service = _RecordingService()
        self.client = TestClient(
            create_app(
                self.service,
                audit_sink=InMemoryAuditSink(),
                auth_service=self.auth_service,
                identity_provider=LocalSessionIdentityProvider(self.auth_service),
                policy_store=RoleAuthorizationPolicyStore(),
            )
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def _next_token(self) -> str:
        self.token_number += 1
        return f"query-auth-token-{self.token_number}"

    def test_unauthenticated_query_is_rejected_before_downstream(self) -> None:
        response = self.client.post(
            "/api/v1/query",
            json={"question": "查询销售额"},
            headers={"X-Request-ID": "req-no-session"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.service.requests, [])

    def test_analyst_session_can_query_through_existing_chain(self) -> None:
        login = self.client.post(
            "/auth/login",
            json={"username": "analyst-1", "password": "analyst-password-123"},
        )
        token = login.json()["access_token"]

        response = self.client.post(
            "/api/v1/query",
            json={"question": "查询销售额"},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Request-ID": "req-local-auth",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["request_id"], "req-local-auth")
        self.assertEqual(len(self.service.requests), 1)

    def test_first_login_and_disabled_user_cannot_query(self) -> None:
        first_login = self.client.post(
            "/auth/login",
            json={
                "username": "first-login-1",
                "password": "first-login-password-123",
            },
        )
        first_token = first_login.json()["access_token"]
        blocked = self.client.post(
            "/api/v1/query",
            json={"question": "查询销售额"},
            headers={"Authorization": f"Bearer {first_token}"},
        )
        self.assertEqual(blocked.status_code, 403)

        login = self.client.post(
            "/auth/login",
            json={"username": "analyst-1", "password": "analyst-password-123"},
        )
        analyst_id = login.json()["username"]
        self.assertEqual(analyst_id, "analyst-1")
        token = login.json()["access_token"]
        with self.session_factory() as session:
            user = session.query(User).filter_by(username="analyst-1").one()
            user_id = user.id
        self.auth_service.disable_user(user_id)

        disabled = self.client.post(
            "/api/v1/query",
            json={"question": "查询销售额"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(disabled.status_code, 401)
        self.assertEqual(len(self.service.requests), 0)
