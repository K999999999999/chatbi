"""Online Retrieval（在线检索）的 Snapshot、资源和字段阶段。"""

from src.rag_offline.embedding import EmbeddingError
from src.rag_offline.qdrant_store import QdrantStoreError

from ..contracts import (
    MetricHit,
    MetricPlanStatus,
    MetricRetrievalEvidence,
    OnlineRetrievalResult,
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
    RetrievalUnavailableError,
)
from .resource_retrieval import (
    ResourceRetrievalContractError,
    _column_hits,
    _column_query,
    _metric_hits,
    _multi_column_query,
    _parse_time_field,
    _required_columns_many,
    _table_extra_queries,
    _table_hits,
    _table_query,
)
from .retrieval_errors import (
    RequiredCandidateUnavailableError,
    RetrievalContractError,
)
from .retrieval_pipeline import (
    _ColumnStage,
    _ResourceStage,
    _RetrievalExecution,
)
from .retrieval_results import failure as _failure
from .retrieval_results import result as _result
from .retrieval_selection import (
    candidate_table_hits,
    grouping_table_names,
    requires_date_context,
)
from .retrieval_trace import (
    merge_metric_hits as _merge_metric_hits,
    safe_enrich_current as _safe_enrich_current,
    safe_span as _safe_span,
)


def _resolve_snapshot(
    execution: _RetrievalExecution,
    request: RetrievalRequest,
) -> tuple[AssetSnapshot | None, OnlineRetrievalResult | None]:
    try:
        with _safe_span(execution.trace_recorder, "asset.resolve"):
            snapshot = execution.runtime.get_snapshot()
            _safe_enrich_current(
                execution.trace_recorder,
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
    execution: _RetrievalExecution,
    request: RetrievalRequest,
    semantic_query: ValidatedSemanticQuery,
    snapshot: AssetSnapshot,
) -> tuple[_ResourceStage | None, OnlineRetrievalResult | None]:
    try:
        query_embedding = execution.embed_query(snapshot, _table_query(semantic_query))
        table_hits = _table_hits(
            snapshot,
            query_embedding,
            execution.config,
            extra_queries=_table_extra_queries(semantic_query),
            embed_query=lambda text: execution.embed_query(snapshot, text),
            search=lambda collection_name, query, **kwargs: execution.search(
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
                execution.embed_query(snapshot, metric_text),
                execution.config,
                search=lambda collection_name, query, **kwargs: execution.search(
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
    return _plan_metrics(
        request,
        semantic_query,
        snapshot,
        table_hits,
        metric_hits_by_query,
        metric_hits,
        evidence,
    )


def _plan_metrics(
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
                plan.mentions[index].document_id if index < len(plan.mentions) else ""
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
    execution: _RetrievalExecution,
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
            execution.config,
            required=required,
            grouping_query=grouping_text,
            grouping_tables=grouping_tables,
            embed_query=lambda text: execution.embed_query(snapshot, text),
            search=lambda collection_name, query, **kwargs: execution.search(
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
