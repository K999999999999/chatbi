"""持久化审计和安全失败语义测试。"""

from datetime import UTC, datetime
from unittest import TestCase

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.authorization import hash_password
from src.authorization.audit_service import (
    AuditRecord,
    AuditUnavailable,
    PersistentAuditSink,
)
from src.authorization.auth_service import AuthService
from src.authorization.contracts import (
    AuditDecision,
    AuthorizationAuditEvent,
)
from src.chatbi_control.models import AuditEvent, Base, User, UserSession


class _FailingAuditWriter:
    def write(self, session, record) -> None:
        del session, record
        raise RuntimeError("audit database unavailable")


class PersistentAuditTest(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)
        with self.session_factory() as session:
            user = User(
                username="analyst-1",
                password_hash=hash_password("analyst-password-123"),
                is_active=True,
                must_change_password=False,
            )
            session.add(user)
            session.commit()
            self.user_id = user.id

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_authorization_event_is_persisted_without_query_payload(self) -> None:
        sink = PersistentAuditSink(self.session_factory)
        sink.emit(
            AuthorizationAuditEvent(
                request_id="req-audit-1",
                subject_id="analyst-1",
                identity_provider="local",
                resource="mart_sales",
                action="query",
                decision=AuditDecision.ALLOW,
                reason_code="AUTHORIZED",
                policy_version="rbac-v1",
                timestamp=datetime(2026, 9, 20, 12, tzinfo=UTC),
            )
        )

        with self.session_factory() as session:
            event = session.scalar(select(AuditEvent))
            self.assertIsNotNone(event)
            assert event is not None
            self.assertEqual(event.actor_user_id, self.user_id)
            self.assertEqual(event.event_type, "query.authorization")
            self.assertEqual(event.outcome, "allow")
            self.assertEqual(event.request_id, "req-audit-1")
            self.assertNotIn("SELECT", str(event.details))
            self.assertNotIn("查询销售额", str(event.details))

    def test_audit_record_rejects_sensitive_detail_keys(self) -> None:
        with self.assertRaises(ValueError):
            AuditRecord(
                event_type="auth.login",
                target_type="user",
                target_id="analyst-1",
                outcome="failure",
                details={"token_hash": "should-not-be-recorded"},
            )

    def test_security_audit_failure_rolls_back_login(self) -> None:
        service = AuthService(
            self.session_factory,
            clock=lambda: datetime(2026, 9, 20, 12, tzinfo=UTC),
            token_factory=lambda: "raw-token",
            audit_sink=_FailingAuditWriter(),
        )

        with self.assertRaises(AuditUnavailable):
            service.login("analyst-1", "analyst-password-123")

        with self.session_factory() as session:
            self.assertIsNone(session.scalar(select(UserSession)))
            self.assertIsNone(session.scalar(select(AuditEvent)))

    def test_query_outcome_is_persisted_as_a_separate_event(self) -> None:
        sink = PersistentAuditSink(self.session_factory)
        sink.emit_query_outcome(
            request_id="req-query-1",
            actor_user_id=self.user_id,
            outcome="success",
            reason="QUERY_SUCCEEDED",
        )

        with self.session_factory() as session:
            event = session.scalar(select(AuditEvent))
            self.assertIsNotNone(event)
            assert event is not None
            self.assertEqual(event.event_type, "query.outcome")
            self.assertEqual(event.actor_user_id, self.user_id)
            self.assertEqual(event.target_id, "mart_sales")


if __name__ == "__main__":
    import unittest

    unittest.main()
