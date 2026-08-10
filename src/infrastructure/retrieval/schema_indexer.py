"""Schema Document 到 Qdrant 两个 Collection 的离线构建流程。"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from langchain_core.documents import Document
from qdrant_client import models

from .bge_m3 import BGE_M3Encoder, EncodedText
from .qdrant_store import QdrantStore, point_vector


TABLE_COLLECTION = "schema_tables"
COLUMN_COLLECTION = "schema_columns"
EXPECTED_TABLE_DOCUMENTS = 5
EXPECTED_COLUMN_DOCUMENTS = 40
SCHEMA_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "chatbi-engine/schema")


class SchemaIndexError(ValueError):
    """Schema Document 或索引构建契约失败。"""


@dataclass(frozen=True)
class IndexBuildResult:
    table_document_count: int
    column_document_count: int
    table_point_count: int
    column_point_count: int


class SchemaIndexer:
    """复用 Loader 输出，批量编码并幂等写入 Schema Collection。"""

    def __init__(self, encoder: BGE_M3Encoder, store: QdrantStore) -> None:
        self.encoder = encoder
        self.store = store

    @staticmethod
    def deterministic_point_id(kind: str, identity: str) -> str:
        """同一个 Schema 对象始终得到同一个 UUID5 Point ID。"""

        return str(uuid.uuid5(SCHEMA_ID_NAMESPACE, f"{kind}:{identity}"))

    def build(
        self,
        table_documents: Sequence[Document],
        column_documents: Sequence[Document],
    ) -> IndexBuildResult:
        self._validate_documents(
            table_documents,
            expected_count=EXPECTED_TABLE_DOCUMENTS,
            kind="table",
        )
        self._validate_documents(
            column_documents,
            expected_count=EXPECTED_COLUMN_DOCUMENTS,
            kind="column",
        )

        documents = [*table_documents, *column_documents]
        embeddings = self.encoder.encode_documents(documents)
        if len(embeddings) != len(documents):
            raise SchemaIndexError("embedding count does not match Document count")

        table_embeddings = embeddings[: len(table_documents)]
        column_embeddings = embeddings[len(table_documents) :]
        table_points = self._build_points(table_documents, table_embeddings, kind="table")
        column_points = self._build_points(
            column_documents,
            column_embeddings,
            kind="column",
        )

        self.store.ensure_collection(TABLE_COLLECTION)
        self.store.ensure_collection(COLUMN_COLLECTION)
        self.store.upsert(TABLE_COLLECTION, table_points)
        self.store.upsert(COLUMN_COLLECTION, column_points)

        table_point_count = self.store.count(TABLE_COLLECTION)
        column_point_count = self.store.count(COLUMN_COLLECTION)
        if table_point_count != EXPECTED_TABLE_DOCUMENTS:
            raise SchemaIndexError(
                f"schema_tables point count must be {EXPECTED_TABLE_DOCUMENTS}, "
                f"got {table_point_count}"
            )
        if column_point_count != EXPECTED_COLUMN_DOCUMENTS:
            raise SchemaIndexError(
                f"schema_columns point count must be {EXPECTED_COLUMN_DOCUMENTS}, "
                f"got {column_point_count}"
            )

        return IndexBuildResult(
            table_document_count=len(table_documents),
            column_document_count=len(column_documents),
            table_point_count=table_point_count,
            column_point_count=column_point_count,
        )

    def build_collection(
        self,
        documents: Sequence[Document],
        *,
        collection_name: str,
        kind: str,
        expected_count: int,
        identity_key: str,
    ) -> int:
        """将一类 Document 批量编码并幂等写入一个 named-vector Collection。"""

        self._validate_collection_documents(
            documents,
            expected_count=expected_count,
            kind=kind,
            identity_key=identity_key,
        )
        embeddings = self.encoder.encode_documents(documents)
        if len(embeddings) != len(documents):
            raise SchemaIndexError("embedding count does not match Document count")

        points = self._build_points(
            documents,
            embeddings,
            kind=kind,
            identity_key=identity_key,
        )
        self.store.ensure_collection(collection_name)
        self.store.upsert(collection_name, points)
        point_count = self.store.count(collection_name)
        if point_count != expected_count:
            raise SchemaIndexError(
                f"{collection_name} point count must be {expected_count}, got {point_count}"
            )
        return point_count

    @staticmethod
    def _validate_documents(
        documents: Sequence[Document],
        *,
        expected_count: int,
        kind: str,
    ) -> None:
        if len(documents) != expected_count:
            raise SchemaIndexError(
                f"{kind} Document count must be {expected_count}, got {len(documents)}"
            )

        identities: set[str] = set()
        for document in documents:
            if document.metadata.get("kind") != kind:
                raise SchemaIndexError(f"Document kind must be {kind}")
            table_name = document.metadata.get("table_name")
            if not isinstance(table_name, str) or not table_name:
                raise SchemaIndexError("Document table_name metadata is required")
            if kind == "table":
                identity = table_name
            else:
                column_name = document.metadata.get("column_name")
                if not isinstance(column_name, str) or not column_name:
                    raise SchemaIndexError("Column name metadata is required")
                if not isinstance(document.metadata.get("data_type"), str):
                    raise SchemaIndexError("Column data_type metadata is required")
                identity = f"{table_name}.{column_name}"
            if identity in identities:
                raise SchemaIndexError(f"Duplicate Schema identity: {identity}")
            identities.add(identity)

    @staticmethod
    def _validate_collection_documents(
        documents: Sequence[Document],
        *,
        expected_count: int,
        kind: str,
        identity_key: str,
    ) -> None:
        if len(documents) != expected_count:
            raise SchemaIndexError(
                f"{kind} Document count must be {expected_count}, got {len(documents)}"
            )
        identities: set[str] = set()
        for document in documents:
            identity = document.metadata.get(identity_key)
            if not isinstance(identity, str) or not identity:
                raise SchemaIndexError(f"Document {identity_key} metadata is required")
            if identity in identities:
                raise SchemaIndexError(f"Duplicate {kind} identity: {identity}")
            identities.add(identity)

    def _build_points(
        self,
        documents: Sequence[Document],
        embeddings: Sequence[EncodedText],
        *,
        kind: str,
        identity_key: str | None = None,
    ) -> list[models.PointStruct]:
        points: list[models.PointStruct] = []
        for document, embedding in zip(documents, embeddings, strict=True):
            if identity_key is not None:
                identity = str(document.metadata[identity_key])
            else:
                table_name = str(document.metadata["table_name"])
                if kind == "table":
                    identity = table_name
                else:
                    identity = f"{table_name}.{document.metadata['column_name']}"
            payload = {"page_content": document.page_content, **document.metadata}
            points.append(
                models.PointStruct(
                    id=self.deterministic_point_id(kind, identity),
                    vector=point_vector(embedding),
                    payload=payload,
                )
            )
        return points
