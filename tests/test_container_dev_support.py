"""容器验收账号建立失败时的精确补偿。"""

from datetime import UTC, datetime, timedelta
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from src.authorization import hash_password
from src.chatbi_control.models import Base, Role, User, UserSession
from tests import container_dev_support as support


@pytest.fixture
def acceptance_database(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'control.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        analyst = Role(name="analyst", description="test analyst")
        session.add(analyst)
        session.flush()
        unrelated = User(
            username="web-e2e-container-unrelated",
            password_hash=hash_password("test-password-123"),
            is_active=True,
            must_change_password=False,
            roles=[analyst],
        )
        session.add(unrelated)
        session.commit()
        unrelated_id = unrelated.id

    report = tmp_path / "report"
    report.mkdir(mode=0o700)
    monkeypatch.setattr(support, "REPORT", report)
    monkeypatch.setattr(
        support,
        "ControlDatabaseConfig",
        SimpleNamespace(from_environment=lambda **_: None),
    )
    monkeypatch.setattr(support, "create_control_engine", lambda _: engine)
    monkeypatch.setattr(support, "reference", lambda: {"fixture": "reference"})
    yield engine, report, unrelated_id
    engine.dispose()


def test_committed_account_remains_identifiable_if_final_manifest_write_fails(
    acceptance_database, monkeypatch
):
    engine, report, unrelated_id = acceptance_database
    original_replace = support.os.replace

    def fail_final_manifest(source, destination):
        if str(destination) == str(report / "account.json"):
            raise OSError("injected account manifest publication failure")
        original_replace(source, destination)

    monkeypatch.setattr(support.os, "replace", fail_final_manifest)

    with pytest.raises(OSError, match="publication failure"):
        support.prepare()

    pending = report / "account.pending.json"
    assert pending.is_file()
    account = json.loads(pending.read_text())
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        target = session.get(User, account["id"])
        assert target is not None and target.username == account["username"]
        now = datetime.now(UTC)
        session.add(
            UserSession(
                token_hash="a" * 64,
                user_id=target.id,
                created_at=now,
                last_seen_at=now,
                expires_at=now + timedelta(minutes=30),
                absolute_expires_at=now + timedelta(hours=8),
            )
        )
        session.commit()

    support.cleanup()

    with factory() as session:
        target = session.get(User, account["id"])
        active_sessions = session.scalar(
            select(func.count())
            .select_from(UserSession)
            .where(
                UserSession.user_id == account["id"],
                UserSession.revoked_at.is_(None),
            )
        )
        unrelated = session.get(User, unrelated_id)
    assert target is not None and target.username == account["username"]
    assert target.is_active is False
    assert active_sessions == 0
    assert unrelated is not None and unrelated.is_active is True
    assert json.loads((report / "cleanup.json").read_text()) == {
        "disabled": True,
        "active_sessions": 0,
        "account_exists": True,
    }


def test_account_record_failure_before_commit_does_not_create_user(
    acceptance_database, monkeypatch
):
    engine, report, _ = acceptance_database
    original_replace = support.os.replace

    def fail_pending_manifest(source, destination):
        if str(destination) == str(report / "account.pending.json"):
            raise OSError("injected durable identity record failure")
        original_replace(source, destination)

    monkeypatch.setattr(support.os, "replace", fail_pending_manifest)

    with pytest.raises(OSError, match="identity record failure"):
        support.prepare()

    with Session(engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.username.like("web-e2e-container-%"))
            )
            == 1
        )
    assert not (report / "account.pending.json").exists()
    assert not (report / "account.json").exists()


def test_pending_record_after_rolled_back_insert_does_not_touch_other_accounts(
    acceptance_database, monkeypatch
):
    engine, report, unrelated_id = acceptance_database
    write_manifest = support._write_account_manifest

    def fail_after_durable_record(path, account):
        write_manifest(path, account)
        raise OSError("injected transaction failure after durable identity")

    monkeypatch.setattr(support, "_write_account_manifest", fail_after_durable_record)

    with pytest.raises(OSError, match="after durable identity"):
        support.prepare()

    assert (report / "account.pending.json").is_file()
    support.cleanup()

    with Session(engine) as session:
        assert session.get(User, unrelated_id).is_active is True
        assert (
            session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.username.like("web-e2e-container-%"))
            )
            == 1
        )
    assert json.loads((report / "cleanup.json").read_text()) == {
        "disabled": True,
        "active_sessions": 0,
        "account_exists": False,
    }
