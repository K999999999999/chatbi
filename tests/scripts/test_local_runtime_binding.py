import uuid

import pytest

from scripts.local_runtime_binding import BindingInvalid, validate_binding


def restore_record(restore_id, status="verified"):
    from datetime import UTC, datetime

    from scripts.local_runtime_binding import restore_binding

    return {
        "format": 1,
        "id": restore_id,
        "status": status,
        "backup_id": "c" * 32,
        "binding": restore_binding(
            restore_id,
            database_image="chatbi-local-postgres:source",
            database_image_id="sha256:" + "b" * 64,
        ),
        "source_commit": "d" * 40,
        "api_image": "chatbi-local-api:source",
        "api_image_id": "sha256:" + "e" * 64,
        "database_image": "chatbi-local-postgres:source",
        "database_image_id": "sha256:" + "b" * 64,
        "compatibility_sha256": "f" * 64,
        "created_at": datetime.now(UTC).isoformat(),
        "verified_at": datetime.now(UTC).isoformat(),
        "fingerprints": {
            "business": {"public.items": {"rows": 1, "sha256": "1" * 64}},
            "control": {"public.users": {"rows": 1, "sha256": "2" * 64}},
        },
        "normalization": {
            "restored_epoch": str(uuid.uuid4()),
            "active_epoch": str(uuid.uuid4()),
        },
        "verification": {
            "readiness": True,
            "login": True,
            "history": True,
            "index_ready": True,
            "duration_seconds": 42,
        },
    }


def legacy():
    return {
        "format": 1,
        "environment_id": "legacy",
        "postgres_volume": "chatbi_stable_postgres_data",
        "qdrant_volume": "chatbi_stable_qdrant_data",
        "rag_dir": ".local/rag",
        "operations_api_dir": ".local/operations/api",
        "config_file": ".env.local",
        "secrets_file": ".env.local.secrets",
        "release_file": ".local/release.env",
        "database_image": None,
        "database_image_id": None,
    }


def test_unknown_resources_and_traversal_never_become_active_binding():
    for updates in (
        {"postgres_volume": "other_project_pg"},
        {"rag_dir": "../../other"},
        {"config_file": "/tmp/secrets"},
        {"environment_id": "unknown"},
    ):
        with pytest.raises(BindingInvalid):
            validate_binding(dict(legacy(), **updates))


def test_restore_binding_requires_matching_verified_registry():
    value = dict(legacy(), environment_id="a" * 32)
    with pytest.raises(BindingInvalid):
        validate_binding(value, registry={})


def test_missing_schema_field_and_extra_commands_are_rejected():
    missing = legacy()
    missing.pop("qdrant_volume")
    for value in (missing, dict(legacy(), command="rm -rf /"), [], None):
        with pytest.raises(BindingInvalid):
            validate_binding(value)


def test_legacy_and_registered_restore_accept_only_their_exact_resources():
    from scripts.local_runtime_binding import restore_binding

    assert validate_binding(legacy()) == legacy()
    value = restore_binding(
        "a" * 32,
        database_image="chatbi-local-postgres:source",
        database_image_id="sha256:" + "b" * 64,
    )
    record = restore_record("a" * 32)
    assert record["binding"] == value
    assert validate_binding(value, registry={"a" * 32: record}) == value
    record["status"] = "preparing"
    with pytest.raises(BindingInvalid):
        validate_binding(value, registry={"a" * 32: record})


def test_volume_names_alone_do_not_prove_ownership():
    from scripts.local_runtime_binding import restore_binding, validate_volume

    original = legacy()
    with pytest.raises(BindingInvalid):
        validate_volume(
            original, "postgres", {"Name": original["postgres_volume"], "Labels": {}}
        )
    labels = {
        "com.docker.compose.project": "chatbi-stable",
        "com.docker.compose.volume": "postgres_data",
    }
    validate_volume(
        original, "postgres", {"Name": original["postgres_volume"], "Labels": labels}
    )
    restored = restore_binding(
        "a" * 32,
        database_image="chatbi-local-postgres:source",
        database_image_id="sha256:" + "b" * 64,
    )
    labels = {
        "com.chatbi.restore-id": "a" * 32,
        "com.chatbi.resource-kind": "postgres",
        "com.chatbi.product": "chatbi-engine",
    }
    validate_volume(
        restored, "postgres", {"Name": restored["postgres_volume"], "Labels": labels}
    )
    labels["com.chatbi.restore-id"] = "c" * 32
    with pytest.raises(BindingInvalid):
        validate_volume(
            restored,
            "postgres",
            {"Name": restored["postgres_volume"], "Labels": labels},
        )


