"""Deterministic checks used by the fixed-version local deployment."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import tempfile
import time
from datetime import UTC, datetime
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
_COMPATIBILITY_PROFILE_KEYS = {
    "format",
    "compatibility_id",
    "control_migrations",
    "checkpoint_migrations",
    "business_seed_versions",
    "business_catalog_schema_metadata_sha256",
    "history_snapshot_versions",
    "rag_pointer_schema_versions",
    "rag_manifest_schema_versions",
    "rag_model_revision",
    "rag_embedding_dimension",
    "rag_provenance",
}


def validate_compatibility_profile(profile: dict[str, object]) -> None:
    """Reject incomplete or internally inconsistent image compatibility claims."""

    if (
        not isinstance(profile, dict)
        or type(profile.get("format")) is not int
        or profile.get("format") != 1
    ):
        raise LocalReleaseError("兼容性声明格式不受支持")
    if set(profile) != _COMPATIBILITY_PROFILE_KEYS:
        raise LocalReleaseError("兼容性声明字段缺失或未知")
    compatibility_id = profile.get("compatibility_id")
    if (
        not isinstance(compatibility_id, str)
        or re.fullmatch(r"[A-Za-z0-9._-]{1,80}", compatibility_id) is None
    ):
        raise LocalReleaseError("兼容性声明 ID 无效")

    control = profile.get("control_migrations")
    if not isinstance(control, dict) or set(control) != {"required", "allowed"}:
        raise LocalReleaseError("兼容性声明的 control migrations 无效")
    _validate_declared_set(
        control["required"], control["allowed"], str, "control migrations"
    )

    checkpoint = profile.get("checkpoint_migrations")
    if not isinstance(checkpoint, dict) or set(checkpoint) != {
        "required",
        "allowed",
    }:
        raise LocalReleaseError("兼容性声明的 checkpoint migrations 无效")
    _validate_declared_set(
        checkpoint["required"],
        checkpoint["allowed"],
        int,
        "checkpoint migrations",
    )

    for key, label in (
        ("business_seed_versions", "Sales Mart Seed"),
        ("history_snapshot_versions", "snapshot"),
        ("rag_pointer_schema_versions", "RAG current pointer"),
        ("rag_manifest_schema_versions", "RAG manifest"),
    ):
        value = profile.get(key)
        expected_type = str if key == "business_seed_versions" else int
        _validate_nonempty_unique_list(value, expected_type, label)

    revision = profile.get("rag_model_revision")
    if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise LocalReleaseError("兼容性声明的 Embedding model revision 无效")
    dimension = profile.get("rag_embedding_dimension")
    if type(dimension) is not int or dimension <= 0:
        raise LocalReleaseError("兼容性声明的 Embedding dimension 无效")
    catalog_hash = profile.get("business_catalog_schema_metadata_sha256")
    if not isinstance(catalog_hash, str) or re.fullmatch(r"[0-9a-f]{64}", catalog_hash) is None:
        raise LocalReleaseError("兼容性声明的 business catalog 指纹无效")
    provenance = profile.get("rag_provenance")
    expected_provenance_keys = {
        "schema_metadata_sha256",
        "metrics_sha256",
        "embedding_config_sha256",
        "source_sha256",
    }
    if not isinstance(provenance, dict) or set(provenance) != expected_provenance_keys:
        raise LocalReleaseError("兼容性声明的 RAG provenance 无效")
    if any(
        not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
        for value in provenance.values()
    ):
        raise LocalReleaseError("兼容性声明的 RAG provenance 指纹无效")
    if provenance["schema_metadata_sha256"] != catalog_hash:
        raise LocalReleaseError(
            "兼容性声明的 business catalog 与 RAG schema metadata 指纹不一致"
        )


def validate_compatibility_state(
    profile: dict[str, object], state: dict[str, object]
) -> None:
    """Fail closed unless every persisted compatibility marker is declared."""

    validate_compatibility_profile(profile)
    if not isinstance(state, dict):
        raise LocalReleaseError("无法读取持久化兼容状态")

    control = profile["control_migrations"]
    assert isinstance(control, dict)
    actual_control = _actual_set(state.get("control_migrations"), str, "control migration")
    allowed_control = set(control["allowed"])
    if not set(control["required"]).issubset(actual_control):
        raise LocalReleaseError("Control DB 缺少声明要求的 required migrations")
    if not actual_control.issubset(allowed_control):
        raise LocalReleaseError("存在未知或不兼容的 control migration marker")

    checkpoint = profile["checkpoint_migrations"]
    assert isinstance(checkpoint, dict)
    actual_checkpoint = _actual_set(
        state.get("checkpoint_migrations"), int, "checkpoint migration"
    )
    allowed_checkpoint = set(checkpoint["allowed"])
    if not set(checkpoint["required"]).issubset(actual_checkpoint):
        raise LocalReleaseError("Control DB 缺少声明要求的 required checkpoint migrations")
    if not actual_checkpoint.issubset(allowed_checkpoint):
        raise LocalReleaseError("存在未知或不兼容的 checkpoint migration marker")

    seed_version = state.get("business_seed_version")
    if not isinstance(seed_version, str) or seed_version not in profile[
        "business_seed_versions"
    ]:
        raise LocalReleaseError("Sales Mart Seed 版本未被此发布声明兼容")
    if state.get("catalog_verified") is not True:
        raise LocalReleaseError("PostgreSQL catalog 未通过只读结构核对")
    if state.get("catalog_schema_metadata_sha256") != profile[
        "business_catalog_schema_metadata_sha256"
    ]:
        raise LocalReleaseError("business catalog schema metadata 指纹不兼容")

    snapshot_versions = _actual_set(
        state.get("history_snapshot_versions"), int, "snapshot"
    )
    if not snapshot_versions.issubset(set(profile["history_snapshot_versions"])):
        raise LocalReleaseError("历史快照含有未知或不兼容的 snapshot version")

    pointer_version = state.get("rag_pointer_schema_version")
    if (
        type(pointer_version) is not int
        or pointer_version not in profile["rag_pointer_schema_versions"]
    ):
        raise LocalReleaseError("RAG current pointer schema version 不兼容")
    manifest_version = state.get("rag_manifest_schema_version")
    if (
        type(manifest_version) is not int
        or manifest_version not in profile["rag_manifest_schema_versions"]
    ):
        raise LocalReleaseError("RAG manifest schema version 不兼容")
    model_revision = state.get("rag_model_revision")
    if not isinstance(model_revision, str) or model_revision != profile[
        "rag_model_revision"
    ]:
        raise LocalReleaseError("RAG Embedding model revision 不兼容")
    dimension = state.get("rag_embedding_dimension")
    if (
        type(dimension) is not int
        or dimension != profile["rag_embedding_dimension"]
    ):
        raise LocalReleaseError("RAG Embedding dimension 不兼容")
    if state.get("rag_provenance_verified") is not True:
        raise LocalReleaseError("RAG provenance 未通过来源与 catalog 只读核对")
    if state.get("rag_provenance") != profile["rag_provenance"]:
        raise LocalReleaseError("RAG provenance 不匹配此发布的已声明输入")


def _validate_declared_set(
    required: object, allowed: object, value_type: type, label: str
) -> None:
    required_values = _validate_nonempty_unique_list(required, value_type, label)
    allowed_values = _validate_nonempty_unique_list(allowed, value_type, label)
    if not set(required_values).issubset(allowed_values):
        raise LocalReleaseError(f"兼容性声明 required {label} 不在 allowed 集合中")


def _validate_nonempty_unique_list(
    value: object, value_type: type, label: str
) -> list[object]:
    if not isinstance(value, list) or not value:
        raise LocalReleaseError(f"兼容性声明的 {label} 必须是非空列表")
    if any(type(item) is not value_type for item in value) or len(set(value)) != len(
        value
    ):
        raise LocalReleaseError(f"兼容性声明的 {label} 含非法或重复值")
    if value_type is str and any(not item.strip() for item in value):
        raise LocalReleaseError(f"兼容性声明的 {label} 含空值")
    if value_type is int and any(item < 0 for item in value):
        raise LocalReleaseError(f"兼容性声明的 {label} 含负数")
    return value


def _actual_set(value: object, value_type: type, label: str) -> set[object]:
    if not isinstance(value, list) or any(type(item) is not value_type for item in value):
        raise LocalReleaseError(f"无法读取实际 {label} 状态")
    return set(value)


def validate_snapshot_rows(rows: list[tuple[object, object]]) -> list[int]:
    """Check the persisted history column and its JSON envelope agree."""

    versions: set[int] = set()
    for column_version, payload_version in rows:
        if (
            type(column_version) is not int
            or not isinstance(payload_version, str)
            or re.fullmatch(r"[0-9]+", payload_version) is None
            or int(payload_version) != column_version
        ):
            raise LocalReleaseError(
                "历史 snapshot version 列与 JSON payload 不一致或无效"
            )
        versions.add(column_version)
    return sorted(versions)


def load_compatibility_profile(path: Path = Path("/opt/chatbi-compatibility.json")) -> dict:
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise LocalReleaseError("发布镜像缺少有效兼容性声明") from None
    validate_compatibility_profile(profile)
    return profile


def update_deployment_state(
    path: Path,
    *,
    event: str,
    operation: str,
    target_commit: str | None,
    phase: str,
    runtime_status: str,
    active_release: dict[str, str] | None = None,
    baseline_active_release: dict[str, str] | None = None,
) -> dict[str, object]:
    """Atomically retain the last successful release and the actual last stage."""

    if event not in {"begin", "phase", "succeeded", "failed", "stopped"}:
        raise LocalReleaseError("部署状态 event 无效")
    if operation not in {"up", "upgrade", "rollback", "down"}:
        raise LocalReleaseError("部署状态 operation 无效")
    if target_commit is not None and re.fullmatch(r"[0-9a-f]{40}", target_commit) is None:
        raise LocalReleaseError("部署状态 target commit 无效")
    if event != "stopped" and target_commit is None:
        raise LocalReleaseError("部署状态缺少 target commit")
    if re.fullmatch(r"[a-z][a-z0-9-]{0,47}", phase) is None:
        raise LocalReleaseError("部署状态 phase 无效")
    if runtime_status not in {"unknown", "running", "transitioning", "stopped", "unhealthy"}:
        raise LocalReleaseError("部署状态 runtime status 无效")
    if event == "succeeded" and runtime_status != "running":
        raise LocalReleaseError("成功部署必须记录 running 状态")
    if event == "failed" and runtime_status not in {"unknown", "stopped", "unhealthy"}:
        raise LocalReleaseError("失败部署必须记录真实非运行状态")

    path = Path(path)
    current = _read_deployment_state(path)
    state: dict[str, object] = (
        current
        if current is not None
        else {
            "format": 1,
            "active_release": None,
            "runtime_status": "unknown",
            "last_operation": None,
        }
    )
    if baseline_active_release is not None:
        _validate_active_release(baseline_active_release)
        existing_active = state.get("active_release")
        if existing_active is None:
            state["active_release"] = baseline_active_release
        elif existing_active != baseline_active_release:
            raise LocalReleaseError("本机 active release 与正在运行的旧 API 身份不一致")

    if (
        event == "begin"
        and operation in {"upgrade", "rollback"}
        and state.get("active_release") is None
    ):
        raise LocalReleaseError("没有已成功运行的 active release；先运行 ./local up")

    last = state.get("last_operation")
    if event in {"phase", "succeeded", "failed"} and (
            not isinstance(last, dict)
            or last.get("operation") != operation
            or last.get("target_commit") != target_commit
            or last.get("result") != "in-progress"
    ):
        raise LocalReleaseError("部署状态没有匹配的 in-progress 操作")
    if event == "stopped":
        state["runtime_status"] = "stopped"
        state["last_operation"] = {
            "operation": "down",
            "target_commit": None,
            "phase": "stopped",
            "result": "stopped",
            "updated_at": _utc_timestamp(),
        }
    else:
        if event == "begin":
            state["last_operation"] = {
                "operation": operation,
                "target_commit": target_commit,
                "phase": phase,
                "result": "in-progress",
                "updated_at": _utc_timestamp(),
            }
        else:
            assert isinstance(last, dict)
            last = dict(last)
            last["phase"] = phase
            last["updated_at"] = _utc_timestamp()
            if event in {"succeeded", "failed"}:
                last["result"] = event
            state["last_operation"] = last
        state["runtime_status"] = runtime_status

    if event == "succeeded":
        if active_release is None:
            raise LocalReleaseError("成功部署缺少 active release 身份")
        _validate_active_release(active_release)
        if active_release["source_commit"] != target_commit:
            raise LocalReleaseError("active release 与目标 commit 不一致")
        state["active_release"] = active_release
    elif active_release is not None:
        raise LocalReleaseError("只有成功部署可以替换 active release")

    _write_deployment_state(path, state)
    return state


def _read_deployment_state(path: Path) -> dict[str, object] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError):
        raise LocalReleaseError("本机部署状态文件无法安全读取") from None
    try:
        state = json.loads(raw)
    except json.JSONDecodeError:
        raise LocalReleaseError("本机部署状态文件不是有效 JSON") from None
    if (
        not isinstance(state, dict)
        or type(state.get("format")) is not int
        or state.get("format") != 1
        or set(state) != {"format", "active_release", "runtime_status", "last_operation"}
    ):
        raise LocalReleaseError("本机部署状态文件格式未知；拒绝覆盖")
    if state["active_release"] is not None:
        _validate_active_release(state["active_release"])
    if not isinstance(state["runtime_status"], str) or state["runtime_status"] not in {
        "unknown",
        "running",
        "transitioning",
        "stopped",
        "unhealthy",
    }:
        raise LocalReleaseError("本机部署状态含未知 runtime status；拒绝覆盖")
    last = state["last_operation"]
    if last is not None:
        if (
            not isinstance(last, dict)
            or set(last)
            != {"operation", "target_commit", "phase", "result", "updated_at"}
        ):
            raise LocalReleaseError("本机部署状态含未知操作阶段；拒绝覆盖")
        if (
            not isinstance(last["operation"], str)
            or last["operation"] not in {"up", "upgrade", "rollback", "down"}
            or not isinstance(last["result"], str)
            or last["result"] not in {"in-progress", "succeeded", "failed", "stopped"}
            or not isinstance(last["phase"], str)
            or re.fullmatch(r"[a-z][a-z0-9-]{0,47}", last["phase"]) is None
            or not isinstance(last["updated_at"], str)
        ):
            raise LocalReleaseError("本机部署状态含未知操作阶段；拒绝覆盖")
        target = last["target_commit"]
        if target is not None and (
            not isinstance(target, str)
            or re.fullmatch(r"[0-9a-f]{40}", target) is None
        ):
            raise LocalReleaseError("本机部署状态含无效 target commit；拒绝覆盖")
        if last["operation"] == "down" and target is not None:
            raise LocalReleaseError("本机部署状态的 down 操作含 target commit；拒绝覆盖")
        try:
            datetime.fromisoformat(last["updated_at"])
        except ValueError:
            raise LocalReleaseError("本机部署状态更新时间无效；拒绝覆盖") from None
    if state["runtime_status"] == "running" and state["active_release"] is None:
        raise LocalReleaseError("本机部署状态称服务运行但缺少 active release；拒绝覆盖")
    return state


def _validate_active_release(release: object) -> None:
    if not isinstance(release, dict) or set(release) != {
        "source_commit",
        "api_image",
        "api_image_id",
        "database_runtime_image",
        "database_runtime_image_id",
    }:
        raise LocalReleaseError("active release 身份字段无效")
    if not isinstance(release["source_commit"], str) or re.fullmatch(
        r"[0-9a-f]{40}", release["source_commit"]
    ) is None:
        raise LocalReleaseError("active release source commit 无效")
    if not isinstance(release["api_image"], str) or re.fullmatch(
        r"chatbi-local-api:[A-Za-z0-9._:-]+", release["api_image"]
    ) is None:
        raise LocalReleaseError("active release API image 无效")
    if not isinstance(release["database_runtime_image"], str) or re.fullmatch(
        r"chatbi-local-postgres:[A-Za-z0-9._:-]+",
        release["database_runtime_image"],
    ) is None:
        raise LocalReleaseError("active release database runtime image 无效")
    for key in (
        "api_image_id",
        "database_runtime_image_id",
    ):
        if not isinstance(release[key], str) or re.fullmatch(
            r"sha256:[0-9a-f]{64}", release[key]
        ) is None:
            raise LocalReleaseError(f"active release {key} 无效")


def _write_deployment_state(path: Path, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            os.fchmod(output.fileno(), 0o600)
            json.dump(state, output, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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
    compatibility_profile = load_compatibility_profile()

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
        import psycopg
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
                control_migrations = sorted(
                    connection.execute(
                        text("SELECT version FROM schema_migrations")
                    ).scalars()
                )
                checkpoint_migrations = sorted(
                    connection.execute(
                        text("SELECT v FROM checkpoint_migrations")
                    ).scalars()
                )
                snapshot_rows = connection.execute(
                    text(
                        """
                        SELECT snapshot_version, snapshot->>'version' AS payload_version
                        FROM history_turns
                        WHERE snapshot IS NOT NULL
                        UNION ALL
                        SELECT snapshot_version, snapshot->>'version' AS payload_version
                        FROM saved_results
                        """
                    )
                ).all()
                history_snapshot_versions = validate_snapshot_rows(
                    [(row[0], row[1]) for row in snapshot_rows]
                )
                has_admin = connection.execute(
                    text("SELECT EXISTS (SELECT 1 FROM users)")
                ).scalar_one()
            if not has_admin:
                raise LocalReleaseError("尚无管理员；运行 ./local create-admin")
        finally:
            engine.dispose()

        executor = PsycopgQueryExecutor.from_env(environ)
        with psycopg.connect(
            host=environ["POSTGRES_HOST"],
            port=int(environ["POSTGRES_PORT"]),
            dbname=environ["POSTGRES_DB"],
            user=environ["POSTGRES_APP_USER"],
            password=environ["POSTGRES_APP_PASSWORD"],
            connect_timeout=5,
        ) as connection:
            connection.read_only = True
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT seed_version FROM mart_sales.dev_seed_metadata "
                    "WHERE singleton LIMIT 2"
                )
                seed_rows = cursor.fetchall()
        if len(seed_rows) != 1:
            raise LocalReleaseError("Sales Mart Seed marker 缺失或重复")

        runtime = RagRuntime(
            OfflineBuildConfig.from_environment(), production_mode=True
        )
        try:
            current_pointer = json.loads(
                (rag_root / "current.json").read_text(encoding="utf-8")
            )
            snapshot = runtime.verify_production_ready(
                executor.verify_structure_metadata
            )
        finally:
            runtime.close()

        embedding = snapshot.manifest.get("embedding")
        provenance = snapshot.manifest.get("provenance")
        if not isinstance(embedding, dict) or not isinstance(provenance, dict):
            raise LocalReleaseError("RAG manifest 缺少 Embedding 或 provenance 身份")
        state = {
            "control_migrations": control_migrations,
            "checkpoint_migrations": checkpoint_migrations,
            "business_seed_version": seed_rows[0][0],
            "catalog_verified": True,
            "catalog_schema_metadata_sha256": provenance.get(
                "schema_metadata_sha256"
            ),
            "history_snapshot_versions": history_snapshot_versions,
            "rag_pointer_schema_version": current_pointer.get("schema_version"),
            "rag_manifest_schema_version": snapshot.manifest.get("schema_version"),
            "rag_model_revision": embedding.get("revision"),
            "rag_embedding_dimension": embedding.get("dimension"),
            "rag_provenance_verified": True,
            "rag_provenance": {
                key: provenance.get(key)
                for key in (
                    "schema_metadata_sha256",
                    "metrics_sha256",
                    "embedding_config_sha256",
                    "source_sha256",
                )
            },
        }
        validate_compatibility_state(compatibility_profile, state)
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
        "Control / checkpoint migration、历史快照、Sales Mart Seed、"
        "PostgreSQL catalog 与固定来源 RAG 索引均已通过只读兼容核验。"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.local_release")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify-runtime", help="校验稳定环境启动前置条件")
    commands.add_parser("wait-qdrant", help="等待本稳定项目内的 Qdrant 端口")
    state_parser = commands.add_parser("record-state", help="原子记录本机部署状态")
    state_parser.add_argument(
        "--state-path", default="/opt/chatbi-state/deployment-state.json"
    )
    state_parser.add_argument(
        "--event", choices=("begin", "phase", "succeeded", "failed", "stopped"), required=True
    )
    state_parser.add_argument(
        "--operation", choices=("up", "upgrade", "rollback", "down"), required=True
    )
    state_parser.add_argument("--target-commit")
    state_parser.add_argument("--phase", required=True)
    state_parser.add_argument(
        "--runtime-status",
        choices=("unknown", "running", "transitioning", "stopped", "unhealthy"),
        required=True,
    )
    _add_release_arguments(state_parser, "active")
    _add_release_arguments(state_parser, "baseline")
    args = parser.parse_args(argv)
    try:
        if args.command == "verify-runtime":
            verify_runtime(dict(os.environ))
        elif args.command == "wait-qdrant":
            wait_for_qdrant(dict(os.environ))
        else:
            active_release = _release_from_arguments(args, "active")
            baseline_active_release = _release_from_arguments(args, "baseline")
            state = update_deployment_state(
                Path(args.state_path),
                event=args.event,
                operation=args.operation,
                target_commit=args.target_commit,
                phase=args.phase,
                runtime_status=args.runtime_status,
                active_release=active_release,
                baseline_active_release=baseline_active_release,
            )
            last = state["last_operation"]
            assert isinstance(last, dict)
            print(
                "本机部署状态已原子更新："
                f"runtime={state['runtime_status']} phase={last['phase']} result={last['result']}"
            )
    except LocalReleaseError as error:
        print(f"本地发布检查失败：{error}", file=sys.stderr)
        return 1
    return 0


def _add_release_arguments(parser: argparse.ArgumentParser, prefix: str) -> None:
    for suffix in (
        "source-commit",
        "api-image",
        "api-image-id",
        "database-runtime-image",
        "database-runtime-image-id",
    ):
        parser.add_argument(f"--{prefix}-{suffix}")


def _release_from_arguments(
    args: argparse.Namespace, prefix: str
) -> dict[str, str] | None:
    suffixes = (
        "source_commit",
        "api_image",
        "api_image_id",
        "database_runtime_image",
        "database_runtime_image_id",
    )
    values = {
        suffix: getattr(args, f"{prefix}_{suffix}") for suffix in suffixes
    }
    if all(value is None for value in values.values()):
        return None
    if any(value is None for value in values.values()):
        raise LocalReleaseError(f"{prefix} release 身份字段不完整")
    return values


if __name__ == "__main__":
    raise SystemExit(main())
