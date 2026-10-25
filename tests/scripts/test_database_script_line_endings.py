from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_postgres_init_scripts_are_kept_as_lf_for_linux_containers() -> None:
    attributes = (PROJECT_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "database/init/*.sh text eol=lf" in attributes

    for path in sorted((PROJECT_ROOT / "database" / "init").glob("*.sh")):
        assert b"\r\n" not in path.read_bytes(), path.name
