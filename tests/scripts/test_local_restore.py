import hashlib
import json

import pytest

from scripts.local_restore import RestoreFailed, validate_manifest


def _write(path, value):
    data = value if isinstance(value, bytes) else value.encode()
    path.write_bytes(data)
    path.chmod(0o600)
    return data


def _manifest(tmp_path):
    payload = tmp_path / "payload"
    payload.mkdir(mode=0o700)
    config = (
        "CHATBI_LOCAL_HTTP_PORT=8080\n"
        "CHATBI_LOCAL_MODEL_DIR=.model-cache/bge-m3-5617a9f61b02\n"
        "POSTGRES_DB=chatbi_mvp\nPOSTGRES_MIGRATOR_USER=chatbi_migrator\n"
        "LLM_API_KEY=fixture-key\nLLM_BASE_URL=https://example.invalid\n"
        "LLM_MODEL=test\nLLM_TEMPERATURE=0.1\nLLM_MAX_TOKENS=4096\nLLM_TIMEOUT_SECONDS=30\n"
    )
    secrets = "".join(
        f"{name}={'x' * 64}\n"
        for name in (
            "POSTGRES_MIGRATOR_PASSWORD",
            "POSTGRES_APP_PASSWORD",
            "POSTGRES_CONTROL_APP_PASSWORD",
            "CHATBI_ADMIN_SECRET_KEY",
            "QDRANT_API_KEY",
        )
    )
    _write(payload / "config.env", config)
    _write(payload / "secrets.env", secrets)
    _write(
        payload / "release.env",
        "CHATBI_SOURCE_COMMIT=" + "a" * 40 + "\n"
        "CHATBI_API_IMAGE=chatbi-local-api:release\n"
        "CHATBI_API_IMAGE_ID=sha256:" + "b" * 64 + "\n"
        "CHATBI_DATABASE_IMAGE=chatbi-local-postgres:release\n"
        "CHATBI_DATABASE_IMAGE_ID=sha256:" + "c" * 64 + "\n",
    )
    current = json.dumps({"format": 1, "manifest_path": "manifest.json"}).encode()
    rag_manifest = json.dumps({"format": 1}).encode()
    compatibility = json.dumps({"format": 1}).encode()
    for name, value in (
        ("rag-current.json", current),
        ("rag-manifest.json", rag_manifest),
        ("compatibility.json", compatibility),
    ):
        _write(payload / name, value)
    for name in ("business.dump", "control.dump"):
        _write(payload / name, b"dump")
    source = {
        "format": 1,
        "source_commit": "a" * 40,
        "api_image": "chatbi-local-api:release",
        "api_image_id": "sha256:" + "b" * 64,
        "database_image": "chatbi-local-postgres:release",
        "database_image_id": "sha256:" + "c" * 64,
        "captured_at": "2026-10-08T12:00:00+00:00",
        "live_required": False,
        "asset_sha256": {
            "rag-current.json": hashlib.sha256(current).hexdigest(),
            "rag-manifest.json": hashlib.sha256(rag_manifest).hexdigest(),
        },
    }
    roles = [
        {
            "name": name,
            "superuser": name == "chatbi_migrator",
            "create_database": name == "chatbi_migrator",
            "create_role": name == "chatbi_migrator",
            "login": True,
            "replication": False,
            "bypass_rls": False,
        }
        for name in ("chatbi_migrator", "chatbi_app", "chatbi_control_user")
    ]
    tables = {"public.records": {"rows": 2, "sha256": "d" * 64}}
    manifest = {
        "format": 1,
        "id": "e" * 32,
        "created_at": "2026-10-08T12:00:00+00:00",
        "source": source,
        "roles": roles,
        "databases": {
            "business": {"name": "chatbi_mvp", "tables": tables},
            "control": {"name": "chatbi_control", "tables": tables},
        },
        "members": {
            name: {"size": 1, "sha256": "a" * 64}
            for name in (
                "business.dump",
                "control.dump",
                "config.env",
                "secrets.env",
                "release.env",
                "rag-current.json",
                "rag-manifest.json",
                "compatibility.json",
            )
        },
    }
    return manifest, payload


def _restore_record(restore_id, status="preparing"):
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
        "verified_at": None,
        "fingerprints": {
            "business": {"public.items": {"rows": 1, "sha256": "1" * 64}},
            "control": {"public.history_records": {"rows": 1, "sha256": "2" * 64}},
        },
        "normalization": {"restored_epoch": None, "active_epoch": None},
        "verification": {
            "readiness": False,
            "login": False,
            "history": False,
            "index_ready": False,
            "duration_seconds": 0,
        },
    }


def test_restore_manifest_accepts_only_known_role_and_resource_contracts(
    tmp_path, monkeypatch
):
    import scripts.local_release as release
    import scripts.local_restore as restore

    monkeypatch.setattr(restore, "verify_dump", lambda _path: None)
    monkeypatch.setattr(
        release, "validate_compatibility_profile", lambda _profile: None
    )
    manifest, payload = _manifest(tmp_path)
    checked = validate_manifest(manifest, backup_id="e" * 32, payload=payload)
    assert checked["source"]["source_commit"] == "a" * 40
    assert (
        checked["fingerprints"]["control"] == manifest["databases"]["control"]["tables"]
    )

    manifest["roles"][1]["superuser"] = True
    with pytest.raises(RestoreFailed):
        validate_manifest(manifest, backup_id="e" * 32, payload=payload)


