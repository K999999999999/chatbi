import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_devcontainer_uses_shared_compose_without_volume_deletion() -> None:
    source_lines = (
        (PROJECT_ROOT / ".devcontainer" / "devcontainer.json")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    json_lines = [line for line in source_lines if not line.lstrip().startswith("//")]
    config = json.loads("\n".join(json_lines))

    assert config["dockerComposeFile"] == "../docker-compose.yml"
    assert config["service"] == "devcontainer"
    assert config["runServices"] == ["devcontainer"]
    assert config["shutdownAction"] == "stopContainer"
    assert config["remoteEnv"]["LOCAL_WORKSPACE_FOLDER"] == "${localWorkspaceFolder}"
    assert "uv sync --locked" in config["postCreateCommand"]
    assert "down -v" not in config["postCreateCommand"]
