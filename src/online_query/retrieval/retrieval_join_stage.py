"""Online Retrieval（在线检索）的 Join 和 Context 阶段。"""

from ..contracts import (
    OnlineRetrievalResult,
    RetrievalEvidence,
    RetrievalRequest,
    RetrievalStatus,
)
from .rag_runtime import AssetSnapshot
from .relationship_graph import (
    RelationshipGraphAmbiguousError as _AmbiguousRetrieval,
    RelationshipGraphContractError,
    RelationshipGraphUnreachableError as _UnreachableRequired,
    parse_edges as _graph_edges,
    resolve_join_paths as _resolve_join_paths,
    validate_time_edge as _validate_time_edge,
    validated_join_constraints as _validated_join_constraints,
)
from .resource_retrieval import ResourceRetrievalContractError
from .retrieval_context import assemble_context
from .retrieval_errors import RetrievalContractError
from .retrieval_pipeline import (
    _ColumnStage,
    _JoinStage,
    _ResourceStage,
    _RetrievalExecution,
)
from .retrieval_results import failure as _failure
from .retrieval_results import result as _result
from .retrieval_selection import select_anchor, target_tables
from .retrieval_trace import (
    _TRACE_EVIDENCE_LIMIT,
    join_trace_attributes as _join_trace_attributes,
    safe_enrich_current as _safe_enrich_current,
    safe_span as _safe_span,
)


def _resolve_join(
    execution: _RetrievalExecution,
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
            execution.trace_recorder,
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
                execution.trace_recorder,
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


def _assemble_success(
    execution: _RetrievalExecution,
    request: RetrievalRequest,
    resources: _ResourceStage,
    columns: _ColumnStage,
    join: _JoinStage,
) -> OnlineRetrievalResult:
    snapshot: AssetSnapshot = resources.snapshot

    with _safe_span(
        execution.trace_recorder,
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
            execution.trace_recorder,
            {
                "chatbi.retrieval.table_count": len(final_tables),
                "chatbi.retrieval.column_count": len(final_fields),
                "chatbi.retrieval.metric_count": len(resources.selected_metrics),
                "chatbi.retrieval.candidate.qualified_tables": tuple(
                    hit.qualified_name for hit in final_tables[:_TRACE_EVIDENCE_LIMIT]
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