def test_restore_preserves_optional_trace_configuration(tmp_path, monkeypatch):
    import scripts.local_release as release
    import scripts.local_restore as restore

    monkeypatch.setattr(restore, "verify_dump", lambda _path: None)
    monkeypatch.setattr(
        release, "validate_compatibility_profile", lambda _profile: None
    )
    manifest, payload = _manifest(tmp_path)
    with (payload / "config.env").open("ab") as stream:
        stream.write(
            b"CHATBI_OBSERVABILITY_ENABLED=true\n"
            b"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://collector.invalid/v1/traces\n"
            b"CHATBI_OTLP_TIMEOUT_SECONDS=5\n"
        )
    with (payload / "secrets.env").open("ab") as stream:
        stream.write(b"OTEL_EXPORTER_OTLP_HEADERS=Authentication=fixture-token\n")

    checked = validate_manifest(manifest, backup_id="e" * 32, payload=payload)

    assert checked["config"]["CHATBI_OBSERVABILITY_ENABLED"] == "true"
    assert checked["config"]["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"].startswith(
        "https://"
    )
    assert checked["secrets"]["OTEL_EXPORTER_OTLP_HEADERS"].startswith(
        "Authentication="
    )


def test_restore_manifest_rejects_extra_config_and_release_identity_mismatch(
    tmp_path, monkeypatch
):
    import scripts.local_release as release
    import scripts.local_restore as restore

    monkeypatch.setattr(restore, "verify_dump", lambda _path: None)
    monkeypatch.setattr(
        release, "validate_compatibility_profile", lambda _profile: None
    )
    alternate = tmp_path / "alternate"
    alternate.mkdir(mode=0o700)
    manifest, payload = _manifest(alternate)
    with (payload / "config.env").open("ab") as stream:
        stream.write(b"CHATBI_COMMAND=unexpected\n")
    with pytest.raises(RestoreFailed):
        validate_manifest(manifest, backup_id="e" * 32, payload=payload)

    manifest, payload = _manifest(tmp_path)
    manifest["source"]["api_image_id"] = "sha256:" + "f" * 64
    with pytest.raises(RestoreFailed):
        validate_manifest(manifest, backup_id="e" * 32, payload=payload)


def test_temporary_verifier_copies_a_completed_snapshot_without_reassigning_source(
    tmp_path, monkeypatch
):
    import uuid

    import scripts.local_restore as restore

    restore_id = "a" * 32
    state_root = tmp_path / "operations"
    state_root.mkdir(mode=0o700)
    record = _restore_record(restore_id)
    record["normalization"] = {
        "restored_epoch": str(uuid.uuid4()),
        "active_epoch": None,
    }
    restore.write_record(state_root, record)
    sql = []
    monkeypatch.setattr(
        restore, "_control_psql", lambda statement, *, env: sql.append(statement)
    )
    monkeypatch.setattr(restore, "pg_environment", lambda _database: {})
    credentials = {
        "username": "restore_test_aaaaaaaaaaaa",
        "password": "secret-" + "x" * 40,
        "password_hash": "$argon2id$test-hash",
    }
    result = restore.create_verification_identity(
        tmp_path, restore_id, json.dumps(credentials).encode()
    )
    assert result == {"status": "created", "username": credentials["username"]}
    assert "t.status='succeeded'" in sql[0]
    assert "v_source.snapshot" in sql[0]
    assert "owner_user_id=" not in sql[0]
    assert "UPDATE history_records" in sql[0]

    monkeypatch.setattr(restore, "_scalar", lambda *args, **kwargs: "0")
    result = restore.cleanup_verification_identity(tmp_path, restore_id)
    assert result == {"status": "cleaned", "username": credentials["username"]}
    assert "DELETE FROM history_records WHERE owner_user_id=v_user_id" in sql[1]


def test_failed_restore_can_clear_plaintext_payload_without_marking_verified(tmp_path):
    from scripts.local_backup_archive import MEMBERS
    from scripts.local_restore import clear_payload
    from scripts.local_restore_state import load_record, write_record

    restore_id = "a" * 32
    operations = tmp_path / "operations"
    operations.mkdir(mode=0o700)
    record = _restore_record(restore_id)
    write_record(operations, record)
    payload = operations / "restores" / restore_id / "payload"
    payload.mkdir(mode=0o700)
    for name in MEMBERS | {"manifest.json"}:
        member = payload / name
        member.write_bytes(b"private restore material")
        member.chmod(0o600)

    result = clear_payload(tmp_path, restore_id)
    assert result == {"status": "cleared", "restore_id": restore_id}
    assert not payload.exists()
    assert load_record(operations, restore_id)["status"] == "preparing"


