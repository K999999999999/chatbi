from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATE_HELPER = ROOT / "scripts" / "local_deployment_state.sh"
RELEASE_FIELDS = (
    "a" * 40,
    "chatbi-local-api:test",
    "sha256:" + "1" * 64,
    "chatbi-local-postgres:test",
    "sha256:" + "2" * 64,
)


@pytest.mark.parametrize("role", ["active", "baseline"])
def test_release_state_arguments_keep_their_explicit_role(role: str) -> None:
    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                'source "$1"; state_args=(); '
                'append_deployment_release_arguments state_args "$2" "${@:3}"; '
                'printf "%s\\n" "${state_args[@]}"'
            ),
            "test-local-deployment-state",
            str(STATE_HELPER),
            role,
            *RELEASE_FIELDS,
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        f"--{role}-source-commit",
        RELEASE_FIELDS[0],
        f"--{role}-api-image",
        RELEASE_FIELDS[1],
        f"--{role}-api-image-id",
        RELEASE_FIELDS[2],
        f"--{role}-database-runtime-image",
        RELEASE_FIELDS[3],
        f"--{role}-database-runtime-image-id",
        RELEASE_FIELDS[4],
    ]


def test_release_state_arguments_reject_unknown_role() -> None:
    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                'source "$1"; state_args=(); '
                'append_deployment_release_arguments state_args invalid "${@:3}"'
            ),
            "test-local-deployment-state",
            str(STATE_HELPER),
            *RELEASE_FIELDS,
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 2
