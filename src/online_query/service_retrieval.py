"""OnlineQueryService 的 Online Retrieval 上下文解析适配。"""

from collections.abc import Mapping
import logging

from ..observability.contracts import ErrorType, TraceOutcome, TraceRecorder
from .contracts import (
    QueryContext,
    QueryErrorCode,
    RetrievalProvider,
    RetrievalRequest,
    RetrievalStatus,
)
from .query_trace import (
    enrich_failure_span as _enrich_failure_span,
    safe_enrich as _safe_enrich,
    safe_trace_scope as _safe_trace_scope,
)
from .retrieval.multi_metric import build_retrieval_request


# 保持原 Service logger 名称，兼容现有日志采集和测试捕获规则。
_LOGGER = logging.getLogger("src.online_query.service")

_BUSINESS_RETRIEVAL_FAILURES = {
    RetrievalStatus.NO_TABLE_HIT,
    RetrievalStatus.NO_REQUIRED_COLUMN_HIT,
    RetrievalStatus.NO_METRIC_HIT,
    RetrievalStatus.PARTIAL_UNREACHABLE,
    RetrievalStatus.AMBIGUOUS,
}


def resolve_retrieval_context(
    provider: RetrievalProvider,
    trace_recorder: TraceRecorder,
    question: str,
    request_id: str,
) -> tuple[QueryContext | None, QueryErrorCode | None]:
    with _safe_trace_scope(trace_recorder, name="retrieval.plan"):
        try:
            retrieval_request = build_retrieval_request(question)
        except Exception:
            error = QueryErrorCode.CONTEXT_ERROR
            _enrich_failure_span(
                trace_recorder,
                error,
                ErrorType.RETRIEVAL,
            )
            return None, error
        _safe_enrich(
            trace_recorder,
            attributes={
                "chatbi.retrieval.request_shape": retrieval_request.request_shape.value,
                "chatbi.retrieval.fallback_policy": retrieval_request.fallback_policy.value,
            },
            outcome=TraceOutcome.SUCCESS,
        )

    with _safe_trace_scope(trace_recorder, name="retrieval.execute"):
        base_attributes = {
            "chatbi.retrieval.request_shape": retrieval_request.request_shape.value,
            "chatbi.retrieval.fallback_policy": retrieval_request.fallback_policy.value,
            "chatbi.retrieval.fallback_used": False,
        }
        try:
            result = provider.retrieve(retrieval_request)
        except Exception as exc:
            _LOGGER.warning(
                "Online Retrieval technical failure: request_id=%s status=PROVIDER_EXCEPTION "
                "error_type=%s",
                request_id,
                type(exc).__name__,
            )
            return _retrieval_failure_or_error(
                trace_recorder,
                request_id,
                retrieval_request,
                status=RetrievalStatus.RETRIEVAL_UNAVAILABLE,
                attributes=base_attributes,
            )

        retrieval_attributes = {
            **base_attributes,
            "chatbi.retrieval.status": result.status.value,
            "chatbi.retrieval.asset_version": result.asset_version,
            "chatbi.retrieval.table_count": len(result.tables),
            "chatbi.retrieval.column_count": len(result.fields),
            "chatbi.retrieval.metric_count": len(result.metrics),
        }
        if result.status == RetrievalStatus.SUCCESS:
            try:
                resolved_context = result.to_query_context()
                _safe_enrich(
                    trace_recorder,
                    attributes=retrieval_attributes,
                    outcome=TraceOutcome.SUCCESS,
                )
                return resolved_context, None
            except ValueError as exc:
                _LOGGER.warning(
                    "Online Retrieval fallback: request_id=%s status=SUCCESS "
                    "asset_version=%s error_type=%s",
                    request_id,
                    result.asset_version,
                    type(exc).__name__,
                )
                return _retrieval_failure_or_error(
                    trace_recorder,
                    request_id,
                    retrieval_request,
                    status=result.status,
                    attributes=retrieval_attributes,
                )
        if result.status in _BUSINESS_RETRIEVAL_FAILURES:
            error = QueryErrorCode.CANNOT_ANSWER
            _safe_enrich(
                trace_recorder,
                attributes=retrieval_attributes,
                outcome=TraceOutcome.BUSINESS_REJECTION,
                error_type=ErrorType.RETRIEVAL,
                error_code=error.value,
            )
            return None, error
        _LOGGER.warning(
            "Online Retrieval technical failure: request_id=%s status=%s asset_version=%s "
            "reason=%s",
            request_id,
            result.status.value,
            result.asset_version,
            _fallback_reason(result.warnings),
        )
        return _retrieval_failure_or_error(
            trace_recorder,
            request_id,
            retrieval_request,
            status=result.status,
            attributes=retrieval_attributes,
        )


def _retrieval_failure_or_error(
    trace_recorder: TraceRecorder,
    request_id: str,
    retrieval_request: RetrievalRequest,
    *,
    status: RetrievalStatus,
    attributes: Mapping[str, object],
) -> tuple[QueryContext | None, QueryErrorCode | None]:
    del request_id, retrieval_request
    error = QueryErrorCode.CONTEXT_ERROR
    _safe_enrich(
        trace_recorder,
        attributes={
            **attributes,
            "chatbi.retrieval.status": status.value,
            "chatbi.retrieval.fallback_used": False,
        },
        outcome=TraceOutcome.TECHNICAL_FAILURE,
        error_type=ErrorType.RETRIEVAL,
        error_code=error.value,
    )
    return None, error


def _fallback_reason(warnings: tuple[str, ...]) -> str:
    """只保留已有 warning 的短摘要，避免日志写入完整 Prompt 或 Secret。"""

    if not warnings:
        return "unspecified"
    reason = warnings[0].replace("\r", " ").replace("\n", " ").strip()
    return reason[:256] or "unspecified"