def test_failed_backup_preflight_removes_its_partial_plaintext_stage(
    tmp_path, monkeypatch
):
    import scripts.local_restore as restore

    operations = tmp_path / "operations"
    operations.mkdir(mode=0o700)

    class FailingStore:
        def __init__(self, _root, *, create):
            assert create is False

        def known_artifact(self, _backup_id):
            return tmp_path / "unused.age", {
                "source_commit": "a" * 40,
                "created_at": "2026-10-08T12:00:00+00:00",
            }

        def require_key(self):
            return None

        def decrypt(self, _backup_id, payload):
            _write(payload / "secrets.env", b"sensitive plaintext")
            raise RestoreFailed("RESTORE_INVALID")

    monkeypatch.setattr(restore, "BackupStore", FailingStore)
    restore_id = "f" * 32
    with pytest.raises(RestoreFailed, match="RESTORE_INVALID"):
        restore.prepare_restore(tmp_path, "e" * 32, restore_id)

    assert not (operations / "restores" / restore_id).exists()


def test_temporary_credentials_work_when_launched_outside_the_repository(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).parents[2] / "scripts" / "local_restore_credentials.py"
    result = subprocess.run(
        [sys.executable, str(script), "--restore-id", "a" * 32],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    credentials = json.loads(result.stdout)
    assert credentials["username"] == "restore_test_aaaaaaaaaaaa"
    assert len(credentials["password"]) >= 32
    assert credentials["password_hash"].startswith("$argon2id$")


def test_login_verifier_reads_a_completed_history_and_saved_snapshot_then_logs_out(
    monkeypatch,
):
    import scripts.local_restore_login as client

    history_id = "11111111-1111-4111-8111-111111111111"
    turn_id = "22222222-2222-4222-8222-222222222222"
    result_id = "33333333-3333-4333-8333-333333333333"
    calls = []

    def request(_base, path, *, token=None, body=None, method=None):
        calls.append((path, token, body, method))
        if path == "/auth/login":
            return 200, {"access_token": "ephemeral-token"}
        if path == "/auth/me":
            return 200, {"username": "restore_test"}
        if path == "/api/v1/histories?limit=20":
            return 200, {"items": [{"id": history_id}]}
        if path == "/api/v1/histories/" + history_id:
            return 200, {"id": history_id}
        if path == "/api/v1/histories/" + history_id + "/turns?limit=100":
            return 200, {"items": [{"id": turn_id, "status": "succeeded"}]}
        if path == "/api/v1/histories/" + history_id + "/turns/" + turn_id:
            return 200, {"snapshot": {"version": 1}}
        if path == "/api/v1/saved-results?limit=1":
            return 200, {"items": [{"id": result_id}]}
        if path == "/api/v1/saved-results/" + result_id:
            return 200, {"snapshot": {"version": 1}}
        if path == "/auth/logout":
            return 204, None
        raise AssertionError(path)

    monkeypatch.setattr(client, "_request", request)
    credentials = {
        "username": "restore_test",
        "password": "secret-not-logged",
        "password_hash": "$argon2id$unused",
    }
    assert client.verify(8080, credentials) == {"login": True, "history": True}
    assert calls[-1][0] == "/auth/logout"
    assert calls[-1][1] == "ephemeral-token"


@pytest.mark.parametrize(
    "failure",
    ["wrong_identity", "empty_histories", "no_succeeded_turn", "empty_results"],
)
def test_login_verifier_rejects_missing_or_wrong_history_evidence_and_logs_out(
    monkeypatch, failure
):
    import scripts.local_restore_login as client

    history_id = "11111111-1111-4111-8111-111111111111"
    turn_id = "22222222-2222-4222-8222-222222222222"
    calls = []

    def request(_base, path, *, token=None, body=None, method=None):
        calls.append(path)
        if path == "/auth/login":
            return 200, {"access_token": "ephemeral-token"}
        if path == "/auth/me":
            username = "someone-else" if failure == "wrong_identity" else "restore_test"
            return 200, {"username": username}
        if path == "/api/v1/histories?limit=20":
            items = [] if failure == "empty_histories" else [{"id": history_id}]
            return 200, {"items": items}
        if path == "/api/v1/histories/" + history_id:
            return 200, {"id": history_id}
        if path == "/api/v1/histories/" + history_id + "/turns?limit=100":
            status = "failed" if failure == "no_succeeded_turn" else "succeeded"
            return 200, {"items": [{"id": turn_id, "status": status}]}
        if path == "/api/v1/histories/" + history_id + "/turns/" + turn_id:
            return 200, {"snapshot": {"version": 1}}
        if path == "/api/v1/saved-results?limit=1":
            items = (
                []
                if failure == "empty_results"
                else [{"id": "33333333-3333-4333-8333-333333333333"}]
            )
            return 200, {"items": items}
        if path == "/auth/logout":
            return 204, None
        raise AssertionError(path)

    monkeypatch.setattr(client, "_request", request)
    credentials = {
        "username": "restore_test",
        "password": "secret-not-logged",
        "password_hash": "$argon2id$unused",
    }
    with pytest.raises(RuntimeError):
        client.verify(8080, credentials)
    assert calls[-1] == "/auth/logout"


def test_restore_state_cli_runs_from_outside_the_repository(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts" / "local_restore_state.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
