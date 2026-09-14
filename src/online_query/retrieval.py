"""Online Retrieval（在线检索）三路检索、关系解析和上下文组装。"""

from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import replace
import re
from typing import Any

from src.observability.contracts import TraceRecorder
from src.observability.tracing import create_trace_recorder
from src.rag_offline.embedding import EmbeddingError
from src.rag_offline.qdrant_store import QdrantStoreError, SearchHit

from .contracts import (
    ColumnHit,
    FallbackPolicy,
    JoinConstraint,
    JoinResolution,
    MetricConstraint,
    MetricHit,
    MetricPlanStatus,
    MetricRetrievalEvidence,
    OnlineRetrievalResult,
    QueryContext,
    RequestShape,
    RetrievalConfig,
    RetrievalEvidence,
    RetrievalRequest,
    RetrievalStatus,
    TableHit,
)
from .multi_metric import plan_multi_metric_request
from .rag_runtime import (
    AssetSnapshot,
    AssetUnavailableError,
    EmbeddingUnavailableError,
    RagRuntime,
    RetrievalUnavailableError,
)
from .relationship_graph import (
    RelationshipGraphAmbiguousError as _AmbiguousRetrieval,
    RelationshipGraphContractError,
    RelationshipGraphUnreachableError as _UnreachableRequired,
    parse_edges as _graph_edges,
    resolve_join_paths as _resolve_join_paths,
    validate_time_edge as _validate_time_edge,
    validated_multi_joins as _validated_multi_joins,
)
from .resource_retrieval import (
    ResourceRetrievalContractError,
    _TimeField,
    _column_hits,
    _column_query,
    _contains_required_columns,
    _has_metric_intent,
    _metric_data_source,
    _metric_hits,
    _missing_required_column_details,
    _multi_column_query,
    _parse_time_field,
    _required_columns,
    _required_columns_many,
    _select_metric,
    _table_hits,
    _validate_metric_against_constraint,
)
from .retrieval_context import _synthetic_table_hit, assemble_context


class RetrievalContractError(RuntimeError):
    """检索结果或已发布资产不满足在线契约。"""


_GENERIC_GROUPING_TERMS = frozenset(
    {"类型", "属性", "业务", "数据", "信息", "记录", "完成", "订单", "金额", "统计"}
)
_TRACE_EVIDENCE_LIMIT = 10


