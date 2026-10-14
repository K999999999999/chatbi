"""开发入口的错误传播与资源边界，不启动真实 Docker。"""

import json
import os
import subprocess
import socket
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("args", [["help"], ["app", "--help"]])
def test_classified_help_requires_neither_config_nor_docker(args):
    result = invoke(args, {"PATH": "/usr/bin:/bin", "CHATBI_DEV_ENV_FILE": "/missing"})
    assert result.returncode == 0
    assert "环境管理" in result.stdout
    assert "recover-admin" in result.stdout


@pytest.mark.parametrize("command", ["build", "infra", "migrate", "down", "status"])
def test_app_commands_select_only_standard_compose(command, docker_fake):
    result = invoke(
        ["app", command],
        {**docker_fake, "CHATBI_APP_ENV_FILE": docker_fake["CHATBI_DEV_ENV_FILE"]},
    )
    assert result.returncode == 0, result.stderr
    calls = [
        json.loads(line)
        for line in Path(docker_fake["DOCKER_CALLS"]).read_text().splitlines()
    ]
    assert calls
    assert all(str(ROOT / "docker-compose.app.yml") in call for call in calls)
    assert all(str(ROOT / "docker-compose.dev.yml") not in call for call in calls)
    if command == "down":
        assert calls[-1][-4:] == ["stop", "api", "postgres", "qdrant"]


@pytest.mark.parametrize(
    "args",
    [
        ["app", "erase"],
        ["app", "down", "extra"],
        ["up", "extra"],
        ["test", "all", "extra"],
    ],
)
def test_extra_or_unknown_arguments_are_rejected_before_resources(args, docker_fake):
    result = invoke(args, docker_fake)
    assert result.returncode == 2
    assert not Path(docker_fake["DOCKER_CALLS"]).exists()


@pytest.fixture
def docker_fake(tmp_path):
    fake = tmp_path / "docker"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "with open(os.environ['DOCKER_CALLS'], 'a') as f:\n"
        "    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if os.environ.get('DOCKER_FAIL_ON') in sys.argv[1:]:\n"
        "    sys.exit(19)\n"
        "if 'info' in sys.argv[1:]: print('/bin/true')\n"
        "if 'config' in sys.argv[1:]:\n"
        "    base = os.path.dirname(os.environ['DOCKER_CALLS'])\n"
        "    print(json.dumps({'services': {'tools': {'environment': {'RAG_MODEL_DIR': '/model', 'RAG_OUTPUT_DIR': '/rag'}, 'volumes': [{'source': base+'/model', 'target': '/model'}, {'source': base+'/rag', 'target': '/rag'}]}, 'api': {'ports': [{'published': os.environ.get('DOCKER_PUBLISHED_PORT', '18000')}]}, 'web': {'ports': [{'published': '18001'}]}}}))\n"
        "if 'run' in sys.argv[1:] and '--entrypoint' in sys.argv[1:]:\n"
        "    import subprocess\n"
        "    sys.exit(subprocess.run([sys.executable, '-c', sys.argv[-1]], input=sys.stdin.read(), text=True).returncode)\n"
        "sys.exit(int(os.environ.get('DOCKER_RESULT', '0')))\n"
    )
    fake.chmod(0o755)
    env_file = tmp_path / ".env"
    env_file.write_text("# 不含真实凭据的隔离配置\n")
    return {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "DOCKER_CALLS": str(tmp_path / "calls.jsonl"),
        "CHATBI_DEV_ENV_FILE": str(env_file),
    }


def invoke(command, environ):
    return subprocess.run(
        ["bash", str(ROOT / "dev"), *command],
        env=environ,
        capture_output=True,
        text=True,
        check=False,
    )


def test_stop_keeps_volumes_and_only_targets_project_services(docker_fake):
    result = invoke(["down"], docker_fake)
    assert result.returncode == 0, result.stderr
    calls = [
        json.loads(line)
        for line in Path(docker_fake["DOCKER_CALLS"]).read_text().splitlines()
    ]
    assert calls[-1][-5:] == ["stop", "api", "web", "postgres", "qdrant"]
    assert not any("down" in call or "-v" in call or "rm" in call for call in calls)


def test_docker_failure_is_nonzero_and_does_not_report_success(docker_fake):
    result = invoke(["down"], {**docker_fake, "DOCKER_RESULT": "19"})
    assert result.returncode == 19
    assert "已启动" not in result.stdout


def test_unknown_command_is_rejected_before_docker(docker_fake):
    result = invoke(["erase-data"], docker_fake)
    assert result.returncode == 2
    assert not Path(docker_fake["DOCKER_CALLS"]).exists()


def test_test_command_rejects_unknown_suite_before_docker(docker_fake):
    result = invoke(["test", "erase-data"], docker_fake)
    assert result.returncode == 2
    assert "python|database|web|renderer|all" in result.stderr
    assert not Path(docker_fake["DOCKER_CALLS"]).exists()


def test_python_tests_run_in_a_container_and_propagate_failure(docker_fake):
    result = invoke(["test", "python"], {**docker_fake, "DOCKER_FAIL_ON": "run"})
    assert result.returncode == 19
    calls = [
        json.loads(line)
        for line in Path(docker_fake["DOCKER_CALLS"]).read_text().splitlines()
    ]
    assert any("run" in call for call in calls)


