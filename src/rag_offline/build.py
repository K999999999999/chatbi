"""RAG Offline Build（RAG 离线构建）编排和发布保护。"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
from typing import Any, Protocol
import uuid

from .config import DEFAULT_ASSET_DIR
from .documents import (
    COLUMN_COLLECTION,
    METRIC_COLLECTION,
    TABLE_COLLECTION,
    RetrievalDocument,
    build_documents,
)
from .embedding import EmbeddedText, EmbeddingError, EmbeddingProvider
from .qdrant_store import QdrantStoreError
from .relationships import RelationshipGraphError, build_relationship_graph
from .sources import (
    DEFAULT_METRICS_PATH,
    DEFAULT_STRUCTURE_DIR,
    Facts,
    SourceLoadError,
    load_facts,
)


COLLECTIONS = (TABLE_COLLECTION, COLUMN_COLLECTION, METRIC_COLLECTION)
CURRENT_POINTER = "current.json"
_SAFE_BUILD_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class OfflineBuildValidationError(RuntimeError):
    """离线构建产物或配置校验失败。"""


class PublishedAssetError(RuntimeError):
    """当前已发布离线资产无法安全重载。"""


class AssetStore(Protocol):
    """构建编排依赖的最小向量资产存储契约。"""

    def create_collection(self, collection_name: str, dimension: int) -> None:
        """创建新的、不可覆盖的物理集合。"""

    def upsert_documents(
        self,
        collection_name: str,
        documents: Sequence[RetrievalDocument],
        embeddings: Sequence[EmbeddedText],
    ) -> None:
        """批量写入文档、向量和元数据。"""

    def validate_collection(
        self,
        collection_name: str,
        expected_count: int,
        probe: EmbeddedText,
    ) -> None:
        """重新加载集合并完成数量与检索校验。"""

    def delete_collection(self, collection_name: str) -> None:
        """删除本次构建创建的失败临时集合。"""


@dataclass(frozen=True, slots=True)
class BuildSummary:
    """符合输出契约的离线构建摘要。"""

    status: str
    build_id: str
    table_document_count: int
    column_document_count: int
    metric_document_count: int
    relationship_edge_count: int
    collections_reloaded: Mapping[str, bool]
    published: bool
    failure_count: int
    failure_category: str | None = None
    failure_message: str | None = None
    manifest_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "build_id": self.build_id,
            "table_document_count": self.table_document_count,
            "column_document_count": self.column_document_count,
            "metric_document_count": self.metric_document_count,
            "relationship_edge_count": self.relationship_edge_count,
            "collections_reloaded": dict(self.collections_reloaded),
            "published": self.published,
            "failure_count": self.failure_count,
            "failure_category": self.failure_category,
            "failure_message": self.failure_message,
            "manifest_path": self.manifest_path,
        }


@dataclass(frozen=True, slots=True)
class PublishedAsset:
    """在线模块启动时可读取的已发布资产索引。"""

    build_id: str
    manifest_path: Path
    collection_names: Mapping[str, str]
    relationship_graph: Mapping[str, Any]
    manifest: Mapping[str, Any]


def build_offline_assets(
    embedding: EmbeddingProvider,
    store: AssetStore,
    *,
    facts: Facts | None = None,
    structure_dir: Path = DEFAULT_STRUCTURE_DIR,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    output_dir: Path = DEFAULT_ASSET_DIR,
    collection_prefix: str = "chatbi",
    expected_dimension: int | None = None,
    build_id: str | None = None,
) -> BuildSummary:
    """完成一次隔离构建，并仅在全部校验通过后替换 current 指针。"""

    resolved_build_id = build_id or _new_build_id()
    output_dir = Path(output_dir)
    reloaded = {collection: False for collection in COLLECTIONS}
    counts = {collection: 0 for collection in COLLECTIONS}
    relationship_edge_count = 0
    created_collections: list[str] = []
    staging_dir: Path | None = None
    final_dir = output_dir / resolved_build_id
    staging_dir_created = False
    final_dir_created = False
    pointer_published = False

    try:
        _validate_build_id(resolved_build_id)
        _validate_collection_prefix(collection_prefix)
        if facts is None:
            facts = load_facts(structure_dir, metrics_path)
        documents = build_documents(facts)
        graph = build_relationship_graph(facts)
        _validate_documents(documents)
        grouped = _group_documents(documents)
        counts = {collection: len(grouped[collection]) for collection in COLLECTIONS}
        relationship_edge_count = graph.edge_count

        dimension = _provider_dimension(embedding)
        if expected_dimension is not None and dimension != expected_dimension:
            raise OfflineBuildValidationError(
                f"Embedding 维度为 {dimension}，配置期望 {expected_dimension}"
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        staging_dir = output_dir / ".staging" / resolved_build_id
        if staging_dir.exists() or final_dir.exists():
            raise OfflineBuildValidationError(
                f"构建目录已存在，拒绝覆盖：{resolved_build_id}"
            )
        staging_dir.mkdir(parents=True, exist_ok=False)
        staging_dir_created = True

        collection_names: dict[str, str] = {}
        for collection in COLLECTIONS:
            collection_documents = grouped[collection]
            texts = [document.page_content for document in collection_documents]
            embeddings = embedding.embed_documents(texts)
            _validate_embeddings(embeddings, len(texts), dimension, collection)

            physical_name = _physical_collection_name(
                collection_prefix,
                collection,
                resolved_build_id,
            )
            collection_names[collection] = physical_name
            store.create_collection(physical_name, dimension)
            created_collections.append(physical_name)
            store.upsert_documents(physical_name, collection_documents, embeddings)
            store.validate_collection(
                physical_name,
                expected_count=len(collection_documents),
                probe=embeddings[0],
            )
            reloaded[collection] = True

        _write_json(staging_dir / "relationship_graph.json", graph.to_dict())
        manifest = {
            "schema_version": 1,
            "status": "READY",
            "build_id": resolved_build_id,
            "collections": {
                collection: {
                    "name": collection_names[collection],
                    "document_count": counts[collection],
                }
                for collection in COLLECTIONS
            },
            "document_counts": counts,
            "relationship_edge_count": relationship_edge_count,
            "relationship_graph": "relationship_graph.json",
            "embedding": _jsonable(dict(embedding.config)),
        }
        _write_json(staging_dir / "manifest.json", manifest)
        staging_dir.replace(final_dir)
        staging_dir_created = False
        staging_dir = None
        final_dir_created = True

        _write_json_atomic(
            output_dir / CURRENT_POINTER,
            {
                "schema_version": 1,
                "build_id": resolved_build_id,
                "manifest_path": f"{resolved_build_id}/manifest.json",
                "published_at": _utc_now(),
            },
        )
        pointer_published = True
        return BuildSummary(
            status="PUBLISHED",
            build_id=resolved_build_id,
            table_document_count=counts[TABLE_COLLECTION],
            column_document_count=counts[COLUMN_COLLECTION],
            metric_document_count=counts[METRIC_COLLECTION],
            relationship_edge_count=relationship_edge_count,
            collections_reloaded=reloaded,
            published=True,
            failure_count=0,
            manifest_path=str(final_dir / "manifest.json"),
        )
    except Exception as exc:
        for collection_name in reversed(created_collections):
            try:
                store.delete_collection(collection_name)
            except Exception:
                pass
        if staging_dir_created:
            _remove_generated_directory(staging_dir)
        if final_dir_created and not pointer_published:
            _remove_generated_directory(final_dir)
        return BuildSummary(
            status="FAILED",
            build_id=resolved_build_id,
            table_document_count=counts[TABLE_COLLECTION],
            column_document_count=counts[COLUMN_COLLECTION],
            metric_document_count=counts[METRIC_COLLECTION],
            relationship_edge_count=relationship_edge_count,
            collections_reloaded=reloaded,
            published=False,
            failure_count=1,
            failure_category=_failure_category(exc),
            failure_message=str(exc),
        )


def load_published_asset(
    output_dir: Path = DEFAULT_ASSET_DIR,
) -> PublishedAsset:
    """读取 current 指针、清单和关系图，不扫描或重建向量集合。"""

    output_dir = Path(output_dir)
    current = _read_json_object(output_dir / CURRENT_POINTER)
    build_id = current.get("build_id")
    manifest_relative = _safe_relative_path(current.get("manifest_path"))
    if not isinstance(build_id, str) or not build_id:
        raise PublishedAssetError("current.json 缺少有效 build_id")
    if manifest_relative is None:
        raise PublishedAssetError("current.json 的 manifest_path 无效")
    manifest_path = output_dir / manifest_relative
    manifest = _read_json_object(manifest_path)
    if manifest.get("build_id") != build_id or manifest.get("status") != "READY":
        raise PublishedAssetError("已发布 manifest 与 current 指针不一致")

    raw_collections = manifest.get("collections")
    if not isinstance(raw_collections, dict):
        raise PublishedAssetError("manifest 缺少 collections")
    collection_names: dict[str, str] = {}
    for collection in COLLECTIONS:
        item = raw_collections.get(collection)
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise PublishedAssetError(f"manifest 缺少 {collection} 集合")
        collection_names[collection] = item["name"]

    graph_relative = _safe_relative_path(manifest.get("relationship_graph"))
    if graph_relative is None:
        raise PublishedAssetError("manifest 的 relationship_graph 无效")
    graph = _read_json_object(manifest_path.parent / graph_relative)
    if not isinstance(graph.get("foreign_keys"), list):
        raise PublishedAssetError("已发布关系图缺少 foreign_keys")
    return PublishedAsset(
        build_id=build_id,
        manifest_path=manifest_path,
        collection_names=collection_names,
        relationship_graph=graph,
        manifest=manifest,
    )


def _group_documents(
    documents: Sequence[RetrievalDocument],
) -> dict[str, tuple[RetrievalDocument, ...]]:
    grouped = {collection: [] for collection in COLLECTIONS}
    for document in documents:
        grouped[document.collection].append(document)
    return {collection: tuple(grouped[collection]) for collection in COLLECTIONS}


def _validate_documents(documents: Sequence[RetrievalDocument]) -> None:
    if not documents:
        raise OfflineBuildValidationError("检索文档集合不能为空")
    ids: set[str] = set()
    for document in documents:
        if document.collection not in COLLECTIONS:
            raise OfflineBuildValidationError(
                f"文档 {document.document_id} 属于未知集合 {document.collection}"
            )
        if not document.document_id or not document.page_content.strip():
            raise OfflineBuildValidationError("检索文档身份和 page_content 不能为空")
        if document.document_id in ids:
            raise OfflineBuildValidationError(
                f"检索文档存在重复 document_id：{document.document_id}"
            )
        ids.add(document.document_id)
        document.to_payload()


def _provider_dimension(embedding: EmbeddingProvider) -> int:
    dimension = embedding.dimension
    if not isinstance(dimension, int) or dimension <= 0:
        raise OfflineBuildValidationError("Embedding dimension 必须是正整数")
    return dimension


def _validate_embeddings(
    embeddings: Sequence[EmbeddedText],
    expected_count: int,
    dimension: int,
    collection: str,
) -> None:
    if len(embeddings) != expected_count:
        raise EmbeddingError(
            f"{collection} Embedding 输出 {len(embeddings)} 条，期望 {expected_count} 条"
        )
    for index, embedding in enumerate(embeddings, 1):
        if embedding.dimension != dimension:
            raise EmbeddingError(
                f"{collection} 第 {index} 条向量维度为 {embedding.dimension}，"
                f"期望 {dimension}"
            )


def _physical_collection_name(
    prefix: str,
    logical_collection: str,
    build_id: str,
) -> str:
    return f"{prefix}_{logical_collection.lower()}__{build_id}"


def _validate_build_id(build_id: str) -> None:
    if not _SAFE_BUILD_ID.fullmatch(build_id):
        raise OfflineBuildValidationError(
            "build_id 只能包含字母、数字、下划线和连字符"
        )


def _validate_collection_prefix(prefix: str) -> None:
    if not _SAFE_BUILD_ID.fullmatch(prefix):
        raise OfflineBuildValidationError(
            "collection_prefix 只能包含字母、数字、下划线和连字符"
        )


def _new_build_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid.uuid4().hex[:12]}"


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PublishedAssetError(f"发布文件不存在：{path.name}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PublishedAssetError(f"发布文件无法读取：{path.name}") from exc
    if not isinstance(value, dict):
        raise PublishedAssetError(f"发布文件必须是 JSON 对象：{path.name}")
    return value


def _safe_relative_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return None
    return path


def _remove_generated_directory(path: Path | None) -> None:
    if path is None or not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _failure_category(error: Exception) -> str:
    if isinstance(error, (SourceLoadError, RelationshipGraphError)):
        return "SOURCE"
    if isinstance(error, EmbeddingError):
        return "EMBEDDING"
    if isinstance(error, QdrantStoreError):
        return "VECTOR_STORE"
    if isinstance(error, PublishedAssetError):
        return "PUBLISH"
    if isinstance(error, (OSError, PermissionError)):
        return "FILESYSTEM"
    if isinstance(error, (OfflineBuildValidationError, ValueError)):
        return "VALIDATION"
    return "BUILD"


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value
