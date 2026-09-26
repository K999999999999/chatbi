"""Run PostgreSQL integration tests against a temporary isolated database."""

import argparse
import json
import ntpath
import os
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

POSTGRES_IMAGE = "postgres:16-alpine"
RUN_ID_LABEL = "io.chatbi.database-test-run-id"
TEMPORARY_APP_PASSWORD = "ci-app-password"
TEMPORARY_CONTROL_APP_PASSWORD = "temporary-test-control"
DATABASE_TESTS = (
    "tests/online_query/test_database_integration.py",
    "tests/online_query/test_service_integration.py::ServiceDatabaseIntegrationTest",
)


class DatabaseTestRunnerError(RuntimeError):
    """A temporary PostgreSQL test environment could not be prepared."""


def _test_environment(
    host_port: int,
    *,
    profile: str = "ci",
    host: str = "127.0.0.1",
    migrator_password: str | None = None,
) -> dict[str, str]:
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith(("POSTGRES_", "PG")) or name in {
            "RUN_DATABASE_TESTS",
            "RUN_LLM_TESTS",
        }:
            environment.pop(name)

    environment.update(
        {
            "POSTGRES_HOST": host,
            "POSTGRES_PORT": str(host_port),
            "POSTGRES_DB": "chatbi_mvp",
            "POSTGRES_APP_USER": "chatbi_app",
            "POSTGRES_APP_PASSWORD": TEMPORARY_APP_PASSWORD,
            "RUN_DATABASE_TESTS": "1",
        }
    )
    if profile == "development":
        if not migrator_password:
            raise DatabaseTestRunnerError(
                "The temporary development database requires a migrator password."
            )
        environment.update(
            {
                "POSTGRES_MIGRATOR_USER": "chatbi_migrator",
                "POSTGRES_MIGRATOR_PASSWORD": migrator_password,
                "POSTGRES_CONTROL_DB": "chatbi_control",
                "POSTGRES_CONTROL_APP_USER": "chatbi_control_user",
                "POSTGRES_CONTROL_APP_PASSWORD": TEMPORARY_CONTROL_APP_PASSWORD,
                "POSTGRES_CONTROL_MIGRATOR_USER": "chatbi_migrator",
                "RUN_DEVELOPMENT_DATABASE_TESTS": "1",
            }
        )
    return environment


def _resolve_host_port(output: str) -> int:
    binding = output.strip()
    host, separator, port_text = binding.rpartition(":")
    if not separator or host != "127.0.0.1":
        raise DatabaseTestRunnerError(
            "Docker did not publish PostgreSQL on the loopback interface."
        )

    try:
        port = int(port_text)
    except ValueError:
        raise DatabaseTestRunnerError(
            "Docker returned an invalid PostgreSQL port."
        ) from None

    if not 1 <= port <= 65535:
        raise DatabaseTestRunnerError("Docker returned an invalid PostgreSQL port.")
    return port


