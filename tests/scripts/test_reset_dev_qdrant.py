import pytest

from scripts.compose_volume_reset import ComposeVolumeResetError
from scripts.reset_dev_qdrant import (
    _configured_volume,
    _validate_volume_labels,
)


def test_qdrant_reset_uses_only_the_current_projects_volume() -> None:
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
    assert volume_name == "chatbi-engine_qdrant_data"


def test_qdrant_reset_refuses_a_postgres_volume_label() -> None:
    with pytest.raises(ComposeVolumeResetError, match="qdrant_data"):
        _validate_volume_labels(
            {
                "com.docker.compose.project": "chatbi-engine",
                "com.docker.compose.volume": "postgres_data",
            },
            project_name="chatbi-engine",
        )


def test_qdrant_reset_refuses_a_different_compose_project() -> None:
    with pytest.raises(ComposeVolumeResetError, match="another Compose project"):
        _validate_volume_labels(
            {
                "com.docker.compose.project": "other-project",
                "com.docker.compose.volume": "qdrant_data",
            },
            project_name="chatbi-engine",
        )
