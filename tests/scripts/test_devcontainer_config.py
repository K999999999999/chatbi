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


def test_postgres_init_scripts_are_kept_as_lf_for_linux_containers() -> None:
    attributes = (PROJECT_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "database/init/*.sh text eol=lf" in attributes

    for path in sorted((PROJECT_ROOT / "database" / "init").glob("*.sh")):
        assert b"\r\n" not in path.read_bytes(), path.name
