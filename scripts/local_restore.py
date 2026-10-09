"""隔离恢复工具；宿主只调度已登记副本，不接触解密数据库归档。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from scripts.local_backup import (
    BackupFailed,
    BackupStore,
    atomic_json,
    operation_lock,
    secure_directory,
    secure_file,
)
from scripts.local_backup_archive import MEMBERS
from scripts.local_backup_postgres import (
    DatabaseBackupFailed,
    Snapshot,
    pg_environment,
    verify_dump,
)
from scripts.local_restore_state import (
    RestoreStateInvalid,
    load_record,
    write_record,
)

RESTORE_ID = re.compile(r"[0-9a-f]{32}\Z")
ENV_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
REQUIRED_SECRET_KEYS = {
    "POSTGRES_MIGRATOR_PASSWORD",
    "POSTGRES_APP_PASSWORD",
    "POSTGRES_CONTROL_APP_PASSWORD",
    "CHATBI_ADMIN_SECRET_KEY",
    "QDRANT_API_KEY",
}
SECRET_KEYS = REQUIRED_SECRET_KEYS | {"OTEL_EXPORTER_OTLP_HEADERS"}
REQUIRED_CONFIG_KEYS = {
    "CHATBI_LOCAL_HTTP_PORT",
    "CHATBI_LOCAL_MODEL_DIR",
    "POSTGRES_DB",
    "POSTGRES_MIGRATOR_USER",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_TEMPERATURE",
    "LLM_MAX_TOKENS",
    "LLM_TIMEOUT_SECONDS",
}
CONFIG_KEYS = REQUIRED_CONFIG_KEYS | {
    "CHATBI_OBSERVABILITY_ENABLED",
    "CHATBI_TRACE_CONTENT_ENABLED",
    "OTEL_SERVICE_NAME",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "CHATBI_OTLP_TIMEOUT_SECONDS",
}
ROLE_FIELDS = {
    "name",
    "superuser",
    "create_database",
    "create_role",
    "login",
    "replication",
    "bypass_rls",
}


class RestoreFailed(RuntimeError):
    pass


def parse_env(data: bytes, *, allowed, required):
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeError:
        raise RestoreFailed("RESTORE_INVALID") from None
    values = {}
    for original in lines:
        line = original.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise RestoreFailed("RESTORE_INVALID")
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not ENV_KEY.fullmatch(key) or key not in allowed or key in values:
            raise RestoreFailed("RESTORE_INVALID")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            quote = value[0]
            value = value[1:-1]
            if quote == "'":
                value = value.replace("\\'", "'")
            else:
                value = value.replace('\\"', '"').replace("\\\\", "\\")
        if any(char in value for char in "\0\n\r"):
            raise RestoreFailed("RESTORE_INVALID")
        values[key] = value
    if not required <= values.keys():
        raise RestoreFailed("RESTORE_INVALID")
    return values


def validate_manifest(manifest, *, backup_id, payload):
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"format", "id", "created_at", "source", "roles", "databases", "members"}
        or type(manifest.get("format")) is not int
        or manifest["format"] != 1
        or manifest.get("id") != backup_id
        or not isinstance(manifest.get("created_at"), str)
        or not isinstance(manifest.get("members"), dict)
        or set(manifest["members"]) != MEMBERS
        or not isinstance(manifest.get("source"), dict)
        or not isinstance(manifest.get("roles"), list)
        or not isinstance(manifest.get("databases"), dict)
        or set(manifest["databases"]) != {"business", "control"}
    ):
        raise RestoreFailed("RESTORE_INVALID")
    try:
        created_at = datetime.fromisoformat(manifest["created_at"])
        if created_at.tzinfo is None:
            raise ValueError()
    except (TypeError, ValueError):
        raise RestoreFailed("RESTORE_INVALID") from None

    source = manifest["source"]
    expected_source_fields = {
        "format",
        "source_commit",
        "api_image",
        "api_image_id",
        "database_image",
        "database_image_id",
        "captured_at",
        "live_required",
        "asset_sha256",
    }
    if (
        set(source) != expected_source_fields
        or type(source["format"]) is not int
        or source["format"] != 1
        or not isinstance(source["source_commit"], str)
        or not re.fullmatch(r"[0-9a-f]{40}", source["source_commit"])
        or not isinstance(source["api_image"], str)
        or not re.fullmatch(r"chatbi-local-api:[A-Za-z0-9_.-]+", source["api_image"])
        or not isinstance(source["database_image"], str)
        or not re.fullmatch(r"chatbi-local-postgres:[A-Za-z0-9_.-]+", source["database_image"])
        or any(
            not isinstance(source[key], str)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", source[key])
            for key in ("api_image_id", "database_image_id")
        )
        or type(source["live_required"]) is not bool
        or not isinstance(source["asset_sha256"], dict)
        or set(source["asset_sha256"]) != {"rag-current.json", "rag-manifest.json"}
        or any(
            not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
            for value in source["asset_sha256"].values()
        )
    ):
        raise RestoreFailed("RESTORE_INVALID")
    try:
        captured = datetime.fromisoformat(source["captured_at"])
        if captured.tzinfo is None:
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise RestoreFailed("RESTORE_INVALID") from None

    config = parse_env(
        secure_file(payload / "config.env"),
        allowed=CONFIG_KEYS,
        required=REQUIRED_CONFIG_KEYS,
    )
    secrets = parse_env(
        secure_file(payload / "secrets.env"),
        allowed=SECRET_KEYS,
        required=REQUIRED_SECRET_KEYS,
    )
    release = parse_env(
        secure_file(payload / "release.env"),
        allowed={
            "CHATBI_SOURCE_COMMIT",
            "CHATBI_API_IMAGE",
            "CHATBI_API_IMAGE_ID",
            "CHATBI_DATABASE_IMAGE",
            "CHATBI_DATABASE_IMAGE_ID",
        },
        required={
            "CHATBI_SOURCE_COMMIT",
            "CHATBI_API_IMAGE",
            "CHATBI_API_IMAGE_ID",
            "CHATBI_DATABASE_IMAGE",
            "CHATBI_DATABASE_IMAGE_ID",
        },
    )
    if any(
        release[key] != source[value]
        for key, value in (
            ("CHATBI_SOURCE_COMMIT", "source_commit"),
            ("CHATBI_API_IMAGE", "api_image"),
            ("CHATBI_API_IMAGE_ID", "api_image_id"),
            ("CHATBI_DATABASE_IMAGE", "database_image"),
            ("CHATBI_DATABASE_IMAGE_ID", "database_image_id"),
        )
    ):
        raise RestoreFailed("RESTORE_INVALID")
    try:
        local_port = int(config["CHATBI_LOCAL_HTTP_PORT"])
        temperature = float(config["LLM_TEMPERATURE"])
        max_tokens = int(config["LLM_MAX_TOKENS"])
        timeout = int(config["LLM_TIMEOUT_SECONDS"])
    except (TypeError, ValueError):
        raise RestoreFailed("RESTORE_INVALID") from None
    if (
        not 1 <= local_port <= 65535
        or not 0 <= temperature <= 2
        or not 1 <= max_tokens <= 32768
        or not 1 <= timeout <= 300
        or config["POSTGRES_DB"] != "chatbi_mvp"
        or config["POSTGRES_MIGRATOR_USER"] != "chatbi_migrator"
        or not config["LLM_API_KEY"].strip()
        or any(
            not secrets[key] or len(secrets[key]) < 32
            for key in REQUIRED_SECRET_KEYS
        )
    ):
        raise RestoreFailed("RESTORE_INVALID")
    if (
        config["POSTGRES_DB"] != "chatbi_mvp"
        or config["POSTGRES_DB"] != manifest["databases"]["business"].get("name")
        or manifest["databases"]["control"].get("name") != "chatbi_control"
        or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", config["POSTGRES_DB"])
        or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", config["POSTGRES_MIGRATOR_USER"])
    ):
        raise RestoreFailed("RESTORE_INVALID")

    roles = manifest["roles"]
    if (
        len(roles) != 3
        or any(not isinstance(role, dict) or set(role) != ROLE_FIELDS for role in roles)
        or {role.get("name") for role in roles}
        != {config["POSTGRES_MIGRATOR_USER"], "chatbi_app", "chatbi_control_user"}
        or any(type(role[key]) is not bool for role in roles for key in ROLE_FIELDS - {"name"})
        or any(
            not role["login"]
            or (
                role["name"] != config["POSTGRES_MIGRATOR_USER"]
                and any(role[key] for key in ("superuser", "create_database", "create_role", "replication", "bypass_rls"))
            )
            for role in roles
        )
    ):
        raise RestoreFailed("RESTORE_INVALID")

    for name, dump in (("business", "business.dump"), ("control", "control.dump")):
        database = manifest["databases"][name]
        if (
            not isinstance(database, dict)
            or set(database) != {"name", "tables"}
            or not isinstance(database["name"], str)
            or not isinstance(database["tables"], dict)
            or not database["tables"]
            or any(
                not isinstance(table, str)
                or not isinstance(fingerprint, dict)
                or set(fingerprint) != {"rows", "sha256"}
                or type(fingerprint["rows"]) is not int
                or fingerprint["rows"] < 0
                or not isinstance(fingerprint["sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", fingerprint["sha256"])
                for table, fingerprint in database["tables"].items()
            )
        ):
            raise RestoreFailed("RESTORE_INVALID")
        verify_dump(payload / dump)

    for filename, digest in source["asset_sha256"].items():
        if hashlib.sha256(secure_file(payload / filename)).hexdigest() != digest:
            raise RestoreFailed("RESTORE_INVALID")
    try:
        current = json.loads(secure_file(payload / "rag-current.json"))
        manifest_value = json.loads(secure_file(payload / "rag-manifest.json"))
        compatibility = json.loads(secure_file(payload / "compatibility.json"))
    except (ValueError, TypeError):
        raise RestoreFailed("RESTORE_INVALID") from None
    if (
        not isinstance(current, dict)
        or not isinstance(manifest_value, dict)
        or not isinstance(compatibility, dict)
    ):
        raise RestoreFailed("RESTORE_INVALID")
    from scripts.local_release import validate_compatibility_profile

    validate_compatibility_profile(compatibility)
    return {
        "source": source,
        "config": config,
        "secrets": secrets,
        "release": release,
        "compatibility": compatibility,
        "fingerprints": {
            "business": manifest["databases"]["business"]["tables"],
            "control": manifest["databases"]["control"]["tables"],
        },
    }


def _write_private(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def prepare_restore(root, backup_id, restore_id):
    if not RESTORE_ID.fullmatch(restore_id):
        raise RestoreFailed("RESTORE_INVALID")
    store = BackupStore(root, create=False)
    _artifact, catalog_entry = store.known_artifact(backup_id)
    store.require_key()
    root = Path(root)
    operations = secure_directory(root / "operations", create=False)
    restores = secure_directory(operations / "restores", create=True)
    restore_dir = restores / restore_id
    if restore_dir.exists() or restore_dir.is_symlink():
        raise RestoreFailed("RESTORE_ID_EXISTS")
    restore_dir.mkdir(mode=0o700)
    try:
        payload = restore_dir / "payload"
        payload.mkdir(mode=0o700)
        manifest = store.decrypt(backup_id, payload)
        checked = validate_manifest(manifest, backup_id=backup_id, payload=payload)
        if (
            catalog_entry["source_commit"] != checked["source"]["source_commit"]
            or catalog_entry["created_at"] != manifest["created_at"]
        ):
            raise RestoreFailed("RESTORE_INVALID")
        atomic_json(payload / "manifest.json", manifest)
        for name in ("config.env", "secrets.env", "release.env", "compatibility.json"):
            _write_private(restore_dir / name, secure_file(payload / name))
        evidence = restore_dir / "evidence"
        evidence.mkdir(mode=0o700)
        for name in ("rag-current.json", "rag-manifest.json"):
            _write_private(evidence / name, secure_file(payload / name))
        (restore_dir / "rag").mkdir(mode=0o700)
        (restore_dir / "api").mkdir(mode=0o700)
        source = checked["source"]
        from scripts.local_runtime_binding import restore_binding

        record = {
            "format": 1,
            "id": restore_id,
            "status": "preparing",
            "backup_id": backup_id,
            "binding": restore_binding(
                restore_id,
                database_image=source["database_image"],
                database_image_id=source["database_image_id"],
            ),
            "source_commit": source["source_commit"],
            "api_image": source["api_image"],
            "api_image_id": source["api_image_id"],
            "database_image": source["database_image"],
            "database_image_id": source["database_image_id"],
            "compatibility_sha256": hashlib.sha256(
                secure_file(restore_dir / "compatibility.json")
            ).hexdigest(),
            "created_at": datetime.now(UTC).isoformat(),
            "verified_at": None,
            "fingerprints": checked["fingerprints"],
            "normalization": {"restored_epoch": None, "active_epoch": None},
            "verification": {
                "readiness": False,
                "login": False,
                "history": False,
                "index_ready": False,
                "duration_seconds": 0,
            },
        }
        write_record(operations, record)
    except BaseException:
        try:
            if restore_dir.is_symlink():
                raise OSError("restore directory replaced")
            shutil.rmtree(restore_dir)
        except OSError:
            raise RestoreFailed("RESTORE_STORAGE_CLEANUP_FAILED") from None
        raise
    return {
        "restore_id": restore_id,
        "source_commit": source["source_commit"],
        "api_image": source["api_image"],
        "api_image_id": source["api_image_id"],
        "database_image": source["database_image"],
        "database_image_id": source["database_image_id"],
    }


def _run(arguments, *, env, timeout=900):
    try:
        subprocess.run(
            arguments,
            env=env,
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RestoreFailed("RESTORE_TIMEOUT") from None
    except (OSError, subprocess.CalledProcessError):
        raise RestoreFailed("RESTORE_DATABASE_FAILED") from None


def _create_control_database(name, *, env):
    if name != "chatbi_control":
        raise RestoreFailed("RESTORE_INVALID")
    check = subprocess.run(
        ["psql", "-X", "--no-password", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-c",
         "SELECT 1 FROM pg_database WHERE datname='chatbi_control'"],
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=15,
    )
    if check.stdout.strip() != b"1":
        maintenance_env = dict(env, PGDATABASE="postgres")
        _run(
            ["createdb", "--no-password", "--owner=chatbi_control_user", "chatbi_control"],
            env=maintenance_env,
            timeout=30,
        )


def _scalar(database, statement, *, env):
    try:
        result = subprocess.run(
            ["psql", "-X", "--no-password", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", database, "-c", statement],
            env=env,
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        raise RestoreFailed("RESTORE_DATABASE_FAILED") from None
    return result.stdout.decode("utf-8", errors="strict").strip()


def _restore_database(database, dump, *, env):
    db_env = dict(env, PGDATABASE=database)
    _run(
        [
            "pg_restore",
            "--no-password",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-acl",
            "--exit-on-error",
            "--dbname",
            database,
            str(dump),
        ],
        env=db_env,
    )


def restore_databases(root, restore_id):
    operations = secure_directory(Path(root) / "operations", create=False)
    record = load_record(operations, restore_id)
    if record["status"] != "preparing":
        raise RestoreFailed("RESTORE_STATE_INVALID")
    restore_dir = secure_directory(operations / "restores" / restore_id, create=False)
    payload = secure_directory(restore_dir / "payload", create=False)
    manifest = json.loads(secure_file(payload / "manifest.json"))
    checked = validate_manifest(manifest, backup_id=record["backup_id"], payload=payload)
    env = pg_environment(os.environ.get("POSTGRES_DB", "chatbi_mvp"))
    _create_control_database("chatbi_control", env=env)
    _restore_database(os.environ.get("POSTGRES_DB", "chatbi_mvp"), payload / "business.dump", env=env)
    _restore_database("chatbi_control", payload / "control.dump", env=env)
    _run(
        ["psql", "-X", "--no-password", "-q", "-v", "ON_ERROR_STOP=1", "-d", "chatbi_mvp", "-f", "/workspace/database/grants.sql"],
        env=env,
    )
    _run(
        ["psql", "-X", "--no-password", "-q", "-v", "ON_ERROR_STOP=1", "-d", "chatbi_control", "-f", "/workspace/database/control/003_grants.sql"],
        env=env,
    )
    grant_statement = """\
