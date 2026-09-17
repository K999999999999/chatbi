"""Online Retrieval（在线检索）三路检索、关系解析和上下文组装。"""

from collections.abc import Mapping
from typing import Any

from src.observability.contracts import TraceRecorder
from src.observability.tracing import create_trace_recorder
from src.rag_offline.embedding import EmbeddingError
from src.rag_offline.qdrant_store import QdrantStoreError, SearchHit

from ..contracts import (
    ColumnHit,
    JoinConstraint,
    MetricConstraint,
    MetricHit,
    MetricPlanStatus,
    MetricRetrievalEvidence,
    OnlineRetrievalResult,
    QueryContext,
    RetrievalConfig,
    RetrievalEvidence,
    RetrievalRequest,
    RetrievalStatus,
    TableHit,
)
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

        metric_queries: tuple[MetricRetrievalEvidence, ...] = ()
        selected_tuple: tuple[MetricHit, ...] = ()
        constraints: tuple[MetricConstraint, ...] = ()
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
            return _failure(
                RetrievalStatus.EMBEDDING_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                request=request,
            )
        except QdrantStoreError as exc:
            return _failure(
                RetrievalStatus.RETRIEVAL_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                request=request,
            )
        except ResourceRetrievalContractError as exc:
            return _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                request=request,
            )
        except RetrievalContractError as exc:
            return _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                asset_version=snapshot.asset_version,
                request=request,
            )
        evidence = RetrievalEvidence(
            table_hits=table_hits,
            metric_hits=metric_hits,
        )

        if semantic_query.metrics:
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
                return _failure(
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
                return _result(
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
                selected_tuple = tuple(
                    hits_by_document[constraint.document_id]
                    for constraint in constraints
                )
            except KeyError as exc:
                return _result(
                    RetrievalStatus.NO_METRIC_HIT,
                    snapshot.asset_version,
                    tables=table_hits,
                    evidence=evidence,
                    warnings=(f"指标候选在本次检索中缺失：{exc.args[0]}",),
                    request=request,
                    internal_reason="NO_METRIC_HIT",
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

        metric_table = constraints[0].data_source if constraints else None
        if metric_table is not None and not any(
            hit.qualified_name == metric_table for hit in table_hits
        ):
            return _result(
                RetrievalStatus.NO_TABLE_HIT,
                snapshot.asset_version,
                tables=table_hits,
                metrics=selected_tuple,
                evidence=evidence,
                warnings=("指标 data_source 没有被 TABLE 路线命中",),
                request=request,
                metric_constraints=constraints,
            )

        try:
            time_field = (
                _parse_time_field(selected_tuple[0])
                if selected_tuple and requires_date_context(semantic_query)
                else None
            )
            required = (
                _required_columns_many(selected_tuple, time_field)
                if selected_tuple
                else {}
            )
            candidate_tables = candidate_table_hits(
                semantic_query.dimensions,
                table_hits,
                metric_table,
                time_field,
            )
            grouping_tables = grouping_table_names(
                semantic_query.dimensions,
                table_hits,
                metric_table,
            )
            if not selected_tuple:
                column_query = _column_query(semantic_query, None)
            elif len(selected_tuple) == 1:
                column_query = _column_query(semantic_query, selected_tuple[0])
            else:
                column_query = _multi_column_query(semantic_query, selected_tuple)
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
        except RequiredCandidateUnavailableError as exc:
            return _result(
                RetrievalStatus.PARTIAL_UNREACHABLE,
                snapshot.asset_version,
                tables=table_hits,
                metrics=selected_tuple,
                evidence=evidence,
                warnings=(str(exc),),
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
            metric_hits=metric_hits,
            metric_queries=metric_queries,
        )
        if not column_hits:
            return _result(
                RetrievalStatus.NO_REQUIRED_COLUMN_HIT,
                snapshot.asset_version,
                tables=table_hits,
                fields=column_hits,
                metrics=selected_tuple,
                evidence=evidence,
                warnings=("COLUMN 检索没有超过阈值的有效候选",),
                request=request,
                metric_constraints=constraints,
            )
        if selected_tuple and not _contains_required_columns(column_hits, required):
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
                anchor, reason = select_anchor(
                    selected_tuple[0] if selected_tuple else None,
                    table_hits,
                )
                edges = _graph_edges(snapshot.relationship_graph)
                if time_field is not None:
                    time_field = _validate_time_edge(time_field, edges)
                targets = target_tables(candidate_tables, metric_table, time_field)
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
                metric=selected_tuple[0] if len(selected_tuple) == 1 else None,
                metrics=selected_tuple if len(selected_tuple) >= 2 else (),
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
                        hit.qualified_name
                        for hit in final_tables[:_TRACE_EVIDENCE_LIMIT]
                    ),
                },
            )
        evidence = RetrievalEvidence(
            table_hits=table_hits,
            column_hits=column_hits,
            metric_hits=metric_hits,
            metric_queries=metric_queries,
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
            warnings=(f"anchor_reason={reason}",),
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
