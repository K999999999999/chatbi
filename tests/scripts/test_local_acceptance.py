from __future__ import annotations

import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from scripts.local_acceptance import (
    LocalAcceptanceError,
    acceptance_volume_names,
    clean_compose_environment,
    parse_env_text,
    project_name,
    render_compose_override,
    write_acceptance_env_files,
)

RUN_ID = "20261008T021500Z-a1b2c3d4"


def isolated_api_metadata():
    return {
        "Config": {"Env": ["POSTGRES_APP_USER=chatbi_app"]},
        "Mounts": [
            {
                "Destination": "/opt/chatbi-model/bge-m3-5617a9f61b02",
                "RW": False,
                "Type": "bind",
            },
            {"Destination": "/opt/chatbi-rag", "RW": False, "Type": "bind"},
            {"Destination": "/opt/chatbi-runtime", "RW": True, "Type": "bind"},
        ],
    }


def test_api_isolation_allows_only_the_approved_runtime_write_directory():
    from scripts.verify_local_deployment import validate_api_isolation

    validate_api_isolation(isolated_api_metadata())


@pytest.mark.parametrize(
    "corruption", ["migrator", "writable_assets", "extra_mount", "foreign_destination"]
)
def test_api_isolation_still_rejects_privileged_credentials_and_foreign_writes(
    corruption,
):
    from scripts.verify_local_deployment import validate_api_isolation

    item = isolated_api_metadata()
    if corruption == "migrator":
        item["Config"]["Env"].append("POSTGRES_MIGRATOR_PASSWORD=synthetic")
    elif corruption == "writable_assets":
        item["Mounts"][0]["RW"] = True
    elif corruption == "extra_mount":
        item["Mounts"].append({"Destination": "/workspace", "RW": True, "Type": "bind"})
    else:
        item["Mounts"][2]["Destination"] = "/foreign"
    with pytest.raises(LocalAcceptanceError, match="隔离检查失败"):
        validate_api_isolation(item)


@pytest.fixture
def readiness_server():
    responses = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status, payload = responses.pop(0) if len(responses) > 1 else responses[0]
            self.send_response(status)
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port, responses
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_acceptance_waits_for_ready_before_allowing_business(
    tmp_path, readiness_server
):
    from scripts.verify_local_deployment import Acceptance

    port, responses = readiness_server
    responses.extend(
        [
            (503, b'{"status":"unknown"}'),
            (503, b'{"status":"not_ready"}'),
            (200, b'{"status":"ready"}'),
        ]
    )
    acceptance = Acceptance(tmp_path, "a" * 40)
    acceptance.port = port
    acceptance.report.mkdir(parents=True)
    acceptance.wait_ready("startup", timeout=1, interval=0.01)
    evidence = json.loads((acceptance.report / "readiness-startup.json").read_text())
    assert evidence["status"] == "ready"
    assert [item["state"] for item in evidence["samples"]] == [
        "unknown",
        "not_ready",
        "ready",
    ]


@pytest.mark.parametrize(
    "status,payload",
    [
        (503, b'{"status":"ready","private":"synthetic-sensitive"}'),
        (200, b'{"status":"not_ready"}'),
        (200, b"synthetic-sensitive-invalid-json"),
        (200, b'{"status":[]}'),
    ],
)
def test_acceptance_does_not_confuse_liveness_or_invalid_reply_with_readiness(
    tmp_path, readiness_server, status, payload
):
    from scripts.verify_local_deployment import Acceptance

    port, responses = readiness_server
    responses.append((status, payload))
    acceptance = Acceptance(tmp_path, "a" * 40)
    acceptance.port = port
    acceptance.report.mkdir(parents=True)
    with pytest.raises(LocalAcceptanceError, match="就绪"):
        acceptance.wait_ready("restart", timeout=0.05, interval=0.01)
    report = (acceptance.report / "readiness-restart.json").read_text()
    assert json.loads(report)["status"] == "timeout"
    assert "synthetic-sensitive" not in report


@pytest.mark.parametrize(
    "path", ["relative.exe", "C:relative.exe", "C:\\browser.txt", "C:\\browser.exe\n"]
)
def test_acceptance_refuses_invalid_windows_browser_before_creating_resources(
    tmp_path, monkeypatch, path
):
    from scripts.verify_local_deployment import Acceptance

    monkeypatch.setenv("CHATBI_ACCEPTANCE_BROWSER_EXECUTABLE", path)
    with pytest.raises(LocalAcceptanceError, match="Windows 绝对 EXE"):
        Acceptance(tmp_path, "a" * 40)
    assert not (tmp_path / ".local").exists()


def test_acceptance_resources_have_run_scoped_nonstable_identity() -> None:
    assert project_name(RUN_ID) == f"chatbi-r6-accept-{RUN_ID.lower()}"
    assert acceptance_volume_names(RUN_ID) == (
        f"chatbi_r6_accept_{RUN_ID.replace('-', '_')}_postgres_data",
        f"chatbi_r6_accept_{RUN_ID.replace('-', '_')}_qdrant_data",
    )

    with pytest.raises(LocalAcceptanceError, match="run ID"):
        project_name("chatbi-stable")


