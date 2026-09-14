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

from .contracts import (
    ColumnHit,
    MetricConstraint,
    MetricHit,
    RetrievalConfig,
    RetrievalStatus,
    TableHit,
)
from .rag_runtime import AssetSnapshot


class ResourceRetrievalContractError(RuntimeError):
    """候选资源或指标必需字段不满足在线 Contract。"""


_METRIC_EXPRESSIONS = ("金额", "数量", "总额", "平均值", "占比", "率", "统计")
_METRIC_INTENT_TERMS = (
    "已完成订单数",
    "已完成订单数量",
    "完成订单数",
    "销售额",
    "净销售额",
    "营收",
    "销售成本",
    "人民币成本",
    "毛利率",
    "毛利润率",
    "毛利",
    "毛利润",
    "成本",
    "金额",
    "数量",
    "总额",
    "平均值",
    "占比",
    "统计",
)
_TIME_FIELD_PATTERN = re.compile(r"^\s*(?P<source>[^\s]+)\s*->\s*(?P<target>[^\s]+)\s*$")


@dataclass(frozen=True, slots=True)
class _TimeField:
    source_table: str
    source_column: str
    target_table: str
    filter_column: str
    edge_id: str = ""


def _has_metric_intent(
    question: str,
    catalog: Any | None = None,
) -> bool:
    """判断是否需要进入 METRIC 路线，不把普通实体查询误判为指标查询。"""

    normalized_question = _normalize(question)
    if any(
        _contains_normalized(normalized_question, term)
        for term in _METRIC_INTENT_TERMS
    ):
        return True
    entries = getattr(catalog, "entries", ())
    return any(
        _contains_normalized(normalized_question, label)
        for entry in entries
        for label in (entry.metric_name, *entry.aliases)
    )

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
    return tuple(_to_table_hit(hit, rank) for rank, hit in enumerate(filtered, 1))


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
    return tuple(_to_metric_hit(hit, rank) for rank, hit in enumerate(filtered, 1))


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
    # 所有字段只能来自候选表范围内的一次语义路线；不做业务字段补充。
    del required, grouping_query, grouping_tables
    embed = embed_query or snapshot.embedding_provider.embed_query
    search_hits = search or snapshot.qdrant_store.search
    embedded_query = embed(column_query)
    raw: list[ColumnHit] = []
    seen: set[str] = set()
    for table in table_hits:
        hits = search_hits(
            snapshot.collection_names[COLUMN_COLLECTION],
            embedded_query,
            limit=config.column_top_k,
            filter_payload={
                "schema_name": table.schema_name,
                "table_name": table.table_name,
            },
        )
        for hit in _filtered_hits(hits, config.column_score_threshold):
            column = _to_column_hit(hit, 0)
            if column.document_id not in seen:
                seen.add(column.document_id)
                raw.append(column)
    raw.sort(key=lambda item: (-item.score, item.document_id))
    selected = {
        (hit.qualified_table, hit.column_name): hit
        for hit in raw[: config.column_top_k]
    }
    ordered = sorted(selected.values(), key=lambda item: (-item.score, item.document_id))
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


def _is_metric_request(
    question: str,
    metric_hits: tuple[MetricHit, ...],
) -> bool:
    normalized_question = _normalize(question)
    for hit in metric_hits:
        candidates = (hit.metric_name, *_as_strings(hit.metadata.get("aliases")))
        if any(_contains_normalized(normalized_question, candidate) for candidate in candidates):
            return True
    return any(expression in question for expression in _METRIC_EXPRESSIONS)


def _select_metric(
    question: str,
    metric_hits: tuple[MetricHit, ...],
) -> tuple[MetricHit | None, RetrievalStatus | None]:
    normalized_question = _normalize(question)
    matched = tuple(
        (match_length, hit)
        for hit in metric_hits
        if (match_length := _metric_match_length(normalized_question, hit)) > 0
    )
    longest_match = max((length for length, _ in matched), default=0)
    exact = {
        hit.metric_name: hit
        for length, hit in matched
        if length == longest_match
    }
    if len(exact) == 1:
        return next(iter(exact.values())), None
    if len(exact) > 1:
        return None, RetrievalStatus.AMBIGUOUS
    if len(metric_hits) == 1:
        return metric_hits[0], None
    if not metric_hits:
        return None, None
    return None, RetrievalStatus.AMBIGUOUS


def _metric_match_length(question: str, hit: MetricHit) -> int:
    """返回命中的最长指标名或别名，避免短别名遮蔽长指标名。"""

    return max(
        (
            len(_normalize(candidate))
            for candidate in (
                hit.metric_name,
                *_as_strings(hit.metadata.get("aliases")),
            )
            if _contains_normalized(question, candidate)
        ),
        default=0,
    )


def _metric_data_source(metric: MetricHit) -> str:
    return _required_metadata_text(metric.metadata, "data_source", metric.document_id)


def _validate_metric_against_constraint(
    metric: MetricHit,
    constraint: MetricConstraint,
) -> None:
    """防止向量命中内容与同版本目录中的认证业务事实发生漂移。"""

    actual = (
        metric.metric_name,
        _required_metadata_text(metric.metadata, "formula", metric.document_id),
        _metric_data_source(metric),
        _required_metadata_text(metric.metadata, "time_field", metric.document_id),
        _as_strings(metric.metadata.get("filters")),
        _as_strings(metric.metadata.get("depends_on")),
    )
    expected = (
        constraint.metric_name,
        constraint.formula,
        constraint.data_source,
        constraint.time_field,
        constraint.filters,
        constraint.depends_on,
    )
    if actual != expected:
        raise ResourceRetrievalContractError(
            f"指标 {constraint.document_id} 的检索结果与同版本目录不一致"
        )


def _column_query(question: str, metric: MetricHit | None) -> str:
    if metric is None:
        return question
    formula = metric.metadata.get("formula", "")
    time_field = metric.metadata.get("time_field", "")
    return "\n".join(
        value
        for value in (question, metric.page_content, str(formula), str(time_field))
        if value
    )


def _multi_column_query(question: str, metrics: tuple[MetricHit, ...]) -> str:
    """合并全部指标的语义文本和认证字段事实，形成一次 COLUMN 查询。"""

    values: list[str] = [question]
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


def _as_strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(
        item.strip()
        for item in value
        if isinstance(item, str) and item.strip()
    )


def _normalize(value: str) -> str:
    return "".join(
        char
        for char in value.casefold()
        if char.isalnum() or "\u4e00" <= char <= "\u9fff"
    )


def _contains_normalized(text: str, candidate: str) -> bool:
    normalized = _normalize(candidate)
    return bool(normalized) and normalized in text