GRANT SELECT, INSERT, UPDATE ON TABLE business_analysis_runs TO chatbi_control_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE history_records, history_turns, saved_results, history_executions TO chatbi_control_user;
GRANT SELECT, INSERT, UPDATE ON TABLE history_runtime TO chatbi_control_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE checkpoints, checkpoint_blobs, checkpoint_writes TO chatbi_control_user;
GRANT SELECT ON TABLE checkpoint_migrations TO chatbi_control_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO chatbi_control_user;
"""
    _run(
        [
            "psql",
            "-X",
            "--no-password",
            "-q",
            "-v",
            "ON_ERROR_STOP=1",
            "-d",
            "chatbi_control",
            "-c",
            grant_statement,
        ],
        env=env,
    )
    for database, expected in (
        (os.environ.get("POSTGRES_DB", "chatbi_mvp"), checked["fingerprints"]["business"]),
        ("chatbi_control", checked["fingerprints"]["control"]),
    ):
        with Snapshot(database) as snapshot:
            actual = snapshot.fingerprints()
        if actual != expected:
            raise RestoreFailed("RESTORE_FINGERPRINT_MISMATCH")
    with Snapshot(os.environ.get("POSTGRES_DB", "chatbi_mvp")) as snapshot:
        roles = snapshot.approved_roles()
    if {role["name"] for role in roles} != {
        os.environ.get("POSTGRES_MIGRATOR_USER", "chatbi_migrator"),
        "chatbi_app",
        "chatbi_control_user",
    }:
        raise RestoreFailed("RESTORE_ROLE_MISMATCH")
    _run(
        ["psql", "-X", "--no-password", "-q", "-v", "ON_ERROR_STOP=1", "-d", "chatbi_control", "-c",
         "UPDATE sessions SET revoked_at=COALESCE(revoked_at,CURRENT_TIMESTAMP) WHERE revoked_at IS NULL"],
        env=env,
    )
    restored_epoch = _scalar(
        "chatbi_control",
        "SELECT runtime_epoch::text FROM history_runtime WHERE singleton",
        env=env,
    )
    try:
        uuid.UUID(restored_epoch)
    except (ValueError, TypeError, AttributeError):
        raise RestoreFailed("RESTORE_INVALID") from None
    record["normalization"]["restored_epoch"] = restored_epoch
    write_record(operations, record)
    # Archive contents and restored control rows are retained until candidate
    # readiness/login checks finish; deletion is explicit and scoped below.
    return {"status": "restored", "restore_id": restore_id}


def mark_verified(root, restore_id, verification):
    operations = secure_directory(Path(root) / "operations", create=False)
    record = load_record(operations, restore_id)
    if record["status"] != "preparing":
        raise RestoreFailed("RESTORE_STATE_INVALID")
    if (
        not isinstance(verification, dict)
        or set(verification)
        != {"readiness", "login", "history", "index_ready", "duration_seconds"}
        or any(type(verification[key]) is not bool for key in ("readiness", "login", "history", "index_ready"))
        or type(verification["duration_seconds"]) is not int
        or not 0 <= verification["duration_seconds"] <= 1800
        or not all(verification[key] for key in ("readiness", "login", "history", "index_ready"))
    ):
        raise RestoreFailed("RESTORE_VERIFICATION_INCOMPLETE")
    env = pg_environment(os.environ.get("POSTGRES_DB", "chatbi_mvp"))
    if _scalar("chatbi_control", "SELECT count(*) FROM sessions WHERE revoked_at IS NULL", env=env) != "0":
        raise RestoreFailed("RESTORE_SESSIONS_ACTIVE")
    if _scalar("chatbi_control", "SELECT count(*) FROM history_records WHERE active_turn_id IS NOT NULL", env=env) != "0":
        raise RestoreFailed("RESTORE_HISTORY_ACTIVE")
    if _scalar("chatbi_control", "SELECT count(*) FROM history_turns WHERE status='accepted'", env=env) != "0":
        raise RestoreFailed("RESTORE_HISTORY_ACTIVE")
    if _scalar("chatbi_control", "SELECT count(*) FROM history_executions WHERE status IN ('accepted','running','stopping')", env=env) != "0":
        raise RestoreFailed("RESTORE_EXECUTION_ACTIVE")
    active_epoch = _scalar(
        "chatbi_control",
        "SELECT runtime_epoch::text FROM history_runtime WHERE singleton",
        env=env,
    )
    try:
        uuid.UUID(active_epoch)
    except (ValueError, TypeError, AttributeError):
        raise RestoreFailed("RESTORE_EPOCH_INVALID") from None
    if not record["normalization"]["restored_epoch"] or active_epoch == record["normalization"]["restored_epoch"]:
        raise RestoreFailed("RESTORE_EPOCH_NOT_FENCED")
    record["normalization"]["active_epoch"] = active_epoch
    record["status"] = "verified"
    record["verification"] = verification
    record["verified_at"] = datetime.now(UTC).isoformat()
    write_record(operations, record)
    return {"status": "verified", "restore_id": restore_id}


def clear_payload(root, restore_id):
    operations = secure_directory(Path(root) / "operations", create=False)
    load_record(operations, restore_id)
    restore_dir = secure_directory(operations / "restores" / restore_id, create=False)
    payload = secure_directory(restore_dir / "payload", create=False)
    from scripts.local_backup_archive import MEMBERS

    items = list(payload.iterdir())
    if (
        {item.name for item in items} != set(MEMBERS) | {"manifest.json"}
        or any(item.is_symlink() or not item.is_file() for item in items)
    ):
        raise RestoreFailed("RESTORE_STORAGE_UNSAFE")
    for item in items:
        item.unlink()
    payload.rmdir()
    return {"status": "cleared", "restore_id": restore_id}


def _sql_literal(value):
    if not isinstance(value, str) or any(char in value for char in "\0\n\r"):
        raise RestoreFailed("RESTORE_INVALID")
    return "'" + value.replace("'", "''") + "'"


def _temporary_identity_input(data, restore_id):
    try:
        value = json.loads(data)
    except (ValueError, TypeError):
        raise RestoreFailed("RESTORE_VERIFICATION_FAILED") from None
    if (
        not isinstance(value, dict)
        or set(value) != {"username", "password", "password_hash"}
        or value["username"] != "restore_test_" + restore_id[:12]
        or not isinstance(value["password"], str)
        or len(value["password"]) < 32
        or not isinstance(value["password_hash"], str)
        or not value["password_hash"].startswith("$argon2id$")
        or len(value["password_hash"]) > 512
    ):
        raise RestoreFailed("RESTORE_VERIFICATION_FAILED")
    return value


def _control_psql(sql, *, env):
    try:
        subprocess.run(
            ["psql", "-X", "--no-password", "-q", "-v", "ON_ERROR_STOP=1", "-d", "chatbi_control"],
            env=env,
            input=sql.encode("utf-8"),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        raise RestoreFailed("RESTORE_TIMEOUT") from None
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        raise RestoreFailed("RESTORE_VERIFICATION_FAILED") from None


def create_verification_identity(root, restore_id, data):
    operations = secure_directory(Path(root) / "operations", create=False)
    record = load_record(operations, restore_id)
    if record["status"] != "preparing" or not record["normalization"]["restored_epoch"]:
        raise RestoreFailed("RESTORE_STATE_INVALID")
    identity = _temporary_identity_input(data, restore_id)
    username, password_hash = identity["username"], identity["password_hash"]
    # Dynamic values are SQL literals validated and escaped by _sql_literal.
    sql = """
