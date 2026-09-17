"""候选资源检索，并兼容转发指标必需字段辅助。"""

from collections.abc import Callable, Iterable, Mapping
from types import MappingProxyType
from typing import Any

from src.rag_offline.documents import COLUMN_COLLECTION, METRIC_COLLECTION, TABLE_COLLECTION
from src.rag_offline.qdrant_store import SearchHit

from ..contracts import ColumnHit, MetricHit, RetrievalConfig, TableHit
# 保留原模块路径，避免内部调用和既有测试一次性迁移。
from .metric_requirements import (
    ResourceRetrievalContractError,
    _TimeField,
    _column_query,
    _contains_required_columns,
    _has_metric_intent,
    _metric_data_source,
    _missing_required_column_details,
    _multi_column_query,
    _parse_time_field,
    _required_columns_many,
)
from .rag_runtime import AssetSnapshot


def _table_hits(
    snapshot: AssetSnapshot,
    query: Any,
    config: RetrievalConfig,
    *,
    extra_queries: tuple[str, ...] = (),
    embed_query: Callable[[str], Any] | None = None,
    search: Callable[..., Iterable[SearchHit]] | None = None,
) -> tuple[TableHit, ...]:
    embed = embed_query or snapshot.embedding_provider.embed_query
    search_hits = search or snapshot.qdrant_store.search
    collection_name = snapshot.collection_names[TABLE_COLLECTION]
    raw_hits = list(
        search_hits(
            collection_name,
            query,
            limit=config.table_top_k,
        )
    )
    for extra_query in extra_queries:
        extra_embedding = embed(extra_query)
        raw_hits.extend(
            search_hits(
                collection_name,
                extra_embedding,
                limit=config.table_top_k,
            )
        )
    best_by_document: dict[str, SearchHit] = {}
    for hit in raw_hits:
        previous = best_by_document.get(hit.document_id)
        if previous is None or hit.score > previous.score:
            best_by_document[hit.document_id] = hit
    filtered = _filtered_hits(
        best_by_document.values(),
        config.table_score_threshold,
    )
    return tuple(
        _to_table_hit(hit, rank)
        for rank, hit in enumerate(filtered[: config.table_top_k], 1)
    )


def _metric_hits(
    snapshot: AssetSnapshot,
    query: Any,
    config: RetrievalConfig,
    *,
    search: Callable[..., Iterable[SearchHit]] | None = None,
) -> tuple[MetricHit, ...]:
    search_hits = search or snapshot.qdrant_store.search
    raw_hits = search_hits(
        snapshot.collection_names[METRIC_COLLECTION],
        query,
        limit=config.metric_top_k,
    )
    filtered = _filtered_hits(raw_hits, config.metric_score_threshold)
    return tuple(
        _to_metric_hit(hit, rank)
        for rank, hit in enumerate(filtered[: config.metric_top_k], 1)
    )


def _column_hits(
    snapshot: AssetSnapshot,
    table_hits: tuple[TableHit, ...],
    column_query: str,
    config: RetrievalConfig,
    *,
    required: Mapping[str, frozenset[str]] = MappingProxyType({}),
    grouping_query: str = "",
    grouping_tables: frozenset[str] = frozenset(),
    embed_query: Callable[[str], Any] | None = None,
    search: Callable[..., Iterable[SearchHit]] | None = None,
) -> tuple[ColumnHit, ...]:
    # 只在候选表范围内恢复明确依赖字段和用户明确请求的分组字段。
    # 恢复结果与普通语义结果共用全局 column_top_k 预算，避免扩大 Schema 暴露范围。
    embed = embed_query or snapshot.embedding_provider.embed_query
    search_hits = search or snapshot.qdrant_store.search
    embedded_query = embed(column_query)
    grouping_embedding = (
        embed(grouping_query)
        if grouping_query and grouping_tables
        else None
    )
    required_hits: dict[tuple[str, str], ColumnHit] = {}
    grouping_hits: dict[tuple[str, str], ColumnHit] = {}
    semantic_hits: dict[tuple[str, str], ColumnHit] = {}

    def collect(
        target: dict[tuple[str, str], ColumnHit],
        hits: Iterable[SearchHit],
        *,
        apply_threshold: bool = True,
    ) -> None:
        filtered = (
            _filtered_hits(hits, config.column_score_threshold)
            if apply_threshold
            else tuple(sorted(hits, key=lambda item: (-item.score, item.document_id)))
        )
        for hit in filtered:
            column = _to_column_hit(hit, 0)
            identity = (column.qualified_table, column.column_name)
            previous = target.get(identity)
            if previous is None or column.score > previous.score:
                target[identity] = column

    for table in table_hits:
        table_filter = {
            "schema_name": table.schema_name,
            "table_name": table.table_name,
        }
        hits = search_hits(
            snapshot.collection_names[COLUMN_COLLECTION],
            embedded_query,
            limit=config.column_top_k,
            filter_payload=table_filter,
        )
        collect(semantic_hits, hits)

        if grouping_embedding is not None and table.qualified_name in grouping_tables:
            grouped_hits = search_hits(
                snapshot.collection_names[COLUMN_COLLECTION],
                grouping_embedding,
                limit=min(2, config.column_top_k),
                filter_payload=table_filter,
            )
            collect(grouping_hits, grouped_hits)

        for required_column in sorted(required.get(table.qualified_name, frozenset())):
            exact_hits = search_hits(
                snapshot.collection_names[COLUMN_COLLECTION],
                embedded_query,
                limit=1,
                filter_payload={
                    **table_filter,
                    "column_name": required_column,
                },
            )
            # 物理字段已由 METRIC / time_field 权威事实确定；精确 Metadata
            # 过滤命中即可恢复，不再用语义分数把它丢掉。
            collect(required_hits, exact_hits, apply_threshold=False)

    ordered: list[ColumnHit] = []
    seen: set[tuple[str, str]] = set()
    for bucket in (required_hits, grouping_hits, semantic_hits):
        for hit in sorted(
            bucket.values(),
            key=lambda item: (-item.score, item.document_id),
        ):
            identity = (hit.qualified_table, hit.column_name)
            if identity in seen:
                continue
            seen.add(identity)
            ordered.append(hit)
            if len(ordered) == config.column_top_k:
                break
        if len(ordered) == config.column_top_k:
            break
    return tuple(_re_rank_column(hit, rank) for rank, hit in enumerate(ordered, 1))


