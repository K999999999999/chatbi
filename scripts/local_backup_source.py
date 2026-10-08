"""由持锁 local 进程捕获实际 Docker 运行身份；敏感 stdout 仅留内存。"""

import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from scripts.local_backup import (
    BackupFailed,
    atomic_json,
    secure_directory,
    secure_file,
)


def docker(*args):
    try:
        return subprocess.run(
            ["docker", *args], capture_output=True, check=True, timeout=30
        ).stdout
    except (OSError, subprocess.SubprocessError):
        raise BackupFailed("BACKUP_SOURCE_CHANGED") from None


def container(project, service):
    ids = (
        docker(
            "ps",
            "-q",
            "--filter",
            f"label=com.docker.compose.project={project}",
            "--filter",
            f"label=com.docker.compose.service={service}",
        )
        .decode()
        .split()
    )
    if len(ids) != 1:
        raise BackupFailed("BACKUP_SOURCE_CHANGED")
    value = json.loads(docker("inspect", ids[0]))[0]
    if not value["State"]["Running"]:
        raise BackupFailed("BACKUP_SOURCE_CHANGED")
    return value


def capture(root, *, project="chatbi-stable"):
    root = Path(root)
    operations = secure_directory(root / ".local" / "operations")
    destination = secure_directory(operations / "source")
    api, database = container(project, "api"), container(project, "postgres")
    source = api["Config"]["Labels"].get("org.opencontainers.image.revision", "")
    release = json.loads(docker("exec", api["Id"], "cat", "/opt/chatbi-release.json"))
    if (
        not re.fullmatch("[0-9a-f]{40}", source)
        or release.get("source_commit") != source
    ):
        raise BackupFailed("BACKUP_SOURCE_CHANGED")
    env = dict(item.split("=", 1) for item in api["Config"]["Env"] if "=" in item)
    # Confirm the dedicated config still describes the active runtime, not a new target.
    config = secure_file(root / ".env.local")
    secrets = secure_file(root / ".env.local.secrets")
    for line in (config + b"\n" + secrets).decode().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            if key in env and value != env[key]:
                raise BackupFailed("BACKUP_SOURCE_CHANGED")
    rag = root / ".local" / "rag"
    pointer = (rag / "current.json").read_bytes()
    value = json.loads(pointer)
    manifest_ref = Path(value["manifest_path"])
    if manifest_ref.is_absolute() or ".." in manifest_ref.parts:
        raise BackupFailed("BACKUP_SOURCE_CHANGED")
    manifest_path = rag / manifest_ref
    if manifest_path.is_symlink() or not manifest_path.resolve().is_relative_to(
        rag.resolve()
    ):
        raise BackupFailed("BACKUP_SOURCE_CHANGED")
    manifest = manifest_path.read_bytes()
    compatibility = docker("exec", api["Id"], "cat", "/opt/chatbi-compatibility.json")
    identity = {
        "format": 1,
        "source_commit": source,
        "api_image": api["Config"]["Image"],
        "api_image_id": api["Image"],
        "database_image": database["Config"]["Image"],
        "database_image_id": database["Image"],
        "captured_at": datetime.now(UTC).isoformat(),
        "live_required": bool(env.get("CHATBI_OPERATIONS_SOCKET_PATH")),
        "asset_sha256": {
            "rag-current.json": hashlib.sha256(pointer).hexdigest(),
            "rag-manifest.json": hashlib.sha256(manifest).hexdigest(),
        },
    }
    release_env = "\n".join(
        [
            f"CHATBI_SOURCE_COMMIT={source}",
            f"CHATBI_API_IMAGE={identity['api_image']}",
            f"CHATBI_API_IMAGE_ID={api['Image']}",
            f"CHATBI_DATABASE_IMAGE={identity['database_image']}",
            f"CHATBI_DATABASE_IMAGE_ID={database['Image']}",
            "",
        ]
    ).encode()
    files = {
        "config.env": config,
        "secrets.env": secrets,
        "release.env": release_env,
        "rag-current.json": pointer,
        "rag-manifest.json": manifest,
        "compatibility.json": compatibility,
    }
    for name, data in files.items():
        if len(data) > 1024**2:
            raise BackupFailed("BACKUP_SOURCE_CHANGED")
        target = destination / name
        # Only replace known source filenames inside the private owned directory.
        if target.exists():
            secure_file(target)
        temporary = destination / (".pending-" + name)
        fd = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        )
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    # Last identity write publishes a complete capture; interrupted captures never get used.
    atomic_json(destination / "identity.json", identity)
    return identity


def main():
    import sys

    os.umask(0o077)
    try:
        capture(Path(sys.argv[1]))
    except (BackupFailed, OSError, ValueError, KeyError):
        print("备份来源未确认；拒绝备份。", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
