"""Online Retrieval（在线检索）的结果构造辅助。"""

from src.online_query.contracts import (
    ColumnHit,
    FallbackPolicy,
    JoinConstraint,
    JoinResolution,
    MetricConstraint,
    MetricHit,
    OnlineRetrievalResult,
    QueryContext,
    RequestShape,
    RetrievalEvidence,
    RetrievalRequest,
    RetrievalStatus,
    TableHit,
)


def result(
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


def failure(
    status: RetrievalStatus,
    warning: str,
    *,
    asset_version: str | None = None,
    evidence: RetrievalEvidence | None = None,
    request: RetrievalRequest | None = None,
    internal_reason: str | None = None,
    metric_constraints: tuple[MetricConstraint, ...] = (),
) -> OnlineRetrievalResult:
    return result(
        status,
        asset_version,
        evidence=evidence,
        warnings=(warning,),
        request=request,
        internal_reason=internal_reason,
        metric_constraints=metric_constraints,
    )
