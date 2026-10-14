"""宿主编排的纯JSON配置筛选与资源身份校验；不执行Docker或SQL。"""

import argparse
import json
import re
import sys
from pathlib import PurePosixPath

from scripts.compose_volume_reset import configured_volume, validate_volume_labels

CONTROL_KEYS = {
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_APP_USER",
    "POSTGRES_CONTROL_DB",
    "POSTGRES_CONTROL_APP_USER",
    "POSTGRES_CONTROL_APP_PASSWORD",
}


def map_runtime_paths(config, *, local_root, host_root):
    """已插值配置映射宿主bind；再次提交Compose保持字面美元符号。"""
    for service in config["services"].values():
        for volume in service.get("volumes", []):
            source = volume.get("source", "")
            if volume.get("type") == "bind" and source.startswith(local_root + "/"):
                volume["source"] = host_root + source[len(local_root) :]

    # Compose config已经为再次读取转义美元符号；保持其序列化值。
    return config


def project_name(config):
    name = config.get("name")
    if not isinstance(name, str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9_-]{0,127}", name
    ):
        raise ValueError("项目身份无效")
    return name


def maintenance_template(
    config, *, operation, container_id, target, local_root=None, host_root=None
):
    """剪裁后再交给Compose插值，避免无关LLM强制配置。"""
    project = project_name(config)
    if not re.fullmatch(r"[a-f0-9]{12,64}", container_id):
        raise ValueError("容器身份无效")
    tools = config["services"]["tools"]
    if any(
        tools.get(key)
        for key in ("env_file", "env_from", "privileged", "devices", "cap_add")
    ):
        raise ValueError("不支持的工具配置")
    keys = CONTROL_KEYS.copy()
    if operation == "doctor":
        keys |= {key for key in tools.get("environment", {}) if key.startswith("RAG_")}
        keys |= {"POSTGRES_APP_PASSWORD", "QDRANT_API_KEY"}
    if operation == "metadata":
        keys |= {"POSTGRES_MIGRATOR_USER", "POSTGRES_MIGRATOR_PASSWORD"}
    environment = {k: v for k, v in tools.get("environment", {}).items() if k in keys}
    environment.update(
        {
            k: v
            for k, v in config["services"]["migrator"].get("environment", {}).items()
            if k in {"POSTGRES_MIGRATOR_USER", "POSTGRES_CONTROL_MIGRATOR_USER"}
        }
    )
    if operation == "metadata":
        environment.update(
            {
                k: v
                for k, v in config["services"]["migrator"]["environment"].items()
                if k in keys
            }
        )
    environment.update(
        POSTGRES_HOST="127.0.0.1", POSTGRES_PORT="5432", PYTHONDONTWRITEBYTECODE="1"
    )
    environment["CHATBI_MAINTENANCE_TARGET"] = target
    environment["CHATBI_DEV_WEB_PORT"] = (
        config["services"]
        .get("web", {})
        .get("environment", {})
        .get("CHATBI_DEV_WEB_PORT", "5173")
    )
    service = {
        "image": tools["image"],
        "working_dir": tools.get("working_dir", "/workspace"),
        "user": tools.get("user", "1000:1000"),
        "init": True,
        "entrypoint": ["python"],
        "network_mode": f"container:{container_id}",
        "environment": environment,
        "volumes": [],
    }
    declared_volumes = {}
    for volume in tools.get("volumes", []):
        destination = volume.get("target", "")
        if "docker.sock" in destination or destination in {"/", "/var/run"}:
            raise ValueError("工具绑定越界")
        source_code = destination in {"/workspace/src", "/workspace/scripts"}
        if target == "app" and source_code:
            raise ValueError("标准应用维护必须使用打包代码，拒绝源码覆盖")
        if source_code or operation == "doctor":
            mapped = {**volume, "read_only": True}
            if (
                volume["type"] == "bind"
                and local_root
                and host_root
                and volume["source"].startswith(local_root + "/")
            ):
                mapped["source"] = host_root + volume["source"][len(local_root) :]
            service["volumes"].append(mapped)
            if volume["type"] == "volume":
                declared_volumes[volume["source"]] = config["volumes"][volume["source"]]
    return {
        "name": project,
        "services": {"maintenance": service},
        "volumes": declared_volumes,
    }


