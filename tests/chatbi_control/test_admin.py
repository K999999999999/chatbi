"""SQLAdmin 管理后台和 RBAC 不变量测试。"""

from unittest import TestCase
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.authorization import AuthService, hash_password, verify_password
from src.chatbi_control.admin import (
    AdminPolicyError,
    LastAdminError,
    PermissionAdmin,
    RoleAdmin,
    UserAdmin,
    set_user_roles,
)
from src.chatbi_control.bootstrap import seed_rbac
from src.chatbi_control.models import Base, Role, User
from src.query_api.app import create_app


class SqlAdminIntegrationTest(TestCase):
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
                        username="admin-1",
                        password_hash=hash_password("admin-password-123"),
                        is_active=True,
                        must_change_password=False,
                        roles=[roles["admin"]],
                    ),
                    User(
                        username="analyst-1",
                        password_hash=hash_password("analyst-password-123"),
                        is_active=True,
                        must_change_password=False,
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
        self.app = create_app(
            Mock(),
            auth_service=self.auth_service,
            admin_engine=self.engine,
            admin_secret_key="admin-test-secret",
            admin_session_factory=self.session_factory,
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def _next_token(self) -> str:
        self.token_number += 1
        return f"admin-test-token-{self.token_number}"

    def test_admin_can_access_backend_and_password_hash_is_not_rendered(self) -> None:
        client = TestClient(self.app)

        login = client.post(
            "/admin/login",
            data={"username": "admin-1", "password": "admin-password-123"},
            follow_redirects=False,
        )
        self.assertEqual(login.status_code, 302)

        page = client.get("/admin/user/list")
        self.assertEqual(page.status_code, 200)
        self.assertIn("admin-1", page.text)
        self.assertNotIn("$argon2id$", page.text)
        self.assertNotIn("admin-password-123", page.text)

    def test_analyst_is_rejected_and_anonymous_is_sent_to_login(self) -> None:
        anonymous = TestClient(self.app)
        anonymous_response = anonymous.get("/admin/", follow_redirects=False)
        self.assertEqual(anonymous_response.status_code, 302)
        self.assertIn("/admin/login", anonymous_response.headers["location"])

        analyst = TestClient(self.app)
        response = analyst.post(
            "/admin/login",
            data={"username": "analyst-1", "password": "analyst-password-123"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_user_without_persisting_plaintext_password(self) -> None:
        client = TestClient(self.app)
        client.post(
            "/admin/login",
            data={"username": "admin-1", "password": "admin-password-123"},
        )
        with self.session_factory() as session:
            analyst_role_id = session.scalar(
                select(Role.id).where(Role.name == "analyst")
            )

        response = client.post(
            "/admin/user/create",
            data={
                "username": "new-user",
                "password_hash": "new-user-password-123",
                "is_active": "y",
                "must_change_password": "y",
                "roles": str(analyst_role_id),
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        with self.session_factory() as session:
            user = session.scalar(select(User).where(User.username == "new-user"))
            self.assertIsNotNone(user)
            assert user is not None
            self.assertNotEqual(user.password_hash, "new-user-password-123")
            self.assertTrue(
                verify_password("new-user-password-123", user.password_hash)
            )
            self.assertEqual([role.name for role in user.roles], ["analyst"])

    def test_user_delete_and_role_permission_mutation_are_disabled(self) -> None:
        self.assertFalse(UserAdmin.can_delete)
        self.assertFalse(RoleAdmin.can_create)
        self.assertFalse(RoleAdmin.can_edit)
        self.assertFalse(RoleAdmin.can_delete)
        self.assertFalse(PermissionAdmin.can_create)
        self.assertFalse(PermissionAdmin.can_edit)
        self.assertFalse(PermissionAdmin.can_delete)

    def test_last_active_admin_cannot_be_demoted(self) -> None:
        with self.session_factory() as session:
            admin = session.query(User).filter_by(username="admin-1").one()
            admin_id = admin.id

        with self.assertRaises(LastAdminError):
            set_user_roles(
                self.session_factory,
                user_id=admin_id,
                role_names={"analyst"},
            )

    def test_unknown_role_cannot_be_assigned(self) -> None:
        with self.session_factory() as session:
            admin_id = session.query(User).filter_by(username="admin-1").one().id

        with self.assertRaisesRegex(AdminPolicyError, "固定"):
            set_user_roles(
                self.session_factory,
                user_id=admin_id,
                role_names={"unknown"},
            )
