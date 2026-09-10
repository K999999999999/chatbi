"""Qdrant Asset Store（Qdrant 离线资产存储适配器）。"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import uuid
from typing import Any

from .documents import RetrievalDocument
from .embedding import EmbeddedText


class QdrantStoreError(RuntimeError):
    """向量集合创建、写入、重载或检索校验失败。"""


@dataclass(frozen=True, slots=True)
class SearchHit:
    """对 Qdrant 检索结果做稳定的最小封装。"""

    document_id: str
    score: float
    payload: Mapping[str, Any]


class QdrantAssetStore:
    """使用 direct qdrant-client 管理版本化离线集合。"""

    def __init__(self, client: Any) -> None:
        self._client = client
        self._models: Any | None = None

    @classmethod
    def connect(
        cls,
        *,
        url: str | None = None,
        path: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> "QdrantAssetStore":
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:
            raise QdrantStoreError(
                "未安装 qdrant-client，无法连接向量库；请先同步项目依赖"
            ) from exc

        if path:
            try:
                client = QdrantClient(path=path)
            except Exception as exc:
                raise QdrantStoreError(f"无法打开 Qdrant 本地目录 {path}：{exc}") from exc
            return cls(client)
        if not url:
            raise QdrantStoreError("Qdrant 必须配置 url 或 path")

        kwargs: dict[str, Any] = {"url": url, "timeout": timeout}
        if api_key:
            kwargs["api_key"] = api_key
        try:
            client = QdrantClient(**kwargs)
        except Exception as exc:
            raise QdrantStoreError(f"无法连接 Qdrant {url}：{exc}") from exc
        return cls(client)

    def create_collection(self, collection_name: str, dimension: int) -> None:
        if dimension <= 0:
            raise QdrantStoreError("向量维度必须为正数")
        if self.collection_exists(collection_name):
            raise QdrantStoreError(f"集合已存在，拒绝覆盖：{collection_name}")
        models = self._load_models()
        try:
            self._client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "dense": models.VectorParams(
                        size=dimension,
                        distance=models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    "sparse": models.SparseVectorParams(),
                },
            )
        except Exception as exc:
            raise QdrantStoreError(f"创建集合失败 {collection_name}：{exc}") from exc

    def upsert_documents(
        self,
        collection_name: str,
        documents: Sequence[RetrievalDocument],
        embeddings: Sequence[EmbeddedText],
    ) -> None:
        if len(documents) != len(embeddings):
            raise QdrantStoreError("文档数量与向量数量不一致")
        models = self._load_models()
        points = []
        for document, embedding in zip(documents, embeddings, strict=True):
            payload = document.to_payload()
            metadata = payload.get("metadata")
            if isinstance(metadata, dict):
                # 顶层索引字段便于候选表过滤，同时保留完整 metadata 对象。
                payload.update(metadata)
            points.append(
                models.PointStruct(
                    id=_point_id(document),
                    vector={
                        "dense": list(embedding.dense),
                        "sparse": models.SparseVector(
                            indices=list(embedding.sparse.indices),
                            values=list(embedding.sparse.values),
                        ),
                    },
                    payload=payload,
                )
            )
        if not points:
            raise QdrantStoreError(f"拒绝向空集合写入：{collection_name}")
        try:
            self._client.upsert(
                collection_name=collection_name,
                points=points,
                wait=True,
            )
        except Exception as exc:
            raise QdrantStoreError(f"写入集合失败 {collection_name}：{exc}") from exc

    def validate_collection(
        self,
        collection_name: str,
        expected_count: int,
        probe: EmbeddedText,
    ) -> None:
        if not self.collection_exists(collection_name):
            raise QdrantStoreError(f"集合重载失败，集合不存在：{collection_name}")
        actual_count = self.count(collection_name)
        if actual_count != expected_count:
            raise QdrantStoreError(
                f"集合 {collection_name} 文档数量为 {actual_count}，"
                f"期望 {expected_count}"
            )
        hits = self.search(collection_name, probe, limit=1)
        if not hits:
            raise QdrantStoreError(f"集合 {collection_name} 重载后无法完成检索")

    def count(self, collection_name: str) -> int:
        try:
            result = self._client.count(collection_name=collection_name, exact=True)
            value = _field(result, "count")
            return int(value)
        except Exception as exc:
            raise QdrantStoreError(f"读取集合数量失败 {collection_name}：{exc}") from exc

    def scroll_payloads(
        self,
        collection_name: str,
        *,
        page_size: int = 100,
    ) -> tuple[Mapping[str, Any], ...]:
        """分页读取集合全部 Payload，不加载向量，并按 document_id 排序。"""

        if page_size <= 0:
            raise QdrantStoreError("Payload 分页大小必须为正数")

        payloads: list[dict[str, Any]] = []
        offset: Any | None = None
        seen_offsets: set[str] = set()
        while True:
            try:
                response = self._client.scroll(
                    collection_name=collection_name,
                    limit=page_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
            except Exception as exc:
                raise QdrantStoreError(
                    f"读取集合 Payload 失败 {collection_name}：{exc}"
                ) from exc

            if not isinstance(response, tuple) or len(response) != 2:
                raise QdrantStoreError(
                    f"集合 {collection_name} 返回了无效 Scroll 响应"
                )
            points, next_offset = response
            if not isinstance(points, Sequence) or isinstance(points, (str, bytes)):
                raise QdrantStoreError(
                    f"集合 {collection_name} 返回了无效 Scroll 记录"
                )
            for point in points:
                payload = _field(point, "payload", {}) or {}
                if not isinstance(payload, Mapping):
                    raise QdrantStoreError(
                        f"集合 {collection_name} 返回了无效 payload"
                    )
                payloads.append(dict(payload))

            if next_offset is None:
                break
            offset_marker = repr(next_offset)
            if offset_marker in seen_offsets:
                raise QdrantStoreError(
                    f"集合 {collection_name} Scroll 游标重复，拒绝继续读取"
                )
            seen_offsets.add(offset_marker)
            offset = next_offset

        return tuple(
            sorted(
                payloads,
                key=lambda payload: str(payload.get("document_id", "")),
            )
        )

    def search(
        self,
        collection_name: str,
        query: EmbeddedText,
        *,
        limit: int = 5,
        filter_payload: Mapping[str, Any] | None = None,
    ) -> tuple[SearchHit, ...]:
        if limit <= 0:
            raise QdrantStoreError("检索 limit 必须为正数")
        kwargs: dict[str, Any] = {
            "collection_name": collection_name,
            "query": list(query.dense),
            "using": "dense",
            "limit": limit,
            "with_payload": True,
        }
        query_filter = self._build_filter(filter_payload)
        if query_filter is not None:
            kwargs["query_filter"] = query_filter
        try:
            response = self._client.query_points(**kwargs)
        except AttributeError:
            # 兼容仍暴露旧 search API 的客户端；项目默认版本使用 query_points。
            kwargs.pop("query", None)
            kwargs.pop("using", None)
            kwargs["query_vector"] = list(query.dense)
            response = self._client.search(**kwargs)
        except Exception as exc:
            raise QdrantStoreError(f"检索集合失败 {collection_name}：{exc}") from exc

        points = _field(response, "points", response)
        hits: list[SearchHit] = []
        for point in points:
            payload = _field(point, "payload", {}) or {}
            if not isinstance(payload, Mapping):
                raise QdrantStoreError(f"集合 {collection_name} 返回了无效 payload")
            document_id = payload.get("document_id")
            if not isinstance(document_id, str) or not document_id:
                raise QdrantStoreError(
                    f"集合 {collection_name} 返回了缺少 document_id 的点"
                )
            hits.append(
                SearchHit(
                    document_id=document_id,
                    score=float(_field(point, "score", 0.0)),
                    payload=dict(payload),
                )
            )
        return tuple(hits)

    def collection_exists(self, collection_name: str) -> bool:
        try:
            method = getattr(self._client, "collection_exists", None)
            if method is not None:
                return bool(method(collection_name))
            self._client.get_collection(collection_name=collection_name)
            return True
        except Exception as exc:
            if _is_not_found(exc):
                return False
            raise QdrantStoreError(f"检查集合失败 {collection_name}：{exc}") from exc

    def delete_collection(self, collection_name: str) -> None:
        try:
            if self.collection_exists(collection_name):
                self._client.delete_collection(collection_name=collection_name)
        except Exception as exc:
            raise QdrantStoreError(f"删除失败集合 {collection_name}：{exc}") from exc

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close is not None:
            close()

    def _load_models(self) -> Any:
        if self._models is not None:
            return self._models
        try:
            from qdrant_client import models
        except ImportError as exc:
            raise QdrantStoreError(
                "未安装 qdrant-client，无法创建 Qdrant 模型对象"
            ) from exc
        self._models = models
        return models

    def _build_filter(
        self,
        filter_payload: Mapping[str, Any] | None,
    ) -> Any | None:
        if not filter_payload:
            return None
        models = self._load_models()
        conditions = [
            models.FieldCondition(
                key=str(key),
                match=models.MatchValue(value=value),
            )
            for key, value in filter_payload.items()
        ]
        return models.Filter(must=conditions)


def _point_id(document: RetrievalDocument) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"chatbi-rag/{document.collection}/{document.document_id}",
        )
    )


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _is_not_found(error: Exception) -> bool:
    message = str(error).lower()
    return "404" in message or "not found" in message or "doesn't exist" in message
