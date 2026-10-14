"""隔离development fixture的真实锁、权限与审计提交回滚。"""

import os
import time
from datetime import UTC, datetime
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import event, select, text, update
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import IntegrityError

from src.authorization.audit_service import PersistentAuditSink
from src.authorization.auth_service import AuthService, AuthenticationFailed
from src.authorization.passwords import hash_password, verify_password
from src.chatbi_control.admin import set_user_roles
from src.chatbi_control.database import (
    ControlDatabaseConfig,
    create_control_engine,
    verify_control_schema,
)
from src.chatbi_control.models import AuditEvent, Role, User, UserSession

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DEVELOPMENT_DATABASE_TESTS") != "1",
    reason="需要显式隔离development PostgreSQL",
)


@pytest.fixture
def recovery_accounts():
    engine = create_control_engine(
        ControlDatabaseConfig.from_environment(require_migrator=False)
    )
    verify_control_schema(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    username = "recover-" + uuid4().hex[:12]
    with factory.begin() as session:
        role = session.scalar(select(Role).where(Role.name == "admin"))
        user = User(
            username=username,
            password_hash=hash_password("original-test-password"),
            is_active=True,
            must_change_password=False,
            roles=[role],
        )
        # 另一个active admin保护角色移除测试，不改变最后管理员规则。
        session.add_all(
            [
                user,
                User(
                    username=username + "-other",
                    password_hash=hash_password("other-test-password"),
                    is_active=True,
                    roles=[role],
                ),
            ]
        )
        session.flush()
        user_id = user.id
    yield engine, factory, username, user_id
    with factory.begin() as session:
        users = list(
            session.scalars(
                select(User).where(User.username.in_([username, username + "-other"]))
            )
        )
        for user in users:
            user.is_active = False
        session.execute(
            update(UserSession)
            .where(UserSession.user_id.in_([user.id for user in users]))
            .values(revoked_at=datetime.now(UTC))
        )
    engine.dispose()


def recover(factory, username):
    AuthService(factory, audit_sink=PersistentAuditSink(factory)).recover_admin(
        username,
        new_password="recovered-test-password",
        environment="dev",
        project="isolated-integration",
    )


def await_database_lock(engine, pid):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            if connection.scalar(
                text(
                    "SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=:pid"
                ),
                {"pid": pid},
            ):
                return
        time.sleep(0.02)
    pytest.fail("恢复连接没有在User锁上等待")


@pytest.mark.parametrize("writer", ["login", "password", "disable", "roles"])
def test_recovery_serializes_with_existing_account_writers(recovery_accounts, writer):
    engine, factory, username, user_id = recovery_accounts
    locked, release, recovery_connected = Event(), Event(), Event()
    worker_pid = []

    class WriterSession(Session):
        pass

    class RecoverySession(Session):
        pass

    @event.listens_for(WriterSession, "before_flush")
    def hold_writer(session, flush_context, instances):
        locked.set()
        assert release.wait(15), "测试writer等待释放超时"

    @event.listens_for(RecoverySession, "after_begin")
    def identify_recovery(session, transaction, connection):
        worker_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
        recovery_connected.set()

    writer_factory = sessionmaker(engine, class_=WriterSession, expire_on_commit=False)
    recovery_factory = sessionmaker(
        engine, class_=RecoverySession, expire_on_commit=False
    )
    current_service = AuthService(factory)
    old_token = current_service.login(username, "original-test-password").token
    writer_service = AuthService(writer_factory)

    def write():
        if writer == "login":
            return writer_service.login(username, "original-test-password").token
        if writer == "password":
            writer_service.change_password(
                old_token,
                current_password="original-test-password",
                new_password="changed-test-password",
            )
        elif writer == "disable":
            writer_service.disable_user(user_id)
        else:
            set_user_roles(writer_factory, user_id=user_id, role_names={"analyst"})
        return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending_writer = pool.submit(write)
        try:
            assert locked.wait(10), "writer没有进入持锁变更"
            pending_recovery = pool.submit(recover, recovery_factory, username)
            assert recovery_connected.wait(10)
            await_database_lock(engine, worker_pid[0])
        finally:
            release.set()
        writer_token = pending_writer.result(timeout=15)
        if writer in {"disable", "roles"}:
            with pytest.raises(AuthenticationFailed):
                pending_recovery.result(timeout=15)
        else:
            pending_recovery.result(timeout=15)
            with factory() as session:
                user = session.get(User, user_id)
                assert verify_password("recovered-test-password", user.password_hash)
                assert all(
                    s.revoked_at is not None
                    for s in session.scalars(
                        select(UserSession).where(UserSession.user_id == user_id)
                    )
                )
            for token in (old_token, writer_token):
                if token:
                    with pytest.raises(AuthenticationFailed):
                        current_service.authenticate_session(token)


def test_postgres_audit_commit_failure_rolls_back_every_recovery_write(
    recovery_accounts,
):
    _, factory, username, user_id = recovery_accounts
    service = AuthService(factory)
    token = service.login(username, "original-test-password").token

    class InvalidAudit:
        def write(self, session, record):
            session.add(
                AuditEvent(
                    event_type=None,
                    target_type="user",
                    target_id=str(user_id),
                    outcome="success",
                )
            )

    with pytest.raises(IntegrityError):
        AuthService(factory, audit_sink=InvalidAudit()).recover_admin(
            username,
            new_password="recovered-test-password",
            environment="dev",
            project="isolated-integration",
        )
    assert service.authenticate_session(token).username == username
    assert service.login(username, "original-test-password")


@pytest.mark.parametrize("writer", ["login", "password"])
def test_old_credentials_waiting_behind_recovery_cannot_write_after_commit(
    recovery_accounts, writer
):
    engine, factory, username, user_id = recovery_accounts
    locked, release, connected = Event(), Event(), Event()
    worker_pid = []
    token = AuthService(factory).login(username, "original-test-password").token

    class HoldingAudit(PersistentAuditSink):
        def write(self, session, record):
            super().write(session, record)
            locked.set()
            assert release.wait(15)

    class WaitingWriter(Session):
        pass

    @event.listens_for(WaitingWriter, "after_begin")
    def identify_writer(session, transaction, connection):
        worker_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
        connected.set()

    writer_service = AuthService(sessionmaker(engine, class_=WaitingWriter))

    def write():
        if writer == "login":
            writer_service.login(username, "original-test-password")
        else:
            writer_service.change_password(
                token,
                current_password="original-test-password",
                new_password="changed-test-password",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending_recovery = pool.submit(
            AuthService(factory, audit_sink=HoldingAudit(factory)).recover_admin,
            username,
            new_password="recovered-test-password",
            environment="dev",
            project="isolated-integration",
        )
        try:
            assert locked.wait(10)
            pending_writer = pool.submit(write)
            assert connected.wait(10)
            await_database_lock(engine, worker_pid[0])
        finally:
            release.set()
        pending_recovery.result(timeout=15)
        with pytest.raises(AuthenticationFailed):
            pending_writer.result(timeout=15)
    with factory() as session:
        user = session.get(User, user_id)
        assert verify_password("recovered-test-password", user.password_hash)
        assert user.must_change_password
        assert all(
            value.revoked_at is not None
            for value in session.scalars(
                select(UserSession).where(UserSession.user_id == user_id)
            )
        )
