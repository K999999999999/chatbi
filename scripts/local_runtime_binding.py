"""本机资源绑定格式；只接受原R6资源或已登记恢复对象。"""

import re
from pathlib import PurePosixPath

LEGACY = {
    "format": 1,
    "environment_id": "legacy",
    "postgres_volume": "chatbi_stable_postgres_data",
    "qdrant_volume": "chatbi_stable_qdrant_data",
    "rag_dir": ".local/rag",
    "operations_api_dir": ".local/operations/api",
    "config_file": ".env.local",
    "secrets_file": ".env.local.secrets",
    "release_file": ".local/release.env",
    "database_image": None,
    "database_image_id": None,
}


class BindingInvalid(RuntimeError):
    pass


def restore_binding(restore_id, *, database_image, database_image_id):
    if not isinstance(restore_id, str) or not re.fullmatch("[0-9a-f]{32}", restore_id):
        raise BindingInvalid("BINDING_INVALID")
    if not isinstance(database_image, str) or not re.fullmatch(
        r"chatbi-local-postgres:[A-Za-z0-9_.-]+", database_image
    ):
        raise BindingInvalid("BINDING_INVALID")
    prefix = ".local/operations/restores/" + restore_id
    return {
        "format": 1,
        "environment_id": restore_id,
        "postgres_volume": f"chatbi_restore_{restore_id}_postgres_data",
        "qdrant_volume": f"chatbi_restore_{restore_id}_qdrant_data",
        "rag_dir": prefix + "/rag",
        "operations_api_dir": prefix + "/api",
        "config_file": prefix + "/config.env",
        "secrets_file": prefix + "/secrets.env",
        "release_file": prefix + "/release.env",
        "database_image": database_image,
        "database_image_id": database_image_id,
    }


def validate_binding(value, *, registry=None):
    if (
        not isinstance(value, dict)
        or set(value) != set(LEGACY)
        or type(value["format"]) is not int
        or value["format"] != 1
    ):
        raise BindingInvalid("BINDING_INVALID")
    for key in (
        "environment_id",
        "postgres_volume",
        "qdrant_volume",
        "rag_dir",
        "operations_api_dir",
        "config_file",
        "secrets_file",
        "release_file",
    ):
        if not isinstance(value[key], str):
            raise BindingInvalid("BINDING_INVALID")
    image = value["database_image_id"]
    if image is not None and (
        not isinstance(image, str) or not re.fullmatch("sha256:[0-9a-f]{64}", image)
    ):
        raise BindingInvalid("BINDING_INVALID")
    for key in ("rag_dir", "config_file", "secrets_file", "release_file"):
        path = PurePosixPath(value[key])
        if path.is_absolute() or ".." in path.parts or str(path) != value[key]:
            raise BindingInvalid("BINDING_INVALID")
    environment = value["environment_id"]
    if environment == "legacy":
        if (
            (value["database_image"] is None) != (image is None)
            or (
                value["database_image"] is not None
                and (
                    not isinstance(value["database_image"], str)
                    or not re.fullmatch(
                        r"chatbi-local-postgres:[A-Za-z0-9_.-]+",
                        value["database_image"],
                    )
                )
            )
        ):
            raise BindingInvalid("BINDING_INVALID")
        for key in (
            "postgres_volume",
            "qdrant_volume",
            "rag_dir",
            "operations_api_dir",
            "config_file",
            "secrets_file",
        ):
            if value[key] != LEGACY[key]:
                raise BindingInvalid("BINDING_INVALID")
        if value["release_file"] != ".local/release.env" and not re.fullmatch(
            r"\.local/releases/[0-9a-f]{40}\.env", value["release_file"]
        ):
            raise BindingInvalid("BINDING_INVALID")
    else:
        database_image = value["database_image"]
        expected = restore_binding(
            environment, database_image=database_image, database_image_id=image
        )
        if image is None or value != expected:
            raise BindingInvalid("BINDING_INVALID")
        record = (registry or {}).get(environment)
        if (
            not isinstance(record, dict)
            or type(record.get("format")) is not int
            or record.get("format") != 1
            or not isinstance(record.get("status"), str)
            or record.get("status") not in {"verified", "activated"}
            or record.get("binding") != value
        ):
            raise BindingInvalid("BINDING_INVALID")
    return dict(value)


