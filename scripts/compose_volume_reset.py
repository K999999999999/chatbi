"""Safely remove and recreate one named volume owned by this Compose project."""

import json
import subprocess
from pathlib import Path


class ComposeVolumeResetError(RuntimeError):
    """A Compose volume reset could not be completed safely."""


def configured_volume(
    compose_config: dict[str, object], volume_key: str
) -> tuple[str, str]:
    project_name = compose_config.get("name")
    volumes = compose_config.get("volumes")
    if not isinstance(project_name, str) or not project_name:
        raise ComposeVolumeResetError("Compose did not report a project name.")
    if not isinstance(volumes, dict):
        raise ComposeVolumeResetError("Compose did not report configured volumes.")

    volume_config = volumes.get(volume_key)
    if not isinstance(volume_config, dict):
        raise ComposeVolumeResetError(f"The {volume_key} volume is not configured.")
    if volume_config.get("external"):
        raise ComposeVolumeResetError(
            f"Refusing to reset an external {volume_key} volume."
        )

    volume_name = volume_config.get("name")
    if not isinstance(volume_name, str) or not volume_name:
        raise ComposeVolumeResetError(
            f"Compose did not resolve the {volume_key} volume name."
        )
    return project_name, volume_name


def validate_volume_labels(
    labels: object,
    *,
    project_name: str,
    volume_key: str,
) -> None:
    if not isinstance(labels, dict):
        raise ComposeVolumeResetError("The volume has no Compose ownership labels.")
    if labels.get("com.docker.compose.project") != project_name:
        raise ComposeVolumeResetError("The volume belongs to another Compose project.")
    if labels.get("com.docker.compose.volume") != volume_key:
        raise ComposeVolumeResetError(
            f"The volume is not the configured {volume_key} volume."
        )


def _run(
    arguments: list[str],
    *,
    project_root: Path,
    operation: str,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        arguments,
        cwd=project_root,
        check=False,
        capture_output=capture_output,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() if capture_output else ""
        suffix = f": {detail}" if detail else ""
        raise ComposeVolumeResetError(
            f"{operation} failed (exit code {result.returncode}){suffix}"
        )
    return result


def _confirm_reset(
    volume_name: str,
    *,
    phrase: str,
    summary: str,
    confirmed: bool,
) -> bool:
    if confirmed:
        return True
    try:
        answer = input(
            f"This deletes {volume_name} ({summary}). Type {phrase} to continue: "
        )
    except EOFError:
        return False
    return answer == phrase


def reset_compose_volume(
    project_root: Path,
    *,
    service: str,
    volume_key: str,
    confirmation_phrase: str,
    deletion_summary: str,
    confirmed: bool,
) -> int:
    version = _run(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        project_root=project_root,
        operation="Checking Docker Engine",
        capture_output=True,
    )
    if not version.stdout.strip():
        raise ComposeVolumeResetError("Docker Engine did not report a server version.")

    config_result = _run(
        ["docker", "compose", "config", "--format", "json"],
        project_root=project_root,
        operation="Resolving the current Compose project",
        capture_output=True,
    )
    try:
        compose_config = json.loads(config_result.stdout)
    except json.JSONDecodeError:
        raise ComposeVolumeResetError(
            "Compose returned invalid configuration JSON."
        ) from None

    project_name, volume_name = configured_volume(compose_config, volume_key)
    volume_result = subprocess.run(
        ["docker", "volume", "inspect", volume_name],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if volume_result.returncode != 0:
        if "no such volume" in volume_result.stderr.lower():
            print(f"No {volume_key} volume exists; nothing to reset.")
            return 0
        raise ComposeVolumeResetError("Could not verify volume ownership.")

    try:
        inspected = json.loads(volume_result.stdout)
        labels = inspected[0]["Labels"]
    except (IndexError, KeyError, TypeError, json.JSONDecodeError):
        raise ComposeVolumeResetError(
            "Docker returned incomplete volume metadata."
        ) from None

    validate_volume_labels(
        labels,
        project_name=project_name,
        volume_key=volume_key,
    )
    if not _confirm_reset(
        volume_name,
        phrase=confirmation_phrase,
        summary=deletion_summary,
        confirmed=confirmed,
    ):
        print(f"{service} data reset cancelled.")
        return 0

    _run(
        ["docker", "compose", "stop", service],
        project_root=project_root,
        operation=f"Stopping this project's {service} service",
    )
    _run(
        ["docker", "compose", "rm", "--force", service],
        project_root=project_root,
        operation=f"Removing this project's {service} container",
    )
    _run(
        ["docker", "volume", "rm", volume_name],
        project_root=project_root,
        operation=f"Removing the verified {volume_key} volume",
    )
    _run(
        ["docker", "compose", "up", "--detach", "--wait", service],
        project_root=project_root,
        operation=f"Recreating this project's {service} service",
    )
    print(f"The {volume_key} volume was recreated.")
    return 0
