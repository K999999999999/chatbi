"""Online Query 编排使用的 Trace 安全边界和结果标记。"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from ..observability.contracts import (
    ErrorType,
    QuerySource,
    TraceOutcome,
    TraceRecorder,
)
from .contracts import QueryErrorCode, QueryResult, QuerySuccess


@contextmanager
def safe_trace_scope(
    recorder: TraceRecorder,
    *,
    name: str,
    root: bool = False,
    attributes: dict[str, object] | None = None,
) -> Iterator[Any]:
    """让 Trace 失败退化为空作用域，不影响业务节点。"""

    try:
        scope = (
            recorder.query_trace(
                QuerySource.INTERNAL,
                attributes=attributes,
            )
            if root
            else recorder.span(name, attributes=attributes)
        )
    except Exception:
        scope = _NoopTraceScope()

    entered = False
    try:
        try:
            scope.__enter__()
            entered = True
        except Exception:
            scope = _NoopTraceScope()
            scope.__enter__()
            entered = True
        yield scope
    finally:
        if entered:
            try:
                scope.__exit__(None, None, None)
            except Exception:
                pass


class _NoopTraceScope:
    def __enter__(self) -> "_NoopTraceScope":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        return False


def safe_enrich(
    recorder: TraceRecorder,
    *,
    attributes: dict[str, object] | None = None,
    outcome: TraceOutcome | None = None,
    error_type: ErrorType | None = None,
    error_code: str | None = None,
) -> None:
    try:
        recorder.enrich_current(
            attributes=attributes,
            outcome=outcome,
            error_type=error_type,
            error_code=error_code,
        )
    except Exception:
        pass


def enrich_failure_span(
    recorder: TraceRecorder,
    error_code: QueryErrorCode,
    error_type: ErrorType,
) -> None:
    outcome = (
        TraceOutcome.TIMEOUT
        if error_code == QueryErrorCode.QUERY_TIMEOUT
        else TraceOutcome.BUSINESS_REJECTION
        if error_code
        in {
            QueryErrorCode.INVALID_REQUEST,
            QueryErrorCode.CANNOT_ANSWER,
            QueryErrorCode.SQL_REJECTED,
        }
        else TraceOutcome.TECHNICAL_FAILURE
    )
    safe_enrich(
        recorder,
        outcome=outcome,
        error_type=error_type,
        error_code=error_code.value,
    )


def enrich_query_result(recorder: TraceRecorder, result: QueryResult) -> None:
    if isinstance(result, QuerySuccess):
        safe_enrich(
            recorder,
            attributes={
                "chatbi.result.row_count": result.row_count,
                "chatbi.result.truncated": result.truncated,
            },
            outcome=TraceOutcome.SUCCESS,
        )
        return
    error_type, outcome = failure_trace_mapping(result.error_code)
    safe_enrich(
        recorder,
        outcome=outcome,
        error_type=error_type,
        error_code=result.error_code.value,
    )


def failure_trace_mapping(
    error_code: QueryErrorCode,
) -> tuple[ErrorType, TraceOutcome]:
    if error_code == QueryErrorCode.INVALID_REQUEST:
        return ErrorType.VALIDATION, TraceOutcome.BUSINESS_REJECTION
    if error_code == QueryErrorCode.CANNOT_ANSWER:
        return ErrorType.RETRIEVAL, TraceOutcome.BUSINESS_REJECTION
    if error_code == QueryErrorCode.SQL_REJECTED:
        return ErrorType.SQL_GUARD, TraceOutcome.BUSINESS_REJECTION
    if error_code == QueryErrorCode.LLM_ERROR:
        return ErrorType.LLM, TraceOutcome.TECHNICAL_FAILURE
    if error_code == QueryErrorCode.CONTEXT_ERROR:
        return ErrorType.RETRIEVAL, TraceOutcome.TECHNICAL_FAILURE
    if error_code == QueryErrorCode.QUERY_TIMEOUT:
        return ErrorType.TIMEOUT, TraceOutcome.TIMEOUT
    return ErrorType.DATABASE, TraceOutcome.TECHNICAL_FAILURE
