"""Online Retrieval（在线检索）的阶段结果和执行依赖。"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from src.observability.contracts import TraceRecorder
from src.rag_offline.qdrant_store import SearchHit

from ..contracts import (
    ColumnHit,
    JoinConstraint,
    JoinResolution,
    MetricConstraint,
    MetricHit,
    MetricRetrievalEvidence,
    RetrievalConfig,
    RetrievalEvidence,
    TableHit,
)
from .rag_runtime import AssetSnapshot, RagRuntime
from .resource_retrieval import _TimeField
from .retrieval_trace import (
    candidate_trace_attributes as _candidate_trace_attributes,
    qualified_filter_table as _qualified_filter_table,
    safe_enrich_current as _safe_enrich_current,
    safe_span as _safe_span,
)


@dataclass(frozen=True, slots=True)
class _ResourceStage:
    """TABLE / METRIC 检索和指标计划阶段的内部结果。"""

    snapshot: AssetSnapshot
    table_hits: tuple[TableHit, ...]
    metric_hits_by_query: tuple[tuple[MetricHit, ...], ...]
    metric_hits: tuple[MetricHit, ...]
    metric_queries: tuple[MetricRetrievalEvidence, ...]
    selected_metrics: tuple[MetricHit, ...]
    metric_constraints: tuple[MetricConstraint, ...]
    evidence: RetrievalEvidence


@dataclass(frozen=True, slots=True)
class _ColumnStage:
    """COLUMN 检索和必需字段推导阶段的内部结果。"""

    time_field: _TimeField | None
    required: Mapping[str, frozenset[str]]
    candidate_tables: tuple[TableHit, ...]
    column_hits: tuple[ColumnHit, ...]
    evidence: RetrievalEvidence


@dataclass(frozen=True, slots=True)
class _JoinStage:
    """关系图解析阶段的内部结果。"""

    resolution: JoinResolution
    join_constraints: tuple[JoinConstraint, ...]
    anchor_reason: str


@dataclass(frozen=True, slots=True)
class _RetrievalExecution:
    """为各检索阶段提供共享 Runtime、配置和可观测性能力。"""

    runtime: RagRuntime
    config: RetrievalConfig
    trace_recorder: TraceRecorder | None

    def embed_query(self, snapshot: AssetSnapshot, text: str) -> Any:
        with _safe_span(self.trace_recorder, "embedding.query"):
            return snapshot.embedding_provider.embed_query(text)

    def search(
        self,
        stage: str,
        snapshot: AssetSnapshot,
        collection_name: str,
        query: Any,
        *,
        limit: int = 5,
        filter_payload: Mapping[str, str] | None = None,
    ) -> tuple[SearchHit, ...]:
        attributes: dict[str, object] = {
            "chatbi.retrieval.asset_version": snapshot.asset_version,
        }
        qualified_table = _qualified_filter_table(filter_payload)
        if qualified_table is not None:
            attributes["chatbi.retrieval.search.qualified_table"] = qualified_table
        with _safe_span(self.trace_recorder, stage, attributes):
            hits = tuple(
                snapshot.qdrant_store.search(
                    collection_name,
                    query,
                    limit=limit,
                    filter_payload=filter_payload,
                )
            )
            _safe_enrich_current(
                self.trace_recorder,
                _candidate_trace_attributes(hits, scope_table=qualified_table),
            )
            return hits