DO $$
DECLARE
    v_user_id BIGINT;
    v_role_id BIGINT;
    v_source RECORD;
    v_history_id UUID;
    v_turn_id UUID;
BEGIN
    INSERT INTO users(username,password_hash,is_active,must_change_password,failed_login_count,locked_until)
    VALUES ({username},{password_hash},TRUE,FALSE,0,NULL)
    RETURNING id INTO v_user_id;
    SELECT id INTO v_role_id FROM roles WHERE name='analyst';
    IF v_role_id IS NULL THEN RAISE EXCEPTION 'verification role missing'; END IF;
    INSERT INTO user_roles(user_id,role_id) VALUES (v_user_id,v_role_id);

    SELECT h.first_question,h.creation_operation_hash,t.operation_hash,t.question,
           t.created_at,t.completed_at,t.attempt_input,t.snapshot_version,t.snapshot
      INTO v_source
      FROM history_records h
      JOIN history_turns t ON t.history_id=h.id
     WHERE h.kind='query' AND h.deleted_at IS NULL
       AND t.status='succeeded' AND t.snapshot IS NOT NULL
       AND t.snapshot_version=1
     ORDER BY t.completed_at DESC NULLS LAST,t.created_at DESC
     LIMIT 1;
    IF NOT FOUND THEN RAISE EXCEPTION 'completed history snapshot missing'; END IF;

    INSERT INTO history_records(
        id,owner_user_id,kind,title,first_question,creation_operation_id,
        creation_operation_hash,created_at,updated_at,context_revision,
        record_revision,next_ordinal,last_success_turn_id,active_turn_id,
        execution_generation,analysis_run_id,deleted_at
    ) VALUES (
        gen_random_uuid(),v_user_id,'query','恢复核验临时副本',v_source.first_question,
        gen_random_uuid(),v_source.creation_operation_hash,CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP,0,0,2,NULL,NULL,0,NULL,NULL
    ) RETURNING id INTO v_history_id;

    INSERT INTO history_turns(
        id,history_id,ordinal,operation_id,operation_hash,question,request_id,
        status,runtime_epoch,execution_generation,created_at,completed_at,
        public_error,attempt_input,snapshot_version,snapshot
    ) VALUES (
        gen_random_uuid(),v_history_id,1,gen_random_uuid(),v_source.operation_hash,
        v_source.question,'restore-verification','succeeded',
        (SELECT runtime_epoch FROM history_runtime WHERE singleton),0,
        v_source.created_at,v_source.completed_at,NULL,v_source.attempt_input,
        v_source.snapshot_version,v_source.snapshot
    ) RETURNING id INTO v_turn_id;
    UPDATE history_records SET last_success_turn_id=v_turn_id WHERE id=v_history_id;

    INSERT INTO saved_results(
        id,owner_user_id,kind,title,record_revision,created_at,updated_at,
        source_history_id,source_turn_id,snapshot_version,snapshot
    ) VALUES (
        gen_random_uuid(),v_user_id,'query','恢复核验临时成果',0,
        CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,v_history_id,v_turn_id,
        v_source.snapshot_version,v_source.snapshot
    );
