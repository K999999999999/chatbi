"""开发入口的错误传播与资源边界，不启动真实 Docker。"""

import json
import os
import socket
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def host_workspace(path: Path) -> Path:
    """Expose real read-only sources while keeping report output in this fixture."""
    path.mkdir()
    for name in (
        ".git",
        "frontend",
        "src",
        "scripts",
        "database",
        "pyproject.toml",
        "uv.lock",
    ):
        (path / name).symlink_to(
            ROOT / name, target_is_directory=(ROOT / name).is_dir()
        )
    return path


def test_help_requires_neither_config_nor_docker():
    result = invoke(
        ["help"], {"PATH": "/usr/bin:/bin", "CHATBI_DEV_ENV_FILE": "/missing"}
    )
    assert result.returncode == 0
    assert "环境管理" in result.stdout
    assert "recover-admin" in result.stdout
    assert "./dev app" not in result.stdout
    assert "verify app" not in result.stdout


def test_build_keeps_the_development_python_and_node_images(docker_fake):
    result = invoke(["build"], docker_fake)
    assert result.returncode == 0, result.stderr
    calls = [
        json.loads(line)
        for line in Path(docker_fake["DOCKER_CALLS"]).read_text().splitlines()
    ]
    assert calls == [
        [
            "compose",
            "--project-directory",
            str(ROOT),
            "--env-file",
            docker_fake["CHATBI_DEV_ENV_FILE"],
            "-f",
            str(ROOT / "docker-compose.yml"),
            "-f",
            str(ROOT / "docker-compose.dev.yml"),
            "build",
            "api",
            "web",
        ]
    ]


