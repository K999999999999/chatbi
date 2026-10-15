"""纯目标校验与CLI委派；不启动真实服务或LLM。"""

import copy
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.dev_compose import (
    maintenance_template,
    map_runtime_paths,
    validate_container,
)

ROOT = Path(__file__).resolve().parents[2]


def test_host_path_mapping_keeps_credentials_literal_when_compose_reads_again(tmp_path):
    config = {
        "name": "test-project",
        "services": {
            "maintenance": {
                "image": "matching-image:local",
                "environment": {"TEST_VALUE": "literal-$$TEST_MARKER-$$$$"},
                "volumes": [
                    {
                        "type": "bind",
                        "source": "/container/repo/src",
                        "target": "/workspace/src",
                        "read_only": True,
                    }
                ],
            }
        },
    }
    mapped = map_runtime_paths(
        config, local_root="/container/repo", host_root="/host/repo"
    )
    assert mapped["services"]["maintenance"]["volumes"][0]["source"] == "/host/repo/src"
    import json

    file = tmp_path / "compose.json"
    file.write_text(json.dumps(mapped))
    result = subprocess.run(
        ["docker", "compose", "-f", str(file), "config", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    environment = json.loads(result.stdout)["services"]["maintenance"]["environment"]
    assert environment["TEST_VALUE"] == "literal-$$TEST_MARKER-$$$$"


def minimal_config():
    return {
        "name": "test-project",
        "services": {
            "tools": {
                "image": "matching-image:local",
                "environment": {
                    "POSTGRES_CONTROL_APP_PASSWORD": "${POSTGRES_CONTROL_APP_PASSWORD:?required}",
                    "LLM_API_KEY": "${LLM_API_KEY:?required}",
                    "QDRANT_API_KEY": "${QDRANT_API_KEY:?required}",
                },
                "volumes": [],
                "depends_on": {"api": {}},
                "build": {"context": "."},
            },
            "migrator": {"environment": {"POSTGRES_MIGRATOR_USER": "test-migrator"}},
        },
    }


def test_recovery_template_preserves_runtime_credentials_without_application_dependencies():
    config = minimal_config()
    before = copy.deepcopy(config)
    result = maintenance_template(config, operation="recover", container_id="a" * 64)
    assert config == before
    service = result["services"]["maintenance"]
    assert service["image"] == "matching-image:local"
    assert service["network_mode"] == "container:" + "a" * 64
    assert "POSTGRES_CONTROL_APP_PASSWORD" in service["environment"]
    assert "LLM_API_KEY" not in service["environment"]
    assert "QDRANT_API_KEY" not in service["environment"]
    assert not any(
        key in service for key in ("build", "depends_on", "privileged", "restart")
    )


@pytest.mark.parametrize("setting", ["env_file", "privileged", "devices", "cap_add"])
def test_unsupported_tool_settings_fail_closed(setting):
    config = minimal_config()
    config["services"]["tools"][setting] = ["unexpected"]
    with pytest.raises(ValueError):
        maintenance_template(config, operation="recover", container_id="a" * 64)


def test_retired_app_container_cannot_be_recovered_as_dev():
    inspected = [
        {
            "Config": {
                "Labels": {
                    "com.docker.compose.project": "test-project",
                    "com.docker.compose.service": "postgres",
                    "com.docker.compose.project.config_files": "/project/docker-compose.app.yml",
                }
            },
            "Mounts": [],
        }
    ]
    with pytest.raises(ValueError, match="退役"):
        validate_container(inspected, project="test-project", service="postgres")


@pytest.mark.parametrize(
    "arguments, expected",
    [
        (["verify", "dev"], "isolated"),
        (["verify", "dev", "isolated"], "isolated"),
        (["verify", "dev", "real"], "real"),
    ],
)
def test_container_acceptance_delegates_mode_and_exit_status(
    tmp_path, arguments, expected
):
    shutil.copy(ROOT / "dev", tmp_path / "dev")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    output = tmp_path / "mode"
    (scripts / "verify_container_dev.sh").write_text(
        '#!/usr/bin/env bash\nprintf "%s" "${1:-isolated}" > "$VERIFY_MODE"\nexit 17\n'
    )
    result = subprocess.run(
        ["bash", str(tmp_path / "dev"), *arguments],
        env={**os.environ, "VERIFY_MODE": str(output)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 17
    assert output.read_text() == expected


def test_hooks_install_is_scoped_to_command_repository(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    subprocess.run(["git", "init", "-q", str(clone)], check=True)
    shutil.copy(ROOT / "dev", clone / "dev")
    (clone / "scripts").mkdir()
    shutil.copy(
        ROOT / "scripts/install_git_hooks.sh", clone / "scripts/install_git_hooks.sh"
    )
    (clone / ".githooks").mkdir()
    hook = clone / ".githooks/pre-commit"
    hook.write_text("#!/bin/sh\nexit 0\n")
    hook.chmod(0o755)
    subprocess.run(
        ["bash", str(clone / "dev"), "hooks", "install"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    result = subprocess.check_output(
        ["git", "-C", str(clone), "config", "--local", "core.hooksPath"], text=True
    )
    assert result.strip() == ".githooks"
    subprocess.run(
        ["git", "-C", str(clone), "config", "--local", "core.hooksPath", "other-hooks"],
        check=True,
    )
    refused = subprocess.run(
        ["bash", str(clone / "dev"), "hooks", "install"],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    assert refused.returncode == 1
    assert (
        subprocess.check_output(
            ["git", "-C", str(clone), "config", "--local", "core.hooksPath"], text=True
        ).strip()
        == "other-hooks"
    )


def test_legacy_operational_compose_is_not_a_development_maintenance_target():
    metadata = [
        {
            "Config": {
                "Labels": {
                    "com.docker.compose.project": "test-project",
                    "com.docker.compose.service": "postgres",
                    "com.docker.compose.project.config_files": "/private/state/stable/compose.yml",
                }
            },
            "Mounts": [],
        }
    ]
    with pytest.raises(ValueError, match="旧运维"):
        validate_container(metadata, project="test-project", service="postgres")


def test_removed_target_flag_rejects_app_before_reading_configuration():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.dev_compose",
            "validate-container",
            "--target",
            "app",
        ],
        input="{}",
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 2
    assert "--target" in result.stderr