def test_start_rejects_an_occupied_host_port_without_stopping_its_owner(docker_fake):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        result = invoke(["up"], {**docker_fake, "DOCKER_PUBLISHED_PORT": str(port)})
        assert result.returncode == 1
        assert "已被占用" in result.stderr
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass
    calls = [
        json.loads(line)
        for line in Path(docker_fake["DOCKER_CALLS"]).read_text().splitlines()
    ]
    assert not any("up" in call or "stop" in call or "kill" in call for call in calls)


def test_missing_config_gives_safe_actionable_message(docker_fake):
    result = invoke(
        ["up"], {**docker_fake, "CHATBI_DEV_ENV_FILE": "/missing/chatbi.env"}
    )
    assert result.returncode != 0
    assert ".env.example" in result.stderr


def test_migration_failure_does_not_enter_full_health_wait(docker_fake):
    result = invoke(["migrate"], {**docker_fake, "DOCKER_FAIL_ON": "migrator"})
    assert result.returncode == 19
    calls = [
        json.loads(line)
        for line in Path(docker_fake["DOCKER_CALLS"]).read_text().splitlines()
    ]
    assert not any("--wait" in call for call in calls)
    assert "已启动" not in result.stdout


def test_admin_creation_requires_terminal_before_starting_resources(docker_fake):
    result = invoke(["create-admin", "--username", "admin"], docker_fake)
    assert result.returncode == 2
    assert "交互终端" in result.stderr
    assert not Path(docker_fake["DOCKER_CALLS"]).exists()


def test_compose_config_excludes_secrets_and_migration_identity_from_api(tmp_path):
    safe_config = (
        (ROOT / ".env.example")
        .read_text()
        .replace(
            "CHATBI_ADMIN_SECRET_KEY=\n", "CHATBI_ADMIN_SECRET_KEY=safe-test-key\n"
        )
        .replace("LLM_API_KEY=\n", "LLM_API_KEY=safe-test-key\n")
    )
    env_file = tmp_path / ".env"
    env_file.write_text(safe_config)
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--profile",
            "tools",
            "--env-file",
            str(env_file),
            "-f",
            str(ROOT / "docker-compose.yml"),
            "-f",
            str(ROOT / "docker-compose.dev.yml"),
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        env={
            "PATH": os.environ["PATH"],
            "CHATBI_DEV_MODEL_DIR": str(ROOT / ".model-cache/bge-m3-5617a9f61b02"),
            "CHATBI_DEV_SECCOMP_PROFILE": str(
                ROOT / "docker/third-party/playwright-seccomp-profile.json"
            ),
        },
        capture_output=True,
        text=True,
        check=True,
    )
    services = json.loads(result.stdout)["services"]
    api = services["api"]
    assert api["command"] == ["python", "-m", "scripts.start_dev_api"]
    assert not any("MIGRATOR" in key for key in api["environment"])
    assert api["security_opt"] == [
        f"seccomp={ROOT}/docker/third-party/playwright-seccomp-profile.json"
    ]
    assert api["environment"]["POSTGRES_HOST"] == "postgres"
    assert api["environment"]["RAG_EMBEDDING_DEVICE"] == "cpu"
    assert any(
        v["target"] == api["environment"]["RAG_MODEL_DIR"] == v["source"]
        for v in api["volumes"]
    )
    assert all(
        services[name]["restart"] == "unless-stopped"
        for name in ("api", "web", "postgres", "qdrant")
    )
    assert all(services[name]["restart"] == "no" for name in ("tools", "migrator"))
    assert all(
        port["host_ip"] == "127.0.0.1"
        for service in services.values()
        for port in service.get("ports", [])
    )
    assert all(Path(v["source"]).name != ".env" for v in api["volumes"])
    assert all(v["read_only"] for v in api["volumes"])
    assert services["migrator"]["profiles"] == ["tools"]
    assert "POSTGRES_MIGRATOR_PASSWORD" in services["migrator"]["environment"]


@pytest.mark.parametrize(
    "args",
    [
        ["check", "--help"],
        ["verify", "dev", "--help"],
        ["reset", "--help"],
        ["recover-admin", "--help"],
        ["harness", "--help"],
    ],
)
def test_group_help_has_no_environment_dependency(args):
    result = invoke(args, {"PATH": "/usr/bin:/bin", "CHATBI_DEV_ENV_FILE": "/missing"})
    assert result.returncode == 0
    assert "用法" in result.stdout


@pytest.mark.parametrize(
    "args",
    [
        ["recover-admin"],
        ["recover-admin", "dev", "--username", "admin"],
        ["recover-admin", "stable", "--username", "admin"],
        ["reset", "app"],
        ["doctor", "stable"],
        ["verify", "dev", "extra"],
    ],
)
def test_sensitive_commands_reject_invalid_or_nonterminal_input_before_docker(
    args, docker_fake
):
    result = invoke(args, docker_fake)
    assert result.returncode == 2
    assert not Path(docker_fake["DOCKER_CALLS"]).exists()


def test_devcontainer_environment_keeps_host_project_identity(docker_fake):
    result = invoke(
        ["infra"], {**docker_fake, "LOCAL_WORKSPACE_FOLDER": "/host/selected-project"}
    )
    assert result.returncode == 0
    calls = [
        json.loads(line)
        for line in Path(docker_fake["DOCKER_CALLS"]).read_text().splitlines()
    ]
    assert str(ROOT / "docker/dev-project-name.yml") in calls[-1]