def _run_docker(
    docker: str,
    arguments: list[str],
    *,
    operation: str,
    capture_output: bool = False,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [docker, *arguments],
        check=False,
        capture_output=capture_output,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        raise DatabaseTestRunnerError(
            f"{operation} failed (Docker exit code {result.returncode})."
        )
    return result


def _start_container(
    docker: str,
    container_name: str,
    run_id: str,
    project_root: Path,
    *,
    profile: str,
    migrator_password: str,
    network_name: str | None = None,
) -> None:
    database_directory = _database_mount_path(project_root)
    development_init_script = _database_mount_path(
        project_root,
        "init",
        "10_chatbi_dev_environment.sh",
    )
    arguments = [
        "run",
        "--detach",
        "--rm",
        "--name",
        container_name,
        "--label",
        f"{RUN_ID_LABEL}={run_id}",
        "--mount",
        f"type=bind,source={database_directory},target=/workspace/database,readonly",
    ]
    if network_name is None:
        arguments.extend(["--publish", "127.0.0.1::5432"])
    else:
        arguments.extend(["--network", network_name, "--network-alias", container_name])
    arguments.extend(
        [
            "--env",
            "POSTGRES_USER=chatbi_migrator",
            "--env",
            f"POSTGRES_PASSWORD={migrator_password}",
            "--env",
            "POSTGRES_DB=chatbi_mvp",
            "--env",
            f"POSTGRES_APP_PASSWORD={TEMPORARY_APP_PASSWORD}",
        ]
    )
    if profile == "development":
        arguments.extend(
            [
                "--mount",
                f"type=bind,source={development_init_script},target=/docker-entrypoint-initdb.d/10_chatbi_dev_environment.sh,readonly",
                "--env",
                "POSTGRES_APP_USER=chatbi_app",
                "--env",
                "POSTGRES_CONTROL_DB=chatbi_control",
                "--env",
                "POSTGRES_CONTROL_APP_USER=chatbi_control_user",
                "--env",
                f"POSTGRES_CONTROL_APP_PASSWORD={TEMPORARY_CONTROL_APP_PASSWORD}",
                "--env",
                "POSTGRES_CONTROL_MIGRATOR_USER=chatbi_migrator",
            ]
        )
    arguments.append(POSTGRES_IMAGE)
    _run_docker(
        docker,
        arguments,
        operation="Starting the temporary PostgreSQL container",
        capture_output=True,
    )


def _published_host_port(docker: str, container_name: str) -> int:
    result = _run_docker(
        docker,
        ["port", container_name, "5432/tcp"],
        operation="Reading the temporary PostgreSQL port",
        capture_output=True,
    )
    return _resolve_host_port(result.stdout)


def _wait_until_ready(
    docker: str,
    container_name: str,
    *,
    timeout_seconds: int = 60,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                docker,
                "exec",
                container_name,
                "pg_isready",
                "--username",
                "chatbi_migrator",
                "--dbname",
                "chatbi_mvp",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return
        state = subprocess.run(
            [
                docker,
                "inspect",
                "--format",
                "{{.State.Running}}",
                container_name,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if state.returncode != 0 or state.stdout.strip().lower() != "true":
            raise DatabaseTestRunnerError(
                "Temporary PostgreSQL stopped before becoming ready."
            )
        time.sleep(1)

    raise DatabaseTestRunnerError(
        f"Temporary PostgreSQL did not become ready within {timeout_seconds} seconds."
    )


def _load_ci_fixture(docker: str, container_name: str) -> None:
    _run_docker(
        docker,
        [
            "exec",
            container_name,
            "psql",
            "--set",
            "ON_ERROR_STOP=1",
            "--username",
            "chatbi_migrator",
            "--dbname",
            "chatbi_mvp",
            "--file",
            "/workspace/database/ci/bootstrap.sql",
        ],
        operation="Loading the CI PostgreSQL fixture",
    )


def _run_tests(
    project_root: Path,
    host_port: int,
    *,
    profile: str,
    host: str = "127.0.0.1",
    migrator_password: str | None = None,
) -> int:
    tests = list(DATABASE_TESTS)
    if profile == "development":
        tests.append("tests/chatbi_control/test_postgres_dev_environment.py")
        tests.append("tests/evaluation/test_database_fingerprint.py")
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *tests],
        cwd=project_root,
        env=_test_environment(
            host_port,
            profile=profile,
            host=host,
            migrator_password=migrator_password,
        ),
        check=False,
    )
    return completed.returncode


def _cleanup_container(docker: str, container_name: str, run_id: str) -> None:
    try:
        inspected = subprocess.run(
            [
                docker,
                "inspect",
                "--format",
                '{{ index .Config.Labels "' + RUN_ID_LABEL + '" }}',
                container_name,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        print(
            "Could not verify ownership of the temporary PostgreSQL container; "
            "cleanup was skipped.",
            file=sys.stderr,
        )
        return

    if inspected.returncode != 0:
        return
    if inspected.stdout.strip() != run_id:
        print(
            "The temporary PostgreSQL container ownership label did not match; "
            "cleanup was skipped.",
            file=sys.stderr,
        )
        return

    try:
        removed = subprocess.run(
            [docker, "rm", "--force", "--volumes", container_name],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        print("Could not remove the temporary PostgreSQL container.", file=sys.stderr)
        return

    if removed.returncode != 0:
        print("Could not remove the temporary PostgreSQL container.", file=sys.stderr)


def _run_with_temporary_database(
    docker: str,
    project_root: Path,
    run_id: str,
    *,
    profile: str = "ci",
) -> int:
    container_name = f"chatbi-db-test-{run_id}"
    compose_network = (
        _compose_default_network(docker, project_root)
        if os.environ.get("LOCAL_WORKSPACE_FOLDER", "").strip()
        else None
    )
    migrator_password = secrets.token_urlsafe(32)
    try:
        _start_container(
            docker,
            container_name,
            run_id,
            project_root,
            profile=profile,
            migrator_password=migrator_password,
            network_name=compose_network,
        )
        host_port = (
            _published_host_port(docker, container_name)
            if compose_network is None
            else 5432
        )
        test_host = "127.0.0.1" if compose_network is None else container_name
        _wait_until_ready(docker, container_name)
        if profile == "ci":
            _load_ci_fixture(docker, container_name)
        else:
            _wait_until_development_ready(docker, container_name)
        return _run_tests(
            project_root,
            host_port,
            profile=profile,
            host=test_host,
            migrator_password=migrator_password,
        )
    finally:
        _cleanup_container(docker, container_name, run_id)


def _wait_until_development_ready(
    docker: str,
    container_name: str,
    *,
    timeout_seconds: int = 60,
) -> None:
    checks = (
        (
            "chatbi_mvp",
            "SELECT seed_version FROM mart_sales.dev_seed_metadata WHERE singleton",
            "chatbi-sales-mart-dev-v1",
        ),
        (
            "chatbi_control",
            "SELECT version FROM schema_migrations WHERE version = 'chatbi-control-v1'",
            "chatbi-control-v1",
        ),
    )
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if all(
            _container_query(docker, container_name, database, query) == expected
            for database, query, expected in checks
        ):
            return
        time.sleep(1)
    raise DatabaseTestRunnerError(
        "Temporary PostgreSQL did not finish initializing the development databases."
    )


def _container_query(
    docker: str,
    container_name: str,
    database: str,
    query: str,
) -> str | None:
    result = subprocess.run(
        [
            docker,
            "exec",
            container_name,
            "psql",
            "--username",
            "chatbi_migrator",
            "--dbname",
            database,
            "--tuples-only",
            "--no-align",
            "--command",
            query,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _compose_default_network(docker: str, project_root: Path) -> str:
    result = _run_docker(
        docker,
        ["compose", "config", "--format", "json"],
        operation="Resolving the development Compose network",
        capture_output=True,
        cwd=project_root,
    )
    try:
        config = json.loads(result.stdout)
        network = config["networks"]["default"]["name"]
    except (KeyError, TypeError, json.JSONDecodeError):
        raise DatabaseTestRunnerError(
            "Compose did not report its default development network."
        ) from None
    if not isinstance(network, str) or not network:
        raise DatabaseTestRunnerError(
            "Compose did not report its default development network."
        )
    return network


def _database_mount_path(project_root: Path, *parts: str) -> str:
    host_workspace = os.environ.get("LOCAL_WORKSPACE_FOLDER", "").strip()
    if not host_workspace:
        return str((project_root / "database" / Path(*parts)).resolve())
    separator = "\\" if ntpath.splitdrive(host_workspace)[0] else "/"
    segments = [host_workspace.rstrip("/\\"), "database", *parts]
    return separator.join(segments)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=("ci", "development"),
        default="ci",
        help="CI fixture or a complete fresh development environment",
    )
    args = parser.parse_args(argv)

    docker = shutil.which("docker")
    if docker is None:
        print(
            "Docker CLI was not found. Start Docker and rerun this command.",
            file=sys.stderr,
        )
        return 2

    version = subprocess.run(
        [docker, "version", "--format", "{{.Server.Version}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if version.returncode != 0:
        print(
            "Docker Engine is unavailable. Start Docker and rerun this command.",
            file=sys.stderr,
        )
        return 2

    project_root = Path(__file__).resolve().parents[1]
    run_id = uuid.uuid4().hex
    try:
        return _run_with_temporary_database(
            docker,
            project_root,
            run_id,
            profile=args.profile,
        )
    except KeyboardInterrupt:
        print("PostgreSQL integration tests were interrupted.", file=sys.stderr)
        return 130
    except (DatabaseTestRunnerError, OSError) as error:
        print(f"PostgreSQL integration tests could not start: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
