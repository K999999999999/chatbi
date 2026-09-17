"""候选资源检索与指标必需字段处理。"""

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Any

from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError

from src.rag_offline.documents import COLUMN_COLLECTION, METRIC_COLLECTION, TABLE_COLLECTION
from src.rag_offline.qdrant_store import SearchHit

from .contracts import ColumnHit, MetricHit, RetrievalConfig, TableHit
from .query_understanding import ValidatedSemanticQuery
from .rag_runtime import AssetSnapshot


class ResourceRetrievalContractError(RuntimeError):
    """候选资源或指标必需字段不满足在线 Contract。"""


_TIME_FIELD_PATTERN = re.compile(r"^\s*(?P<source>[^\s]+)\s*->\s*(?P<target>[^\s]+)\s*$")


@dataclass(frozen=True, slots=True)
class _TimeField:
    source_table: str
    source_column: str
    target_table: str
    filter_column: str
    edge_id: str = ""


def _table_query(query: ValidatedSemanticQuery) -> str:
    """将已确认的业务主题、维度、指标和过滤字段拼成 TABLE 查询。"""

    return _semantic_query_text(
        (
            *query.subjects,
            *query.dimensions,
            *query.metrics,
            *(item.field_text for item in query.filters),
        )
    )


def _semantic_query_text(values: tuple[str, ...]) -> str:
    return "、".join(value.strip() for value in values if value.strip())


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


def _metric_data_source(metric: MetricHit) -> str:
    return _required_metadata_text(metric.metadata, "data_source", metric.document_id)


def _column_query(query: ValidatedSemanticQuery, metric: MetricHit | None) -> str:
    base_query = _semantic_query_text(
        (
            *query.dimensions,
            *(item.field_text for item in query.filters),
            *query.subjects,
        )
    )
    formula = metric.metadata.get("formula", "") if metric else ""
    time_field = metric.metadata.get("time_field", "") if metric else ""
    return "\n".join(
        value
        for value in (
            base_query,
            metric.page_content if metric else "",
            str(formula),
            str(time_field),
        )
        if value
    )


def _multi_column_query(
    query: ValidatedSemanticQuery,
    metrics: tuple[MetricHit, ...],
) -> str:
    """合并全部指标的语义文本和认证字段事实，形成一次 COLUMN 查询。"""

    values: list[str] = [
        _semantic_query_text(
            (
                *query.dimensions,
                *(item.field_text for item in query.filters),
                *query.subjects,
            )
        )
    ]
    for metric in metrics:
        values.extend(
            (
                metric.page_content,
                str(metric.metadata.get("formula", "")),
                str(metric.metadata.get("time_field", "")),
            )
        )
    return "\n".join(dict.fromkeys(value for value in values if value))


def _parse_time_field(metric: MetricHit | None) -> _TimeField | None:
    if metric is None:
        return None
    raw = metric.metadata.get("time_field")
    if not isinstance(raw, str) or not raw.strip():
        raise ResourceRetrievalContractError(f"指标 {metric.metric_name} 缺少有效 time_field")
    match = _TIME_FIELD_PATTERN.fullmatch(raw)
    if match is None:
        raise ResourceRetrievalContractError(f"指标 {metric.metric_name} 的 time_field 格式无效")
    source_table, source_column = _split_field_ref(match.group("source"), metric)
    target_table, filter_column = _split_field_ref(match.group("target"), metric)
    return _TimeField(source_table, source_column, target_table, filter_column)


def _split_field_ref(value: str, metric: MetricHit) -> tuple[str, str]:
    parts = value.split(".")
    if len(parts) == 2:
        return f"{_metric_schema(metric)}.{parts[0]}", parts[1]
    if len(parts) == 3:
        return f"{parts[0]}.{parts[1]}", parts[2]
    raise ResourceRetrievalContractError(f"指标 {metric.metric_name} 的字段引用格式无效：{value}")


def _metric_schema(metric: MetricHit) -> str:
    source = _metric_data_source(metric).split(".")
    if len(source) != 2:
        raise ResourceRetrievalContractError(f"指标 {metric.metric_name} 的 data_source 格式无效")
    return source[0]


