"""Online RAG Runtime（在线 RAG 运行时）和不可变资产快照。"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from types import MappingProxyType
from typing import Any

from src.rag_offline.build import (
    COLLECTIONS,
    PublishedAsset,
    PublishedAssetError,
    load_published_asset,
)
from src.rag_offline.config import OfflineBuildConfig
from src.rag_offline.embedding import BgeM3EmbeddingProvider, EmbeddingProvider
from src.rag_offline.qdrant_store import QdrantAssetStore, QdrantStoreError


class RagRuntimeError(RuntimeError):
    """在线 RAG 运行时无法提供安全资产快照。"""


class AssetUnavailableError(RagRuntimeError):
    """发布资产不存在、不一致或不满足运行时契约。"""


class RetrievalUnavailableError(RagRuntimeError):
    """Qdrant 等检索服务不可用。"""


class EmbeddingUnavailableError(RagRuntimeError):
    """查询 Embedding 运行时不可用。"""


@dataclass(frozen=True, slots=True)
class AssetSnapshot:
    """一次请求可安全共享的不可变发布资产快照。"""

    asset_version: str
    collection_names: Mapping[str, str]
    relationship_graph: Mapping[str, Any]
    manifest: Mapping[str, Any]
    embedding_provider: EmbeddingProvider
    qdrant_store: QdrantAssetStore


StoreFactory = Callable[[OfflineBuildConfig], QdrantAssetStore]
EmbeddingFactory = Callable[
    [OfflineBuildConfig, Mapping[str, Any]],
    EmbeddingProvider,
]
AssetLoader = Callable[[Path], PublishedAsset]


class RagRuntime:
    """加载当前发布指针，并按 build_id 缓存不可变运行时快照。"""

    def __init__(
        self,
        config: OfflineBuildConfig,
        *,
        asset_loader: AssetLoader = load_published_asset,
        store_factory: StoreFactory | None = None,
        embedding_factory: EmbeddingFactory | None = None,
    ) -> None:
        self._config = config
        self._asset_loader = asset_loader
        self._store_factory = store_factory or _default_store_factory
        self._embedding_factory = embedding_factory or _default_embedding_factory
        self._snapshots: dict[str, AssetSnapshot] = {}
        self._lock = RLock()

    @classmethod
    def from_environment(cls) -> "RagRuntime":
        """使用项目已有 RAG 环境变量创建运行时。"""

        return cls(OfflineBuildConfig.from_environment())

    def get_snapshot(self) -> AssetSnapshot:
        """每次调用只读取一次 current.json，并返回对应版本快照。"""

        try:
            published = self._asset_loader(self._config.output_dir)
        except PublishedAssetError as exc:
            raise AssetUnavailableError(str(exc)) from exc

        with self._lock:
            cached = self._snapshots.get(published.build_id)
            if cached is not None:
                return cached
            snapshot = self._create_snapshot(published)
            self._snapshots[published.build_id] = snapshot
            return snapshot

    def close(self) -> None:
        """关闭所有 Qdrant client，但不删除发布资产。"""

        with self._lock:
            snapshots = tuple(self._snapshots.values())
            self._snapshots.clear()
        for snapshot in snapshots:
            snapshot.qdrant_store.close()

    def _create_snapshot(self, published: PublishedAsset) -> AssetSnapshot:
        _validate_manifest(published, self._config)
        try:
            store = self._store_factory(self._config)
        except QdrantStoreError as exc:
            raise RetrievalUnavailableError(str(exc)) from exc
        try:
            _validate_collections(store, published)
            embedding_config = _embedding_config(published.manifest)
            embedding = self._embedding_factory(self._config, embedding_config)
        except AssetUnavailableError:
            store.close()
            raise
        except QdrantStoreError as exc:
            store.close()
            raise RetrievalUnavailableError(str(exc)) from exc
        except EmbeddingUnavailableError:
            store.close()
            raise
        except Exception as exc:
            store.close()
            raise EmbeddingUnavailableError(f"Embedding 运行时创建失败：{exc}") from exc

        return AssetSnapshot(
            asset_version=published.build_id,
            collection_names=MappingProxyType(dict(published.collection_names)),
            relationship_graph=published.relationship_graph,
            manifest=published.manifest,
            embedding_provider=embedding,
            qdrant_store=store,
        )


def _default_store_factory(config: OfflineBuildConfig) -> QdrantAssetStore:
    return QdrantAssetStore.connect(
        url=config.qdrant_url,
        path=str(config.qdrant_path) if config.qdrant_path is not None else None,
        api_key=config.qdrant_api_key,
        timeout=config.qdrant_timeout_seconds,
    )


def _default_embedding_factory(
    config: OfflineBuildConfig,
    manifest_embedding: Mapping[str, Any],
) -> EmbeddingProvider:
    model = manifest_embedding.get("model")
    if not isinstance(model, str) or not model.strip():
        raise EmbeddingUnavailableError("Manifest 缺少有效 Embedding model")
    return BgeM3EmbeddingProvider(
        model_name_or_path=model,
        batch_size=config.embedding_batch_size,
        use_fp16=config.embedding_use_fp16,
        devices=config.embedding_device,
    )


def _validate_manifest(
    published: PublishedAsset,
    config: OfflineBuildConfig,
) -> None:
    manifest = published.manifest
    if manifest.get("status") != "READY":
        raise AssetUnavailableError("已发布 manifest 不是 READY 状态")
    if manifest.get("build_id") != published.build_id:
        raise AssetUnavailableError("Manifest build_id 与发布资产不一致")
    embedding = _embedding_config(manifest)
    dimension = embedding.get("dimension")
    if dimension != config.embedding_dimension:
        raise AssetUnavailableError(
            f"Embedding 维度不一致：资产={dimension}，配置={config.embedding_dimension}"
        )
    model = embedding.get("model")
    if not isinstance(model, str) or not model.strip():
        raise AssetUnavailableError("Manifest 缺少有效 Embedding model")
    if _normalize_path_or_name(model) != _normalize_path_or_name(
        config.model_name_or_path
    ):
        raise AssetUnavailableError("Embedding Model 与发布资产不匹配")


def _validate_collections(
    store: QdrantAssetStore,
    published: PublishedAsset,
) -> None:
    raw_collections = published.manifest.get("collections")
    if not isinstance(raw_collections, Mapping):
        raise AssetUnavailableError("Manifest 缺少 collections")
    for collection in COLLECTIONS:
        name = published.collection_names.get(collection)
        if not isinstance(name, str) or not name:
            raise AssetUnavailableError(f"Manifest 缺少 {collection} 集合名称")
        if not store.collection_exists(name):
            raise AssetUnavailableError(f"发布集合不存在：{name}")
        item = raw_collections.get(collection)
        expected_count = item.get("document_count") if isinstance(item, Mapping) else None
        if not isinstance(expected_count, int) or expected_count <= 0:
            raise AssetUnavailableError(f"Manifest 缺少 {collection} 文档数量")
        if store.count(name) != expected_count:
            raise AssetUnavailableError(f"发布集合数量与 Manifest 不一致：{name}")


def _embedding_config(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    embedding = manifest.get("embedding")
    if not isinstance(embedding, Mapping):
        raise AssetUnavailableError("Manifest 缺少 embedding 配置")
    return embedding


def _normalize_path_or_name(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or ":" in value or "\\" in value:
        return str(path).replace("/", "\\").rstrip("\\").casefold()
    return value.strip().casefold()
