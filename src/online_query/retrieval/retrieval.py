"""Online Retrieval（在线检索）三路检索、关系解析和上下文组装。"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from src.observability.contracts import TraceRecorder
from src.observability.tracing import create_trace_recorder
from src.rag_offline.embedding import EmbeddingError
from src.rag_offline.qdrant_store import QdrantStoreError, SearchHit

from ..contracts import (
    ColumnHit,
    JoinConstraint,
    JoinResolution,
    MetricConstraint,
    MetricHit,
    MetricPlanStatus,
    MetricRetrievalEvidence,
    OnlineRetrievalResult,
    RetrievalConfig,
    RetrievalEvidence,
    RetrievalRequest,
    RetrievalStatus,
    TableHit,
)
from ..query_understanding import ValidatedSemanticQuery
from .multi_metric import plan_retrieved_metrics
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
    validated_join_constraints as _validated_join_constraints,
)
from .resource_retrieval import (
    ResourceRetrievalContractError,
    _column_hits,
    _column_query,
    _contains_required_columns,
    _metric_hits,
    _missing_required_column_details,
    _multi_column_query,
    _parse_time_field,
    _required_columns_many,
    _TimeField,
    _table_query,
    _table_hits,
)
from .retrieval_context import assemble_context
from .retrieval_errors import (
    RequiredCandidateUnavailableError,
    RetrievalContractError,
)
from .retrieval_selection import (
    candidate_table_hits,
    grouping_table_names,
    grouping_text_from_dimensions,
    requires_date_context,
    select_anchor,
    target_tables,
)
from .retrieval_results import failure as _failure
from .retrieval_results import result as _result
from .retrieval_trace import (
    _TRACE_EVIDENCE_LIMIT,
    candidate_trace_attributes as _candidate_trace_attributes,
    join_trace_attributes as _join_trace_attributes,
    merge_metric_hits as _merge_metric_hits,
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

    def retrieve(self, request: RetrievalRequest) -> OnlineRetrievalResult:
        """消费结构化查询，执行 TABLE、COLUMN、METRIC 和关系解析流水线。"""

        if not isinstance(request, RetrievalRequest):
            raise TypeError("OnlineRetriever.retrieve 需要 RetrievalRequest")
        return self._retrieve_request(request)

    def _retrieve_request(
        self,
        request: RetrievalRequest,
    ) -> OnlineRetrievalResult:
        """在同一条链路中处理 metrics = 0 / 1 / N。"""

        if request.semantic_query is None:
            raise ValueError("RetrievalRequest 缺少 ValidatedSemanticQuery")
        if not isinstance(request.question, str) or not request.question.strip():
            raise ValueError("检索问题不能为空")
        semantic_query = request.semantic_query
        grouping_text = grouping_text_from_dimensions(semantic_query.dimensions)
        snapshot, failure = self._resolve_snapshot(request)
        if failure is not None:
            return failure
        assert snapshot is not None

        resources, failure = self._retrieve_resources(
            request,
            semantic_query,
            snapshot,
        )
        if failure is not None:
            return failure
        assert resources is not None

        if not resources.table_hits:
            return _result(
                RetrievalStatus.NO_TABLE_HIT,
                snapshot.asset_version,
                evidence=resources.evidence,
                warnings=("TABLE 检索没有超过阈值的有效候选",),
                request=request,
                metric_constraints=resources.metric_constraints,
            )

        metric_table = (
            resources.metric_constraints[0].data_source
            if resources.metric_constraints
            else None
        )
        if metric_table is not None and not any(
            hit.qualified_name == metric_table for hit in resources.table_hits
        ):
            return _result(
                RetrievalStatus.NO_TABLE_HIT,
                snapshot.asset_version,
                tables=resources.table_hits,
                metrics=resources.selected_metrics,
                evidence=resources.evidence,
                warnings=("指标 data_source 没有被 TABLE 路线命中",),
                request=request,
                metric_constraints=resources.metric_constraints,
            )

        columns, failure = self._retrieve_columns(
            request,
            semantic_query,
            grouping_text,
            resources,
        )
        if failure is not None:
            return failure
        assert columns is not None

        if not columns.column_hits:
            return _result(
                RetrievalStatus.NO_REQUIRED_COLUMN_HIT,
                snapshot.asset_version,
                tables=resources.table_hits,
                fields=columns.column_hits,
                metrics=resources.selected_metrics,
                evidence=columns.evidence,
                warnings=("COLUMN 检索没有超过阈值的有效候选",),
                request=request,
                metric_constraints=resources.metric_constraints,
            )

        if resources.selected_metrics and not _contains_required_columns(
            columns.column_hits,
            columns.required,
        ):
            missing_details = _missing_required_column_details(
                resources.selected_metrics,
                columns.time_field,
                columns.column_hits,
            )
            return _result(
                RetrievalStatus.NO_REQUIRED_COLUMN_HIT,
                snapshot.asset_version,
                tables=resources.table_hits,
                fields=columns.column_hits,
                metrics=resources.selected_metrics,
                evidence=columns.evidence,
                warnings=(
                    "至少一个指标的必需字段没有被 COLUMN 有效命中",
                    *missing_details,
                ),
                request=request,
                metric_constraints=resources.metric_constraints,
            )

        join, failure = self._resolve_join(request, resources, columns)
        if failure is not None:
            return failure
        assert join is not None
        return self._assemble_success(request, resources, columns, join)

    def _assemble_success(
        self,
        request: RetrievalRequest,
        resources: _ResourceStage,
        columns: _ColumnStage,
        join: _JoinStage,
    ) -> OnlineRetrievalResult:
        snapshot = resources.snapshot

        with _safe_span(
            self._trace_recorder,
            "context.assemble",
            {"chatbi.retrieval.asset_version": snapshot.asset_version},
        ):
            context = assemble_context(
                columns.candidate_tables,
                columns.column_hits,
                join.resolution,
                metric=(
                    resources.selected_metrics[0]
                    if len(resources.selected_metrics) == 1
                    else None
                ),
                metrics=(
                    resources.selected_metrics
                    if len(resources.selected_metrics) >= 2
                    else ()
                ),
                request_shape=request.request_shape,
                metric_constraints=resources.metric_constraints,
                join_constraints=join.join_constraints,
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
                    "chatbi.retrieval.metric_count": len(resources.selected_metrics),
                    "chatbi.retrieval.candidate.qualified_tables": tuple(
                        hit.qualified_name
                        for hit in final_tables[:_TRACE_EVIDENCE_LIMIT]
                    ),
                },
            )
        evidence = RetrievalEvidence(
            table_hits=resources.table_hits,
            column_hits=columns.column_hits,
            metric_hits=resources.metric_hits,
            metric_queries=resources.metric_queries,
            join_paths=join.resolution.paths,
        )
        return _result(
            RetrievalStatus.SUCCESS,
            snapshot.asset_version,
            tables=final_tables,
            fields=final_fields,
            metrics=resources.selected_metrics,
            join_path=join.resolution,
            dynamic_schema=dynamic_schema,
            indicator_context=indicator_context,
            evidence=evidence,
            warnings=(f"anchor_reason={join.anchor_reason}",),
            query_context=query_context,
            request=request,
            metric_constraints=resources.metric_constraints,
            join_constraints=join.join_constraints,
        )

    def _resolve_snapshot(
        self,
        request: RetrievalRequest,
    ) -> tuple[AssetSnapshot | None, OnlineRetrievalResult | None]:
        try:
            with _safe_span(self._trace_recorder, "asset.resolve"):
                snapshot = self._runtime.get_snapshot()
                _safe_enrich_current(
                    self._trace_recorder,
                    {"chatbi.retrieval.asset_version": snapshot.asset_version},
                )
        except AssetUnavailableError as exc:
            return None, _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                request=request,
            )
        except RetrievalUnavailableError as exc:
            return None, _failure(
                RetrievalStatus.RETRIEVAL_UNAVAILABLE,
                str(exc),
                request=request,
            )
        except EmbeddingUnavailableError as exc:
            return None, _failure(
                RetrievalStatus.EMBEDDING_UNAVAILABLE,
                str(exc),
                request=request,
            )
        except Exception as exc:
            return None, _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                request=request,
            )
        return snapshot, None

    def _retrieve_resources(
        self,
        request: RetrievalRequest,
        semantic_query: ValidatedSemanticQuery,
        snapshot: AssetSnapshot,
    ) -> tuple[_ResourceStage | None, OnlineRetrievalResult | None]:
        try:
            query_embedding = self._embed_query(snapshot, _table_query(semantic_query))
            table_hits = _table_hits(
                snapshot,
                query_embedding,
                self._config,
                extra_queries=semantic_query.dimensions,
                embed_query=lambda text: self._embed_query(snapshot, text),
                search=lambda collection_name, query, **kwargs: self._search(
                    "table.search",
                    snapshot,
                    collection_name,
                    query,
                    **kwargs,
                ),
            )
            metric_hits_by_query = tuple(
                _metric_hits(
                    snapshot,
                    self._embed_query(snapshot, metric_text),
                    self._config,
                    search=lambda collection_name, query, **kwargs: self._search(
                        "metric.search",
                        snapshot,
                        collection_name,
                        query,
                        **kwargs,
                    ),
                )
                for metric_text in semantic_query.metrics
            )
            metric_hits = _merge_metric_hits(metric_hits_by_query)
        except EmbeddingError as exc:
            return None, _failure(
                RetrievalStatus.EMBEDDING_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                request=request,
            )
        except QdrantStoreError as exc:
            return None, _failure(
                RetrievalStatus.RETRIEVAL_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                request=request,
            )
        except ResourceRetrievalContractError as exc:
            return None, _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                request=request,
            )
        except RetrievalContractError as exc:
            return None, _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                request=request,
            )

        evidence = RetrievalEvidence(
            table_hits=table_hits,
            metric_hits=metric_hits,
        )
        if not semantic_query.metrics:
            return _ResourceStage(
                snapshot=snapshot,
                table_hits=table_hits,
                metric_hits_by_query=metric_hits_by_query,
                metric_hits=metric_hits,
                metric_queries=(),
                selected_metrics=(),
                metric_constraints=(),
                evidence=evidence,
            ), None
        return self._plan_metrics(
            request,
            semantic_query,
            snapshot,
            table_hits,
            metric_hits_by_query,
            metric_hits,
            evidence,
        )

    def _plan_metrics(
        self,
        request: RetrievalRequest,
        semantic_query: ValidatedSemanticQuery,
        snapshot: AssetSnapshot,
        table_hits: tuple[TableHit, ...],
        metric_hits_by_query: tuple[tuple[MetricHit, ...], ...],
        metric_hits: tuple[MetricHit, ...],
        evidence: RetrievalEvidence,
    ) -> tuple[_ResourceStage | None, OnlineRetrievalResult | None]:
        plan = plan_retrieved_metrics(request, metric_hits_by_query)
        metric_queries = tuple(
            MetricRetrievalEvidence(
                requested_text=requested_text,
                target_document_id=(
                    plan.mentions[index].document_id
                    if index < len(plan.mentions)
                    else ""
                ),
                hits=metric_hits_by_query[index],
            )
            for index, requested_text in enumerate(semantic_query.metrics)
        )
        evidence = RetrievalEvidence(
            table_hits=table_hits,
            metric_hits=metric_hits,
            metric_queries=metric_queries,
        )
        if plan.status == MetricPlanStatus.INVALID_ASSET:
            return None, _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                plan.reason,
                asset_version=snapshot.asset_version,
                evidence=evidence,
                request=request,
                internal_reason=plan.status.value,
            )
        if plan.status != MetricPlanStatus.SUCCESS:
            status = (
                RetrievalStatus.NO_METRIC_HIT
                if plan.status == MetricPlanStatus.NO_METRIC
                else RetrievalStatus.AMBIGUOUS
            )
            internal_reason = (
                "TOO_MANY_METRICS"
                if plan.status == MetricPlanStatus.TOO_MANY
                else (
                    "UNSUPPORTED_METRIC_COMBINATION"
                    if plan.status == MetricPlanStatus.UNSUPPORTED_COMBINATION
                    else (
                        "NO_METRIC_HIT"
                        if plan.status == MetricPlanStatus.NO_METRIC
                        else plan.status.value
                    )
                )
            )
            return None, _result(
                status,
                snapshot.asset_version,
                tables=table_hits,
                evidence=evidence,
                warnings=(plan.reason or "指标请求无法形成确定计划",),
                request=request,
                internal_reason=internal_reason,
            )

        constraints = plan.constraints
        hits_by_document = {hit.document_id: hit for hit in metric_hits}
        try:
            selected_metrics = tuple(
                hits_by_document[constraint.document_id] for constraint in constraints
            )
        except KeyError as exc:
            return None, _result(
                RetrievalStatus.NO_METRIC_HIT,
                snapshot.asset_version,
                tables=table_hits,
                evidence=evidence,
                warnings=(f"指标候选在本次检索中缺失：{exc.args[0]}",),
                request=request,
                internal_reason="NO_METRIC_HIT",
            )
        return _ResourceStage(
            snapshot=snapshot,
            table_hits=table_hits,
            metric_hits_by_query=metric_hits_by_query,
            metric_hits=metric_hits,
            metric_queries=metric_queries,
            selected_metrics=selected_metrics,
            metric_constraints=constraints,
            evidence=evidence,
        ), None

    def _retrieve_columns(
        self,
        request: RetrievalRequest,
        semantic_query: ValidatedSemanticQuery,
        grouping_text: str,
        resources: _ResourceStage,
    ) -> tuple[_ColumnStage | None, OnlineRetrievalResult | None]:
        snapshot = resources.snapshot
        selected_metrics = resources.selected_metrics
        metric_table = (
            resources.metric_constraints[0].data_source
            if resources.metric_constraints
            else None
        )
        try:
            time_field = (
                _parse_time_field(selected_metrics[0])
                if selected_metrics and requires_date_context(semantic_query)
                else None
            )
            required = (
                _required_columns_many(selected_metrics, time_field)
                if selected_metrics
                else {}
            )
            candidate_tables = candidate_table_hits(
                semantic_query.dimensions,
                resources.table_hits,
                metric_table,
                time_field,
            )
            grouping_tables = grouping_table_names(
                semantic_query.dimensions,
                resources.table_hits,
                metric_table,
            )
            if not selected_metrics:
                column_query = _column_query(semantic_query, None)
            elif len(selected_metrics) == 1:
                column_query = _column_query(semantic_query, selected_metrics[0])
            else:
                column_query = _multi_column_query(semantic_query, selected_metrics)
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
            return None, _failure(
                RetrievalStatus.EMBEDDING_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                evidence=resources.evidence,
                request=request,
                metric_constraints=resources.metric_constraints,
            )
        except QdrantStoreError as exc:
            return None, _failure(
                RetrievalStatus.RETRIEVAL_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                evidence=resources.evidence,
                request=request,
                metric_constraints=resources.metric_constraints,
            )
        except ResourceRetrievalContractError as exc:
            return None, _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                evidence=resources.evidence,
                request=request,
                metric_constraints=resources.metric_constraints,
            )
        except RequiredCandidateUnavailableError as exc:
            return None, _result(
                RetrievalStatus.PARTIAL_UNREACHABLE,
                snapshot.asset_version,
                tables=resources.table_hits,
                metrics=selected_metrics,
                evidence=resources.evidence,
                warnings=(str(exc),),
                request=request,
                metric_constraints=resources.metric_constraints,
            )
        except RetrievalContractError as exc:
            return None, _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                evidence=resources.evidence,
                request=request,
                metric_constraints=resources.metric_constraints,
            )

        evidence = RetrievalEvidence(
            table_hits=resources.table_hits,
            column_hits=column_hits,
            metric_hits=resources.metric_hits,
            metric_queries=resources.metric_queries,
        )
        return _ColumnStage(
            time_field=time_field,
            required=required,
            candidate_tables=candidate_tables,
            column_hits=column_hits,
            evidence=evidence,
        ), None

    def _resolve_join(
        self,
        request: RetrievalRequest,
        resources: _ResourceStage,
        columns: _ColumnStage,
    ) -> tuple[_JoinStage | None, OnlineRetrievalResult | None]:
        snapshot = resources.snapshot
        selected_metrics = resources.selected_metrics
        metric_table = (
            resources.metric_constraints[0].data_source
            if resources.metric_constraints
            else None
        )
        try:
            with _safe_span(
                self._trace_recorder,
                "join.resolve",
                {"chatbi.retrieval.asset_version": snapshot.asset_version},
            ):
                anchor, reason = select_anchor(
                    selected_metrics[0] if selected_metrics else None,
                    resources.table_hits,
                )
                edges = _graph_edges(snapshot.relationship_graph)
                time_field = columns.time_field
                if time_field is not None:
                    time_field = _validate_time_edge(time_field, edges)
                targets = target_tables(
                    columns.candidate_tables,
                    metric_table,
                    time_field,
                )
                resolution = _resolve_join_paths(
                    anchor,
                    targets,
                    edges,
                    time_edge=time_field.edge_id if time_field else None,
                    time_target=time_field.target_table if time_field else None,
                )
                join_constraints = _validated_join_constraints(
                    anchor,
                    resolution,
                    snapshot.relationship_graph,
                )
                _safe_enrich_current(
                    self._trace_recorder,
                    _join_trace_attributes(resolution),
                )
        except _AmbiguousRetrieval as exc:
            return None, _result(
                RetrievalStatus.AMBIGUOUS,
                snapshot.asset_version,
                tables=resources.table_hits,
                fields=columns.column_hits,
                metrics=selected_metrics,
                evidence=columns.evidence,
                warnings=(str(exc),),
                request=request,
                metric_constraints=resources.metric_constraints,
            )
        except _UnreachableRequired as exc:
            return None, _result(
                RetrievalStatus.PARTIAL_UNREACHABLE,
                snapshot.asset_version,
                tables=resources.table_hits,
                fields=columns.column_hits,
                metrics=selected_metrics,
                evidence=columns.evidence,
                warnings=(str(exc),),
                request=request,
                metric_constraints=resources.metric_constraints,
            )
        except RelationshipGraphContractError as exc:
            return None, _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                evidence=columns.evidence,
                request=request,
                metric_constraints=resources.metric_constraints,
            )
        except ResourceRetrievalContractError as exc:
            return None, _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                evidence=columns.evidence,
                request=request,
                metric_constraints=resources.metric_constraints,
            )
        except RetrievalContractError as exc:
            return None, _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                evidence=columns.evidence,
                request=request,
                metric_constraints=resources.metric_constraints,
            )
        return _JoinStage(resolution, join_constraints, reason), None

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