def _required_columns(
    metric: MetricHit | None,
    time_field: _TimeField | None,
) -> Mapping[str, frozenset[str]]:
    if metric is None:
        return MappingProxyType({})
    formula = metric.metadata.get("formula")
    if not isinstance(formula, str) or not formula.strip():
        raise ResourceRetrievalContractError(f"指标 {metric.metric_name} 缺少有效 formula")
    try:
        expression = parse_one(f"SELECT {formula}", read="postgres")
    except (SqlglotError, ValueError, TypeError) as exc:
        raise ResourceRetrievalContractError(
            f"指标 {metric.metric_name} 的 formula 无法确定性解析"
        ) from exc
    result: dict[str, set[str]] = defaultdict(set)
    data_source = _metric_data_source(metric)
    for column in expression.find_all(exp.Column):
        if not column.name or column.name == "*":
            raise ResourceRetrievalContractError(
                f"指标 {metric.metric_name} 的 formula 存在无法解析的字段引用"
            )
        result[data_source].add(column.name)
    filters = metric.metadata.get("filters", ())
    if not isinstance(filters, (list, tuple)):
        raise ResourceRetrievalContractError(f"指标 {metric.metric_name} 的 filters 格式无效")
    for index, filter_expression in enumerate(filters, 1):
        if not isinstance(filter_expression, str) or not filter_expression.strip():
            raise ResourceRetrievalContractError(
                f"指标 {metric.metric_name} 的第 {index} 个 filter 无效"
            )
        try:
            filter_ast = parse_one(
                f"SELECT {filter_expression}",
                read="postgres",
            )
        except (SqlglotError, ValueError, TypeError) as exc:
            raise ResourceRetrievalContractError(
                f"指标 {metric.metric_name} 的 filter 无法确定性解析"
            ) from exc
        for column in filter_ast.find_all(exp.Column):
            if not column.name or column.name == "*":
                raise ResourceRetrievalContractError(
                    f"指标 {metric.metric_name} 的 filter 存在无法解析的字段引用"
                )
            result[data_source].add(column.name)
    if time_field is not None:
        result[time_field.source_table].add(time_field.source_column)
        result[time_field.target_table].add(time_field.filter_column)
    return MappingProxyType(
        {table: frozenset(columns) for table, columns in result.items()}
    )


def _required_columns_many(
    metrics: tuple[MetricHit, ...],
    time_field: _TimeField | None,
) -> Mapping[str, frozenset[str]]:
    """合并全部指标公式、过滤条件及公共时间关系要求的字段。"""

    merged: defaultdict[str, set[str]] = defaultdict(set)
    for metric in metrics:
        for table, columns in _required_columns(metric, time_field).items():
            merged[table].update(columns)
    return MappingProxyType(
        {
            table: frozenset(columns)
            for table, columns in sorted(merged.items())
        }
    )


def _contains_required_columns(
    column_hits: tuple[ColumnHit, ...],
    required: Mapping[str, frozenset[str]],
) -> bool:
    by_table: defaultdict[str, set[str]] = defaultdict(set)
    for hit in column_hits:
        by_table[hit.qualified_table].add(hit.column_name)
    return all(
        required_columns <= by_table.get(table, set())
        for table, required_columns in required.items()
    )


def _missing_required_column_details(
    metrics: tuple[MetricHit, ...],
    time_field: _TimeField | None,
    column_hits: tuple[ColumnHit, ...],
) -> tuple[str, ...]:
    """记录每个缺失物理字段及依赖它的请求指标。"""

    available = {
        (hit.qualified_table, hit.column_name)
        for hit in column_hits
    }
    dependents: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    for metric in metrics:
        for table, columns in _required_columns(metric, time_field).items():
            for column in columns:
                if (table, column) not in available:
                    dependents[(table, column)].add(metric.metric_name)
    return tuple(
        f"缺失字段 {table}.{column}；影响指标：{'、'.join(sorted(names))}"
        for (table, column), names in sorted(dependents.items())
    )


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