class OnlineRetriever:
    """使用一个 RAG Runtime 完成单次同步在线检索。"""

    def __init__(
        self,
        runtime: RagRuntime,
        *,
        config: RetrievalConfig | None = None,
        trace_recorder: TraceRecorder | None = None,
    ) -> None:
        self._runtime = runtime
        self._config = config or RetrievalConfig()
        if trace_recorder is not None:
            self._trace_recorder = trace_recorder
        else:
            try:
                self._trace_recorder = create_trace_recorder()
            except Exception:
                self._trace_recorder = None

    def retrieve(self, question: str | RetrievalRequest) -> OnlineRetrievalResult:
        """执行 TABLE、COLUMN、METRIC 和确定性关系解析。"""

        if isinstance(question, RetrievalRequest):
            if question.request_shape != RequestShape.BASELINE:
                return self._retrieve_multi(question)
            question = question.question
        if not isinstance(question, str) or not question.strip():
            raise ValueError("检索问题不能为空")
        question = question.strip()
        grouping_text = _grouping_text(question)
        try:
            with _safe_span(self._trace_recorder, "asset.resolve"):
                snapshot = self._runtime.get_snapshot()
                _safe_enrich_current(
                    self._trace_recorder,
                    {"chatbi.retrieval.asset_version": snapshot.asset_version},
                )
        except AssetUnavailableError as exc:
            return _failure(RetrievalStatus.ASSET_UNAVAILABLE, str(exc))
        except RetrievalUnavailableError as exc:
            return _failure(RetrievalStatus.RETRIEVAL_UNAVAILABLE, str(exc))
        except EmbeddingUnavailableError as exc:
            return _failure(RetrievalStatus.EMBEDDING_UNAVAILABLE, str(exc))
        except Exception as exc:
            return _failure(RetrievalStatus.ASSET_UNAVAILABLE, str(exc))

        metric_intent = _has_metric_intent(question, snapshot.metric_catalog)
        try:
            query_embedding = self._embed_query(snapshot, question)
            table_hits = _table_hits(
                snapshot,
                query_embedding,
                self._config,
                extra_queries=(grouping_text,) if grouping_text else (),
                embed_query=lambda text: self._embed_query(snapshot, text),
                search=lambda collection_name, query, **kwargs: self._search(
                    "table.search",
                    snapshot,
                    collection_name,
                    query,
                    **kwargs,
                ),
            )
            metric_hits = (
                _metric_hits(
                    snapshot,
                    query_embedding,
                    self._config,
                    search=lambda collection_name, query, **kwargs: self._search(
                        "metric.search",
                        snapshot,
                        collection_name,
                        query,
                        **kwargs,
                    ),
                )
                if metric_intent
                else ()
            )
        except EmbeddingError as exc:
            return _failure(RetrievalStatus.EMBEDDING_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version)
        except QdrantStoreError as exc:
            return _failure(RetrievalStatus.RETRIEVAL_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version)
        except ResourceRetrievalContractError as exc:
            return _failure(RetrievalStatus.ASSET_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version)
        except RetrievalContractError as exc:
            return _failure(RetrievalStatus.ASSET_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version)
        except Exception as exc:
            return _failure(RetrievalStatus.RETRIEVAL_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version)

        evidence = RetrievalEvidence(table_hits=table_hits, metric_hits=metric_hits)
        if not table_hits:
            return _result(RetrievalStatus.NO_TABLE_HIT, snapshot.asset_version, evidence=evidence, warnings=("TABLE 检索没有超过阈值的有效候选",))

        metric = None
        if metric_intent:
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
                embed_query=lambda text: self._embed_query(snapshot, text),
                search=lambda collection_name, query, **kwargs: self._search(
                    "column.search",
                    snapshot,
                    collection_name,
                    query,
                    **kwargs,
                ),
            )
        except EmbeddingError as exc:
            return _failure(RetrievalStatus.EMBEDDING_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version, evidence=evidence)
        except QdrantStoreError as exc:
            return _failure(RetrievalStatus.RETRIEVAL_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version, evidence=evidence)
        except ResourceRetrievalContractError as exc:
            return _failure(RetrievalStatus.ASSET_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version, evidence=evidence)
        except RetrievalContractError as exc:
            return _failure(RetrievalStatus.ASSET_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version, evidence=evidence)

        evidence = RetrievalEvidence(table_hits=table_hits, column_hits=column_hits, metric_hits=metric_hits)
        if not column_hits:
            return _result(RetrievalStatus.NO_REQUIRED_COLUMN_HIT, snapshot.asset_version, tables=table_hits, metrics=(metric,) if metric else (), evidence=evidence, warnings=("COLUMN 检索没有超过阈值的有效候选",))

        try:
            if not _contains_required_columns(column_hits, required):
                return _result(RetrievalStatus.NO_REQUIRED_COLUMN_HIT, snapshot.asset_version, tables=table_hits, fields=column_hits, metrics=(metric,) if metric else (), evidence=evidence, warnings=("公式或 time_field 引用的必需字段没有被 COLUMN 命中",))
            with _safe_span(
                self._trace_recorder,
                "join.resolve",
                {"chatbi.retrieval.asset_version": snapshot.asset_version},
            ):
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
                _safe_enrich_current(
                    self._trace_recorder,
                    _join_trace_attributes(resolution),
                )
        except _AmbiguousRetrieval as exc:
            return _result(RetrievalStatus.AMBIGUOUS, snapshot.asset_version, tables=table_hits, fields=column_hits, metrics=(metric,) if metric else (), evidence=evidence, warnings=(str(exc),))
        except _UnreachableRequired as exc:
            return _result(RetrievalStatus.PARTIAL_UNREACHABLE, snapshot.asset_version, tables=table_hits, fields=column_hits, metrics=(metric,) if metric else (), evidence=evidence, warnings=(str(exc),))
        except RelationshipGraphContractError as exc:
            return _failure(RetrievalStatus.ASSET_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version, evidence=evidence)
        except ResourceRetrievalContractError as exc:
            return _failure(RetrievalStatus.ASSET_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version, evidence=evidence)
        except RetrievalContractError as exc:
            return _failure(RetrievalStatus.ASSET_UNAVAILABLE, str(exc), asset_version=snapshot.asset_version, evidence=evidence)

        with _safe_span(
            self._trace_recorder,
            "context.assemble",
            {"chatbi.retrieval.asset_version": snapshot.asset_version},
        ):
            context = assemble_context(
                candidate_tables,
                column_hits,
                resolution,
                metric=metric,
            )
            final_tables = context.final_tables
            final_fields = context.final_fields
            dynamic_schema = context.dynamic_schema
            indicator_context = context.indicator_context
            query_context = context.query_context
            _safe_enrich_current(
                self._trace_recorder,
                {
                    "chatbi.retrieval.table_count": len(final_tables),
                    "chatbi.retrieval.column_count": len(final_fields),
                    "chatbi.retrieval.metric_count": 1 if metric is not None else 0,
                    "chatbi.retrieval.candidate.qualified_tables": tuple(
                        hit.qualified_name for hit in final_tables[:_TRACE_EVIDENCE_LIMIT]
                    ),
                },
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

    def _retrieve_multi(
        self,
        request: RetrievalRequest,
    ) -> OnlineRetrievalResult:
        """执行已预判多指标请求的完整检索，但不调用 LLM 或数据库。"""

        question = request.question
        grouping_text = _grouping_text(question)
        try:
            with _safe_span(self._trace_recorder, "asset.resolve"):
                snapshot = self._runtime.get_snapshot()
                _safe_enrich_current(
                    self._trace_recorder,
                    {"chatbi.retrieval.asset_version": snapshot.asset_version},
                )
        except AssetUnavailableError as exc:
            return _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                request=request,
            )
        except RetrievalUnavailableError as exc:
            return _failure(
                RetrievalStatus.RETRIEVAL_UNAVAILABLE,
                str(exc),
                request=request,
            )
        except EmbeddingUnavailableError as exc:
            return _failure(
                RetrievalStatus.EMBEDDING_UNAVAILABLE,
                str(exc),
                request=request,
            )
        except Exception as exc:
            return _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                request=request,
            )

        plan = plan_multi_metric_request(request, snapshot.metric_catalog)
        if plan.status == MetricPlanStatus.INVALID_ASSET:
            return _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                plan.reason,
                asset_version=snapshot.asset_version,
                request=request,
                internal_reason=plan.status.value,
                metric_constraints=plan.constraints,
            )
        if plan.status != MetricPlanStatus.SUCCESS:
            status = (
                RetrievalStatus.NO_METRIC_HIT
                if plan.status == MetricPlanStatus.NO_METRIC
                else RetrievalStatus.AMBIGUOUS
            )
            internal_reason = (
                "UNSUPPORTED_METRIC_COMBINATION"
                if plan.status
                in {
                    MetricPlanStatus.TOO_MANY,
                    MetricPlanStatus.UNSUPPORTED_COMBINATION,
                }
                else plan.status.value
            )
            return _result(
                status,
                snapshot.asset_version,
                warnings=(plan.reason or "多指标请求无法形成确定计划",),
                request=request,
                internal_reason=internal_reason,
                metric_constraints=plan.constraints,
            )

        constraints = plan.constraints
        metric_queries: list[MetricRetrievalEvidence] = []
        selected_metrics: list[MetricHit] = []
        try:
            question_embedding = self._embed_query(snapshot, question)
            table_hits = _table_hits(
                snapshot,
                question_embedding,
                self._config,
                extra_queries=(grouping_text,) if grouping_text else (),
                embed_query=lambda text: self._embed_query(snapshot, text),
                search=lambda collection_name, query, **kwargs: self._search(
                    "table.search",
                    snapshot,
                    collection_name,
                    query,
                    **kwargs,
                ),
            )
            # 同一完整问题向量同时服务 TABLE 和一次综合 METRIC 路线，
            # 不再按请求指标重复生成查询或发起补检索。
            metric_config = replace(
                self._config,
                metric_top_k=max(self._config.metric_top_k, 5, len(constraints)),
            )
            combined_metric_hits = _metric_hits(
                snapshot,
                question_embedding,
                metric_config,
                search=lambda collection_name, query, **kwargs: self._search(
                    "metric.search",
                    snapshot,
                    collection_name,
                    query,
                    **kwargs,
                ),
            )
            metric_queries = [
                MetricRetrievalEvidence(
                    requested_text=constraint.requested_text,
                    target_document_id=constraint.document_id,
                    hits=combined_metric_hits,
                )
                for constraint in constraints
            ]
            for constraint in constraints:
                selected = next(
                    (
                        hit
                        for hit in combined_metric_hits
                        if hit.document_id == constraint.document_id
                    ),
                    None,
                )
                if selected is None:
                    evidence = RetrievalEvidence(
                        table_hits=table_hits,
                        metric_hits=combined_metric_hits,
                        metric_queries=tuple(metric_queries),
                    )
                    return _result(
                        RetrievalStatus.NO_METRIC_HIT,
                        snapshot.asset_version,
                        tables=table_hits,
                        evidence=evidence,
                        warnings=(
                            f"指标未在综合 METRIC 检索中有效命中："
                            f"{constraint.requested_text}",
                        ),
                        request=request,
                        internal_reason="NO_METRIC_HIT",
                        metric_constraints=constraints,
                    )
                _validate_metric_against_constraint(selected, constraint)
                selected_metrics.append(selected)
        except EmbeddingError as exc:
            return _failure(
                RetrievalStatus.EMBEDDING_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                request=request,
                metric_constraints=constraints,
            )
        except QdrantStoreError as exc:
            return _failure(
                RetrievalStatus.RETRIEVAL_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                request=request,
                metric_constraints=constraints,
            )
        except ResourceRetrievalContractError as exc:
            return _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                request=request,
                metric_constraints=constraints,
            )
        except RetrievalContractError as exc:
            return _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                request=request,
                metric_constraints=constraints,
            )

        selected_tuple = tuple(selected_metrics)
        evidence = RetrievalEvidence(
            table_hits=table_hits,
            metric_hits=combined_metric_hits,
            metric_queries=tuple(metric_queries),
        )
        if not table_hits:
            return _result(
                RetrievalStatus.NO_TABLE_HIT,
                snapshot.asset_version,
                evidence=evidence,
                warnings=("TABLE 检索没有超过阈值的有效候选",),
                request=request,
                metric_constraints=constraints,
            )

        metric_table = constraints[0].data_source
        if not any(hit.qualified_name == metric_table for hit in table_hits):
            return _result(
                RetrievalStatus.NO_TABLE_HIT,
                snapshot.asset_version,
                tables=table_hits,
                metrics=selected_tuple,
                evidence=evidence,
                warnings=("共同指标 data_source 没有被 TABLE 路线命中",),
                request=request,
                metric_constraints=constraints,
            )

        try:
            time_field = _parse_time_field(selected_tuple[0])
            required = _required_columns_many(selected_tuple, time_field)
            candidate_tables = _candidate_table_hits(
                question,
                table_hits,
                metric_table,
                time_field,
            )
            grouping_tables = _grouping_table_names(
                grouping_text,
                table_hits,
                metric_table,
            )
            column_hits = _column_hits(
                snapshot,
                candidate_tables,
                _multi_column_query(question, selected_tuple),
                self._config,
                required=required,
                grouping_query=grouping_text,
                grouping_tables=grouping_tables,
                embed_query=lambda text: self._embed_query(snapshot, text),
                search=lambda collection_name, query, **kwargs: self._search(
                    "column.search",
                    snapshot,
                    collection_name,
                    query,
                    **kwargs,
                ),
            )
        except EmbeddingError as exc:
            return _failure(
                RetrievalStatus.EMBEDDING_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                evidence=evidence,
                request=request,
                metric_constraints=constraints,
            )
        except QdrantStoreError as exc:
            return _failure(
                RetrievalStatus.RETRIEVAL_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                evidence=evidence,
                request=request,
                metric_constraints=constraints,
            )
        except ResourceRetrievalContractError as exc:
            return _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                evidence=evidence,
                request=request,
                metric_constraints=constraints,
            )
        except RetrievalContractError as exc:
            return _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                evidence=evidence,
                request=request,
                metric_constraints=constraints,
            )

        evidence = RetrievalEvidence(
            table_hits=table_hits,
            column_hits=column_hits,
            metric_hits=combined_metric_hits,
            metric_queries=tuple(metric_queries),
        )
        if not column_hits or not _contains_required_columns(column_hits, required):
            missing_details = _missing_required_column_details(
                selected_tuple,
                time_field,
                column_hits,
            )
            return _result(
                RetrievalStatus.NO_REQUIRED_COLUMN_HIT,
                snapshot.asset_version,
                tables=table_hits,
                fields=column_hits,
                metrics=selected_tuple,
                evidence=evidence,
                warnings=(
                    "至少一个指标的必需字段没有被 COLUMN 有效命中",
                    *missing_details,
                ),
                request=request,
                metric_constraints=constraints,
            )

        try:
            with _safe_span(
                self._trace_recorder,
                "join.resolve",
                {"chatbi.retrieval.asset_version": snapshot.asset_version},
            ):
                anchor = metric_table
                edges = _graph_edges(snapshot.relationship_graph)
                time_field = _validate_time_edge(time_field, edges)
                targets = _target_tables(candidate_tables, metric_table, time_field)
                resolution = _resolve_join_paths(
                    anchor,
                    targets,
                    edges,
                    time_edge=time_field.edge_id,
                    time_target=time_field.target_table,
                )
                join_constraints = _validated_multi_joins(
                    anchor,
                    resolution,
                    snapshot.relationship_graph,
                )
                _safe_enrich_current(
                    self._trace_recorder,
                    _join_trace_attributes(resolution),
                )
        except _AmbiguousRetrieval as exc:
            return _result(
                RetrievalStatus.AMBIGUOUS,
                snapshot.asset_version,
                tables=table_hits,
                fields=column_hits,
                metrics=selected_tuple,
                evidence=evidence,
                warnings=(str(exc),),
                request=request,
                metric_constraints=constraints,
            )
        except _UnreachableRequired as exc:
            return _result(
                RetrievalStatus.PARTIAL_UNREACHABLE,
                snapshot.asset_version,
                tables=table_hits,
                fields=column_hits,
                metrics=selected_tuple,
                evidence=evidence,
                warnings=(str(exc),),
                request=request,
                metric_constraints=constraints,
            )
        except RelationshipGraphContractError as exc:
            return _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                evidence=evidence,
                request=request,
                metric_constraints=constraints,
            )
        except ResourceRetrievalContractError as exc:
            return _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                evidence=evidence,
                request=request,
                metric_constraints=constraints,
            )
        except RetrievalContractError as exc:
            return _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                evidence=evidence,
                request=request,
                metric_constraints=constraints,
            )

        with _safe_span(
            self._trace_recorder,
            "context.assemble",
            {"chatbi.retrieval.asset_version": snapshot.asset_version},
        ):
            context = assemble_context(
                candidate_tables,
                column_hits,
                resolution,
                metrics=selected_tuple,
                request_shape=request.request_shape,
                metric_constraints=constraints,
                join_constraints=join_constraints,
            )
            final_tables = context.final_tables
            final_fields = context.final_fields
            dynamic_schema = context.dynamic_schema
            indicator_context = context.indicator_context
            query_context = context.query_context
            _safe_enrich_current(
                self._trace_recorder,
                {
                    "chatbi.retrieval.table_count": len(final_tables),
                    "chatbi.retrieval.column_count": len(final_fields),
                    "chatbi.retrieval.metric_count": len(selected_tuple),
                    "chatbi.retrieval.candidate.qualified_tables": tuple(
                        hit.qualified_name for hit in final_tables[:_TRACE_EVIDENCE_LIMIT]
                    ),
                },
            )
        evidence = RetrievalEvidence(
            table_hits=table_hits,
            column_hits=column_hits,
            metric_hits=combined_metric_hits,
            metric_queries=tuple(metric_queries),
            join_paths=resolution.paths,
        )
        return _result(
            RetrievalStatus.SUCCESS,
            snapshot.asset_version,
            tables=final_tables,
            fields=final_fields,
            metrics=selected_tuple,
            join_path=resolution,
            dynamic_schema=dynamic_schema,
            indicator_context=indicator_context,
            evidence=evidence,
            warnings=("anchor_reason=common_metric_data_source",),
            query_context=query_context,
            request=request,
            metric_constraints=constraints,
            join_constraints=join_constraints,
        )

    def _embed_query(self, snapshot: AssetSnapshot, text: str) -> Any:
        with _safe_span(self._trace_recorder, "embedding.query"):
            return snapshot.embedding_provider.embed_query(text)

    def _search(
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
        with _safe_span(self._trace_recorder, stage, attributes):
            hits = tuple(
                snapshot.qdrant_store.search(
                    collection_name,
                    query,
                    limit=limit,
                    filter_payload=filter_payload,
                )
            )
            _safe_enrich_current(
                self._trace_recorder,
                _candidate_trace_attributes(hits, scope_table=qualified_table),
            )
            return hits


@contextmanager
def _safe_span(
    recorder: TraceRecorder | None,
    name: str,
    attributes: Mapping[str, object] | None = None,
) -> Iterator[Any]:
    """创建内部 Retrieval Span；记录器失败时保持业务异常和返回值不变。"""

    scope: Any = _NoopTraceScope()
    try:
        if recorder is not None:
            scope = recorder.span(name, attributes=attributes)
        scope.__enter__()
    except Exception:
        scope = _NoopTraceScope()
        scope.__enter__()

    try:
        yield scope
    except BaseException as exc:
        try:
            scope.__exit__(type(exc), exc, exc.__traceback__)
        except Exception:
            pass
        raise
    else:
        try:
            scope.__exit__(None, None, None)
        except Exception:
            pass


class _NoopTraceScope:
    def __enter__(self) -> "_NoopTraceScope":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        return False


def _safe_enrich_current(
    recorder: TraceRecorder | None,
    attributes: Mapping[str, object],
) -> None:
    if recorder is None:
        return
    try:
        recorder.enrich_current(attributes=attributes)
    except Exception:
        pass


def _candidate_trace_attributes(
    hits: Iterable[SearchHit],
    *,
    scope_table: str | None = None,
) -> dict[str, object]:
    """只提取有界的检索身份/排序证据，不读取正文或完整 Metadata。"""

    materialized = tuple(hits)
    evidence = materialized[:_TRACE_EVIDENCE_LIMIT]
    attributes: dict[str, object] = {
        "chatbi.retrieval.candidate_count": len(materialized),
    }
    if not evidence:
        return attributes

    attributes.update(
        {
            "chatbi.retrieval.candidate.document_ids": tuple(
                hit.document_id for hit in evidence
            ),
            "chatbi.retrieval.candidate.ranks": tuple(
                range(1, len(evidence) + 1)
            ),
            "chatbi.retrieval.candidate.scores": tuple(
                float(hit.score) for hit in evidence
            ),
        }
    )
    qualified_tables = tuple(
        dict.fromkeys(
            table
            for hit in evidence
            if (table := scope_table or _qualified_table_from_hit(hit)) is not None
        )
    )
    if qualified_tables:
        attributes["chatbi.retrieval.candidate.qualified_tables"] = qualified_tables
    return attributes


def _qualified_table_from_hit(hit: SearchHit) -> str | None:
    metadata = hit.payload.get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    schema_name = metadata.get("schema_name")
    table_name = metadata.get("table_name")
    if not isinstance(schema_name, str) or not isinstance(table_name, str):
        return None
    if not schema_name.strip() or not table_name.strip():
        return None
    return f"{schema_name.strip()}.{table_name.strip()}"


def _qualified_filter_table(
    filter_payload: Mapping[str, str] | None,
) -> str | None:
    if not isinstance(filter_payload, Mapping):
        return None
    schema_name = filter_payload.get("schema_name")
    table_name = filter_payload.get("table_name")
    if not isinstance(schema_name, str) or not isinstance(table_name, str):
        return None
    if not schema_name.strip() or not table_name.strip():
        return None
    return f"{schema_name.strip()}.{table_name.strip()}"


def _join_trace_attributes(resolution: JoinResolution) -> dict[str, object]:
    paths = resolution.paths[:_TRACE_EVIDENCE_LIMIT]
    return {
        "chatbi.retrieval.join.edge_ids": tuple(
            edge.edge_id
            for edge in resolution.joins[:_TRACE_EVIDENCE_LIMIT]
        ),
        "chatbi.retrieval.join.path_ids": tuple(
            f"path:{index}"
            for index, _ in enumerate(paths, 1)
        ),
        "chatbi.retrieval.join.path_count": len(resolution.paths),
    }


def _select_anchor(
    metric: MetricHit | None,
    table_hits: tuple[TableHit, ...],
) -> tuple[str, str]:
    if metric is not None:
        return _metric_data_source(metric), "metric_data_source"
    if not table_hits:
        raise RetrievalContractError("无法选择 Anchor：TABLE 候选为空")
    return table_hits[0].qualified_name, "highest_table_score"


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
    request: RetrievalRequest | None = None,
    internal_reason: str | None = None,
    metric_constraints: tuple[MetricConstraint, ...] = (),
    join_constraints: tuple[JoinConstraint, ...] = (),
) -> OnlineRetrievalResult:
    return OnlineRetrievalResult(
        status=status,
        request_shape=(
            request.request_shape if request is not None else RequestShape.BASELINE
        ),
        fallback_policy=(
            request.fallback_policy
            if request is not None
            else FallbackPolicy.FAIL_CLOSED
        ),
        internal_reason=internal_reason,
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
        metric_constraints=metric_constraints,
        join_constraints=join_constraints,
    )


def _failure(
    status: RetrievalStatus,
    warning: str,
    *,
    asset_version: str | None = None,
    evidence: RetrievalEvidence | None = None,
    request: RetrievalRequest | None = None,
    internal_reason: str | None = None,
    metric_constraints: tuple[MetricConstraint, ...] = (),
) -> OnlineRetrievalResult:
    return _result(
        status,
        asset_version,
        evidence=evidence,
        warnings=(warning,),
        request=request,
        internal_reason=internal_reason,
        metric_constraints=metric_constraints,
    )


def _normalize(value: str) -> str:
    return "".join(
        char
        for char in value.casefold()
        if char.isalnum() or "\u4e00" <= char <= "\u9fff"
    )
