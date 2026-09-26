from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts import run_database_tests


def test_test_environment_uses_only_the_temporary_database(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "old-development-host")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_APP_PASSWORD", "old-development-password")
    monkeypatch.setenv("PGHOST", "old-postgres-service")
    monkeypatch.setenv("PGPASSWORD", "old-postgres-password")
    monkeypatch.setenv("RUN_LLM_TESTS", "1")

    environment = run_database_tests._test_environment(43127)

    assert environment["POSTGRES_HOST"] == "127.0.0.1"
    assert environment["POSTGRES_PORT"] == "43127"
    assert environment["POSTGRES_DB"] == "chatbi_mvp"
    assert environment["POSTGRES_APP_USER"] == "chatbi_app"
    assert environment["POSTGRES_APP_PASSWORD"] == "ci-app-password"
    assert environment["RUN_DATABASE_TESTS"] == "1"
    assert "RUN_LLM_TESTS" not in environment
    assert "PGHOST" not in environment
    assert "PGPASSWORD" not in environment


def test_test_environment_can_connect_to_temporary_container_on_compose_network():
    environment = run_database_tests._test_environment(
        5432,
        host="chatbi-db-test-a",
    )

    assert environment["POSTGRES_HOST"] == "chatbi-db-test-a"
    assert environment["POSTGRES_PORT"] == "5432"


def test_ci_fixture_uses_the_mounted_database_directory(monkeypatch) -> None:
    captured = {}

    def record_run(docker, arguments, **kwargs):
        captured["arguments"] = arguments
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_database_tests, "_run_docker", record_run)

    run_database_tests._load_ci_fixture("docker", "chatbi-db-test-a")

    assert captured["arguments"][-1] == "/workspace/database/ci/bootstrap.sql"


def test_development_profile_sets_control_database_test_credentials(
    monkeypatch,
) -> None:
    monkeypatch.setenv("POSTGRES_CONTROL_APP_PASSWORD", "old-control-password")
    environment = run_database_tests._test_environment(
        43127,
        profile="development",
        migrator_password="temporary-migrator",
    )

    assert environment["POSTGRES_CONTROL_DB"] == "chatbi_control"
    assert environment["POSTGRES_CONTROL_APP_USER"] == "chatbi_control_user"
    assert environment["POSTGRES_CONTROL_APP_PASSWORD"] == "temporary-test-control"
    assert environment["POSTGRES_MIGRATOR_PASSWORD"] == "temporary-migrator"
    assert environment["RUN_DEVELOPMENT_DATABASE_TESTS"] == "1"


def test_development_container_and_test_environment_share_credentials(
    monkeypatch,
    tmp_path,
) -> None:
    captured = {}

    def record_run(docker, arguments, **kwargs):
        captured["arguments"] = arguments
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_database_tests, "_run_docker", record_run)
    run_database_tests._start_container(
        "docker",
        "chatbi-db-test-a",
        "a" * 32,
        tmp_path,
        profile="development",
        migrator_password="temporary-migrator",
    )

    arguments = captured["arguments"]
    environment = run_database_tests._test_environment(
        43127,
        profile="development",
        migrator_password="temporary-migrator",
    )
    assert "POSTGRES_PASSWORD=temporary-migrator" in arguments
    assert "POSTGRES_CONTROL_APP_PASSWORD=temporary-test-control" in arguments
    assert environment["POSTGRES_MIGRATOR_PASSWORD"] == "temporary-migrator"
    assert environment["POSTGRES_CONTROL_APP_PASSWORD"] == "temporary-test-control"


def test_resolve_host_port_accepts_only_loopback_mapping() -> None:
    assert run_database_tests._resolve_host_port("127.0.0.1:43127\n") == 43127

    with pytest.raises(RuntimeError, match="loopback"):
        run_database_tests._resolve_host_port("0.0.0.0:43127\n")


def test_compose_network_lookup_uses_the_workspace_compose_project(
    monkeypatch, tmp_path
):
    def resolve_network(docker, arguments, **kwargs):
        assert docker == "docker"
        assert arguments == ["compose", "config", "--format", "json"]
        assert kwargs["cwd"] == tmp_path
        return SimpleNamespace(stdout='{"networks":{"default":{"name":"dev_default"}}}')

    monkeypatch.setattr(run_database_tests, "_run_docker", resolve_network)

    assert (
        run_database_tests._compose_default_network("docker", tmp_path) == "dev_default"
    )


def test_database_mount_uses_host_workspace_inside_devcontainer(monkeypatch):
    monkeypatch.setenv("LOCAL_WORKSPACE_FOLDER", "/host/workspace/chatbi-engine")

    path = run_database_tests._database_mount_path(
        Path("/workspaces/chatbi-engine"),
        "init",
        "init.sh",
    )

    assert path == "/host/workspace/chatbi-engine/database/init/init.sh"


