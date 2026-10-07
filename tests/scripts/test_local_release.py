from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
from pathlib import Path

import pytest
from langgraph.checkpoint.postgres import PostgresSaver

from scripts.local_release import (
    LocalReleaseError,
    update_deployment_state,
    validate_api_environment,
    validate_compatibility_profile,
    validate_compatibility_state,
    validate_snapshot_rows,
    wait_for_qdrant,
)
from src.rag_offline.embedding import BgeM3EmbeddingProvider
from src.rag_offline.provenance import build_provenance
from src.rag_offline.sources import load_facts


def test_local_write_command_rejects_an_active_operation_lock() -> None:
    repository = Path(__file__).resolve().parents[2]
    lock_path = repository / ".local" / "operation.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with lock_path.open("a") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run(
            [str(repository / "local"), "build"],
            capture_output=True,
            check=False,
            close_fds=True,
            env=os.environ.copy(),
            text=True,
        )

    assert result.returncode != 0
    assert "另一个稳定环境写操作正在执行" in result.stderr
    assert "需要 Docker" not in result.stderr


@pytest.fixture
def api_environment() -> dict[str, str]:
    return {
        "CHATBI_ENV": "development",
        "CHATBI_ADMIN_SECRET_KEY": "x" * 48,
        "CHATBI_LOCAL_HTTP_PORT": "8080",
        "CHATBI_WEB_ORIGIN": "http://127.0.0.1:8080",
        "CHATBI_WEB_DIST_DIR": "/opt/chatbi-web",
        "LLM_API_KEY": "test-llm-key-not-a-secret",
        "LLM_MODEL": "test-model",
        "POSTGRES_HOST": "postgres",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "chatbi_mvp",
        "POSTGRES_APP_USER": "chatbi_app",
        "POSTGRES_APP_PASSWORD": "test-business-password",
        "POSTGRES_CONTROL_DB": "chatbi_control",
        "POSTGRES_CONTROL_APP_USER": "chatbi_control_user",
        "POSTGRES_CONTROL_APP_PASSWORD": "test-control-password",
        "RAG_ONLINE_RETRIEVAL_ENABLED": "true",
        "RAG_QDRANT_URL": "http://qdrant:6333",
        "RAG_QDRANT_API_KEY": "test-qdrant-key-not-a-secret",
        "RAG_MODEL_DIR": "/opt/chatbi-model/bge-m3-5617a9f61b02",
        "RAG_OUTPUT_DIR": "/opt/chatbi-rag",
        "RAG_EMBEDDING_DEVICE": "cpu",
        "RAG_EMBEDDING_USE_FP16": "false",
    }


def test_accepts_isolated_cpu_local_runtime(api_environment: dict[str, str]) -> None:
    validate_api_environment(api_environment)


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("CHATBI_ENV", "production", "CHATBI_ENV"),
        ("CHATBI_ADMIN_SECRET_KEY", "short", "CHATBI_ADMIN_SECRET_KEY"),
        ("CHATBI_WEB_ORIGIN", "https://chatbi.example", "CHATBI_WEB_ORIGIN"),
        ("LLM_API_KEY", "replace-me", "LLM_API_KEY"),
        ("LLM_MODEL", "", "LLM_MODEL"),
        ("POSTGRES_HOST", "127.0.0.1", "POSTGRES_HOST"),
        ("POSTGRES_PORT", "5433", "POSTGRES_PORT"),
        ("RAG_ONLINE_RETRIEVAL_ENABLED", "false", "RAG_ONLINE_RETRIEVAL_ENABLED"),
        ("RAG_EMBEDDING_DEVICE", "auto", "RAG_EMBEDDING_DEVICE"),
        ("RAG_EMBEDDING_USE_FP16", "true", "RAG_EMBEDDING_USE_FP16"),
    ],
)
def test_rejects_runtime_that_crosses_local_release_boundary(
    api_environment: dict[str, str], key: str, value: str, message: str
) -> None:
    api_environment[key] = value

    with pytest.raises(LocalReleaseError, match=message):
        validate_api_environment(api_environment)


def test_rejects_static_identity_and_migration_credentials(
    api_environment: dict[str, str],
) -> None:
    api_environment["CHATBI_IDENTITY_PROVIDER"] = "demo"
    api_environment["POSTGRES_MIGRATOR_PASSWORD"] = "must-not-reach-api"

    with pytest.raises(LocalReleaseError, match="CHATBI_IDENTITY_PROVIDER"):
        validate_api_environment(api_environment)


def test_diagnostic_never_echoes_secret(api_environment: dict[str, str]) -> None:
    secret = api_environment["LLM_API_KEY"]
    api_environment["CHATBI_ENV"] = "invalid"

    with pytest.raises(LocalReleaseError) as error:
        validate_api_environment(api_environment)

    assert secret not in str(error.value)


