from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts.reset_dev_postgres import (
    PostgresResetError,
    _configured_volume,
    _initialize_postgres,
    _validate_volume_labels,
)


def test_configured_volume_uses_compose_project_scope() -> None:
    project_name, volume_name = _configured_volume(
        {
            "name": "chatbi-engine",
            "volumes": {
                "postgres_data": {"name": "chatbi-engine_postgres_data"},
                "qdrant_data": {"name": "chatbi-engine_qdrant_data"},
            },
        }
    )

    assert project_name == "chatbi-engine"
    assert volume_name == "chatbi-engine_postgres_data"


def test_reset_refuses_external_postgres_volume() -> None:
    with pytest.raises(PostgresResetError, match="external"):
        _configured_volume(
            {
                "name": "chatbi-engine",
                "volumes": {"postgres_data": {"external": True, "name": "shared"}},
            }
        )


def test_reset_refuses_volume_owned_by_another_project() -> None:
    with pytest.raises(PostgresResetError, match="another Compose project"):
        _validate_volume_labels(
            {
                "com.docker.compose.project": "another-project",
                "com.docker.compose.volume": "postgres_data",
            },
            project_name="chatbi-engine",
            volume_name="chatbi-engine_qdrant_data",
        )


def test_reset_refuses_qdrant_or_other_volume_label() -> None:
    with pytest.raises(PostgresResetError, match="postgres_data"):
        _validate_volume_labels(
            {
                "com.docker.compose.project": "chatbi-engine",
                "com.docker.compose.volume": "qdrant_data",
            },
            project_name="chatbi-engine",
            volume_name="chatbi-engine_postgres_data",
        )


def test_postgres_reset_initializes_migrations_before_waiting_for_health(
    tmp_path,
) -> None:
    results = [SimpleNamespace(returncode=0) for _ in range(3)]
    with patch("scripts.reset_dev_postgres.subprocess.run", side_effect=results) as run:
        _initialize_postgres(tmp_path)

    commands = [call.args[0] for call in run.call_args_list]
    assert commands[0][:5] == ["docker", "compose", "exec", "-T", "postgres"]
    assert commands[0][-1] == "/workspace/database/init/wait_for_base_initialization.sh"
    assert commands[1][-2:] == ["src.chatbi_control", "migrate"]
    assert commands[2] == ["docker", "compose", "up", "--detach", "--wait", "postgres"]


def test_postgres_reset_stops_when_control_migration_fails(tmp_path) -> None:
    results = [SimpleNamespace(returncode=0), SimpleNamespace(returncode=1)]
    with patch("scripts.reset_dev_postgres.subprocess.run", side_effect=results) as run:
        with pytest.raises(PostgresResetError, match="migration"):
            _initialize_postgres(tmp_path)

    assert run.call_count == 2