def test_acceptance_cloud_trace_is_explicit_and_uses_only_selected_credentials(
    tmp_path,
):
    config_path, secret_path = write_acceptance_env_files(
        tmp_path,
        local_values={
            "LLM_API_KEY": "synthetic-llm",
            "CHATBI_OBSERVABILITY_ENABLED": "true",
            "CHATBI_TRACE_CONTENT_ENABLED": "true",
            "OTEL_SERVICE_NAME": "chatbi",
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "https://collector.example/v1/traces",
        },
        trace_headers="x-arms-license-key=synthetic-license",
        port=18432,
        uid=1000,
        gid=1000,
    )
    config = parse_env_text(config_path.read_text())
    private = parse_env_text(secret_path.read_text())
    assert config["CHATBI_OBSERVABILITY_ENABLED"] == "true"
    assert config["CHATBI_TRACE_CONTENT_ENABLED"] == "false"
    assert config["OTEL_SERVICE_NAME"] == "chatbi"
    assert (
        config["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"]
        == "https://collector.example/v1/traces"
    )
    assert (
        private["OTEL_EXPORTER_OTLP_HEADERS"] == "x-arms-license-key=synthetic-license"
    )
    assert "synthetic-license" not in config_path.read_text()
    assert private["POSTGRES_APP_PASSWORD"] != "synthetic-license"


def test_acceptance_cloud_trace_stays_off_without_explicit_header_input(tmp_path):
    config_path, secret_path = write_acceptance_env_files(
        tmp_path,
        local_values={
            "LLM_API_KEY": "synthetic-llm",
            "CHATBI_OBSERVABILITY_ENABLED": "true",
            "OTEL_EXPORTER_OTLP_HEADERS": "x-arms-license-key=must-not-copy",
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "https://collector.example/v1/traces",
        },
        port=18432,
        uid=1000,
        gid=1000,
    )
    config = parse_env_text(config_path.read_text())
    assert config.get("CHATBI_OBSERVABILITY_ENABLED", "false") == "false"
    assert "must-not-copy" not in secret_path.read_text()


def test_local_env_parser_preserves_secret_delimiters_without_shell_execution() -> None:
    parsed = parse_env_text(
        "# ignored\nLLM_API_KEY='part one=part two'\nLLM_MODEL=demo\n"
    )

    assert parsed == {"LLM_API_KEY": "part one=part two", "LLM_MODEL": "demo"}


def test_acceptance_cloud_trace_requires_private_source_credentials(
    tmp_path, monkeypatch
):
    from scripts.local_acceptance import prepare

    config = tmp_path / ".env.local"
    config.write_text("LLM_API_KEY=synthetic-llm\n")
    config.chmod(0o600)
    secret = tmp_path / ".env.local.secrets"
    secret.write_text("OTEL_EXPORTER_OTLP_HEADERS=x-arms-license-key=synthetic\n")
    secret.chmod(0o644)
    monkeypatch.setenv("CHATBI_ACCEPTANCE_TRACE_ENABLED", "1")
    with pytest.raises(LocalAcceptanceError, match="secrets 权限过宽"):
        prepare(tmp_path, tmp_path / "work", RUN_ID, 18432)
    assert not (tmp_path / "work" / "acceptance.secrets.env").exists()


def test_local_env_parser_rejects_ambiguous_duplicate_keys() -> None:
    with pytest.raises(LocalAcceptanceError, match="重复配置项"):
        parse_env_text("LLM_MODEL=first\nLLM_MODEL=second\n")


def test_compose_override_binds_only_run_scoped_acceptance_paths(
    tmp_path: Path,
) -> None:
    rendered = render_compose_override(
        run_id=RUN_ID,
        port=18432,
        model_dir=tmp_path / "model",
        rag_dir=tmp_path / "work" / "rag",
        state_dir=tmp_path / "work" / "state",
        report_dir=tmp_path / "work" / "report",
        tests_dir=tmp_path / "repo" / "tests",
    )

    assert "chatbi-stable" not in rendered
    assert "chatbi_stable_postgres_data" not in rendered
    assert "18432" in rendered
    assert str(tmp_path / "work" / "rag") in rendered
    assert str(tmp_path / "work" / "state") in rendered
    assert str(tmp_path / "work" / "report") in rendered
    assert "com.chatbi.acceptance.run_id" in rendered


def test_compose_subprocess_drops_inherited_project_and_runtime_settings() -> None:
    cleaned = clean_compose_environment(
        {
            "PATH": "/usr/bin",
            "HOME": "/home/user",
            "COMPOSE_PROJECT_NAME": "chatbi-stable",
            "CHATBI_LOCAL_HTTP_PORT": "8080",
            "POSTGRES_PASSWORD": "must-not-win",
            "LLM_API_KEY": "must-not-leak",
            "OTEL_EXPORTER_OTLP_HEADERS": "must-not-copy",
            "DOCKER_HOST": "unix:///var/run/docker.sock",
        }
    )

    assert cleaned == {
        "PATH": "/usr/bin",
        "HOME": "/home/user",
        "DOCKER_HOST": "unix:///var/run/docker.sock",
    }


