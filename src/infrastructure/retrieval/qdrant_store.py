"""Qdrant Dense + Sparse Collection 和 Point 基础操作。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from qdrant_client import QdrantClient, models

from .bge_m3 import BGE_DENSE_DIMENSION, EncodedText


class QdrantStoreError(RuntimeError):
    """Qdrant 连接、配置或读写失败。"""


class QdrantStore:
    """使用现有 Qdrant REST 服务管理 Schema 离线索引。"""

    def __init__(self, url: str, *, timeout: int = 30) -> None:
        self.url = url
        try:
            self.client = QdrantClient(url=url, timeout=timeout)
            self.client.get_collections()
        except Exception as exc:
            raise QdrantStoreError(f"Qdrant connection failed: {type(exc).__name__}") from exc

    def ensure_collection(self, collection_name: str) -> None:
        """创建缺失集合，或验证已有集合与当前 Dense/Sparse 配置兼容。"""

        try:
            if not self.client.collection_exists(collection_name):
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config={
                        "dense": models.VectorParams(
                            size=BGE_DENSE_DIMENSION,
                            distance=models.Distance.COSINE,
                        )
                    },
                    sparse_vectors_config={
                        "sparse": models.SparseVectorParams(
                            index=models.SparseIndexParams(on_disk=False)
                        )
                    },
                )
                return
            self._validate_collection_config(collection_name)
        except QdrantStoreError:
            raise
        except Exception as exc:
            raise QdrantStoreError(
                f"Qdrant collection setup failed for {collection_name}: "
                f"{type(exc).__name__}"
            ) from exc

    def _validate_collection_config(self, collection_name: str) -> None:
        info = self.client.get_collection(collection_name)
        params = info.config.params
        vectors = params.vectors
        if not isinstance(vectors, dict):
            raise QdrantStoreError(
                f"Collection {collection_name} does not use named vectors"
            )
        dense = vectors.get("dense")
        if dense is None:
            raise QdrantStoreError(f"Collection {collection_name} lacks dense vector")
        if dense.size != BGE_DENSE_DIMENSION or dense.distance != models.Distance.COSINE:
            raise QdrantStoreError(
                f"Collection {collection_name} has incompatible dense configuration"
            )

        sparse_vectors = getattr(params, "sparse_vectors", None)
        if not isinstance(sparse_vectors, dict) or "sparse" not in sparse_vectors:
            raise QdrantStoreError(
                f"Collection {collection_name} lacks sparse vector configuration"
            )

    def upsert(
        self,
        collection_name: str,
        points: Sequence[models.PointStruct],
    ) -> None:
        if not points:
            return
        try:
            self.client.upsert(collection_name, points=list(points), wait=True)
        except Exception as exc:
            raise QdrantStoreError(
                f"Qdrant upsert failed for {collection_name}: {type(exc).__name__}"
            ) from exc

    def count(self, collection_name: str) -> int:
        try:
            return int(self.client.count(collection_name, exact=True).count)
        except Exception as exc:
            raise QdrantStoreError(
                f"Qdrant count failed for {collection_name}: {type(exc).__name__}"
            ) from exc

    def retrieve(
        self,
        collection_name: str,
        point_ids: Sequence[str],
        *,
        with_vectors: bool = False,
    ) -> list[models.Record]:
        try:
            return self.client.retrieve(
                collection_name,
                ids=list(point_ids),
                with_payload=True,
                with_vectors=with_vectors,
            )
        except Exception as exc:
            raise QdrantStoreError(
                f"Qdrant retrieve failed for {collection_name}: {type(exc).__name__}"
            ) from exc

    def query_dense(
        self,
        collection_name: str,
        vector: Sequence[float],
        *,
        limit: int = 10,
    ) -> list[models.ScoredPoint]:
        try:
            response = self.client.query_points(
                collection_name,
                query=list(vector),
                using="dense",
                limit=limit,
                with_payload=True,
            )
            return list(response.points)
        except Exception as exc:
            raise QdrantStoreError(
                f"Qdrant Dense query failed for {collection_name}: {type(exc).__name__}"
            ) from exc

    def query_sparse(
        self,
        collection_name: str,
        vector: models.SparseVector,
        *,
        limit: int = 10,
    ) -> list[models.ScoredPoint]:
        try:
            response = self.client.query_points(
                collection_name,
                query=vector,
                using="sparse",
                limit=limit,
                with_payload=True,
            )
            return list(response.points)
        except Exception as exc:
            raise QdrantStoreError(
                f"Qdrant Sparse query failed for {collection_name}: {type(exc).__name__}"
            ) from exc


def point_vector(embedding: EncodedText) -> dict[str, Any]:
    """转换为一个同时包含 named Dense/Sparse 的 Qdrant vector。"""

    return {"dense": embedding.dense, "sparse": embedding.sparse}
