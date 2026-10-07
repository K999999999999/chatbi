from __future__ import annotations

import fcntl
import os
import subprocess
from pathlib import Path

import pytest

from scripts.local_release import (
    LocalReleaseError,
    validate_api_environment,
    wait_for_qdrant,
)


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