def test_temporary_compose_credentials_are_private_and_do_not_copy_stable_secrets(
    tmp_path: Path,
) -> None:
    config_path, secret_path = write_acceptance_env_files(
        tmp_path,
        local_values={
            "CHATBI_LOCAL_MODEL_DIR": ".model-cache/bge-m3-5617a9f61b02",
            "POSTGRES_DB": "chatbi_mvp",
            "POSTGRES_MIGRATOR_USER": "chatbi_migrator",
            "LLM_API_KEY": "acceptance-key=only",
            "LLM_BASE_URL": "https://llm.example/v1",
            "LLM_MODEL": "demo-model",
        },
        port=18432,
        uid=1000,
        gid=1000,
        repository=tmp_path,
    )

    config = config_path.read_text()
    secrets = secret_path.read_text()
    assert "LLM_API_KEY='acceptance-key=only'" in config
    assert "POSTGRES_APP_PASSWORD" not in config
    assert "stable-secret" not in secrets
    assert "POSTGRES_APP_PASSWORD=" in secrets
    assert "CHATBI_ADMIN_SECRET_KEY=" in secrets
    assert "QDRANT_API_KEY=" in secrets
    assert os.stat(config_path).st_mode & 0o777 == 0o600
    assert os.stat(secret_path).st_mode & 0o777 == 0o600


def test_docker_compose_resolves_isolation_without_starting_resources(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    config, private = write_acceptance_env_files(
        tmp_path,
        local_values={"LLM_API_KEY": "synthetic=literal\\backslash'quote"},
        port=18432,
        uid=1000,
        gid=1000,
        repository=root,
    )
    release = tmp_path / "release.env"
    release.write_text(
        "CHATBI_API_IMAGE=chatbi-local-api:test\n"
        "CHATBI_DATABASE_IMAGE=chatbi-local-postgres:test\n"
        "CHATBI_SOURCE_COMMIT=" + "a" * 40 + "\n"
    )
    runtime_dir = tmp_path / "state"
    override = tmp_path / "compose.yml"
    override.write_text(
        render_compose_override(
            run_id=RUN_ID,
            port=18432,
            model_dir=tmp_path / "model",
            rag_dir=tmp_path / "rag",
            state_dir=runtime_dir,
            report_dir=tmp_path / "report",
            tests_dir=root / "tests",
        )
    )
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-name",
            project_name(RUN_ID),
            "--env-file",
            str(config),
            "--env-file",
            str(private),
            "--env-file",
            str(release),
            "-f",
            str(root / "docker-compose.local.yml"),
            "-f",
            str(override),
            "config",
            "--format",
            "json",
        ],
        env=clean_compose_environment(dict(os.environ)),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, "隔离 Compose 必须能解析；诊断不回显环境值"
    resolved = json.loads(result.stdout)
    assert (
        resolved["services"]["api"]["environment"]["LLM_API_KEY"]
        == "synthetic=literal\\backslash'quote"
    )
    assert (
        resolved["volumes"]["postgres_data"]["name"]
        == acceptance_volume_names(RUN_ID)[0]
    )
    assert (
        resolved["services"]["api"]["labels"]["com.chatbi.environment"] == "acceptance"
    )
    api_mounts = {
        volume["target"]: volume for volume in resolved["services"]["api"]["volumes"]
    }
    assert set(api_mounts) == {
        "/opt/chatbi-model/bge-m3-5617a9f61b02",
        "/opt/chatbi-rag",
        "/opt/chatbi-runtime",
    }
    assert api_mounts["/opt/chatbi-runtime"]["source"] == str(runtime_dir)
    assert api_mounts["/opt/chatbi-runtime"].get("read_only", False) is False
    assert all(
        api_mounts[target]["read_only"]
        for target in ("/opt/chatbi-model/bge-m3-5617a9f61b02", "/opt/chatbi-rag")
    )
    assert resolved["services"]["api"]["ports"][0]["host_ip"] == "127.0.0.1"
    assert resolved["services"]["api"]["security_opt"] == [
        f"seccomp={root}/docker/third-party/playwright-seccomp-profile.json"
    ]


@pytest.mark.parametrize(
    "field",
    [
        "com.docker.compose.project",
        "com.chatbi.acceptance.run_id",
        "com.chatbi.environment",
    ],
)
def test_container_operation_refuses_mismatched_identity(tmp_path, monkeypatch, field):
    from scripts.verify_local_deployment import Acceptance

    acceptance = Acceptance(tmp_path, "a" * 40)
    labels = {
        "com.docker.compose.project": acceptance.project,
        "com.chatbi.acceptance.run_id": acceptance.run_id,
        "com.chatbi.environment": "acceptance",
    }
    labels[field] = "another-project"

    def inspected(*args, **kwargs):
        return subprocess.CompletedProcess(
            args, 0, json.dumps([{"Config": {"Labels": labels}}]), ""
        )

    monkeypatch.setattr(acceptance, "run", inspected)
    with pytest.raises(LocalAcceptanceError, match="容器归属不一致"):
        acceptance.assert_container("candidate-container")
