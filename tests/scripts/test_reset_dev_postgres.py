import pytest

from scripts.reset_dev_postgres import (
    PostgresResetError,
    _configured_volume,
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
            volume_name="chatbi-engine_postgres_data",
        )


def test_reset_refuses_qdrant_or_other_volume_label() -> None:
    with pytest.raises(PostgresResetError, match="postgres_data"):
        _validate_volume_labels(
            {
                "com.docker.compose.project": "chatbi-engine",
                "com.docker.compose.volume": "qdrant_data",
            },
            project_name="chatbi-engine",
            volume_name="chatbi-engine_qdrant_data",
        )