@pytest.mark.parametrize(
    "args",
    [
        ["app"],
        ["app", "--help"],
        ["app", "down"],
        ["verify", "app"],
        ["doctor", "app"],
        ["recover-admin", "app", "--username", "test-admin"],
    ],
)
def test_retired_app_targets_are_rejected_before_resources(args, docker_fake):
    result = invoke(args, docker_fake)
    assert result.returncode == 2
    assert not Path(docker_fake["DOCKER_CALLS"]).exists()


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
        "import json, os, subprocess, sys\n"
        "with open(os.environ['DOCKER_CALLS'], 'a') as f:\n"
        "    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if os.environ.get('DOCKER_FAIL_ON') in sys.argv[1:]:\n"
        "    sys.exit(int(os.environ.get('DOCKER_FAIL_CODE', '19')))\n"
        "if 'info' in sys.argv[1:]: print('/bin/true')\n"
        "if 'config' in sys.argv[1:]:\n"
        "    base = os.path.dirname(os.environ['DOCKER_CALLS'])\n"
        "    print(json.dumps({'services': {'tools': {'environment': {'RAG_MODEL_DIR': '/model', 'RAG_OUTPUT_DIR': '/rag'}, 'volumes': [{'source': base+'/model', 'target': '/model'}, {'source': base+'/rag', 'target': '/rag'}]}, 'api': {'ports': [{'published': os.environ.get('DOCKER_PUBLISHED_PORT', '18000')}]}, 'web': {'ports': [{'published': '18001'}]}}}))\n"
        "args = sys.argv[1:]\n"
        "if 'run' in args and '--entrypoint' in args:\n"
        "    entry = args.index('--entrypoint')\n"
        "    command = args[entry + 3:]\n"
        "    if command[:2] == ['-m', 'scripts.verification_report']:\n"
        "        if os.environ.get('EXEC_REPORT_HELPER') == '1':\n"
        "            mounts = {}\n"
        "            for index, item in enumerate(args[:-1]):\n"
        "                if item == '-v':\n"
        "                    source, target = args[index + 1].split(':', 1)\n"
        "                    mounts[target] = source\n"
        "            rewritten = []\n"
        "            for item in command:\n"
        "                mapped = item\n"
        "                for target, source in mounts.items():\n"
        "                    if target not in ('/reports/tests', '/verification'):\n"
        "                        continue\n"
        "                    if item == target or item.startswith(target + '/'):\n"
        "                        mapped = os.path.join(source, item[len(target):].lstrip('/'))\n"
        "                        break\n"
        "                    if item.startswith('--') and '=' + target + '/' in item:\n"
        "                        prefix, value = item.split('=', 1)\n"
        "                        if value.startswith(target + '/'):\n"
        "                            mapped = prefix + '=' + os.path.join(source, value[len(target):].lstrip('/'))\n"
        "                            break\n"
        "                rewritten.append(mapped)\n"
        "            sys.exit(subprocess.run([sys.executable, *rewritten], cwd=os.environ['REPO_ROOT']).returncode)\n"
        "        if command[2] == 'begin':\n"
        "            run_id = '20261015T120000Z-abcdef1-test-python-deadbeef'\n"
        "            target = command[command.index('--reports-directory') + 1]\n"
        "            source = next(args[index + 1].split(':', 1)[0] for index, item in enumerate(args) if item == '-v' and args[index + 1].split(':')[1] == target)\n"
        "            os.makedirs(os.path.join(source, run_id), exist_ok=True)\n"
        "            print(run_id)\n"
        "        sys.exit(0)\n"
        "    if 'pytest' in args:\n"
        "        junit = next((item.split('=', 1)[1] for item in args if item.startswith('--junitxml=')), None)\n"
        "        if junit:\n"
        "            report_source = next(args[index + 1].split(':', 1)[0] for index, item in enumerate(args[:-1]) if item == '-v' and args[index + 1].endswith(':/reports/tests'))\n"
        "            if junit.startswith('/reports/tests/'):\n"
        "                junit = os.path.join(report_source, junit[len('/reports/tests/'):])\n"
        "            os.makedirs(os.path.dirname(junit), exist_ok=True)\n"
        "            open(junit, 'w').write('<testsuite><testcase name=\"fake-test\"/></testsuite>')\n"
        "    if '--reporter=json' in args:\n"
        "        print(json.dumps({'stats': {'expected': 2, 'unexpected': 0, 'flaky': 0, 'skipped': 0}}))\n"
        "    if '-c' in command:\n"
        "        import subprocess\n"
        "        sys.exit(subprocess.run([sys.executable, *command], input=sys.stdin.read(), text=True).returncode)\n"
        "sys.exit(int(os.environ.get('DOCKER_RESULT', '0')))\n"
    )
    fake.chmod(0o755)
    env_file = tmp_path / ".env"
    env_file.write_text("# 不含真实凭据的隔离配置\n")
    env_file.chmod(0o600)
    return {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "DOCKER_CALLS": str(tmp_path / "calls.jsonl"),
        "CHATBI_DEV_ENV_FILE": str(env_file),
        "REPO_ROOT": str(ROOT),
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


def test_direct_development_maintenance_rejects_retired_app_before_docker(
    docker_fake,
):
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/dev_maintenance.sh"), "recover", "app", "admin"],
        env=docker_fake,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert not Path(docker_fake["DOCKER_CALLS"]).exists()


def test_test_command_rejects_unknown_suite_before_docker(docker_fake):
    result = invoke(["test", "erase-data"], docker_fake)
    assert result.returncode == 2
    assert "python|database|web|renderer|all" in result.stderr
    assert not Path(docker_fake["DOCKER_CALLS"]).exists()


def test_python_tests_run_in_a_container_and_propagate_failure(docker_fake):
    workspace = host_workspace(Path(docker_fake["DOCKER_CALLS"]).parent / "workspace")
    result = invoke(
        ["test", "python"],
        {
            **docker_fake,
            "DOCKER_FAIL_ON": "run",
            "LOCAL_WORKSPACE_FOLDER": str(workspace),
        },
    )
    assert result.returncode == 19
    calls = [
        json.loads(line)
        for line in Path(docker_fake["DOCKER_CALLS"]).read_text().splitlines()
    ]
    assert any("run" in call for call in calls)


def test_python_tests_request_junit_and_publish_command_summary(docker_fake):
    workspace = host_workspace(Path(docker_fake["DOCKER_CALLS"]).parent / "workspace")
    result = invoke(
        ["test", "python"],
        {**docker_fake, "LOCAL_WORKSPACE_FOLDER": str(workspace)},
    )

    assert result.returncode == 0, result.stderr
    assert "reports/tests/" in result.stdout
    run_id = result.stdout.split("reports/tests/", 1)[1].split(".json", 1)[0]
    assert (workspace / "reports/tests" / run_id).is_dir()
    calls = [
        json.loads(line)
        for line in Path(docker_fake["DOCKER_CALLS"]).read_text().splitlines()
    ]
    report_calls = [call for call in calls if "scripts.verification_report" in call]
    assert any("begin" in call for call in report_calls)
    assert any("step-start" in call for call in report_calls)
    assert any("step-finish" in call for call in report_calls)
    assert any("finish" in call for call in report_calls)
    pytest_call = next(call for call in calls if "pytest" in call)
    assert any(
        argument.startswith("--junitxml=/reports/tests/") for argument in pytest_call
    )


def test_check_records_each_machine_check_without_inventing_test_counts(docker_fake):
    workspace = host_workspace(Path(docker_fake["DOCKER_CALLS"]).parent / "workspace")
    result = invoke(
        ["check"], {**docker_fake, "LOCAL_WORKSPACE_FOLDER": str(workspace)}
    )

    assert result.returncode == 0, result.stderr
    assert "reports/tests/" in result.stdout
    calls = [
        json.loads(line)
        for line in Path(docker_fake["DOCKER_CALLS"]).read_text().splitlines()
    ]
    step_starts = [
        call[call.index("--name") + 1]
        for call in calls
        if "scripts.verification_report" in call and "step-start" in call
    ]
    assert step_starts == [
        "lock",
        "docs",
        "boundaries",
        "python",
        "web-build",
        "export-build",
    ]
    step_finishes = [
        call
        for call in calls
        if "scripts.verification_report" in call and "step-finish" in call
    ]
    assert all("--counts-not-applicable" in call for call in step_finishes)


def test_all_failure_report_marks_remaining_suites_not_run(docker_fake, tmp_path):
    workspace = host_workspace(tmp_path / "isolated-workspace")
    result = invoke(
        ["test", "all"],
        {
            **docker_fake,
            "LOCAL_WORKSPACE_FOLDER": str(workspace),
            "EXEC_REPORT_HELPER": "1",
            "DOCKER_FAIL_ON": "pytest",
        },
    )

    assert result.returncode == 19
    run_id = result.stdout.split("reports/tests/", 1)[1].split(".json", 1)[0]
    report = json.loads((workspace / "reports/tests" / f"{run_id}.json").read_text())
    assert report["status"] == "failed"
    assert report["steps"][0]["name"] == "python"
    assert report["steps"][0]["status"] == "failed"
    assert [step["status"] for step in report["steps"][1:]] == ["not_run"] * 7


def test_all_interruption_report_marks_running_suite_interrupted(docker_fake, tmp_path):
    workspace = host_workspace(tmp_path / "isolated-workspace")
    result = invoke(
        ["test", "all"],
        {
            **docker_fake,
            "LOCAL_WORKSPACE_FOLDER": str(workspace),
            "EXEC_REPORT_HELPER": "1",
            "DOCKER_FAIL_ON": "pytest",
            "DOCKER_FAIL_CODE": "130",
        },
    )

    assert result.returncode == 130
    run_id = result.stdout.split("reports/tests/", 1)[1].split(".json", 1)[0]
    report = json.loads((workspace / "reports/tests" / f"{run_id}.json").read_text())
    assert report["status"] == "interrupted"
    assert report["exit_code"] == 130
    assert report["steps"][0]["status"] == "interrupted"
    assert [step["status"] for step in report["steps"][1:]] == ["not_run"] * 7


def test_check_failure_report_does_not_run_later_checks(docker_fake, tmp_path):
    workspace = host_workspace(tmp_path / "isolated-workspace")
    result = invoke(
        ["check"],
        {
            **docker_fake,
            "LOCAL_WORKSPACE_FOLDER": str(workspace),
            "EXEC_REPORT_HELPER": "1",
            "DOCKER_FAIL_ON": "uv",
        },
    )

    assert result.returncode == 19
    run_id = result.stdout.split("reports/tests/", 1)[1].split(".json", 1)[0]
    report = json.loads((workspace / "reports/tests" / f"{run_id}.json").read_text())
    assert report["status"] == "failed"
    assert report["steps"][0]["name"] == "lock"
    assert report["steps"][0]["status"] == "failed"
    assert [step["status"] for step in report["steps"][1:]] == ["not_run"] * 5


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


def test_group_readable_config_is_rejected_before_compose(docker_fake):
    env_file = Path(docker_fake["CHATBI_DEV_ENV_FILE"])
    env_file.write_text("CONFIG_SECRET_CANARY=do-not-print\n")
    env_file.chmod(0o644)

    result = invoke(["up"], docker_fake)

    assert result.returncode == 2
    assert "chmod 600" in result.stderr
    assert "CONFIG_SECRET_CANARY" not in result.stdout + result.stderr
    assert not Path(docker_fake["DOCKER_CALLS"]).exists()


def test_config_owned_by_another_user_is_rejected_before_compose(docker_fake, tmp_path):
    fake_stat = tmp_path / "stat"
    fake_stat.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "if sys.argv[1:3] == ['-c', '%u:%a']:\n"
        "    print(f'{os.getuid() + 1}:600')\n"
        "else:\n"
        "    os.execv('/usr/bin/stat', ['/usr/bin/stat', *sys.argv[1:]])\n"
    )
    fake_stat.chmod(0o755)
    env = {**docker_fake, "PATH": f"{tmp_path}:{os.environ['PATH']}"}

    result = invoke(["up"], env)

    assert result.returncode == 2
    assert "属主" in result.stderr
    assert not Path(docker_fake["DOCKER_CALLS"]).exists()