def _filtered_hits(
    hits: Iterable[SearchHit],
    threshold: float,
) -> tuple[SearchHit, ...]:
    return tuple(
        sorted(
            (hit for hit in hits if hit.score >= threshold),
            key=lambda item: (-item.score, item.document_id),
        )
    )


def _to_table_hit(hit: SearchHit, rank: int) -> TableHit:
    metadata = _metadata(hit, "TABLE")
    schema_name = _required_metadata_text(metadata, "schema_name", hit.document_id)
    table_name = _required_metadata_text(metadata, "table_name", hit.document_id)
    table_role = metadata.get("table_type", "")
    if not isinstance(table_role, str):
        table_role = ""
    return TableHit(
        document_id=hit.document_id,
        schema_name=schema_name,
        table_name=table_name,
        table_role=table_role,
        score=hit.score,
        rank=rank,
        metadata=MappingProxyType(dict(metadata)),
        page_content=_page_content(hit, "TABLE"),
    )


def _to_column_hit(hit: SearchHit, rank: int) -> ColumnHit:
    metadata = _metadata(hit, "COLUMN")
    schema_name = _required_metadata_text(metadata, "schema_name", hit.document_id)
    table_name = _required_metadata_text(metadata, "table_name", hit.document_id)
    column_name = _required_metadata_text(metadata, "column_name", hit.document_id)
    data_type = _required_metadata_text(metadata, "data_type", hit.document_id)
    page_content = hit.payload.get("page_content", "")
    if not isinstance(page_content, str):
        raise ResourceRetrievalContractError(f"COLUMN {hit.document_id} 的 page_content 无效")
    return ColumnHit(
        document_id=hit.document_id,
        schema_name=schema_name,
        table_name=table_name,
        column_name=column_name,
        data_type=data_type,
        score=hit.score,
        rank=rank,
        metadata=MappingProxyType(dict(metadata)),
        page_content=page_content,
    )


def _to_metric_hit(hit: SearchHit, rank: int) -> MetricHit:
    metadata = _metadata(hit, "METRIC")
    metric_name = _required_metadata_text(metadata, "metric_name", hit.document_id)
    page_content = hit.payload.get("page_content", "")
    if not isinstance(page_content, str) or not page_content.strip():
        raise ResourceRetrievalContractError(f"METRIC {hit.document_id} 的 page_content 无效")
    return MetricHit(
        document_id=hit.document_id,
        metric_name=metric_name,
        score=hit.score,
        rank=rank,
        metadata=MappingProxyType(dict(metadata)),
        page_content=page_content,
    )


def _page_content(hit: SearchHit, expected_doc_type: str) -> str:
    page_content = hit.payload.get("page_content", "")
    if not isinstance(page_content, str):
        raise ResourceRetrievalContractError(
            f"{expected_doc_type} {hit.document_id} 的 page_content 无效"
        )
    return page_content


def _metadata(hit: SearchHit, expected_doc_type: str) -> Mapping[str, Any]:
    metadata = hit.payload.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ResourceRetrievalContractError(f"{expected_doc_type} {hit.document_id} 缺少 metadata")
    if metadata.get("doc_type") != expected_doc_type:
        raise ResourceRetrievalContractError(f"{hit.document_id} 的 doc_type 不正确")
    return metadata


def _required_metadata_text(
    metadata: Mapping[str, Any],
    key: str,
    document_id: str,
) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ResourceRetrievalContractError(f"{document_id} 缺少有效 {key}")
    return value.strip()


def _re_rank_column(hit: ColumnHit, rank: int) -> ColumnHit:
    return ColumnHit(
        document_id=hit.document_id,
        schema_name=hit.schema_name,
        table_name=hit.table_name,
        column_name=hit.column_name,
        data_type=hit.data_type,
        score=hit.score,
        rank=rank,
        metadata=hit.metadata,
        page_content=hit.page_content,
    )