@pytest.fixture
def compatibility_profile() -> dict:
    return {
        "format": 1,
        "compatibility_id": "chatbi-local-v1",
        "control_migrations": {
            "required": ["chatbi-control-v1", "chatbi-control-v2"],
            "allowed": ["chatbi-control-v1", "chatbi-control-v2"],
        },
        "checkpoint_migrations": {"required": [0, 1], "allowed": [0, 1]},
        "business_seed_versions": ["chatbi-sales-mart-dev-v3"],
        "business_catalog_schema_metadata_sha256": "1" * 64,
        "history_snapshot_versions": [1],
        "rag_pointer_schema_versions": [1],
        "rag_manifest_schema_versions": [1],
        "rag_model_revision": "5617a9f61b028005a4858fdac845db406aefb181",
        "rag_embedding_dimension": 1024,
        "rag_provenance": {
            "schema_metadata_sha256": "1" * 64,
            "metrics_sha256": "2" * 64,
            "embedding_config_sha256": "3" * 64,
            "source_sha256": "4" * 64,
        },
    }


@pytest.fixture
def compatible_state() -> dict:
    return {
        "control_migrations": ["chatbi-control-v1", "chatbi-control-v2"],
        "checkpoint_migrations": [0, 1],
        "business_seed_version": "chatbi-sales-mart-dev-v3",
        "catalog_verified": True,
        "catalog_schema_metadata_sha256": "1" * 64,
        "history_snapshot_versions": [1],
        "rag_pointer_schema_version": 1,
        "rag_manifest_schema_version": 1,
        "rag_model_revision": "5617a9f61b028005a4858fdac845db406aefb181",
        "rag_embedding_dimension": 1024,
        "rag_provenance_verified": True,
        "rag_provenance": {
            "schema_metadata_sha256": "1" * 64,
            "metrics_sha256": "2" * 64,
            "embedding_config_sha256": "3" * 64,
            "source_sha256": "4" * 64,
        },
    }


def test_accepts_only_fully_declared_compatible_state(
    compatibility_profile: dict, compatible_state: dict
) -> None:
    validate_compatibility_profile(compatibility_profile)
    validate_compatibility_state(compatibility_profile, compatible_state)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("control_migrations", ["chatbi-control-v1", "chatbi-control-v2", "unknown"], "control migration"),
        ("checkpoint_migrations", [0, 1, 2], "checkpoint migration"),
        ("business_seed_version", "unknown-seed", "Sales Mart Seed"),
        ("catalog_verified", False, "catalog"),
        ("catalog_schema_metadata_sha256", "f" * 64, "business catalog"),
        ("history_snapshot_versions", [1, 2], "snapshot"),
        ("rag_pointer_schema_version", 2, "RAG current pointer"),
        ("rag_manifest_schema_version", 2, "RAG manifest"),
        ("rag_model_revision", "other-model", "Embedding model"),
        ("rag_provenance_verified", False, "RAG provenance"),
        (
            "rag_provenance",
            {"schema_metadata_sha256": "f" * 64},
            "RAG provenance",
        ),
    ],
)
def test_rejects_unknown_or_unverified_compatibility_state(
    compatibility_profile: dict,
    compatible_state: dict,
    field: str,
    value: object,
    message: str,
) -> None:
    compatible_state[field] = value

    with pytest.raises(LocalReleaseError, match=message):
        validate_compatibility_state(compatibility_profile, compatible_state)


def test_rejects_incomplete_compatibility_declaration(compatibility_profile: dict) -> None:
    compatibility_profile["control_migrations"]["allowed"].pop()

    with pytest.raises(LocalReleaseError, match="required control migrations"):
        validate_compatibility_profile(compatibility_profile)


def test_rejects_missing_required_migration(
    compatibility_profile: dict, compatible_state: dict
) -> None:
    compatible_state["control_migrations"].pop()

    with pytest.raises(LocalReleaseError, match="required migrations"):
        validate_compatibility_state(compatibility_profile, compatible_state)


@pytest.mark.parametrize("row", [(1, None), (1, "2"), (1, "v1"), (True, "1")])
def test_rejects_snapshot_column_and_payload_version_mismatch(row: tuple) -> None:
    with pytest.raises(LocalReleaseError, match="snapshot version"):
        validate_snapshot_rows([row])


def test_collects_versions_from_persisted_snapshot_envelopes() -> None:
    assert validate_snapshot_rows([(1, "1"), (1, "1"), (2, "2")]) == [1, 2]