def test_binding_file_requires_owned_private_record_and_verified_registry(tmp_path):
    import json

    from scripts.local_runtime_binding import LEGACY, load_binding

    path = tmp_path / "binding.json"
    assert load_binding(path, registry_root=tmp_path / "registry") == LEGACY
    record_value = restore_record("a" * 32)
    value = record_value["binding"]
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    registry = tmp_path / "operations" / "restores"
    registry.mkdir(parents=True, mode=0o700)
    record_dir = registry / ("a" * 32)
    record_dir.mkdir(parents=True, mode=0o700)
    record = record_dir / "record.json"
    record.write_text(json.dumps(record_value))
    record.chmod(0o600)
    assert load_binding(path, registry_root=registry) == value
    record_value["status"] = "preparing"
    record.write_text(json.dumps(record_value))
    with pytest.raises(BindingInvalid):
        load_binding(path, registry_root=registry)


def test_record_status_cannot_claim_verified_without_all_restore_checks():
    from scripts.local_restore_state import RestoreStateInvalid, validate_record

    value = restore_record("a" * 32)
    value["verification"]["login"] = False
    with pytest.raises(RestoreStateInvalid):
        validate_record(value)


def test_journal_requires_explicit_recovery_choice_and_preserves_bindings():
    from datetime import UTC, datetime

    from scripts.local_restore_state import RestoreStateInvalid, validate_journal

    value = {
        "format": 1,
        "id": "a" * 32,
        "state": "recovering",
        "phase": "recover-stopping",
        "choice": None,
        "previous": legacy(),
        "candidate": restore_record("a" * 32)["binding"],
        "updated_at": datetime.now(UTC).isoformat(),
    }
    with pytest.raises(RestoreStateInvalid):
        validate_journal(value)
    value["choice"] = "previous"
    assert validate_journal(value)["previous"] == legacy()


def test_journal_switch_is_atomic_and_recovery_requires_an_explicit_binding(tmp_path):
    import json
    from datetime import UTC, datetime

    from scripts.local_restore_state import (
        activate_candidate_binding,
        begin_journal,
        begin_recovery,
        load_active_binding,
        load_journal,
        select_recovery_binding,
        write_record,
    )

    state_root = tmp_path / ".local"
    state_root.mkdir(mode=0o700)
    operations = state_root / "operations"
    operations.mkdir(mode=0o700)
    restore_id = "a" * 32
    record = restore_record(restore_id)
    write_record(operations, record)
    now = datetime.now(UTC).isoformat()
    started = begin_journal(state_root, restore_id, now=now)
    assert started["previous"] == legacy()
    assert load_active_binding(state_root) == legacy()

    from scripts.local_restore_state import update_journal

    update_journal(
        state_root,
        phase="previous-stopped",
        state="activating",
        now=now,
    )
    switched = activate_candidate_binding(state_root, now=now)
    assert switched["phase"] == "binding-switched"
    assert load_active_binding(state_root) == record["binding"]

    begin_recovery(state_root, restore_id, choice="previous", now=now)
    selected = select_recovery_binding(state_root, choice="previous", now=now)
    assert selected["phase"] == "recover-binding-switched"
    assert load_active_binding(state_root) == legacy()
    assert load_journal(state_root)["choice"] == "previous"

    binding_file = state_root / "runtime-binding.json"
    value = json.loads(binding_file.read_text())
    value["postgres_volume"] = "unowned"
    binding_file.write_text(json.dumps(value))
    binding_file.chmod(0o600)
    with pytest.raises(BindingInvalid):
        load_active_binding(state_root)