END $$;
""".format(  # nosec B608
        username=_sql_literal(username), password_hash=_sql_literal(password_hash)
    )
    _control_psql(sql, env=pg_environment(os.environ.get("POSTGRES_DB", "chatbi_mvp")))
    return {"status": "created", "username": username}


def cleanup_verification_identity(root, restore_id):
    operations = secure_directory(Path(root) / "operations", create=False)
    load_record(operations, restore_id)
    username = "restore_test_" + restore_id[:12]
    # The generated username is encoded as a SQL literal before interpolation.
    sql = """
DO $$
DECLARE v_user_id BIGINT;
BEGIN
    SELECT id INTO v_user_id FROM users WHERE username={username};
    IF FOUND THEN
        DELETE FROM sessions WHERE user_id=v_user_id;
        DELETE FROM saved_results WHERE owner_user_id=v_user_id;
        UPDATE history_records
           SET active_turn_id=NULL,last_success_turn_id=NULL
         WHERE owner_user_id=v_user_id;
        DELETE FROM history_executions WHERE owner_user_id=v_user_id;
        DELETE FROM history_turns
         WHERE history_id IN (SELECT id FROM history_records WHERE owner_user_id=v_user_id);
        DELETE FROM history_records WHERE owner_user_id=v_user_id;
        DELETE FROM user_roles WHERE user_id=v_user_id;
        DELETE FROM users WHERE id=v_user_id;
    END IF;
