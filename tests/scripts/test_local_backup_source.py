import json

import pytest

from scripts.local_backup import BackupFailed
from scripts.local_backup_source import capture


def raw_source(tmp_path):
    raw = tmp_path / "capture"
    raw.mkdir(mode=0o700)
    source = "a" * 40

    def container(service):
        return {
            "State": {"Running": True},
            "Image": "sha256:" + "b" * 64,
            "Config": {
                "Image": "chatbi-local-" + service + ":old",
                "Env": ["LLM_MODEL=old-model", "LLM_API_KEY=private-fixture"],
                "Labels": {
                    "com.docker.compose.project": "chatbi-stable",
                    "com.docker.compose.service": service,
                    "org.opencontainers.image.revision": source,
                },
            },
        }

    files = {
        "api.json": json.dumps(container("api")),
        "postgres.json": json.dumps(container("postgres")),
        "capabilities.json": json.dumps({"operations_status": False}),
        "release.json": json.dumps({"format": 1, "source_commit": source}),
        "config.env": "LLM_MODEL=old-model\n",
        "secrets.env": "LLM_API_KEY=private-fixture\n",
        "rag-current.json": json.dumps({"manifest_path": "build/manifest.json"}),
        "rag-manifest.json": json.dumps({"status": "READY"}),
        "compatibility.json": '{"format":1}',
    }
    for name, data in files.items():
        (raw / name).write_text(data)
        (raw / name).chmod(0o600)
    return raw


def test_tool_captures_actual_old_source_without_latest_pointer(tmp_path):
    raw = raw_source(tmp_path)
    (tmp_path / "release.env").write_text("CHATBI_SOURCE_COMMIT=" + "f" * 40 + "\n")
    target = tmp_path / "source"
    identity = capture(raw, target)
    assert identity["source_commit"] == "a" * 40
    assert identity["live_required"] is False
    assert "private-fixture" not in json.dumps(identity)
    assert "CHATBI_SOURCE_COMMIT=" + "a" * 40 in (target / "release.env").read_text()
    assert (target / "secrets.env").read_text() == "LLM_API_KEY=private-fixture\n"
    assert (target / "secrets.env").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "corruption",
    [
        "foreign_project",
        "stopped_api",
        "release_mismatch",
        "config_drift",
        "unsafe_rag_path",
    ],
)
def test_source_failure_never_publishes_identity(tmp_path, corruption):
    raw = raw_source(tmp_path)
    if corruption in {"foreign_project", "stopped_api"}:
        value = json.loads((raw / "api.json").read_bytes())
        if corruption == "foreign_project":
            value["Config"]["Labels"]["com.docker.compose.project"] = "other"
        else:
            value["State"]["Running"] = False
        (raw / "api.json").write_text(json.dumps(value))
    elif corruption == "release_mismatch":
        (raw / "release.json").write_text(json.dumps({"source_commit": "c" * 40}))
    elif corruption == "config_drift":
        (raw / "config.env").write_text("LLM_MODEL=new-model\n")
    else:
        (raw / "rag-current.json").write_text(
            json.dumps({"manifest_path": "../manifest.json"})
        )
    target = tmp_path / "source"
    with pytest.raises(BackupFailed, match="BACKUP_SOURCE_CHANGED"):
        capture(raw, target)
    assert not (target / "identity.json").exists()


def test_legacy_capability_uses_actual_image_not_new_compose_environment(tmp_path):
    raw = raw_source(tmp_path)
    api = json.loads((raw / "api.json").read_bytes())
    api["Config"]["Env"].append(
        "CHATBI_OPERATIONS_SOCKET_PATH=/opt/chatbi-runtime/status.sock"
    )
    (raw / "api.json").write_text(json.dumps(api))
    assert capture(raw, tmp_path / "legacy")["live_required"] is False
    (raw / "capabilities.json").write_text(json.dumps({"operations_status": True}))
    assert capture(raw, tmp_path / "current")["live_required"] is True


def test_source_accepts_quoted_config_without_changing_encrypted_source_bytes(tmp_path):
    raw = raw_source(tmp_path)
    (raw / "config.env").write_text("LLM_MODEL='old-model'\n")
    (raw / "secrets.env").write_text('LLM_API_KEY="private-fixture"\n')
    target = tmp_path / "source"
    identity = capture(raw, target)
    assert identity["source_commit"] == "a" * 40
    assert (target / "config.env").read_text() == "LLM_MODEL='old-model'\n"
    assert (target / "secrets.env").read_text() == 'LLM_API_KEY="private-fixture"\n'


def test_interrupted_source_update_has_no_published_identity(tmp_path, monkeypatch):
    import os

    from scripts import local_backup_source

    raw = raw_source(tmp_path)
    target = tmp_path / "source"
    capture(raw, target)
    (raw / "rag-manifest.json").write_text('{"status":"READY","new":true}')
    replace = os.replace

    def interrupt(source, destination):
        if str(destination).endswith("rag-manifest.json"):
            raise OSError("injected disk failure")
        return replace(source, destination)

    monkeypatch.setattr(local_backup_source.os, "replace", interrupt)
    with pytest.raises(OSError):
        capture(raw, target)
    assert not (target / "identity.json").exists()
    assert not list(target.glob(".pending-*"))
