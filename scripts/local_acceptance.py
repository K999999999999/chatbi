"""Private, run-scoped configuration for the isolated R6 acceptance project."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
from pathlib import Path


class LocalAcceptanceError(ValueError):
    pass


_RUN_ID = re.compile(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}\Z")
_ENV_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def project_name(run_id: str) -> str:
    if not _RUN_ID.fullmatch(run_id):
        raise LocalAcceptanceError("run ID 格式无效")
    return f"chatbi-r6-accept-{run_id.lower()}"


def acceptance_volume_names(run_id: str) -> tuple[str, str]:
    project_name(run_id)
    suffix = run_id.replace("-", "_")
    return (
        f"chatbi_r6_accept_{suffix}_postgres_data",
        f"chatbi_r6_accept_{suffix}_qdrant_data",
    )


def parse_env_text(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, original in enumerate(text.splitlines(), start=1):
        line = original.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise LocalAcceptanceError(f"本地配置第 {number} 行格式无效")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not _ENV_KEY.fullmatch(key):
            raise LocalAcceptanceError(f"本地配置第 {number} 行键名无效")
        if key in values:
            raise LocalAcceptanceError(f"本地配置存在重复配置项：{key}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            quote = value[0]
            value = value[1:-1]
            if quote == "'":
                value = value.replace("\\'", "'")
            else:
                value = value.replace('\\"', '"').replace("\\\\", "\\")
        if "\0" in value or "\n" in value or "\r" in value:
            raise LocalAcceptanceError(f"本地配置第 {number} 行含无效字符")
        values[key] = value
    return values


def clean_compose_environment(environ: dict[str, str]) -> dict[str, str]:
    blocked_prefixes = (
        "COMPOSE_",
        "CHATBI_",
        "POSTGRES_",
        "LLM_",
        "RAG_",
        "QDRANT_",
        "OTEL_",
    )
    return {
        key: value
        for key, value in environ.items()
        if not key.startswith(blocked_prefixes)
    }


def _env_quote(value: str) -> str:
    if "\n" in value or "\r" in value or "\0" in value:
        raise LocalAcceptanceError("临时 Compose 配置含无效字符")
    return "'" + value.replace("'", "\\'") + "'"


def _write_private(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    content = "".join(f"{key}={_env_quote(value)}\n" for key, value in values.items())
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(content)


def write_acceptance_env_files(
    work_dir: Path,
    *,
    local_values: dict[str, str],
    port: int,
    uid: int,
    gid: int,
    repository: Path | None = None,
    trace_headers: str | None = None,
) -> tuple[Path, Path]:
    if not 1 <= port <= 65535:
        raise LocalAcceptanceError("验收端口无效")
    base = (repository or Path.cwd()).resolve()
    model_value = local_values.get(
        "CHATBI_LOCAL_MODEL_DIR", ".model-cache/bge-m3-5617a9f61b02"
    )
    model_dir = Path(model_value)
    if not model_dir.is_absolute():
        model_dir = base / model_dir
    api_key = local_values.get("LLM_API_KEY", "").strip()
    if not api_key or api_key.lower() in {"replace-me", "your-api-key"}:
        raise LocalAcceptanceError(".env.local 缺少真实 LLM_API_KEY")

    config = {
        "CHATBI_LOCAL_HTTP_PORT": str(port),
        "CHATBI_LOCAL_MODEL_DIR": str(model_dir.resolve()),
        "CHATBI_LOCAL_UID": str(uid),
        "CHATBI_LOCAL_GID": str(gid),
        "CHATBI_LOCAL_SECCOMP_PROFILE": str(
            base / "docker/third-party/playwright-seccomp-profile.json"
        ),
        "POSTGRES_DB": local_values.get("POSTGRES_DB", "chatbi_mvp"),
        "POSTGRES_MIGRATOR_USER": local_values.get(
            "POSTGRES_MIGRATOR_USER", "chatbi_migrator"
        ),
        "LLM_API_KEY": api_key,
        "LLM_BASE_URL": local_values.get("LLM_BASE_URL", "https://api.deepseek.com"),
        "LLM_MODEL": local_values.get("LLM_MODEL", "deepseek-flash"),
        "LLM_TEMPERATURE": local_values.get("LLM_TEMPERATURE", "0.1"),
        "LLM_MAX_TOKENS": local_values.get("LLM_MAX_TOKENS", "4096"),
        "LLM_TIMEOUT_SECONDS": local_values.get("LLM_TIMEOUT_SECONDS", "30"),
    }
    private = {
        "POSTGRES_MIGRATOR_PASSWORD": secrets.token_hex(32),
        "POSTGRES_APP_PASSWORD": secrets.token_hex(32),
        "POSTGRES_CONTROL_APP_PASSWORD": secrets.token_hex(32),
        "CHATBI_ADMIN_SECRET_KEY": secrets.token_hex(32),
        "QDRANT_API_KEY": secrets.token_hex(32),
    }
    if trace_headers is not None:
        from src.observability.config import ObservabilityConfig

        trace_config = ObservabilityConfig.from_env(
            {
                **local_values,
                "CHATBI_RUNTIME_ENV": "stable",
                "OTEL_EXPORTER_OTLP_HEADERS": trace_headers,
            }
        )
        if (
            not trace_config.enabled
            or not trace_config.otlp_endpoint
            or not trace_config.otlp_headers
        ):
            raise LocalAcceptanceError("隔离云端 Trace 缺少安全有效配置")
        config.update(
            {
                "CHATBI_OBSERVABILITY_ENABLED": "true",
                "CHATBI_TRACE_CONTENT_ENABLED": "false",
                "OTEL_SERVICE_NAME": trace_config.service_name,
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": trace_config.otlp_endpoint,
                "CHATBI_OTLP_TIMEOUT_SECONDS": str(trace_config.otlp_timeout_seconds),
            }
        )
        private["OTEL_EXPORTER_OTLP_HEADERS"] = ",".join(
            f"{key}={value}" for key, value in trace_config.otlp_headers.items()
        )
    config_path = work_dir / "acceptance.env"
    secret_path = work_dir / "acceptance.secrets.env"
    _write_private(config_path, config)
    _write_private(secret_path, private)
    return config_path, secret_path


def _yaml_string(value: str | Path) -> str:
    return json.dumps(str(value).replace("$", "$$"), ensure_ascii=False)


def _bind(source: Path, target: str, *, read_only: bool) -> list[str]:
    lines = [
        "      - type: bind",
        f"        source: {_yaml_string(source.resolve())}",
        f"        target: {_yaml_string(target)}",
    ]
    if read_only:
        lines.append("        read_only: true")
    lines.extend(["        bind:", "          create_host_path: false"])
    return lines


def render_compose_override(
    *,
    run_id: str,
    port: int,
    model_dir: Path,
    rag_dir: Path,
    state_dir: Path,
    report_dir: Path,
    tests_dir: Path,
) -> str:
    project_name(run_id)
    postgres_volume, qdrant_volume = acceptance_volume_names(run_id)
    if not 1 <= port <= 65535:
        raise LocalAcceptanceError("验收端口无效")

    lines = ["services:"]
    for service in (
        "postgres",
        "qdrant",
        "migrator",
        "qdrant-check",
    ):
        lines.extend(
            [
                f"  {service}:",
                "    labels:",
                "      com.chatbi.environment: acceptance",
                f"      com.chatbi.acceptance.run_id: {_yaml_string(run_id)}",
            ]
        )

    model_target = "/opt/chatbi-model/bge-m3-5617a9f61b02"
    rag_target = "/opt/chatbi-rag"
    labels = [
        "    labels:",
        "      com.chatbi.environment: acceptance",
        f"      com.chatbi.acceptance.run_id: {_yaml_string(run_id)}",
    ]
    lines.extend(
        [
            "  api:",
            *labels,
            "    ports: !override",
            "      - target: 8000",
            f'        published: "{port}"',
            "        host_ip: 127.0.0.1",
            "        protocol: tcp",
            "    volumes: !override",
            *_bind(model_dir, model_target, read_only=True),
            *_bind(rag_dir, rag_target, read_only=True),
            *_bind(state_dir, "/opt/chatbi-runtime", read_only=False),
            "  model:",
            *labels,
            "    volumes: !override",
            *_bind(model_dir, model_target, read_only=True),
            *_bind(rag_dir, rag_target, read_only=False),
            "  verify:",
            *labels,
            "    volumes: !override",
            *_bind(state_dir, "/opt/chatbi-state", read_only=False),
            *_bind(model_dir, model_target, read_only=True),
            *_bind(rag_dir, rag_target, read_only=True),
            "  admin:",
            *labels,
            "    environment:",
            "      LLM_BASE_URL: ${LLM_BASE_URL:?required}",
            "      LLM_MODEL: ${LLM_MODEL:?required}",
            "      CHATBI_CONTAINER_RAG_MANIFEST_PATH: /opt/chatbi-rag/current.json",
            "    volumes:",
            *_bind(tests_dir, "/workspace/tests", read_only=True),
            *_bind(report_dir, "/reports", read_only=False),
            *_bind(rag_dir, rag_target, read_only=True),
            "volumes:",
            "  postgres_data: !override",
            f"    name: {postgres_volume}",
            "    labels:",
            "      com.chatbi.environment: acceptance",
            f"      com.chatbi.acceptance.run_id: {_yaml_string(run_id)}",
            "  qdrant_data: !override",
            f"    name: {qdrant_volume}",
            "    labels:",
            "      com.chatbi.environment: acceptance",
            f"      com.chatbi.acceptance.run_id: {_yaml_string(run_id)}",
            "",
        ]
    )
    if "chatbi_stable_" in "\n".join(lines):
        raise LocalAcceptanceError("验收 Compose 身份与稳定环境重叠")
    return "\n".join(lines)


def prepare(root: Path, work: Path, run_id: str, port: int) -> None:
    project_name(run_id)
    root = root.resolve()
    work.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.chmod(work, 0o700)
    report = work / "report"
    rag = work / "rag"
    state = work / "state"
    for directory in (report, rag, state):
        directory.mkdir(mode=0o700)
    local_config = root / ".env.local"
    if local_config.stat().st_mode & 0o077:
        raise LocalAcceptanceError(".env.local 权限过宽；需要 chmod 600")
    local_values = parse_env_text(local_config.read_text(encoding="utf-8"))
    trace_headers = None
    if os.getenv("CHATBI_ACCEPTANCE_TRACE_ENABLED") == "1":
        trace_secrets = root / ".env.local.secrets"
        if trace_secrets.stat().st_mode & 0o077:
            raise LocalAcceptanceError(".env.local.secrets 权限过宽；需要 chmod 600")
        trace_headers = parse_env_text(trace_secrets.read_text(encoding="utf-8")).get(
            "OTEL_EXPORTER_OTLP_HEADERS", ""
        )
    config_path, secret_path = write_acceptance_env_files(
        work,
        local_values=local_values,
        port=port,
        uid=os.getuid(),
        gid=os.getgid(),
        repository=root,
        trace_headers=trace_headers,
    )
    model_dir = Path(
        local_values.get("CHATBI_LOCAL_MODEL_DIR", ".model-cache/bge-m3-5617a9f61b02")
    )
    if not model_dir.is_absolute():
        model_dir = root / model_dir
    if not (model_dir / "config.json").is_file():
        raise LocalAcceptanceError("固定 revision Embedding 模型缓存不存在")
    override = render_compose_override(
        run_id=run_id,
        port=port,
        model_dir=model_dir,
        rag_dir=rag,
        state_dir=state,
        report_dir=report,
        tests_dir=root / "tests",
    )
    override_path = work / "compose.acceptance.yml"
    override_path.write_text(override, encoding="utf-8")
    os.chmod(override_path, 0o600)
    if not config_path.is_file() or not secret_path.is_file():
        raise LocalAcceptanceError("验收私有配置未创建")
    print("隔离验收配置已准备；临时凭据不会回显。")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.local_acceptance")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--root", type=Path, required=True)
    prepare_parser.add_argument("--work", type=Path, required=True)
    prepare_parser.add_argument("--run-id", required=True)
    prepare_parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            prepare(args.root, args.work, args.run_id, args.port)
    except (LocalAcceptanceError, OSError) as error:
        print(f"本地部署验收配置失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
