"""Online Retrieval（在线检索）三路检索、关系解析和上下文组装。"""

from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import json
import re
from types import MappingProxyType
from typing import Any

from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError

from src.rag_offline.documents import COLUMN_COLLECTION, METRIC_COLLECTION, TABLE_COLLECTION
from src.rag_offline.embedding import EmbeddingError
from src.rag_offline.qdrant_store import QdrantStoreError, SearchHit

from .contracts import (
    ColumnHit,
    JoinEdge,
    JoinPath,
    JoinResolution,
    MetricHit,
    OnlineRetrievalResult,
    QueryContext,
    RetrievalConfig,
    RetrievalEvidence,
    RetrievalStatus,
    TableHit,
)
from .rag_runtime import (
    AssetSnapshot,
    AssetUnavailableError,
    EmbeddingUnavailableError,
    RagRuntime,
    RetrievalUnavailableError,
)


class RetrievalContractError(RuntimeError):
    """检索结果或已发布资产不满足在线契约。"""


class _AmbiguousRetrieval(RuntimeError):
    """确定性规则无法在多个业务路径中做唯一选择。"""


class _UnreachableRequired(RuntimeError):
    """必需表无法通过已验证关系到达。"""


_METRIC_EXPRESSIONS = ("金额", "数量", "总额", "平均值", "占比", "率", "统计")
_GENERIC_GROUPING_TERMS = frozenset(
    {"类型", "属性", "业务", "数据", "信息", "记录", "完成", "订单", "金额", "统计"}
)
_TIME_FIELD_PATTERN = re.compile(r"^\s*(?P<source>[^\s]+)\s*->\s*(?P<target>[^\s]+)\s*$")


@dataclass(frozen=True, slots=True)
class _TimeField:
    source_table: str
    source_column: str
    target_table: str
    filter_column: str
    edge_id: str = ""