def test_help_does_not_validate_or_read_unsafe_config(docker_fake):
    Path(docker_fake["CHATBI_DEV_ENV_FILE"]).chmod(0o644)

    result = invoke(["help"], docker_fake)

    assert result.returncode == 0
    assert "环境管理" in result.stdout
    assert not Path(docker_fake["DOCKER_CALLS"]).exists()


def test_container_acceptance_rejects_unsafe_config_before_compose(docker_fake):
    Path(docker_fake["CHATBI_DEV_ENV_FILE"]).chmod(0o644)
    env = {**docker_fake, "CHATBI_CONTAINER_ALLOW_DIRTY": "1"}

    result = invoke(["verify", "dev", "isolated"], env)

    assert result.returncode == 2
    assert "chmod 600" in result.stderr
    assert not Path(docker_fake["DOCKER_CALLS"]).exists()


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
    assert all(
        v["bind"]["create_host_path"] is False
        for v in services["postgres"]["volumes"]
        if v["type"] == "bind"
    )
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


def test_devcontainer_environment_keeps_host_project_identity(docker_fake, tmp_path):
    workspace = host_workspace(tmp_path / "selected-project")
    result = invoke(
        ["infra"], {**docker_fake, "LOCAL_WORKSPACE_FOLDER": str(workspace)}
    )
    assert result.returncode == 0
    calls = [
        json.loads(line)
        for line in Path(docker_fake["DOCKER_CALLS"]).read_text().splitlines()
    ]
    assert str(ROOT / "docker/dev-project-name.yml") in calls[-1]