def validate_volume(binding, kind, metadata, *, project="chatbi-stable"):
    if kind not in {"postgres", "qdrant"}:
        raise BindingInvalid("BINDING_INVALID")
    name = binding[kind + "_volume"]
    if not isinstance(metadata, dict) or metadata.get("Name") != name:
        raise BindingInvalid("BINDING_INVALID")
    labels = metadata.get("Labels") or {}
    if not isinstance(labels, dict):
        raise BindingInvalid("BINDING_INVALID")
    if binding["environment_id"] == "legacy":
        expected = {
            "com.docker.compose.project": project,
            "com.docker.compose.volume": kind + "_data",
        }
    else:
        expected = {
            "com.chatbi.restore-id": binding["environment_id"],
            "com.chatbi.resource-kind": kind,
            "com.chatbi.product": "chatbi-engine",
        }
    if any(labels.get(key) != value for key, value in expected.items()):
        raise BindingInvalid("BINDING_INVALID")


def load_binding(path, *, registry_root):
    import json
    from pathlib import Path

    from scripts.local_backup import secure_file

    path, registry_root = Path(path), Path(registry_root)
    if not path.exists() and not path.is_symlink():
        return dict(LEGACY)
    value = json.loads(secure_file(path))
    registry = {}
    if isinstance(value, dict):
        environment = value.get("environment_id")
        if isinstance(environment, str) and re.fullmatch("[0-9a-f]{32}", environment):
            from scripts.local_restore_state import load_registry_record

            # Registry root passed by the container is /state/operations/restores;
            # load_record expects its parent /state/operations.
            try:
                registry[environment] = load_registry_record(
                    registry_root.parent, environment
                )
            except (OSError, ValueError, TypeError, RuntimeError, ImportError):
                raise BindingInvalid("BINDING_INVALID") from None
    return validate_binding(value, registry=registry)


def binding_environment(binding):
    """仅固定安全字段，供local逐行白名单解析；永不source执行输出。"""
    names = {
        "postgres_volume": "CHATBI_BOUND_POSTGRES_VOLUME",
        "qdrant_volume": "CHATBI_BOUND_QDRANT_VOLUME",
        "rag_dir": "CHATBI_BOUND_RAG_DIR",
        "operations_api_dir": "CHATBI_BOUND_OPERATIONS_API_DIR",
        "config_file": "CHATBI_BOUND_CONFIG_FILE",
        "secrets_file": "CHATBI_BOUND_SECRET_FILE",
        "release_file": "CHATBI_BOUND_RELEASE_FILE",
        "database_image": "CHATBI_BOUND_DATABASE_IMAGE",
        "database_image_id": "CHATBI_BOUND_DATABASE_IMAGE_ID",
        "environment_id": "CHATBI_BOUND_ENVIRONMENT_ID",
    }
    values = {name: binding[key] or "" for key, name in names.items()}
    values["CHATBI_BOUND_OPERATIONS_API_RELATIVE"] = (
        "api"
        if binding["environment_id"] == "legacy"
        else f"restores/{binding['environment_id']}/api"
    )
    return "\n".join(f"{name}={value}" for name, value in values.items()) + "\n"


def main():
    import argparse
    import json
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["resolve", "volume"])
    parser.add_argument("--path", default="/binding.json")
    parser.add_argument("--registry", default="/state/operations/restores")
    parser.add_argument("--kind", choices=["postgres", "qdrant"])
    args = parser.parse_args()
    try:
        binding = load_binding(Path(args.path), registry_root=Path(args.registry))
        if args.action == "resolve":
            print(binding_environment(binding), end="")
        else:
            if args.kind is None:
                raise BindingInvalid("BINDING_INVALID")
            # Docker inspect bytes arrive on stdin from local; tool has no Docker socket.
            data = sys.stdin.buffer.read(1024**2 + 1)
            if len(data) > 1024**2:
                raise BindingInvalid("BINDING_INVALID")
            metadata = json.loads(data)
            validate_volume(binding, args.kind, metadata)
    except (OSError, ValueError, TypeError, RuntimeError):
        print("资源绑定或归属未确认；拒绝操作。", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
