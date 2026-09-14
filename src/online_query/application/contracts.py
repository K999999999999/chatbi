"""Application（应用层）使用的中立数据传输对象。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from ..domain.models import (
    EmbeddingFingerprint,
    MetricDefinition,
    MetricPlan,
    OpaqueSnapshotIdentity,
    RelationshipGraphFacts,
    SnapshotBoundMetricDefinition,
    SnapshotResourceCatalog,
    TableRef,
)


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必须是非空字符串")
    return value.strip()


def _text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(values)
    if any(not isinstance(value, str) or not value.strip() for value in normalized):
        raise ValueError(f"{field_name} 只能包含非空字符串")
    return tuple(value.strip() for value in normalized)


class ContextSource(StrEnum):
    """最终 QueryContext 的受控来源。"""

    PUBLISHED = "PUBLISHED"
    STATIC_FALLBACK = "STATIC_FALLBACK"


class CollectionKind(StrEnum):
    """Application 可以请求的逻辑资源集合。"""

    TABLE = "TABLE"
    COLUMN = "COLUMN"
    METRIC = "METRIC"


@dataclass(frozen=True, slots=True)
class SanitizedTablePayload:
    """TABLE 命中允许跨越边界的最小正文。"""

    table_ref: TableRef
    display_name: str
    business_description: str
    labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.table_ref, TableRef):
            raise TypeError("table_payload.table_ref 必须是 TableRef")
        object.__setattr__(
            self,
            "display_name",
            _required_text(self.display_name, "table_payload.display_name"),
        )
        object.__setattr__(
            self,
            "business_description",
            _required_text(
                self.business_description,
                "table_payload.business_description",
            ),
        )
        object.__setattr__(self, "labels", _text_tuple(self.labels, "table_payload.labels"))


@dataclass(frozen=True, slots=True)
class SanitizedColumnPayload:
    """COLUMN 命中允许跨越边界的最小正文。"""

    table_ref: TableRef
    column_name: str
    display_name: str
    business_description: str
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.table_ref, TableRef):
            raise TypeError("column_payload.table_ref 必须是 TableRef")
        object.__setattr__(
            self,
            "column_name",
            _required_text(self.column_name, "column_payload.column_name"),
        )
        object.__setattr__(
            self,
            "display_name",
            _required_text(self.display_name, "column_payload.display_name"),
        )
        object.__setattr__(
            self,
            "business_description",
            _required_text(
                self.business_description,
                "column_payload.business_description",
            ),
        )
        object.__setattr__(self, "aliases", _text_tuple(self.aliases, "column_payload.aliases"))


@dataclass(frozen=True, slots=True)
class SanitizedMetricPayload:
    """METRIC 命中允许跨越边界的语义正文。"""

    document_id: str
    metric_name: str
    aliases: tuple[str, ...]
    semantic_text: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "document_id",
            _required_text(self.document_id, "metric_payload.document_id"),
        )
        object.__setattr__(
            self,
            "metric_name",
            _required_text(self.metric_name, "metric_payload.metric_name"),
        )
        object.__setattr__(self, "aliases", _text_tuple(self.aliases, "metric_payload.aliases"))
        object.__setattr__(
            self,
            "semantic_text",
            _required_text(self.semantic_text, "metric_payload.semantic_text"),
        )


SanitizedPayload: TypeAlias = (
    SanitizedTablePayload | SanitizedColumnPayload | SanitizedMetricPayload
)


@dataclass(frozen=True, slots=True)
class RawRetrievalHit:
    """已脱敏、仍保留检索证据的命中 DTO。"""

    snapshot_identity: OpaqueSnapshotIdentity
    asset_version: str
    collection_kind: CollectionKind
    document_id: str
    rank: int
    score: float
    payload: SanitizedPayload
    page_content: str

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot_identity, OpaqueSnapshotIdentity):
            raise TypeError("retrieval_hit.snapshot_identity 类型无效")
        if not isinstance(self.asset_version, str) or not self.asset_version.strip():
            raise ValueError("retrieval_hit.asset_version 必须是非空字符串")
        kind = (
            self.collection_kind
            if isinstance(self.collection_kind, CollectionKind)
            else CollectionKind(self.collection_kind)
        )
        if not isinstance(self.document_id, str) or not self.document_id.strip():
            raise ValueError("retrieval_hit.document_id 必须是非空字符串")
        if not isinstance(self.rank, int) or self.rank <= 0:
            raise ValueError("retrieval_hit.rank 必须是正整数")
        if not isinstance(self.score, (int, float)):
            raise TypeError("retrieval_hit.score 必须是数字")
        if not isinstance(
            self.payload,
            (SanitizedTablePayload, SanitizedColumnPayload, SanitizedMetricPayload),
        ):
            raise TypeError("retrieval_hit.payload 必须是受控 SanitizedPayload")
        expected_payload_type = {
            CollectionKind.TABLE: SanitizedTablePayload,
            CollectionKind.COLUMN: SanitizedColumnPayload,
            CollectionKind.METRIC: SanitizedMetricPayload,
        }[kind]
        if not isinstance(self.payload, expected_payload_type):
            raise TypeError("retrieval_hit.collection_kind 与 payload 类型不一致")
        if not isinstance(self.page_content, str):
            raise TypeError("retrieval_hit.page_content 必须是字符串")
        object.__setattr__(self, "asset_version", self.asset_version.strip())
        object.__setattr__(self, "collection_kind", kind)
        object.__setattr__(self, "document_id", self.document_id.strip())


@dataclass(frozen=True, slots=True)
class PublishedRetrievalSnapshot:
    """同一发布版本的不可变 Application 资产句柄。"""

    identity: OpaqueSnapshotIdentity
    asset_version: str
    available_collection_kinds: frozenset[CollectionKind]
    resource_catalog: SnapshotResourceCatalog
    metric_definitions: tuple[SnapshotBoundMetricDefinition, ...]
    relationship_graph: RelationshipGraphFacts
    embedding_fingerprint: EmbeddingFingerprint
    adapter_private_bindings: object

    def __post_init__(self) -> None:
        if not isinstance(self.identity, OpaqueSnapshotIdentity):
            raise TypeError("snapshot.identity 类型无效")
        if not isinstance(self.asset_version, str) or not self.asset_version.strip():
            raise ValueError("snapshot.asset_version 必须是非空字符串")
        kinds = frozenset(self.available_collection_kinds)
        if any(not isinstance(kind, CollectionKind) for kind in kinds):
            raise TypeError("snapshot.available_collection_kinds 只能包含 CollectionKind")
        definitions = tuple(self.metric_definitions)
        if any(not isinstance(item, SnapshotBoundMetricDefinition) for item in definitions):
            raise TypeError("snapshot.metric_definitions 类型无效")
        if any(
            item.snapshot_identity is not self.identity or item.asset_version != self.asset_version
            for item in definitions
        ):
            raise ValueError("Snapshot 中的指标定义必须绑定当前 identity 和 asset_version")
        if not isinstance(self.resource_catalog, SnapshotResourceCatalog):
            raise TypeError("snapshot.resource_catalog 类型无效")
        if not isinstance(self.relationship_graph, RelationshipGraphFacts):
            raise TypeError("snapshot.relationship_graph 类型无效")
        if not isinstance(self.embedding_fingerprint, EmbeddingFingerprint):
            raise TypeError("snapshot.embedding_fingerprint 类型无效")
        object.__setattr__(self, "asset_version", self.asset_version.strip())
        object.__setattr__(self, "available_collection_kinds", kinds)
        object.__setattr__(self, "metric_definitions", definitions)


__all__ = [
    "CollectionKind",
    "ContextSource",
    "MetricDefinition",
    "MetricPlan",
    "PublishedRetrievalSnapshot",
    "RawRetrievalHit",
    "SanitizedColumnPayload",
    "SanitizedMetricPayload",
    "SanitizedPayload",
    "SanitizedTablePayload",
]
