"""内置账号和数据库 Session 的确定性测试。"""

from datetime import UTC, datetime, timedelta
from unittest import TestCase

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.authorization import hash_password
from src.authorization.auth_service import (
    AuthenticationFailed,
    AuthService,
    SessionExpired,
)
from src.chatbi_control.models import Base, User, UserSession


class _TestClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 9, 20, 12, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.current

    def advance(self, duration: timedelta) -> None:
        self.current += duration


class AuthServiceTest(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)
        with self.session_factory() as session:
            admin = User(
                username="admin-1",
                password_hash=hash_password("initial-password-123"),
                is_active=True,
                must_change_password=True,
            )
            analyst = User(
                username="analyst-1",
                password_hash=hash_password("analyst-password-123"),
                is_active=True,
                must_change_password=False,
            )
            disabled = User(
                username="disabled-1",
                password_hash=hash_password("disabled-password-123"),
                is_active=False,
                must_change_password=False,
            )
            session.add_all([admin, analyst, disabled])
            session.commit()
            self.analyst_id = analyst.id
            self.disabled_id = disabled.id
        self.clock = _TestClock()
        self._token_number = 0
        self.service = AuthService(
            self.session_factory,
            clock=self.clock,
            token_factory=self._next_token,
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def _next_token(self) -> str:
        self._token_number += 1
        return f"raw-token-for-test-{self._token_number}"

    def test_login_creates_hashed_database_session_and_context(self) -> None:
        result = self.service.login(" Analyst-1 ", "analyst-password-123")

        self.assertEqual(result.token, "raw-token-for-test-1")
        self.assertEqual(result.auth_context.username, "analyst-1")
        self.assertEqual(result.auth_context.identity_provider, "local")
        self.assertFalse(result.auth_context.must_change_password)
        with self.session_factory() as session:
            saved = session.scalar(select(UserSession))
        self.assertIsNotNone(saved)
        assert saved is not None
        self.assertNotEqual(saved.token_hash, result.token)
        self.assertNotIn(result.token, saved.token_hash)
        self.assertEqual(len(saved.token_hash), 64)

    def test_unknown_wrong_and_disabled_credentials_have_same_controlled_failure(
        self,
    ) -> None:
        attempts = (
            ("unknown-user", "any-password-123"),
            ("analyst-1", "wrong-password-123"),
            ("disabled-1", "disabled-password-123"),
        )
        for username, password in attempts:
            with self.subTest(username=username):
                with self.assertRaises(AuthenticationFailed) as raised:
                    self.service.login(username, password)
                self.assertEqual(str(raised.exception), "用户名或密码错误")

    def test_first_login_requires_password_change(self) -> None:
        result = self.service.login("admin-1", "initial-password-123")

        self.assertTrue(result.auth_context.must_change_password)
        self.assertFalse(self.service.can_execute_query(result.auth_context))

    def test_idle_and_absolute_session_expiry_are_enforced(self) -> None:
        result = self.service.login("analyst-1", "analyst-password-123")
        self.assertEqual(
            self.service.authenticate_session(result.token).username,
            "analyst-1",
        )

        self.clock.advance(timedelta(minutes=30, seconds=1))
        with self.assertRaises(SessionExpired):
            self.service.authenticate_session(result.token)

        second = self.service.login("analyst-1", "analyst-password-123")
        for _ in range(23):
            self.clock.advance(timedelta(minutes=20))
            self.service.authenticate_session(second.token)
        self.clock.advance(timedelta(minutes=19, seconds=59))
        self.assertEqual(
            self.service.authenticate_session(second.token).username,
            "analyst-1",
        )
        self.clock.advance(timedelta(seconds=2))
        with self.assertRaises(SessionExpired):
            self.service.authenticate_session(second.token)

    def test_logout_password_change_reset_and_disable_revoke_sessions(self) -> None:
        logged_in = self.service.login("analyst-1", "analyst-password-123")
        self.assertTrue(self.service.logout(logged_in.token))
        with self.assertRaises(SessionExpired):
            self.service.authenticate_session(logged_in.token)

        changed = self.service.login("analyst-1", "analyst-password-123")
        self.service.change_password(
            changed.token,
            current_password="analyst-password-123",
            new_password="new-analyst-password-123",
        )
        with self.assertRaises(SessionExpired):
            self.service.authenticate_session(changed.token)
        self.service.login("analyst-1", "new-analyst-password-123")

        self.service.reset_password(
            self.analyst_id,
            new_password="reset-analyst-password-123",
        )
        with self.assertRaises(AuthenticationFailed):
            self.service.login("analyst-1", "new-analyst-password-123")
        reset = self.service.login("analyst-1", "reset-analyst-password-123")
        self.service.disable_user(self.analyst_id)
        with self.assertRaises(SessionExpired):
            self.service.authenticate_session(reset.token)

    def test_five_failures_lock_for_fifteen_minutes_with_controlled_clock(self) -> None:
        for _ in range(5):
            with self.assertRaises(AuthenticationFailed):
                self.service.login("analyst-1", "wrong-password-123")

        with self.assertRaises(AuthenticationFailed):
            self.service.login("analyst-1", "analyst-password-123")
        self.clock.advance(timedelta(minutes=15, seconds=1))
        self.assertEqual(
            self.service.login(
                "analyst-1", "analyst-password-123"
            ).auth_context.username,
            "analyst-1",
        )