class OnlineRetriever:
    """使用一个 RAG Runtime 完成单次同步在线检索。"""

    def __init__(
        self,
        runtime: RagRuntime,
        *,
        config: RetrievalConfig | None = None,
    ) -> None:
        self._runtime = runtime
        self._config = config or RetrievalConfig()

    def retrieve(self, question: str) -> OnlineRetrievalResult:
        """执行 TABLE、COLUMN、METRIC 和确定性关系解析。"""

        if not isinstance(question, str) or not question.strip():
            raise ValueError("检索问题不能为空")
        question = question.strip()
        grouping_text = _grouping_text(question)
        try:
            snapshot = self._runtime.get_snapshot()
        except AssetUnavailableError as exc:
            return _failure(RetrievalStatus.ASSET_UNAVAILABLE, str(exc))
        except RetrievalUnavailableError as exc:
            return _failure(RetrievalStatus.RETRIEVAL_UNAVAILABLE, str(exc))
        except EmbeddingUnavailableError as exc:
            return _failure(RetrievalStatus.EMBEDDING_UNAVAILABLE, str(exc))
        except Exception as exc:
            return _failure(RetrievalStatus.ASSET_UNAVAILABLE, str(exc))

        try:
            query_embedding = snapshot.embedding_provider.embed_query(question)
            table_hits = _table_hits(
                snapshot,
                query_embedding,
                self._config,
                extra_queries=(grouping_text,) if grouping_text else (),
            )
            metric_hits = _metric_hits(snapshot, query_embedding, self._config)
        except EmbeddingError as exc:
            return _failure(RetrievalStatus.EMBEDDING_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version)
        except QdrantStoreError as exc:
            return _failure(RetrievalStatus.RETRIEVAL_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version)
        except RetrievalContractError as exc:
            return _failure(RetrievalStatus.ASSET_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version)
        except Exception as exc:
            return _failure(RetrievalStatus.RETRIEVAL_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version)

        evidence = RetrievalEvidence(table_hits=table_hits, metric_hits=metric_hits)
        if not table_hits:
            return _result(RetrievalStatus.NO_TABLE_HIT, snapshot.asset_version, evidence=evidence, warnings=("TABLE 检索没有超过阈值的有效候选",))

        metric = None
        if _is_metric_request(question, metric_hits):
            metric, metric_error = _select_metric(question, metric_hits)
            if metric_error is not None:
                return _result(metric_error, snapshot.asset_version, tables=table_hits, evidence=evidence, warnings=("METRIC 候选无法唯一确定",))
            if metric is None:
                return _result(RetrievalStatus.NO_METRIC_HIT, snapshot.asset_version, tables=table_hits, evidence=evidence, warnings=("指标类请求没有超过阈值的有效指标",))

        metric_table = _metric_data_source(metric) if metric is not None else None
        if metric_table is not None and not any(hit.qualified_name == metric_table for hit in table_hits):
            return _result(RetrievalStatus.NO_TABLE_HIT, snapshot.asset_version, tables=table_hits, metrics=(metric,), evidence=evidence, warnings=("指标 data_source 没有被 TABLE 路线命中",))

        try:
            time_field = _parse_time_field(metric) if metric is not None else None
            required = _required_columns(metric, time_field)
            candidate_tables = _candidate_table_hits(
                question,
                table_hits,
                metric_table,
                time_field,
            )
            column_query = _column_query(question, metric)
            grouping_tables = _grouping_table_names(
                grouping_text,
                table_hits,
                metric_table,
            )
            column_hits = _column_hits(
                snapshot,
                candidate_tables,
                column_query,
                self._config,
                required=required,
                grouping_query=grouping_text,
                grouping_tables=grouping_tables,
            )
        except EmbeddingError as exc:
            return _failure(RetrievalStatus.EMBEDDING_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version, evidence=evidence)
        except QdrantStoreError as exc:
            return _failure(RetrievalStatus.RETRIEVAL_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version, evidence=evidence)
        except RetrievalContractError as exc:
            return _failure(RetrievalStatus.ASSET_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version, evidence=evidence)

        evidence = RetrievalEvidence(table_hits=table_hits, column_hits=column_hits, metric_hits=metric_hits)
        if not column_hits:
            return _result(RetrievalStatus.NO_REQUIRED_COLUMN_HIT, snapshot.asset_version, tables=table_hits, metrics=(metric,) if metric else (), evidence=evidence, warnings=("COLUMN 检索没有超过阈值的有效候选",))

        try:
            if not _contains_required_columns(column_hits, required):
                return _result(RetrievalStatus.NO_REQUIRED_COLUMN_HIT, snapshot.asset_version, tables=table_hits, fields=column_hits, metrics=(metric,) if metric else (), evidence=evidence, warnings=("公式或 time_field 引用的必需字段没有被 COLUMN 命中",))
            anchor, reason = _select_anchor(metric, table_hits)
            edges = _graph_edges(snapshot.relationship_graph)
            if time_field is not None:
                time_field = _validate_time_edge(time_field, edges)
            targets = _target_tables(candidate_tables, metric_table, time_field)
            resolution = _resolve_join_paths(
                anchor,
                targets,
                edges,
                time_edge=time_field.edge_id if time_field else None,
                time_target=time_field.target_table if time_field else None,
            )
        except _AmbiguousRetrieval as exc:
            return _result(RetrievalStatus.AMBIGUOUS, snapshot.asset_version, tables=table_hits, fields=column_hits, metrics=(metric,) if metric else (), evidence=evidence, warnings=(str(exc),))
        except _UnreachableRequired as exc:
            return _result(RetrievalStatus.PARTIAL_UNREACHABLE, snapshot.asset_version, tables=table_hits, fields=column_hits, metrics=(metric,) if metric else (), evidence=evidence, warnings=(str(exc),))
        except RetrievalContractError as exc:
            return _failure(RetrievalStatus.ASSET_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version, evidence=evidence)

        final_tables = _final_table_hits(candidate_tables, resolution)
        final_fields = _final_column_hits(
            column_hits,
            resolution,
            allowed_tables=frozenset(table.qualified_name for table in final_tables),
        )
        dynamic_schema = _build_dynamic_schema(final_tables, final_fields, resolution)
        indicator_context = _build_indicator_context(metric)
        query_context = QueryContext(
            prompt_context=_build_prompt_context(dynamic_schema, indicator_context),
            allowed_tables=frozenset(hit.qualified_name for hit in final_tables),
            allowed_columns=MappingProxyType(_allowed_columns(final_fields)),
        )
        evidence = RetrievalEvidence(table_hits=table_hits, column_hits=column_hits, metric_hits=metric_hits, join_paths=resolution.paths)
        return _result(
            RetrievalStatus.SUCCESS,
            snapshot.asset_version,
            tables=final_tables,
            fields=final_fields,
            metrics=(metric,) if metric else (),
            join_path=resolution,
            dynamic_schema=dynamic_schema,
            indicator_context=indicator_context,
            evidence=evidence,
            warnings=(f"anchor_reason={reason}",),
            query_context=query_context,
        )