def test_temporary_container_joins_shared_network_without_host_publish(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("LOCAL_WORKSPACE_FOLDER", "/host/workspace/chatbi-engine")
    captured = {}

    def record_run(docker, arguments, **kwargs):
        captured["arguments"] = arguments
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_database_tests, "_run_docker", record_run)

    run_database_tests._start_container(
        "docker",
        "chatbi-db-test-a",
        "a" * 32,
        tmp_path,
        profile="ci",
        migrator_password="temporary-migrator",
        network_name="dev_default",
    )

    arguments = captured["arguments"]
    assert "--publish" not in arguments
    assert arguments[arguments.index("--network") + 1] == "dev_default"
    assert arguments[arguments.index("--network-alias") + 1] == "chatbi-db-test-a"
    assert any(
        argument.startswith(
            "type=bind,source=/host/workspace/chatbi-engine/database,target="
        )
        for argument in arguments
    )


def test_cleanup_removes_only_container_with_matching_run_label() -> None:
    run_id = "a" * 32
    inspect = SimpleNamespace(returncode=0, stdout=f"{run_id}\n")
    removed = SimpleNamespace(returncode=0)

    with patch.object(
        run_database_tests.subprocess, "run", side_effect=[inspect, removed]
    ) as run:
        run_database_tests._cleanup_container("docker", "chatbi-test-a", run_id)

    assert run.call_count == 2
    assert run.call_args_list[1].args[0] == [
        "docker",
        "rm",
        "--force",
        "--volumes",
        "chatbi-test-a",
    ]


def test_cleanup_leaves_container_when_run_label_does_not_match() -> None:
    inspect = SimpleNamespace(returncode=0, stdout="another-run\n")

    with patch.object(
        run_database_tests.subprocess, "run", return_value=inspect
    ) as run:
        run_database_tests._cleanup_container("docker", "chatbi-test-a", "a" * 32)

    assert run.call_count == 1


def test_temporary_container_is_cleaned_when_tests_are_interrupted(monkeypatch) -> None:
    run_id = "b" * 32
    monkeypatch.delenv("LOCAL_WORKSPACE_FOLDER", raising=False)

    def interrupt_tests(*args, **kwargs) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(
        run_database_tests, "_start_container", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(run_database_tests, "_published_host_port", lambda *args: 43127)
    monkeypatch.setattr(run_database_tests, "_wait_until_ready", lambda *args: None)
    monkeypatch.setattr(run_database_tests, "_load_ci_fixture", lambda *args: None)
    monkeypatch.setattr(run_database_tests, "_run_tests", interrupt_tests)

    with (
        patch.object(run_database_tests, "_cleanup_container") as cleanup,
        pytest.raises(KeyboardInterrupt),
    ):
        run_database_tests._run_with_temporary_database("docker", ".", run_id)

    cleanup.assert_called_once_with("docker", f"chatbi-db-test-{run_id}", run_id)


def test_temporary_development_runner_shares_generated_migrator_password(
    monkeypatch,
) -> None:
    run_id = "d" * 32
    credentials = {}
    monkeypatch.delenv("LOCAL_WORKSPACE_FOLDER", raising=False)
    monkeypatch.setattr(
        run_database_tests.secrets,
        "token_urlsafe",
        lambda _: "one-time-test-migrator",
    )
    monkeypatch.setattr(
        run_database_tests,
        "_start_container",
        lambda *args, **kwargs: credentials.update(
            container_password=kwargs["migrator_password"]
        ),
    )
    monkeypatch.setattr(run_database_tests, "_published_host_port", lambda *args: 43127)
    monkeypatch.setattr(run_database_tests, "_wait_until_ready", lambda *args: None)
    monkeypatch.setattr(
        run_database_tests,
        "_wait_until_development_ready",
        lambda *args: None,
    )
    monkeypatch.setattr(
        run_database_tests,
        "_run_tests",
        lambda *args, **kwargs: (
            credentials.update(test_password=kwargs["migrator_password"]) or 0
        ),
    )

    with patch.object(run_database_tests, "_cleanup_container"):
        result = run_database_tests._run_with_temporary_database(
            "docker",
            Path("project"),
            run_id,
            profile="development",
        )

    assert result == 0
    assert credentials["container_password"] == "one-time-test-migrator"
    assert credentials["test_password"] == "one-time-test-migrator"


def test_temporary_container_is_cleaned_when_integration_tests_fail(
    monkeypatch,
) -> None:
    run_id = "c" * 32
    monkeypatch.delenv("LOCAL_WORKSPACE_FOLDER", raising=False)
    monkeypatch.setattr(
        run_database_tests, "_start_container", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(run_database_tests, "_published_host_port", lambda *args: 43127)
    monkeypatch.setattr(run_database_tests, "_wait_until_ready", lambda *args: None)
    monkeypatch.setattr(run_database_tests, "_load_ci_fixture", lambda *args: None)
    monkeypatch.setattr(run_database_tests, "_run_tests", lambda *args, **kwargs: 1)

    with patch.object(run_database_tests, "_cleanup_container") as cleanup:
        result = run_database_tests._run_with_temporary_database("docker", ".", run_id)

    assert result == 1
    cleanup.assert_called_once_with("docker", f"chatbi-db-test-{run_id}", run_id)


def test_main_fails_without_docker_and_does_not_start_other_database(
    monkeypatch,
) -> None:
    monkeypatch.setattr(run_database_tests.shutil, "which", lambda name: None)

    with patch.object(run_database_tests, "_run_with_temporary_database") as run:
        assert run_database_tests.main([]) == 2

    run.assert_not_called()
