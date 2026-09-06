"""RAG Offline Build 配置。"""

from dataclasses import dataclass
import os
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSET_DIR = PROJECT_ROOT / "data" / "rag"
DEFAULT_MODEL = "BAAI/bge-m3"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


class OfflineBuildConfigError(ValueError):
    """离线构建配置无效。"""


@dataclass(frozen=True, slots=True)
class OfflineBuildConfig:
    """可复现离线构建所需的非业务配置。"""

    output_dir: Path = DEFAULT_ASSET_DIR
    qdrant_url: str | None = "http://127.0.0.1:6333"
    qdrant_path: Path | None = None
    qdrant_api_key: str | None = None
    qdrant_timeout_seconds: float = 30.0
    collection_prefix: str = "chatbi"
    model_name_or_path: str = DEFAULT_MODEL
    embedding_dimension: int = 1024
    embedding_batch_size: int = 8
    embedding_use_fp16: bool = False
    embedding_device: str | None = None

    @classmethod
    def from_environment(cls) -> "OfflineBuildConfig":
        output_dir = _path_from_env("RAG_OUTPUT_DIR", DEFAULT_ASSET_DIR)
        qdrant_path = _optional_path_from_env("RAG_QDRANT_PATH")
        qdrant_url = os.getenv("RAG_QDRANT_URL", "http://127.0.0.1:6333").strip()
        if qdrant_path is not None:
            qdrant_url = None
        elif not qdrant_url:
            qdrant_url = None

        prefix = os.getenv("RAG_COLLECTION_PREFIX", "chatbi").strip()
        if not _SAFE_NAME.fullmatch(prefix):
            raise OfflineBuildConfigError(
                "RAG_COLLECTION_PREFIX 只能包含字母、数字、下划线和连字符"
            )

        model_dir = _optional_path_from_env("RAG_MODEL_DIR")
        model = (
            str(model_dir)
            if model_dir is not None and model_dir.exists()
            else (
                _optional_env("RAG_MODEL_NAME_OR_PATH")
                or _optional_env("RAG_EMBEDDING_MODEL")
                or _optional_env("RAG_MODEL_ID")
                or DEFAULT_MODEL
            )
        )
        if not model:
            raise OfflineBuildConfigError("RAG_MODEL_NAME_OR_PATH 不能为空")
        raw_device = _optional_env("RAG_EMBEDDING_DEVICE")
        device = (
            None
            if raw_device is None or raw_device.lower() == "auto"
            else raw_device
        )

        return cls(
            output_dir=output_dir,
            qdrant_url=qdrant_url,
            qdrant_path=qdrant_path,
            qdrant_api_key=(
                _optional_env("RAG_QDRANT_API_KEY")
                or _optional_env("QDRANT_API_KEY")
            ),
            qdrant_timeout_seconds=_positive_float(
                "RAG_QDRANT_TIMEOUT_SECONDS",
                os.getenv("RAG_QDRANT_TIMEOUT_SECONDS", "30"),
            ),
            collection_prefix=prefix,
            model_name_or_path=model,
            embedding_dimension=_positive_int(
                "RAG_EMBEDDING_DIMENSION",
                os.getenv("RAG_EMBEDDING_DIMENSION", "1024"),
            ),
            embedding_batch_size=_positive_int(
                "RAG_EMBEDDING_BATCH_SIZE",
                os.getenv("RAG_EMBEDDING_BATCH_SIZE", "8"),
            ),
            embedding_use_fp16=_bool_env(
                "RAG_EMBEDDING_USE_FP16",
                os.getenv("RAG_EMBEDDING_USE_FP16", "false"),
            ),
            embedding_device=device,
        )

    def collection_name(self, logical_collection: str, build_id: str) -> str:
        logical = logical_collection.strip().lower()
        if not _SAFE_NAME.fullmatch(logical):
            raise OfflineBuildConfigError(
                f"逻辑集合名称包含非法字符：{logical_collection}"
            )
        if not _SAFE_NAME.fullmatch(build_id):
            raise OfflineBuildConfigError("build_id 只能包含字母、数字、下划线和连字符")
        return f"{self.collection_prefix}_{logical}__{build_id}"


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


def _path_from_env(name: str, default: Path) -> Path:
    value = os.getenv(name)
    path = Path(value.strip()) if value and value.strip() else default
    return path if path.is_absolute() else PROJECT_ROOT / path


def _optional_path_from_env(name: str) -> Path | None:
    value = os.getenv(name)
    if not value or not value.strip():
        return None
    path = Path(value.strip())
    return path if path.is_absolute() else PROJECT_ROOT / path


def _positive_int(name: str, value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise OfflineBuildConfigError(f"{name} 必须是正整数") from exc
    if parsed <= 0:
        raise OfflineBuildConfigError(f"{name} 必须是正整数")
    return parsed


def _positive_float(name: str, value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise OfflineBuildConfigError(f"{name} 必须是正数") from exc
    if parsed <= 0:
        raise OfflineBuildConfigError(f"{name} 必须是正数")
    return parsed


def _bool_env(name: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise OfflineBuildConfigError(f"{name} 必须是布尔值")