def test_image_compatibility_declaration_matches_repository_contracts() -> None:
    repository = Path(__file__).resolve().parents[2]
    profile = json.loads(
        (repository / "scripts" / "local_compatibility.json").read_text(
            encoding="utf-8"
        )
    )
    validate_compatibility_profile(profile)

    migration_markers = sorted(
        set(
            re.findall(
                r"chatbi-control-v[0-9]+",
                "\n".join(
                    path.read_text(encoding="utf-8")
                    for path in sorted((repository / "database" / "control").glob("*.sql"))
                ),
            )
        )
    )
    assert profile["control_migrations"]["required"] == migration_markers
    assert profile["control_migrations"]["allowed"] == migration_markers
    checkpoint_migrations = list(range(len(PostgresSaver.MIGRATIONS)))
    assert profile["checkpoint_migrations"]["required"] == checkpoint_migrations
    assert profile["checkpoint_migrations"]["allowed"] == checkpoint_migrations

    seed_sql = (repository / "database" / "dev" / "seed_sales_mart.sql").read_text(
        encoding="utf-8"
    )
    seed_version = re.search(r"Seed 版本：([^\s]+)", seed_sql)
    assert seed_version is not None
    assert profile["business_seed_versions"] == [seed_version.group(1)]
    assert profile["history_snapshot_versions"] == [1]
    assert profile["rag_pointer_schema_versions"] == [1]
    assert profile["rag_manifest_schema_versions"] == [1]

    embedding = BgeM3EmbeddingProvider(
        "/opt/chatbi-model/bge-m3-5617a9f61b02",
        batch_size=8,
        use_fp16=False,
        devices="cpu",
    )
    provenance = build_provenance(load_facts(), embedding.config)
    assert profile["business_catalog_schema_metadata_sha256"] == provenance[
        "schema_metadata_sha256"
    ]
    assert profile["rag_provenance"] == provenance


def test_failed_upgrade_preserves_last_successful_release(tmp_path: Path) -> None:
    state_path = tmp_path / "deployment-state.json"
    previous_release = {
        "source_commit": "a" * 40,
        "api_image": "chatbi-local-api:old",
        "api_image_id": "sha256:" + "1" * 64,
        "database_runtime_image": "chatbi-local-postgres:old",
        "database_runtime_image_id": "sha256:" + "2" * 64,
    }
    update_deployment_state(
        state_path,
        event="begin",
        operation="upgrade",
        target_commit="b" * 40,
        phase="stopping-api",
        runtime_status="transitioning",
        baseline_active_release=previous_release,
    )
    update_deployment_state(
        state_path,
        event="failed",
        operation="upgrade",
        target_commit="b" * 40,
        phase="migrating",
        runtime_status="stopped",
    )

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["active_release"] == previous_release
    assert state["runtime_status"] == "stopped"
    assert state["last_operation"]["phase"] == "migrating"
    assert state["last_operation"]["result"] == "failed"
    assert state_path.stat().st_mode & 0o777 == 0o600


def test_successful_upgrade_atomically_selects_the_new_release(tmp_path: Path) -> None:
    state_path = tmp_path / "deployment-state.json"
    previous_release = {
        "source_commit": "a" * 40,
        "api_image": "chatbi-local-api:old",
        "api_image_id": "sha256:" + "1" * 64,
        "database_runtime_image": "chatbi-local-postgres:stable",
        "database_runtime_image_id": "sha256:" + "2" * 64,
    }
    release = {
        "source_commit": "c" * 40,
        "api_image": "chatbi-local-api:new",
        "api_image_id": "sha256:" + "4" * 64,
        "database_runtime_image": "chatbi-local-postgres:new",
        "database_runtime_image_id": "sha256:" + "5" * 64,
    }
    update_deployment_state(
        state_path,
        event="begin",
        operation="upgrade",
        target_commit="c" * 40,
        phase="stopping-api",
        runtime_status="transitioning",
        baseline_active_release=previous_release,
    )

    update_deployment_state(
        state_path,
        event="succeeded",
        operation="upgrade",
        target_commit="c" * 40,
        phase="running",
        runtime_status="running",
        active_release=release,
    )

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["active_release"] == release
    assert state["runtime_status"] == "running"
    assert state["last_operation"]["result"] == "succeeded"


@pytest.mark.parametrize(
    "url",
    [
        "http://[invalid-ipv6",
        "http://qdrant:65536",
        "http://qdrant",
        "http://other:6333",
        "http://qdrant:6333/private-path",
        "http://user:password@qdrant:6333",
    ],
)
def test_qdrant_wait_rejects_malformed_or_credentialed_urls(url: str) -> None:
    with pytest.raises(LocalReleaseError, match="RAG_QDRANT_URL"):
        wait_for_qdrant({"RAG_QDRANT_URL": url})