def validate_container(inspected, *, project, service, volume=None, target=None):
    if not isinstance(inspected, list) or len(inspected) != 1:
        raise ValueError("容器身份不唯一")
    item = inspected[0]
    labels = item["Config"]["Labels"]
    if (
        labels.get("com.docker.compose.project") != project
        or labels.get("com.docker.compose.service") != service
    ):
        raise ValueError("容器归属不符")
    files = {
        PurePosixPath(value.replace("\\", "/")).name
        for value in labels.get("com.docker.compose.project.config_files", "").split(
            ","
        )
    }
    if target == "dev":
        if "docker-compose.app.yml" in files:
            raise ValueError("标准应用不能作为开发维护目标")
        if not files & {"docker-compose.yml", "docker-compose.dev.yml"}:
            raise ValueError("目标不是受支持的开发Compose；拒绝旧运维资源")
    if target == "app" and (
        "docker-compose.app.yml" not in files or "docker-compose.dev.yml" in files
    ):
        raise ValueError("目标不是标准应用")
    if volume and not any(
        m.get("Name") == volume and m.get("Destination") == "/var/lib/postgresql/data"
        for m in item["Mounts"]
    ):
        raise ValueError("Control DB卷不符")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=(
            "project",
            "volume",
            "template",
            "map-paths",
            "validate-volume",
            "validate-container",
        ),
    )
    parser.add_argument("--key")
    parser.add_argument("--project")
    parser.add_argument("--service")
    parser.add_argument("--volume")
    parser.add_argument(
        "--operation", dest="maintenance", choices=("recover", "doctor", "metadata")
    )
    parser.add_argument("--container")
    parser.add_argument("--target", choices=("dev", "app"))
    parser.add_argument("--local-root")
    parser.add_argument("--host-root")
    args = parser.parse_args()
    try:
        data = json.load(sys.stdin)
        if args.operation == "project":
            print(project_name(data))
        elif args.operation == "volume":
            project, volume = configured_volume(data, args.key)
            if args.key in {"postgres_data", "qdrant_data"}:
                service = args.key.removesuffix("_data")
                destination = (
                    "/var/lib/postgresql/data"
                    if service == "postgres"
                    else "/qdrant/storage"
                )
                if not any(
                    item.get("type") == "volume"
                    and item.get("source") == args.key
                    and item.get("target") == destination
                    for item in data["services"][service].get("volumes", [])
                ):
                    raise ValueError("服务数据卷配置不符")
            if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", volume):
                raise ValueError("数据卷名称无效")
            print(project_name(data), volume)
        elif args.operation == "template":
            print(
                json.dumps(
                    maintenance_template(
                        data,
                        operation=args.maintenance,
                        container_id=args.container,
                        target=args.target,
                        local_root=args.local_root,
                        host_root=args.host_root,
                    )
                )
            )
        elif args.operation == "map-paths":
            print(
                json.dumps(
                    map_runtime_paths(
                        data, local_root=args.local_root, host_root=args.host_root
                    )
                )
            )
        elif args.operation == "validate-container":
            validate_container(
                data,
                project=args.project,
                service=args.service,
                volume=args.volume,
                target=args.target,
            )
        else:
            if len(data) != 1 or data[0]["Name"] != args.volume:
                raise ValueError("数据卷身份不符")
            validate_volume_labels(
                data[0]["Labels"], project_name=args.project, volume_key=args.key
            )
    except Exception:  # noqa: BLE001 - 原配置可能包含Secret
        print("配置或资源身份校验失败；没有授权扩大操作范围。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