def _table_hits(
    snapshot: AssetSnapshot,
    query: Any,
    config: RetrievalConfig,
    *,
    extra_queries: tuple[str, ...] = (),
) -> tuple[TableHit, ...]:
    collection_name = snapshot.collection_names[TABLE_COLLECTION]
    raw_hits = list(
        snapshot.qdrant_store.search(
            collection_name,
            query,
            limit=config.table_top_k,
        )
    )
    for extra_query in extra_queries:
        extra_embedding = snapshot.embedding_provider.embed_query(extra_query)
        raw_hits.extend(
            snapshot.qdrant_store.search(
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
) -> tuple[MetricHit, ...]:
    raw_hits = snapshot.qdrant_store.search(
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
) -> tuple[ColumnHit, ...]:
    # Metric formula/time_field 补充文本需要单独向量化；同一请求仍只保留一条列检索路线。
    embedded_query = snapshot.embedding_provider.embed_query(column_query)
    grouping_embedding = (
        snapshot.embedding_provider.embed_query(grouping_query)
        if grouping_query and grouping_tables
        else None
    )
    raw: list[ColumnHit] = []
    grouping_priority: list[ColumnHit] = []
    seen: set[str] = set()
    for table in table_hits:
        hits = snapshot.qdrant_store.search(
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
        if grouping_embedding is not None and table.qualified_name in grouping_tables:
            grouped_hits = snapshot.qdrant_store.search(
                snapshot.collection_names[COLUMN_COLLECTION],
                grouping_embedding,
                limit=min(2, config.column_top_k),
                filter_payload={
                    "schema_name": table.schema_name,
                    "table_name": table.table_name,
                },
            )
            for hit in _filtered_hits(grouped_hits, config.column_score_threshold)[:2]:
                column = _to_column_hit(hit, 0)
                if column.document_id not in seen:
                    seen.add(column.document_id)
                    raw.append(column)
                grouping_priority.append(column)
        for required_column in required.get(table.qualified_name, frozenset()):
            exact_hits = snapshot.qdrant_store.search(
                snapshot.collection_names[COLUMN_COLLECTION],
                embedded_query,
                limit=1,
                filter_payload={
                    "schema_name": table.schema_name,
                    "table_name": table.table_name,
                    "column_name": required_column,
                },
            )
            for hit in _filtered_hits(exact_hits, config.column_score_threshold):
                column = _to_column_hit(hit, 0)
                if column.document_id not in seen:
                    seen.add(column.document_id)
                    raw.append(column)
    raw.sort(key=lambda item: (-item.score, item.document_id))
    selected = {
        (hit.qualified_table, hit.column_name): hit
        for hit in raw[: config.column_top_k]
    }
    for hit in raw:
        key = (hit.qualified_table, hit.column_name)
        if hit.column_name in required.get(hit.qualified_table, frozenset()):
            selected[key] = hit
    for hit in grouping_priority:
        selected[(hit.qualified_table, hit.column_name)] = hit
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
        raise RetrievalContractError(f"COLUMN {hit.document_id} 的 page_content 无效")
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
        raise RetrievalContractError(f"METRIC {hit.document_id} 的 page_content 无效")
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
        raise RetrievalContractError(
            f"{expected_doc_type} {hit.document_id} 的 page_content 无效"
        )
    return page_content


def _metadata(hit: SearchHit, expected_doc_type: str) -> Mapping[str, Any]:
    metadata = hit.payload.get("metadata")
    if not isinstance(metadata, Mapping):
        raise RetrievalContractError(f"{expected_doc_type} {hit.document_id} 缺少 metadata")
    if metadata.get("doc_type") != expected_doc_type:
        raise RetrievalContractError(f"{hit.document_id} 的 doc_type 不正确")
    return metadata


def _required_metadata_text(
    metadata: Mapping[str, Any],
    key: str,
    document_id: str,
) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RetrievalContractError(f"{document_id} 缺少有效 {key}")
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


def _parse_time_field(metric: MetricHit | None) -> _TimeField | None:
    if metric is None:
        return None
    raw = metric.metadata.get("time_field")
    if not isinstance(raw, str) or not raw.strip():
        raise RetrievalContractError(f"指标 {metric.metric_name} 缺少有效 time_field")
    match = _TIME_FIELD_PATTERN.fullmatch(raw)
    if match is None:
        raise RetrievalContractError(f"指标 {metric.metric_name} 的 time_field 格式无效")
    source_table, source_column = _split_field_ref(match.group("source"), metric)
    target_table, filter_column = _split_field_ref(match.group("target"), metric)
    return _TimeField(source_table, source_column, target_table, filter_column)


def _split_field_ref(value: str, metric: MetricHit) -> tuple[str, str]:
    parts = value.split(".")
    if len(parts) == 2:
        return f"{_metric_schema(metric)}.{parts[0]}", parts[1]
    if len(parts) == 3:
        return f"{parts[0]}.{parts[1]}", parts[2]
    raise RetrievalContractError(f"指标 {metric.metric_name} 的字段引用格式无效：{value}")


def _metric_schema(metric: MetricHit) -> str:
    source = _metric_data_source(metric).split(".")
    if len(source) != 2:
        raise RetrievalContractError(f"指标 {metric.metric_name} 的 data_source 格式无效")
    return source[0]


def _required_columns(
    metric: MetricHit | None,
    time_field: _TimeField | None,
) -> Mapping[str, frozenset[str]]:
    if metric is None:
        return MappingProxyType({})
    formula = metric.metadata.get("formula")
    if not isinstance(formula, str) or not formula.strip():
        raise RetrievalContractError(f"指标 {metric.metric_name} 缺少有效 formula")
    try:
        expression = parse_one(f"SELECT {formula}", read="postgres")
    except (SqlglotError, ValueError, TypeError) as exc:
        raise RetrievalContractError(
            f"指标 {metric.metric_name} 的 formula 无法确定性解析"
        ) from exc
    result: dict[str, set[str]] = defaultdict(set)
    data_source = _metric_data_source(metric)
    for column in expression.find_all(exp.Column):
        if not column.name or column.name == "*":
            raise RetrievalContractError(
                f"指标 {metric.metric_name} 的 formula 存在无法解析的字段引用"
            )
        result[data_source].add(column.name)
    filters = metric.metadata.get("filters", ())
    if not isinstance(filters, (list, tuple)):
        raise RetrievalContractError(f"指标 {metric.metric_name} 的 filters 格式无效")
    for index, filter_expression in enumerate(filters, 1):
        if not isinstance(filter_expression, str) or not filter_expression.strip():
            raise RetrievalContractError(
                f"指标 {metric.metric_name} 的第 {index} 个 filter 无效"
            )
        try:
            filter_ast = parse_one(
                f"SELECT {filter_expression}",
                read="postgres",
            )
        except (SqlglotError, ValueError, TypeError) as exc:
            raise RetrievalContractError(
                f"指标 {metric.metric_name} 的 filter 无法确定性解析"
            ) from exc
        for column in filter_ast.find_all(exp.Column):
            if not column.name or column.name == "*":
                raise RetrievalContractError(
                    f"指标 {metric.metric_name} 的 filter 存在无法解析的字段引用"
                )
            result[data_source].add(column.name)
    if time_field is not None:
        result[time_field.source_table].add(time_field.source_column)
        result[time_field.target_table].add(time_field.filter_column)
    return MappingProxyType(
        {table: frozenset(columns) for table, columns in result.items()}
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


def _select_anchor(
    metric: MetricHit | None,
    table_hits: tuple[TableHit, ...],
) -> tuple[str, str]:
    if metric is not None:
        return _metric_data_source(metric), "metric_data_source"
    if not table_hits:
        raise RetrievalContractError("无法选择 Anchor：TABLE 候选为空")
    return table_hits[0].qualified_name, "highest_table_score"


def _graph_edges(graph: Mapping[str, Any]) -> tuple[JoinEdge, ...]:
    raw_edges = graph.get("foreign_keys")
    if not isinstance(raw_edges, list):
        raise RetrievalContractError("Relationship Graph 缺少 foreign_keys")
    edges: list[JoinEdge] = []
    for index, raw in enumerate(raw_edges, 1):
        if not isinstance(raw, Mapping):
            raise RetrievalContractError(f"Relationship Graph 第 {index} 条边格式无效")
        edge_id = _text(raw, "constraint_name", index)
        source_table = _qualified_from_graph(raw, "source_schema", "source_table", index)
        target_table = _qualified_from_graph(raw, "target_schema", "target_table", index)
        source_columns = _string_tuple(raw.get("source_columns"), "source_columns", index)
        target_columns = _string_tuple(raw.get("target_columns"), "target_columns", index)
        if len(source_columns) != len(target_columns):
            raise RetrievalContractError(f"Relationship Graph 第 {index} 条边键数量不一致")
        edges.append(
            JoinEdge(
                edge_id=edge_id,
                source_table=source_table,
                target_table=target_table,
                source_columns=source_columns,
                target_columns=target_columns,
                constraint_name=edge_id,
                direction="forward",
            )
        )
    return tuple(sorted(edges, key=lambda edge: edge.edge_id))


def _validate_time_edge(
    time_field: _TimeField,
    edges: tuple[JoinEdge, ...],
) -> _TimeField:
    matches = tuple(
        edge
        for edge in edges
        if edge.source_table == time_field.source_table
        and edge.target_table == time_field.target_table
        and edge.source_columns == (time_field.source_column,)
    )
    if not matches:
        raise RetrievalContractError("time_field 无法匹配已验证 Relationship Graph")
    if len(matches) > 1:
        raise _AmbiguousRetrieval("time_field 匹配到多条语义不同关系")
    return _TimeField(
        time_field.source_table,
        time_field.source_column,
        time_field.target_table,
        time_field.filter_column,
        matches[0].edge_id,
    )


def _target_tables(
    candidate_tables: tuple[TableHit, ...],
    metric_table: str | None,
    time_field: _TimeField | None,
) -> tuple[str, ...]:
    tables = {hit.qualified_name for hit in candidate_tables}
    if metric_table is not None:
        tables.add(metric_table)
    if time_field is not None:
        tables.add(time_field.target_table)
    return tuple(sorted(tables))


def _candidate_table_hits(
    question: str,
    table_hits: tuple[TableHit, ...],
    metric_table: str | None,
    time_field: _TimeField | None,
) -> tuple[TableHit, ...]:
    """确定 COLUMN 和 Join 的最小候选表范围。"""

    names: set[str] = set()
    if metric_table is not None:
        names.add(metric_table)
    elif table_hits:
        names.add(table_hits[0].qualified_name)
    if time_field is not None:
        names.add(time_field.target_table)

    # “按……”是 V1 唯一的轻量维度提示；其他 TABLE 命中只保留为证据，
    # 避免把向量误召回的表强行带入 Relationship Graph。
    grouping_text = _grouping_text(question)
    names.update(_grouping_table_names(grouping_text, table_hits, metric_table))

    by_name = {hit.qualified_name: hit for hit in table_hits}
    candidates: list[TableHit] = []
    for name in sorted(names):
        existing = by_name.get(name)
        if existing is not None:
            candidates.append(existing)
        else:
            schema, table = name.split(".", maxsplit=1)
            candidates.append(
                _synthetic_table_hit(
                    schema,
                    table,
                    table_role="relationship_bridge",
                    page_content=f"关系图必需表：{name}",
                )
            )
    return tuple(candidates)


def _grouping_table_names(
    grouping_text: str,
    table_hits: tuple[TableHit, ...],
    metric_table: str | None,
) -> frozenset[str]:
    if not grouping_text:
        return frozenset()
    return frozenset(
        hit.qualified_name
        for hit in table_hits
        if hit.qualified_name != metric_table
        and _table_content_matches(grouping_text, hit.page_content)
    )


def _grouping_text(question: str) -> str:
    match = re.search(
        r"按(?P<grouping>.+?)(?:统计|分析|比较|查询|查看|的)",
        question,
    )
    return match.group("grouping").strip() if match is not None else ""


def _table_content_matches(question: str, page_content: str) -> bool:
    normalized_content = _normalize(page_content)
    return any(
        term in normalized_content
        for term in _cjk_bigrams(question)
    )


def _cjk_bigrams(value: str) -> tuple[str, ...]:
    terms: set[str] = set()
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", value):
        terms.update(
            term
            for index in range(len(run) - 1)
            if (term := run[index : index + 2]) not in _GENERIC_GROUPING_TERMS
        )
    return tuple(sorted(terms))


def _resolve_join_paths(
    anchor_table: str,
    target_tables: tuple[str, ...],
    edges: tuple[JoinEdge, ...],
    *,
    time_edge: str | None,
    time_target: str | None,
) -> JoinResolution:
    all_paths: list[JoinPath] = []
    chosen_joins: list[JoinEdge] = []
    unreachable: list[str] = []
    for target in target_tables:
        if target == anchor_table:
            continue
        paths = _shortest_paths(anchor_table, target, edges)
        if target == time_target and time_edge is not None and any(
            time_edge in {edge.edge_id for edge in path.edges} for path in paths
        ):
            paths = tuple(
                path
                for path in paths
                if time_edge in {edge.edge_id for edge in path.edges}
            )
        unique_paths = _unique_paths(paths)
        if not unique_paths:
            unreachable.append(target)
            continue
        if len(unique_paths) > 1:
            raise _AmbiguousRetrieval(
                f"目标表 {target} 存在多条无法唯一裁决的最短路径"
            )
        path = unique_paths[0]
        all_paths.append(path)
        chosen_joins.extend(path.edges)
    if unreachable:
        raise _UnreachableRequired(f"必需表不可达：{'、'.join(sorted(unreachable))}")
    return JoinResolution(
        anchor_table=anchor_table,
        paths=tuple(all_paths),
        joins=_dedupe_edges(chosen_joins),
        unreachable_tables=(),
    )


def _shortest_paths(
    start: str,
    target: str,
    edges: tuple[JoinEdge, ...],
) -> tuple[JoinPath, ...]:
    adjacency: defaultdict[str, list[tuple[str, JoinEdge]]] = defaultdict(list)
    for edge in edges:
        adjacency[edge.source_table].append((edge.target_table, edge))
        adjacency[edge.target_table].append(
            (
                edge.source_table,
                JoinEdge(
                    edge_id=edge.edge_id,
                    source_table=edge.source_table,
                    target_table=edge.target_table,
                    source_columns=edge.source_columns,
                    target_columns=edge.target_columns,
                    constraint_name=edge.constraint_name,
                    direction="reverse",
                ),
            )
        )
    queue: deque[tuple[str, tuple[str, ...], tuple[JoinEdge, ...]]] = deque(
        [(start, (start,), ())]
    )
    found_distance: int | None = None
    paths: list[JoinPath] = []
    while queue:
        current, tables, path_edges = queue.popleft()
        distance = len(path_edges)
        if found_distance is not None and distance > found_distance:
            continue
        if current == target:
            found_distance = distance
            paths.append(JoinPath(tables=tables, edges=path_edges))
            continue
        for next_table, edge in sorted(
            adjacency.get(current, ()),
            key=lambda item: (item[0], item[1].edge_id, item[1].direction),
        ):
            if next_table in tables:
                continue
            queue.append((next_table, (*tables, next_table), (*path_edges, edge)))
    return tuple(paths)


def _unique_paths(paths: tuple[JoinPath, ...]) -> tuple[JoinPath, ...]:
    result: dict[tuple[Any, ...], JoinPath] = {}
    for path in paths:
        key = (
            path.tables,
            tuple((edge.edge_id, edge.direction) for edge in path.edges),
        )
        result[key] = path
    return tuple(result.values())


def _dedupe_edges(edges: Iterable[JoinEdge]) -> tuple[JoinEdge, ...]:
    result: list[JoinEdge] = []
    seen: set[tuple[str, str]] = set()
    for edge in edges:
        key = (edge.edge_id, edge.direction)
        if key not in seen:
            seen.add(key)
            result.append(edge)
    return tuple(result)


def _final_table_hits(
    table_hits: tuple[TableHit, ...],
    resolution: JoinResolution,
) -> tuple[TableHit, ...]:
    by_name = {hit.qualified_name: hit for hit in table_hits}
    names = {resolution.anchor_table} if resolution.anchor_table else set()
    for path in resolution.paths:
        names.update(path.tables)
    final: list[TableHit] = []
    for name in sorted(name for name in names if name):
        existing = by_name.get(name)
        if existing is not None:
            final.append(existing)
            continue
        schema, table = name.split(".", maxsplit=1)
        final.append(
            _synthetic_table_hit(
                schema,
                table,
                table_role="relationship_bridge",
                page_content=f"关系图桥接表：{name}",
            )
        )
    return tuple(final)


def _synthetic_table_hit(
    schema_name: str,
    table_name: str,
    *,
    table_role: str,
    page_content: str,
) -> TableHit:
    qualified_name = f"{schema_name}.{table_name}"
    return TableHit(
        document_id=f"graph:{qualified_name}",
        schema_name=schema_name,
        table_name=table_name,
        table_role=table_role,
        score=0.0,
        rank=0,
        metadata=MappingProxyType(
            {
                "doc_type": "TABLE",
                "schema_name": schema_name,
                "table_name": table_name,
                "table_type": table_role,
            }
        ),
        page_content=page_content,
    )


def _final_column_hits(
    column_hits: tuple[ColumnHit, ...],
    resolution: JoinResolution,
    *,
    allowed_tables: frozenset[str],
) -> tuple[ColumnHit, ...]:
    by_identity = {
        (hit.qualified_table, hit.column_name): hit for hit in column_hits
        if hit.qualified_table in allowed_tables
    }
    for edge in resolution.joins:
        if edge.direction == "forward":
            endpoints = (
                (edge.source_table, edge.source_columns),
                (edge.target_table, edge.target_columns),
            )
        else:
            endpoints = (
                (edge.target_table, edge.target_columns),
                (edge.source_table, edge.source_columns),
            )
        for table, columns in endpoints:
            if table not in allowed_tables:
                continue
            for column in columns:
                by_identity.setdefault(
                    (table, column),
                    _synthetic_column(table, column, edge.edge_id),
                )
    return tuple(
        sorted(
            by_identity.values(),
            key=lambda hit: (hit.qualified_table, hit.column_name, -hit.score),
        )
    )


def _synthetic_column(table: str, column: str, edge_id: str) -> ColumnHit:
    schema, table_name = table.split(".", maxsplit=1)
    return ColumnHit(
        document_id=f"graph:{table}.{column}",
        schema_name=schema,
        table_name=table_name,
        column_name=column,
        data_type="UNKNOWN",
        score=0.0,
        rank=0,
        metadata=MappingProxyType(
            {
                "doc_type": "COLUMN",
                "schema_name": schema,
                "table_name": table_name,
                "column_name": column,
                "data_type": "UNKNOWN",
                "relationship_edge_id": edge_id,
            }
        ),
        page_content=f"关系键字段：{table}.{column}",
    )


def _build_dynamic_schema(
    tables: tuple[TableHit, ...],
    fields: tuple[ColumnHit, ...],
    resolution: JoinResolution,
) -> str:
    value = {
        "tables": [
            {
                "schema_name": table.schema_name,
                "table_name": table.table_name,
                "table_role": table.table_role,
            }
            for table in tables
        ],
        "columns": [
            {
                "schema_name": field.schema_name,
                "table_name": field.table_name,
                "column_name": field.column_name,
                "data_type": field.data_type,
                "description": field.page_content,
            }
            for field in fields
        ],
        "joins": [
            {
                "edge_id": edge.edge_id,
                "source_table": edge.source_table,
                "source_columns": list(edge.source_columns),
                "target_table": edge.target_table,
                "target_columns": list(edge.target_columns),
                "direction": edge.direction,
            }
            for edge in resolution.joins
        ],
    }
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _build_indicator_context(metric: MetricHit | None) -> str:
    if metric is None:
        return ""
    keys = (
        "metric_name",
        "aliases",
        "level",
        "definition",
        "formula",
        "data_source",
        "time_field",
        "filters",
        "depends_on",
        "notes",
    )
    value = {
        key: _json_value(metric.metadata.get(key))
        for key in keys
        if key in metric.metadata
    }
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _build_prompt_context(dynamic_schema: str, indicator_context: str) -> str:
    parts = [f"Dynamic Schema:\n{dynamic_schema}"]
    if indicator_context:
        parts.append(f"Indicator Context:\n{indicator_context}")
    return "\n\n".join(parts)


def _allowed_columns(fields: tuple[ColumnHit, ...]) -> dict[str, frozenset[str]]:
    result: defaultdict[str, set[str]] = defaultdict(set)
    for field in fields:
        result[field.qualified_table].add(field.column_name)
    return {
        table: frozenset(columns)
        for table, columns in sorted(result.items())
    }


def _result(
    status: RetrievalStatus,
    asset_version: str | None,
    *,
    tables: tuple[TableHit, ...] = (),
    fields: tuple[ColumnHit, ...] = (),
    metrics: tuple[MetricHit, ...] = (),
    join_path: JoinResolution | None = None,
    dynamic_schema: str = "",
    indicator_context: str = "",
    evidence: RetrievalEvidence | None = None,
    warnings: tuple[str, ...] = (),
    query_context: QueryContext | None = None,
) -> OnlineRetrievalResult:
    return OnlineRetrievalResult(
        status=status,
        asset_version=asset_version,
        tables=tables,
        fields=fields,
        metrics=metrics,
        join_path=join_path,
        dynamic_schema=dynamic_schema,
        indicator_context=indicator_context,
        evidence=evidence or RetrievalEvidence(),
        warnings=warnings,
        query_context=query_context,
    )


def _failure(
    status: RetrievalStatus,
    warning: str,
    *,
    asset_version: str | None = None,
    evidence: RetrievalEvidence | None = None,
) -> OnlineRetrievalResult:
    return _result(
        status,
        asset_version,
        evidence=evidence,
        warnings=(warning,),
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


def _qualified_from_graph(
    raw: Mapping[str, Any],
    schema_key: str,
    table_key: str,
    index: int,
) -> str:
    schema = _text(raw, schema_key, index)
    table = _text(raw, table_key, index)
    return f"{schema}.{table}"


def _text(raw: Mapping[str, Any], key: str, index: int) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RetrievalContractError(f"Relationship Graph 第 {index} 条边缺少 {key}")
    return value.strip()


def _string_tuple(value: Any, key: str, index: int) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise RetrievalContractError(f"Relationship Graph 第 {index} 条边的 {key} 无效")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise RetrievalContractError(f"Relationship Graph 第 {index} 条边的 {key} 无效")
    return tuple(item.strip() for item in value)


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


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value
