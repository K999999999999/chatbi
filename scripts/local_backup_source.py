"""工具读取 local 在锁内捕获的 Docker 元数据；不持 Docker socket。"""

import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from scripts.local_backup import (
    BackupFailed,
    atomic_json,
    secure_directory,
    secure_file,
)


def capture(raw, destination, *, project="chatbi-stable"):
    raw, destination = Path(raw), secure_directory(destination)
    api = json.loads(secure_file(raw / "api.json"))
    database = json.loads(secure_file(raw / "postgres.json"))
    for container, service in ((api, "api"), (database, "postgres")):
        labels = container["Config"]["Labels"]
        if (
            not container["State"]["Running"]
            or labels.get("com.docker.compose.project") != project
            or labels.get("com.docker.compose.service") != service
            or not re.fullmatch("sha256:[0-9a-f]{64}", container["Image"])
        ):
            raise BackupFailed("BACKUP_SOURCE_CHANGED")
    source = api["Config"]["Labels"].get("org.opencontainers.image.revision", "")
    release = json.loads(secure_file(raw / "release.json"))
    if (
        not re.fullmatch("[0-9a-f]{40}", source)
        or release.get("source_commit") != source
    ):
        raise BackupFailed("BACKUP_SOURCE_CHANGED")
    env = dict(item.split("=", 1) for item in api["Config"]["Env"] if "=" in item)
    capabilities = json.loads(secure_file(raw / "capabilities.json"))
    if (
        not isinstance(capabilities, dict)
        or set(capabilities) != {"operations_status"}
        or type(capabilities["operations_status"]) is not bool
    ):
        raise BackupFailed("BACKUP_SOURCE_CHANGED")
    config = secure_file(raw / "config.env")
    secrets = secure_file(raw / "secrets.env")
    if not config or not secrets:
        raise BackupFailed("BACKUP_SOURCE_CHANGED")
    for line in (config + b"\n" + secrets).decode().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                quote = value[0]
                value = value[1:-1]
                if quote == "'":
                    value = value.replace("\\'", "'")
                else:
                    value = value.replace('\\"', '"').replace("\\\\", "\\")
            if key in env and value != env[key]:
                raise BackupFailed("BACKUP_SOURCE_CHANGED")
    pointer = secure_file(raw / "rag-current.json")
    value = json.loads(pointer)
    ref = Path(value["manifest_path"])
    if ref.is_absolute() or ".." in ref.parts:
        raise BackupFailed("BACKUP_SOURCE_CHANGED")
    manifest = secure_file(raw / "rag-manifest.json")
    if not isinstance(json.loads(manifest), dict):
        raise BackupFailed("BACKUP_SOURCE_CHANGED")
    compatibility = secure_file(raw / "compatibility.json")
    if not isinstance(json.loads(compatibility), dict):
        raise BackupFailed("BACKUP_SOURCE_CHANGED")
    identity = {
        "format": 1,
        "source_commit": source,
        "api_image": api["Config"]["Image"],
        "api_image_id": api["Image"],
        "database_image": database["Config"]["Image"],
        "database_image_id": database["Image"],
        "captured_at": datetime.now(UTC).isoformat(),
        "live_required": capabilities["operations_status"],
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
    identity_path = destination / "identity.json"
    if identity_path.exists():
        secure_file(identity_path)
        identity_path.unlink()
    # A partial source update has no published identity and cannot seed another backup.
    for name, data in files.items():
        target = destination / name
        if target.exists():
            secure_file(target)
        fd, temporary = tempfile.mkstemp(dir=destination, prefix=".pending-")
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
    atomic_json(destination / "identity.json", identity)
    return identity
