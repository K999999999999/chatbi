"""Online Retrieval（在线检索）的 Join 和 Context 阶段。"""

from dataclasses import replace

from src.rag_offline.documents import METRIC_COLLECTION
from src.rag_offline.qdrant_store import QdrantStoreError

from ..contracts import (
    OnlineRetrievalResult,
    RetrievalEvidence,
    RetrievalRequest,
    RetrievalStatus,
)
from .rag_runtime import AssetSnapshot
from .relationship_graph import (
    RelationshipGraphAmbiguousError as _AmbiguousRetrieval,
)
from .relationship_graph import (
    RelationshipGraphContractError,
)
from .relationship_graph import (
    RelationshipGraphUnreachableError as _UnreachableRequired,
)
from .relationship_graph import (
    parse_edges as _graph_edges,
)
from .relationship_graph import (
    resolve_join_paths as _resolve_join_paths,
)
from .relationship_graph import (
    validate_time_edge as _validate_time_edge,
)
from .relationship_graph import (
    validated_join_constraints as _validated_join_constraints,
)
from .resource_retrieval import (
    ResourceRetrievalContractError,
    _column_hits,
    _contains_required_columns,
    _to_metric_hit,
)
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
)
from .retrieval_trace import (
    join_trace_attributes as _join_trace_attributes,
)
from .retrieval_trace import (
    safe_enrich_current as _safe_enrich_current,
)
from .retrieval_trace import (
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

    column_hits = columns.column_hits
    semantic_metrics = resources.selected_metrics
    if request.semantic_query.restoration_conditions is not None:
        try:
            pending = [
                dep
                for hit in semantic_metrics
                for dep in hit.metadata.get("depends_on", ())
            ]
            collected = {hit.metric_name: hit for hit in semantic_metrics}
            query_vector = None
            while pending:
                name = pending.pop()
                if name in collected:
                    continue
                if query_vector is None:
                    query_vector = execution.embed_query(snapshot, "指标定义")
                hits = snapshot.qdrant_store.search(
                    snapshot.collection_names[METRIC_COLLECTION],
                    query_vector,
                    limit=2,
                    filter_payload={"metric_name": name},
                )
                if len(hits) != 1:
                    raise ResourceRetrievalContractError(
                        "历史指标依赖缺少唯一已发布定义"
                    )
                hit = _to_metric_hit(hits[0], 0)
                if hit.metric_name != name:
                    raise ResourceRetrievalContractError("历史指标依赖身份不符")
                collected[name] = hit
                pending.extend(hit.metadata.get("depends_on", ()))
            semantic_metrics = tuple(collected.values())
        except (QdrantStoreError, ResourceRetrievalContractError) as exc:
            return _failure(
                RetrievalStatus.ASSET_UNAVAILABLE,
                str(exc),
                request=request,
                asset_version=snapshot.asset_version,
                evidence=columns.evidence,
            )
        required = {}
        for edge in join.resolution.joins:
            for table, names in (
                (edge.source_table, edge.source_columns),
                (edge.target_table, edge.target_columns),
            ):
                required.setdefault(table, set()).update(names)
        if "mart_sales.dim_date" in {
            t.qualified_name for t in columns.candidate_tables
        }:
            required.setdefault("mart_sales.dim_date", set()).update(
                ("date_key", "full_date", "year", "month", "quarter")
            )
        missing = {
            table: frozenset(
                names
                - {h.column_name for h in column_hits if h.qualified_table == table}
            )
            for table, names in required.items()
        }
        if any(missing.values()):
            try:
                certified = _column_hits(
                    snapshot,
                    columns.candidate_tables,
                    "认证关系键与日历字段",
                    replace(
                        execution.config,
                        column_top_k=max(
                            execution.config.column_top_k,
                            sum(map(len, missing.values())),
                        ),
                    ),
                    required=missing,
                )
                column_hits = tuple(
                    {
                        (h.qualified_table, h.column_name): h
                        for h in (*column_hits, *certified)
                    }.values()
                )
                if not _contains_required_columns(column_hits, required):
                    raise ResourceRetrievalContractError(
                        "历史条件的关系键或日历字段缺少已发布 Metadata"
                    )
            except (QdrantStoreError, ResourceRetrievalContractError) as exc:
                return _failure(
                    RetrievalStatus.ASSET_UNAVAILABLE,
                    str(exc),
                    request=request,
                    asset_version=snapshot.asset_version,
                    evidence=columns.evidence,
                )

    with _safe_span(
        execution.trace_recorder,
        "context.assemble",
        {"chatbi.retrieval.asset_version": snapshot.asset_version},
    ):
        context = assemble_context(
            columns.candidate_tables,
            column_hits,
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
            semantic_metrics=semantic_metrics,
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