END $$;
""".format(username=_sql_literal(username))  # nosec B608
    _control_psql(sql, env=pg_environment(os.environ.get("POSTGRES_DB", "chatbi_mvp")))
    # The generated username is encoded by _sql_literal before interpolation.
    remaining = _scalar(
        "chatbi_control",
        "SELECT count(*) FROM users WHERE username={}".format(_sql_literal(username)),  # nosec B608
        env=pg_environment(os.environ.get("POSTGRES_DB", "chatbi_mvp")),
    )
    if remaining != "0":
        raise RestoreFailed("RESTORE_VERIFICATION_CLEANUP_FAILED")
    return {"status": "cleaned", "username": username}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "restore-databases", "mark-verified", "clear-payload", "temp-identity"])
    parser.add_argument("--root", default="/state")
    parser.add_argument("--backup-id")
    parser.add_argument("--restore-id", required=True)
    parser.add_argument("--host-locked", action="store_true")
    parser.add_argument("--verification-file")
    parser.add_argument("--identity-action", choices=("prepare", "cleanup"))
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        if args.action == "prepare":
            if not args.host_locked or not args.backup_id:
                raise RestoreFailed("RESTORE_LOCKED")
            with operation_lock(Path(args.root) / "operation.lock", host_locked=True):
                result = prepare_restore(args.root, args.backup_id, args.restore_id)
        elif args.action == "restore-databases":
            if not args.host_locked:
                raise RestoreFailed("RESTORE_LOCKED")
            with operation_lock(Path(args.root) / "operation.lock", host_locked=True):
                result = restore_databases(args.root, args.restore_id)
        elif args.action == "mark-verified":
            if not args.host_locked or not args.verification_file:
                raise RestoreFailed("RESTORE_LOCKED")
            verification = json.loads(secure_file(args.verification_file, maximum=4096))
            with operation_lock(Path(args.root) / "operation.lock", host_locked=True):
                result = mark_verified(args.root, args.restore_id, verification)
        elif args.action == "temp-identity":
            if not args.host_locked or args.identity_action not in {"prepare", "cleanup"}:
                raise RestoreFailed("RESTORE_LOCKED")
            with operation_lock(Path(args.root) / "operation.lock", host_locked=True):
                if args.identity_action == "prepare":
                    data = sys.stdin.buffer.read(8192)
                    if len(data) >= 8192:
                        raise RestoreFailed("RESTORE_VERIFICATION_FAILED")
                    result = create_verification_identity(args.root, args.restore_id, data)
                else:
                    result = cleanup_verification_identity(args.root, args.restore_id)
        else:
            if not args.host_locked:
                raise RestoreFailed("RESTORE_LOCKED")
            with operation_lock(Path(args.root) / "operation.lock", host_locked=True):
                result = clear_payload(args.root, args.restore_id)
        print(json.dumps({"status": "success", "result": result}, sort_keys=True))
    except (
        RestoreFailed,
        RestoreStateInvalid,
        BackupFailed,
        DatabaseBackupFailed,
        OSError,
        ValueError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        code = str(exc) if isinstance(exc, (RestoreFailed, RestoreStateInvalid, BackupFailed, DatabaseBackupFailed)) else "RESTORE_FAILED"
        print(json.dumps({"status": "failure", "failure_code": code}, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
