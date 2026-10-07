"""Deterministic checks used by the fixed-version local deployment."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit


class LocalReleaseError(RuntimeError):
    """A local release precondition is missing or unsafe."""


_STATIC_IDENTITY_KEYS = (
    "CHATBI_IDENTITY_PROVIDER",
    "CHATBI_IDENTITY_SUBJECT_ID",
    "CHATBI_AUTH_POLICY_FILE",
)
_MIGRATOR_KEYS = (
    "POSTGRES_MIGRATOR_USER",
    "POSTGRES_MIGRATOR_PASSWORD",
    "POSTGRES_CONTROL_MIGRATOR_USER",
)
_FALSE_VALUES = {"0", "false", "no", "off"}


def validate_api_environment(environ: dict[str, str]) -> None:
    """Reject settings that escape the approved local runtime boundary."""

    if environ.get("CHATBI_ENV", "").strip().lower() != "development":
        raise LocalReleaseError("CHATBI_ENV 必须固定为 development")

    secret = environ.get("CHATBI_ADMIN_SECRET_KEY", "").strip()
    if len(secret) < 32:
        raise LocalReleaseError("CHATBI_ADMIN_SECRET_KEY 必须至少 32 个字符")

    port = environ.get("CHATBI_LOCAL_HTTP_PORT", "").strip()
    try:
        parsed_port = int(port)
    except ValueError:
        raise LocalReleaseError("CHATBI_LOCAL_HTTP_PORT 必须是有效端口") from None
    if not 1 <= parsed_port <= 65535:
        raise LocalReleaseError("CHATBI_LOCAL_HTTP_PORT 必须是有效端口")

    origin = environ.get("CHATBI_WEB_ORIGIN", "").strip()
    expected_origin = f"http://127.0.0.1:{parsed_port}"
    if origin != expected_origin:
        raise LocalReleaseError(
            "CHATBI_WEB_ORIGIN 必须与仅回环访问的稳定环境端口完全一致"
        )

    if not environ.get("CHATBI_WEB_DIST_DIR", "").strip():
        raise LocalReleaseError("CHATBI_WEB_DIST_DIR 必须指向镜像内网页")

    api_key = environ.get("LLM_API_KEY", "").strip()
    if not api_key or api_key.lower() in {"replace-me", "change-me", "your-api-key"}:
        raise LocalReleaseError("请在独立稳定配置中填写外部 LLM_API_KEY")
    if not environ.get("LLM_MODEL", "").strip():
        raise LocalReleaseError("LLM_MODEL 不能为空")

    expected_database = {
        "POSTGRES_HOST": "postgres",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "chatbi_mvp",
        "POSTGRES_APP_USER": "chatbi_app",
        "POSTGRES_CONTROL_DB": "chatbi_control",
        "POSTGRES_CONTROL_APP_USER": "chatbi_control_user",
    }
    for key, expected in expected_database.items():
        if environ.get(key, "").strip() != expected:
            raise LocalReleaseError(f"{key} 不符合独立稳定数据库配置")
    for key in ("POSTGRES_APP_PASSWORD", "POSTGRES_CONTROL_APP_PASSWORD"):
        if not environ.get(key, "").strip():
            raise LocalReleaseError(f"缺少 {key} 配置")

    for key in _STATIC_IDENTITY_KEYS:
        if environ.get(key, "").strip():
            raise LocalReleaseError(f"稳定环境不能使用 {key}")
    for key in _MIGRATOR_KEYS:
        if key in environ:
            raise LocalReleaseError(f"迁移凭据不得进入 API：{key}")

    if environ.get("RAG_ONLINE_RETRIEVAL_ENABLED", "").strip().lower() not in {
        "true",
        "1",
        "yes",
        "on",
    }:
        raise LocalReleaseError("RAG_ONLINE_RETRIEVAL_ENABLED 必须启用")
    if environ.get("RAG_EMBEDDING_DEVICE", "").strip().lower() != "cpu":
        raise LocalReleaseError("RAG_EMBEDDING_DEVICE 必须固定使用 CPU")
    if environ.get("RAG_EMBEDDING_USE_FP16", "").strip().lower() not in _FALSE_VALUES:
        raise LocalReleaseError("RAG_EMBEDDING_USE_FP16 必须关闭以使用 FP32")
    if environ.get("RAG_QDRANT_URL", "").strip() != "http://qdrant:6333":
        raise LocalReleaseError("RAG_QDRANT_URL 必须位于独立 Compose 网络")
    if not environ.get("RAG_QDRANT_API_KEY", "").strip():
        raise LocalReleaseError("缺少独立稳定 Qdrant 密钥")
    for key in ("RAG_MODEL_DIR", "RAG_OUTPUT_DIR"):
        if not Path(environ.get(key, "").strip()).is_absolute():
            raise LocalReleaseError(f"{key} 必须是容器内绝对路径")


def wait_for_qdrant(environ: dict[str, str], *, timeout_seconds: float = 60) -> None:
    """Wait until the private Qdrant TCP endpoint accepts connections."""

    try:
        parsed = urlsplit(environ.get("RAG_QDRANT_URL", "").strip())
        port = parsed.port
    except ValueError:
        raise LocalReleaseError("RAG_QDRANT_URL 配置无效") from None
    if (
        parsed.scheme != "http"
        or parsed.hostname != "qdrant"
        or port != 6333
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise LocalReleaseError("RAG_QDRANT_URL 配置无效")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((parsed.hostname, port), timeout=1):
                print("Qdrant 私有端口已接受连接。")
                return
        except OSError:
            time.sleep(1)
    raise LocalReleaseError("等待 Qdrant 超时；请检查本稳定环境的服务日志。")


def verify_runtime(environ: dict[str, str]) -> None:
    """Run the existing catalog and production RAG gates before local startup."""

    validate_api_environment(environ)
    source_commit = environ.get("CHATBI_SOURCE_COMMIT", "").strip()
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise LocalReleaseError("镜像来源 commit 缺失或无效")
    try:
        release = json.loads(Path("/opt/chatbi-release.json").read_text())
    except (OSError, json.JSONDecodeError):
        raise LocalReleaseError("镜像缺少有效 /opt/chatbi-release.json") from None
    if (
        not isinstance(release, dict)
        or release.get("format") != 1
        or release.get("source_commit") != source_commit
    ):
        raise LocalReleaseError("当前 API 镜像与选定 source commit 不匹配")

    web_root = Path(environ["CHATBI_WEB_DIST_DIR"])
    if not (web_root / "index.html").is_file() or not (web_root / "assets").is_dir():
        raise LocalReleaseError("镜像内网页构建不完整；请重新构建固定版本镜像")
    model_root = Path(environ["RAG_MODEL_DIR"])
    if not (model_root / "config.json").is_file():
        raise LocalReleaseError("固定 revision Embedding 模型未准备；运行 ./local prepare-model")
    rag_root = Path(environ["RAG_OUTPUT_DIR"])
    if not (rag_root / "current.json").is_file():
        raise LocalReleaseError("稳定环境 RAG 索引未准备；运行 ./local build-rag")

    migration_error_type = None
    try:
        from sqlalchemy import text

        from src.chatbi_control.database import (
            ControlDatabaseConfig,
            ControlDatabaseMigrationError,
            create_control_engine,
            verify_control_schema,
        )
        migration_error_type = ControlDatabaseMigrationError
        from src.online_query.database import PsycopgQueryExecutor
        from src.online_query.retrieval.rag_runtime import RagRuntime
        from src.query_api.export_assets import verify_runtime_manifest
        from src.rag_offline.config import OfflineBuildConfig

        verify_runtime_manifest(Path("/opt/chatbi-export"))

        database = ControlDatabaseConfig.from_environment(require_migrator=False)
        engine = create_control_engine(database)
        try:
            verify_control_schema(engine)
            with engine.connect() as connection:
                has_admin = connection.execute(
                    text("SELECT EXISTS (SELECT 1 FROM users)")
                ).scalar_one()
            if not has_admin:
                raise LocalReleaseError("尚无管理员；运行 ./local create-admin")
        finally:
            engine.dispose()

        executor = PsycopgQueryExecutor.from_env(environ)
        runtime = RagRuntime(
            OfflineBuildConfig.from_environment(), production_mode=True
        )
        try:
            runtime.verify_production_ready(executor.verify_structure_metadata)
        finally:
            runtime.close()
    except LocalReleaseError:
        raise
    except Exception as error:  # noqa: BLE001 - never print configuration or secrets
        if migration_error_type is not None and isinstance(
            error, migration_error_type
        ):
            raise LocalReleaseError(
                "稳定环境应用库尚未完成 migration；请先运行 ./local migrate。"
            ) from None
        raise LocalReleaseError(
            f"本地运行资产/数据库前置检查失败（{type(error).__name__}）；"
            "请检查 migration、模型、索引及本稳定环境依赖。"
        ) from None

    print(
        "本地启动前置检查通过：镜像身份、网页、导出资产、管理员、"
        "PostgreSQL catalog 与固定来源 RAG 索引均已核验。"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.local_release")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify-runtime", help="校验稳定环境启动前置条件")
    commands.add_parser("wait-qdrant", help="等待本稳定项目内的 Qdrant 端口")
    args = parser.parse_args(argv)
    try:
        if args.command == "verify-runtime":
            verify_runtime(dict(os.environ))
        else:
            wait_for_qdrant(dict(os.environ))
    except LocalReleaseError as error:
        print(f"本地发布检查失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
