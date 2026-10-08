import os
import json
from datetime import UTC, datetime, timedelta

import pytest

from scripts.local_backup import (
    BackupFailed,
    BackupStore,
    operation_lock,
    secure_directory,
    verify_source,
)


def test_storage_rejects_symlink_and_wide_permissions(tmp_path):
    wide = tmp_path / "wide"
    wide.mkdir(mode=0o755)
    with pytest.raises(BackupFailed, match="BACKUP_STORAGE_UNSAFE"):
        secure_directory(wide)
    link = tmp_path / "link"
    link.symlink_to(wide)
    with pytest.raises(BackupFailed, match="BACKUP_STORAGE_UNSAFE"):
        secure_directory(link)


def test_lock_conflict_preserves_owner_and_releases_after_failure(tmp_path):
    path = tmp_path / "operation.lock"
    with operation_lock(path):
        with pytest.raises(BackupFailed, match="BACKUP_LOCKED"):
            with operation_lock(path):
                pytest.fail("concurrent operation acquired lock")
    with operation_lock(path):
        pass
    with pytest.raises(RuntimeError):
        with operation_lock(path):
            raise RuntimeError("failed operation")
    with operation_lock(path):
        pass


def test_unknown_backup_id_never_selects_arbitrary_path(tmp_path):
    store = BackupStore(tmp_path)
    for candidate in ("../identity.txt", "a" * 32, "/tmp/archive.age"):
        with pytest.raises(BackupFailed, match="BACKUP_INVALID"):
            store.known_artifact(candidate)
    assert store.catalog()["backups"] == []


def test_public_projection_preserves_last_success_after_failure(tmp_path):
    store = BackupStore(tmp_path)
    timestamp = datetime.now(UTC).isoformat()
    store.projection(success=timestamp)
    store.projection(failure_code="BACKUP_TOOL_FAILED")
    projection = json.loads((store.public / "backup.json").read_bytes())
    assert projection == {
        "version": 1,
        "last_success": timestamp,
        "failure_code": "BACKUP_TOOL_FAILED",
    }
    assert (store.public / "backup.json").stat().st_mode & 0o777 == 0o644
    assert store.operations.stat().st_mode & 0o777 == 0o700
    assert store.public.stat().st_mode & 0o777 == 0o755


def test_source_requires_current_identity_not_latest_or_old_capture():
    now = datetime.now(UTC)
    identity = {
        "format": 1,
        "source_commit": "a" * 40,
        "api_image_id": "sha256:" + "b" * 64,
        "database_image_id": "sha256:" + "c" * 64,
        "captured_at": now.isoformat(),
    }
    verify_source(identity, now, require_live=False)
    with pytest.raises(BackupFailed, match="BACKUP_SOURCE_CHANGED"):
        verify_source(identity, now + timedelta(seconds=1201), require_live=False)
    with pytest.raises(BackupFailed, match="BACKUP_SOURCE_CHANGED"):
        verify_source(dict(identity, source_commit="latest"), now, require_live=False)


def test_missing_key_refuses_before_source_read_and_keeps_existing_artifacts(tmp_path):
    store = BackupStore(tmp_path)
    old = store.backups / "foreign.age"
    old.write_bytes(b"keep this file")
    with pytest.raises(BackupFailed, match="BACKUP_NOT_INITIALIZED"):
        store.backup(tmp_path / "missing-source", require_live=False)
    assert old.read_bytes() == b"keep this file"
    assert not list(store.staging.iterdir())
    assert store.catalog()["backups"] == []


@pytest.mark.parametrize(
    "failure", ["BACKUP_TOOL_FAILED", "BACKUP_TIMEOUT", "BACKUP_STORAGE_UNSAFE"]
)
def test_capture_failure_cleans_plaintext_and_never_registers(
    tmp_path, monkeypatch, failure
):
    from scripts import local_backup

    store = BackupStore(tmp_path)
    source = secure_directory(store.operations / "source")
    identity = {
        "format": 1,
        "source_commit": "a" * 40,
        "api_image_id": "sha256:" + "b" * 64,
        "database_image_id": "sha256:" + "c" * 64,
        "captured_at": datetime.now(UTC).isoformat(),
    }
    for name in (
        "config.env",
        "secrets.env",
        "release.env",
        "rag-current.json",
        "rag-manifest.json",
        "compatibility.json",
    ):
        (source / name).write_text("sensitive")
        (source / name).chmod(0o600)
    (source / "identity.json").write_text(json.dumps(identity))
    (source / "identity.json").chmod(0o600)
    monkeypatch.setattr(store, "require_key", lambda: ("private-key", "recipient"))

    class FailedSnapshot:
        def __init__(self, *_):
            pass

        def __enter__(self):
            raise BackupFailed(failure)

        def __exit__(self, *_):
            pass

    monkeypatch.setattr(local_backup, "Snapshot", FailedSnapshot)
    old = store.backups / "foreign.age"
    old.write_bytes(b"old backup")
    with pytest.raises(BackupFailed, match=failure):
        store.backup(source, require_live=False)
    assert store.catalog()["backups"] == []
    assert not list(store.staging.iterdir())
    assert list(store.backups.iterdir()) == [old]
    assert old.read_bytes() == b"old backup"


def test_public_projection_is_readable_even_under_private_tool_umask(tmp_path):
    previous = os.umask(0o077)
    try:
        store = BackupStore(tmp_path)
        store.projection(success=datetime.now(UTC).isoformat())
    finally:
        os.umask(previous)
    assert store.public.stat().st_mode & 0o777 == 0o755


def test_live_source_requires_matching_running_release_and_assets(
    tmp_path, monkeypatch
):
    from src.bootstrap.operations_socket import OperationsSocket

    path = str(tmp_path / "api.sock")
    now = datetime.now(UTC)
    assets = {"rag-current.json": "d" * 64, "rag-manifest.json": "e" * 64}
    identity = {
        "format": 1,
        "source_commit": "a" * 40,
        "api_image_id": "sha256:" + "b" * 64,
        "database_image_id": "sha256:" + "c" * 64,
        "asset_sha256": assets,
    }
    snapshot = {
        "source_commit": "a" * 40,
        "observed_at": now.isoformat(),
        "asset_sha256": assets,
    }
    server = OperationsSocket(lambda: snapshot, path=path)
    monkeypatch.setenv("CHATBI_OPERATIONS_SOCKET_PATH", path)
    server.start()
    try:
        verify_source(identity, now, require_live=True)
        verify_source(identity, now - timedelta(milliseconds=1), require_live=True)
        with pytest.raises(BackupFailed, match="BACKUP_SOURCE_CHANGED"):
            verify_source(
                dict(identity, source_commit="f" * 40), now, require_live=True
            )
        with pytest.raises(BackupFailed, match="BACKUP_SOURCE_CHANGED"):
            verify_source(
                dict(identity, asset_sha256={"rag-current.json": "f" * 64}),
                now,
                require_live=True,
            )
        with pytest.raises(BackupFailed, match="BACKUP_SOURCE_CHANGED"):
            verify_source(identity, now + timedelta(seconds=30), require_live=True)
    finally:
        server.close()
    with pytest.raises(BackupFailed, match="BACKUP_SOURCE_CHANGED"):
        verify_source(identity, now, require_live=True)


def test_catalog_read_creates_no_files_or_plaintext_directories(tmp_path):
    store = BackupStore(tmp_path)
    store.staging.rmdir()
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    readonly = BackupStore(tmp_path, create=False)
    assert readonly.catalog() == {"format": 1, "backups": []}
    assert (
        sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
        == before
    )
