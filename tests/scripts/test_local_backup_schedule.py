from datetime import UTC, datetime, timedelta

from scripts.local_backup_policy import expired, should_attempt

NOW = datetime(2026, 10, 8, 12, tzinfo=UTC)


def test_start_missing_or_overdue_backup_attempts_immediately():
    assert should_attempt(NOW, starting=True)
    assert should_attempt(
        NOW,
        last_success=NOW - timedelta(hours=25),
        last_attempt=NOW - timedelta(minutes=1),
        starting=True,
    )
    assert not should_attempt(NOW, last_success=NOW - timedelta(hours=1), starting=True)


def test_running_attempts_six_hourly_not_hot_loop_after_failure():
    assert should_attempt(NOW, last_success=NOW - timedelta(hours=6))
    assert not should_attempt(
        NOW, last_success=NOW - timedelta(hours=25), last_attempt=NOW
    )
    assert not should_attempt(
        NOW,
        last_success=NOW - timedelta(hours=25),
        last_attempt=NOW - timedelta(hours=6, microseconds=-1),
    )
    assert should_attempt(
        NOW,
        last_success=NOW - timedelta(hours=25),
        last_attempt=NOW - timedelta(hours=6),
    )


def test_expired_only_after_seven_days():
    assert not expired({"created_at": (NOW - timedelta(days=7)).isoformat()}, NOW)
    assert expired(
        {"created_at": (NOW - timedelta(days=7, seconds=1)).isoformat()}, NOW
    )


def register_artifact(store, backup_id, when):
    import hashlib
    from scripts.local_backup import atomic_json

    data = ("cipher fixture:" + backup_id).encode()
    path = store.backups / (backup_id + ".age")
    path.write_bytes(data)
    path.chmod(0o600)
    entry = {
        "id": backup_id,
        "created_at": when.isoformat(),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "source_commit": "a" * 40,
    }
    catalog = store.catalog()
    catalog["backups"].append(entry)
    atomic_json(store.catalog_path, catalog)
    return path


def test_success_retention_removes_only_registered_expired_ciphers(tmp_path):
    from scripts.local_backup import BackupStore

    store = BackupStore(tmp_path, clock=lambda: NOW)
    old = register_artifact(store, "a" * 32, NOW - timedelta(days=8))
    boundary = register_artifact(store, "b" * 32, NOW - timedelta(days=7))
    newest = register_artifact(store, "c" * 32, NOW)
    unknown = store.backups / "unknown.age"
    unknown.write_bytes(b"unknown file")
    store.prune_after_success("c" * 32)
    assert not old.exists()
    assert boundary.exists() and newest.exists()
    assert unknown.read_bytes() == b"unknown file"
    assert {entry["id"] for entry in store.catalog()["backups"]} == {"b" * 32, "c" * 32}


def test_corrupt_old_copy_aborts_cleanup_without_deleting_other_copies(tmp_path):
    import pytest
    from scripts.local_backup import BackupFailed, BackupStore

    store = BackupStore(tmp_path, clock=lambda: NOW)
    good = register_artifact(store, "a" * 32, NOW - timedelta(days=8))
    bad = register_artifact(store, "b" * 32, NOW - timedelta(days=8))
    newest = register_artifact(store, "c" * 32, NOW)
    bad.write_bytes(b"corruption")
    with pytest.raises(BackupFailed):
        store.prune_after_success("c" * 32)
    assert good.exists() and bad.exists() and newest.exists()
    assert len(store.catalog()["backups"]) == 3


def test_failed_scheduler_attempt_is_persistent_and_does_not_hot_loop(tmp_path):
    import json
    from scripts.local_backup import BackupStore
    from scripts.local_backup_schedule import BackupScheduler

    clock = [NOW]
    store = BackupStore(tmp_path, clock=lambda: clock[0])
    scheduler = BackupScheduler(store, clock=lambda: clock[0])
    assert scheduler.tick(tmp_path / "missing-source") is True
    assert (
        json.loads((store.public / "backup.json").read_bytes())["failure_code"]
        == "BACKUP_KEY_UNAVAILABLE"
    )
    assert scheduler.tick(tmp_path / "missing-source") is False
    clock[0] += timedelta(hours=6)
    assert scheduler.tick(tmp_path / "missing-source") is True
    assert store.catalog()["backups"] == []
    assert not list(store.staging.iterdir())


def test_scheduler_lock_conflict_records_failure_without_touching_api_or_ciphers(
    tmp_path,
):
    import json
    from scripts.local_backup import BackupStore, operation_lock
    from scripts.local_backup_schedule import BackupScheduler

    store = BackupStore(tmp_path, clock=lambda: NOW)
    scheduler = BackupScheduler(store, clock=lambda: NOW)
    with operation_lock(tmp_path / "operation.lock"):
        assert scheduler.tick(tmp_path / "missing-source") is True
    assert (
        json.loads((store.public / "backup.json").read_bytes())["failure_code"]
        == "BACKUP_LOCKED"
    )
    assert scheduler.tick(tmp_path / "missing-source") is False


def test_backward_clock_never_turns_failure_cooldown_into_hot_retries():
    assert not should_attempt(NOW, last_attempt=NOW + timedelta(hours=1))
    assert should_attempt(NOW, last_attempt=NOW + timedelta(hours=1), starting=True)
