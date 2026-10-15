"""本机恢复规则与事务；PostgreSQL锁另由隔离集成测试证明。"""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.authorization.audit_service import AuditUnavailable, PersistentAuditSink
from src.authorization.auth_service import AuthenticationFailed, AuthService
from src.authorization.passwords import hash_password, verify_password
from src.chatbi_control.models import AuditEvent, Base, Role, User, UserSession


@pytest.fixture
def accounts():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        admin = Role(name="admin", description="administrator")
        analyst = Role(name="analyst", description="analyst")
        session.add_all(
            [
                User(
                    username="admin",
                    password_hash=hash_password("original-test-password"),
                    is_active=True,
                    must_change_password=False,
                    roles=[admin],
                ),
                User(
                    username="other",
                    password_hash=hash_password("another-test-password"),
                    is_active=True,
                    must_change_password=False,
                    roles=[admin],
                ),
                User(
                    username="analyst",
                    password_hash=hash_password("analyst-test-password"),
                    is_active=True,
                    roles=[analyst],
                ),
                User(
                    username="disabled",
                    password_hash=hash_password("disabled-test-password"),
                    is_active=False,
                    roles=[admin],
                ),
            ]
        )
    yield factory
    engine.dispose()


def recovery(service, username=" Admin "):
    service.recover_admin(
        username,
        new_password="recovered-test-password",
        environment="dev",
        project="test-project",
    )


def test_recovery_atomically_changes_password_revokes_sessions_and_audits(accounts):
    service = AuthService(accounts, audit_sink=PersistentAuditSink(accounts))
    first = service.login("admin", "original-test-password")
    second = service.login("admin", "original-test-password")
    recovery(service)
    with accounts() as session:
        user = session.scalar(select(User).where(User.username == "admin"))
        assert verify_password("recovered-test-password", user.password_hash)
        assert (
            user.must_change_password
            and user.failed_login_count == 0
            and user.locked_until is None
        )
        assert {r.name for r in user.roles} == {"admin"}
        assert all(
            s.revoked_at is not None for s in session.scalars(select(UserSession))
        )
        audit = session.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "auth.admin_recovery")
        )
        assert audit.actor_user_id is None
        assert audit.details == {
            "environment": "dev",
            "project": "test-project",
            "source": "local_cli",
        }
        other = session.scalar(select(User).where(User.username == "other"))
        assert verify_password("another-test-password", other.password_hash)
    for token in (first.token, second.token):
        with pytest.raises(AuthenticationFailed):
            service.authenticate_session(token)
    with pytest.raises(AuthenticationFailed):
        service.login("admin", "original-test-password")
    assert service.login(
        "admin", "recovered-test-password"
    ).auth_context.must_change_password


@pytest.mark.parametrize("username", ["analyst", "disabled", "missing"])
def test_recovery_refuses_accounts_outside_active_admin_scope(accounts, username):
    with accounts() as session:
        before = [(u.id, u.password_hash) for u in session.scalars(select(User))]
    with pytest.raises(AuthenticationFailed):
        recovery(
            AuthService(accounts, audit_sink=PersistentAuditSink(accounts)), username
        )
    with accounts() as session:
        assert [
            (u.id, u.password_hash) for u in session.scalars(select(User))
        ] == before


def test_mandatory_audit_failure_rolls_back_password_and_session(accounts):
    class BrokenAudit:
        def write(self, session, record):
            raise RuntimeError("test failure")

    service = AuthService(accounts)
    token = service.login("admin", "original-test-password").token
    with pytest.raises(AuditUnavailable):
        recovery(AuthService(accounts, audit_sink=BrokenAudit()))
    assert service.authenticate_session(token).username == "admin"
    assert service.login("admin", "original-test-password")
    with pytest.raises(AuditUnavailable):
        recovery(service)


def test_weak_password_recovery_changes_nothing(accounts):
    with pytest.raises(ValueError):
        AuthService(accounts, audit_sink=PersistentAuditSink(accounts)).recover_admin(
            "admin", new_password="short", environment="dev", project="test-project"
        )


def test_retired_app_recovery_environment_is_rejected_before_account_access(accounts):
    with (
        patch(
            "src.authorization.auth_service.hash_password",
            side_effect=AssertionError("必须在处理密码前拒绝目标"),
        ),
        pytest.raises(ValueError, match="恢复来源不完整"),
    ):
        AuthService(accounts, audit_sink=PersistentAuditSink(accounts)).recover_admin(
            "admin",
            new_password="long-enough-test-password",
            environment="app",
            project="test-project",
        )
