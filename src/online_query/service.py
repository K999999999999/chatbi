"""Online Query（在线查询）主链路编排。"""

import logging
from collections.abc import Callable
from hashlib import sha256
from typing import Any
from uuid import uuid4

from ..observability.contracts import (
    ErrorType,
    TraceOutcome,
    TraceRecorder,
)
from ..observability.tracing import create_trace_recorder
from .context import load_query_context
from .contracts import (
    FallbackPolicy,
    QueryContext,
    QueryErrorCode,
    QueryExecutor,
    QueryFailure,
    QueryRequest,
    QueryResult,
    QuerySuccess,
    RequestShape,
    RetrievalProvider,
    RetrievalRequest,
    RetrievalStatus,
    SQLGenerator,
)
from .database import DatabaseError, DatabaseQueryTimeout
from .prompt import build_prompt
from .query_trace import (
    enrich_failure_span as _enrich_failure_span,
)
from .query_trace import (
    enrich_query_result as _enrich_query_result,
)
from .query_trace import (
    safe_enrich as _safe_enrich,
)
from .query_trace import (
    safe_trace_scope as _safe_trace_scope,
)
from .query_understanding import (
    SemanticQueryCannotAnswer,
    SemanticQueryStructureError,
    ValidatedSemanticQuery,
    validate_candidate,
)
from .query_understanding_llm import QueryUnderstandingAdapter
from .sql_guard import _new_validation_session

_ERROR_MESSAGES = {
    QueryErrorCode.INVALID_REQUEST: "查询问题不能为空或格式错误",
    QueryErrorCode.CONTEXT_ERROR: "查询上下文无法加载",
    QueryErrorCode.LLM_ERROR: "LLM 生成 SQL 失败",
    QueryErrorCode.CANNOT_ANSWER: "当前结构和指标无法回答该问题",
    QueryErrorCode.SQL_REJECTED: "生成的 SQL 未通过安全校验",
    QueryErrorCode.DATABASE_ERROR: "数据库连接或执行失败",
    QueryErrorCode.QUERY_TIMEOUT: "数据库查询超时",
}

_LOGGER = logging.getLogger(__name__)

_BUSINESS_RETRIEVAL_FAILURES = {
    RetrievalStatus.NO_TABLE_HIT,
    RetrievalStatus.NO_REQUIRED_COLUMN_HIT,
    RetrievalStatus.NO_METRIC_HIT,
    RetrievalStatus.PARTIAL_UNREACHABLE,
    RetrievalStatus.AMBIGUOUS,
}

_QUERY_UNDERSTANDING_ERROR_MESSAGE = "暂时无法理解这个查询，请稍后重试"
_QUERY_UNDERSTANDING_MISSING_MESSAGE = "查询理解服务尚未配置，请稍后重试"
_FAILURE_STAGES = {
    QueryErrorCode.INVALID_REQUEST: "request_validation",
    QueryErrorCode.CONTEXT_ERROR: "retrieval",
    QueryErrorCode.LLM_ERROR: "sql_generation",
    QueryErrorCode.CANNOT_ANSWER: "retrieval",
    QueryErrorCode.SQL_REJECTED: "sql_guard",
    QueryErrorCode.DATABASE_ERROR: "database",
    QueryErrorCode.QUERY_TIMEOUT: "database",
}


class OnlineQueryService:
    """同步执行一次自然语言查询完整链路。"""

    def __init__(
        self,
        sql_generator: SQLGenerator,
        query_executor: QueryExecutor,
        *,
        context_loader: Callable[[], QueryContext] = load_query_context,
        retrieval_provider: RetrievalProvider | None = None,
        query_understanding: QueryUnderstandingAdapter | None = None,
        trace_recorder: TraceRecorder | None = None,
    ) -> None:
        self._sql_generator = sql_generator
        self._query_executor = query_executor
        self._context: QueryContext | None = None
        self._context_failed = False
        self._retrieval_provider = retrieval_provider
        self._query_understanding = query_understanding
        self._trace_recorder = trace_recorder or create_trace_recorder()
        if retrieval_provider is None:
            try:
                self._context = context_loader()
            except Exception:
                self._context_failed = True

    def query(self, request: QueryRequest) -> QueryResult:
        request_id, request_id_valid = _resolve_request_id(request.request_id)
        with _safe_trace_scope(
            self._trace_recorder,
            root=True,
            name="query.request",
            attributes={"chatbi.request.id": request_id},
        ):
            result = self._query(
                request,
                request_id,
                request_id_valid,
            )
            _enrich_query_result(self._trace_recorder, result)
            return result

    def _query(
        self,
        request: QueryRequest,
        request_id: str,
        request_id_valid: bool,
    ) -> QueryResult:
        with _safe_trace_scope(
            self._trace_recorder,
            name="request.validate",
        ):
            if (
                not request_id_valid
                or not isinstance(request.question, str)
                or not request.question.strip()
            ):
                result = _failure(request_id, QueryErrorCode.INVALID_REQUEST)
                _enrich_failure_span(
                    self._trace_recorder,
                    result.error_code,
                    ErrorType.VALIDATION,
                )
                return result
            _safe_enrich(self._trace_recorder, outcome=TraceOutcome.SUCCESS)

        semantic_query, understanding_error = self._understand_query(
            request.question.strip(),
            request_id,
        )
        if understanding_error is not None:
            return understanding_error

        context, context_error, context_reason = self._resolve_context(
            request.question.strip(),
            request_id,
            semantic_query,
        )
        if context_error is not None:
            return _failure(
                request_id,
                context_error,
                internal_reason=context_reason,
            )
        if context is None:
            return _failure(request_id, QueryErrorCode.CONTEXT_ERROR)

        with _safe_trace_scope(self._trace_recorder, name="prompt.build"):
            try:
                prompt = build_prompt(
                    semantic_query
                    if semantic_query is not None
                    else request.question.strip(),
                    context,
                    original_question=(
                        request.question.strip() if semantic_query is not None else None
                    ),
                )
            except Exception:
                result = _failure(request_id, QueryErrorCode.CONTEXT_ERROR)
                _enrich_failure_span(
                    self._trace_recorder,
                    result.error_code,
                    ErrorType.RETRIEVAL,
                )
                return result
            _safe_enrich(
                self._trace_recorder,
                attributes={
                    "chatbi.prompt.length": len(prompt),
                    "chatbi.prompt.question_length": len(request.question.strip()),
                    "chatbi.prompt.context_length": len(context.prompt_context),
                },
                outcome=TraceOutcome.SUCCESS,
            )

        with _safe_trace_scope(self._trace_recorder, name="llm.generate"):
            try:
                candidate = self._sql_generator.generate(prompt)
            except Exception:
                result = _failure(request_id, QueryErrorCode.LLM_ERROR)
                _enrich_failure_span(
                    self._trace_recorder,
                    result.error_code,
                    ErrorType.LLM,
                )
                return result

            if candidate == "CANNOT_ANSWER":
                result = _failure(request_id, QueryErrorCode.CANNOT_ANSWER)
                _enrich_failure_span(
                    self._trace_recorder,
                    result.error_code,
                    ErrorType.LLM,
                )
                return result
            _safe_enrich(self._trace_recorder, outcome=TraceOutcome.SUCCESS)

        with _safe_trace_scope(
            self._trace_recorder,
            name="candidate_scope.validate",
        ):
            try:
                validation_session = _new_validation_session(candidate, context)
                validation_session.validate_candidate_scope()
            except Exception:
                result = _failure(request_id, QueryErrorCode.SQL_REJECTED)
                _enrich_failure_span(
                    self._trace_recorder,
                    result.error_code,
                    ErrorType.SQL_GUARD,
                )
                return result
            _safe_enrich(self._trace_recorder, outcome=TraceOutcome.SUCCESS)

        with _safe_trace_scope(self._trace_recorder, name="sql.guard"):
            try:
                validated_sql = validation_session.validate_sql()
            except Exception:
                result = _failure(request_id, QueryErrorCode.SQL_REJECTED)
                _enrich_failure_span(
                    self._trace_recorder,
                    result.error_code,
                    ErrorType.SQL_GUARD,
                )
                return result
            _safe_enrich(
                self._trace_recorder,
                attributes={
                    "chatbi.sql.sha256": sha256(
                        validated_sql.sql.encode("utf-8")
                    ).hexdigest(),
                },
                outcome=TraceOutcome.SUCCESS,
            )

        with _safe_trace_scope(self._trace_recorder, name="database.execute"):
            try:
                data = self._query_executor.execute(validated_sql)
            except DatabaseQueryTimeout:
                result = _failure(request_id, QueryErrorCode.QUERY_TIMEOUT)
                _enrich_failure_span(
                    self._trace_recorder,
                    result.error_code,
                    ErrorType.TIMEOUT,
                )
                return result
            except DatabaseError:
                result = _failure(request_id, QueryErrorCode.DATABASE_ERROR)
                _enrich_failure_span(
                    self._trace_recorder,
                    result.error_code,
                    ErrorType.DATABASE,
                )
                return result
            except Exception:
                result = _failure(request_id, QueryErrorCode.DATABASE_ERROR)
                _enrich_failure_span(
                    self._trace_recorder,
                    result.error_code,
                    ErrorType.DATABASE,
                )
                return result

            _safe_enrich(
                self._trace_recorder,
                attributes={
                    "chatbi.database.row_count": len(data.rows),
                    "chatbi.database.truncated": data.truncated,
                },
                outcome=TraceOutcome.SUCCESS,
            )
            return QuerySuccess(
                request_id=request_id,
                sql=validated_sql.sql,
                columns=data.columns,
                rows=data.rows,
                row_count=len(data.rows),
                truncated=data.truncated,
            )

    def _resolve_context(
        self,
        question: str,
        request_id: str,
        semantic_query: ValidatedSemanticQuery | None,
    ) -> tuple[QueryContext | None, QueryErrorCode | None, str | None]:
        if self._retrieval_provider is None:
            if self._context_failed or self._context is None:
                return (
                    None,
                    QueryErrorCode.CONTEXT_ERROR,
                    "STATIC_CONTEXT_UNAVAILABLE",
                )
            return self._context, None, None

        with _safe_trace_scope(self._trace_recorder, name="retrieval.plan"):
            if semantic_query is None:
                error = QueryErrorCode.CONTEXT_ERROR
                _enrich_failure_span(
                    self._trace_recorder,
                    error,
                    ErrorType.RETRIEVAL,
                )
                return None, error, "SEMANTIC_QUERY_MISSING"
            retrieval_request = RetrievalRequest(
                question=question,
                request_shape=_request_shape(semantic_query),
                fallback_policy=FallbackPolicy.FAIL_CLOSED,
                semantic_query=semantic_query,
            )
            _safe_enrich(
                self._trace_recorder,
                attributes={
                    "chatbi.retrieval.request_shape": retrieval_request.request_shape.value,
                    "chatbi.retrieval.fallback_policy": retrieval_request.fallback_policy.value,
                },
                outcome=TraceOutcome.SUCCESS,
            )

        with _safe_trace_scope(self._trace_recorder, name="retrieval.execute"):
            base_attributes = {
                "chatbi.retrieval.request_shape": retrieval_request.request_shape.value,
                "chatbi.retrieval.fallback_policy": retrieval_request.fallback_policy.value,
                "chatbi.retrieval.fallback_used": False,
            }
            try:
                result = self._retrieval_provider.retrieve(retrieval_request)
            except Exception as exc:
                _LOGGER.warning(
                    "Online Retrieval technical failure: request_id=%s status=PROVIDER_EXCEPTION "
                    "error_type=%s",
                    request_id,
                    type(exc).__name__,
                )
                return self._retrieval_failure_or_error(
                    request_id,
                    retrieval_request,
                    status=RetrievalStatus.RETRIEVAL_UNAVAILABLE,
                    attributes=base_attributes,
                    internal_reason="PROVIDER_EXCEPTION",
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
                        self._trace_recorder,
                        attributes=retrieval_attributes,
                        outcome=TraceOutcome.SUCCESS,
                    )
                    return resolved_context, None, None
                except ValueError as exc:
                    _LOGGER.warning(
                        "Online Retrieval fallback: request_id=%s status=SUCCESS "
                        "asset_version=%s error_type=%s",
                        request_id,
                        result.asset_version,
                        type(exc).__name__,
                    )
                    return self._retrieval_failure_or_error(
                        request_id,
                        retrieval_request,
                        status=result.status,
                        attributes=retrieval_attributes,
                        internal_reason="QUERY_CONTEXT_BUILD_FAILED",
                    )
            if result.status in _BUSINESS_RETRIEVAL_FAILURES:
                error = QueryErrorCode.CANNOT_ANSWER
                _safe_enrich(
                    self._trace_recorder,
                    attributes=retrieval_attributes,
                    outcome=TraceOutcome.BUSINESS_REJECTION,
                    error_type=ErrorType.RETRIEVAL,
                    error_code=error.value,
                )
                return (
                    None,
                    error,
                    result.internal_reason or result.status.value,
                )
            _LOGGER.warning(
                "Online Retrieval technical failure: request_id=%s status=%s asset_version=%s "
                "reason=%s",
                request_id,
                result.status.value,
                result.asset_version,
                _fallback_reason(result.warnings),
            )
            return self._retrieval_failure_or_error(
                request_id,
                retrieval_request,
                status=result.status,
                attributes=retrieval_attributes,
                internal_reason=result.internal_reason or result.status.value,
            )

    def _understand_query(
        self,
        question: str,
        request_id: str,
    ) -> tuple[ValidatedSemanticQuery | None, QueryFailure | None]:
        """在线模式下先完成 Query Understanding，再允许进入 Retrieval。"""

        if self._retrieval_provider is None:
            return None, None

        with _safe_trace_scope(self._trace_recorder, name="query.understanding"):
            if self._query_understanding is None:
                result = _failure(
                    request_id,
                    QueryErrorCode.LLM_ERROR,
                    message=_QUERY_UNDERSTANDING_MISSING_MESSAGE,
                    stage="query_understanding",
                    internal_reason="ADAPTER_NOT_CONFIGURED",
                )
                _safe_enrich(
                    self._trace_recorder,
                    attributes={
                        "chatbi.query_understanding.reason": "ADAPTER_NOT_CONFIGURED",
                    },
                    outcome=TraceOutcome.TECHNICAL_FAILURE,
                    error_type=ErrorType.LLM,
                    error_code=result.error_code.value,
                )
                return None, result

            try:
                candidate = self._query_understanding.understand(question)
            except Exception as exc:
                result = _failure(
                    request_id,
                    QueryErrorCode.LLM_ERROR,
                    message=_QUERY_UNDERSTANDING_ERROR_MESSAGE,
                    stage="query_understanding",
                    internal_reason=_exception_reason(
                        exc,
                        "UNDERSTANDING_FAILED",
                    ),
                )
                _safe_enrich(
                    self._trace_recorder,
                    attributes={
                        "chatbi.query_understanding.reason": _exception_reason(
                            exc,
                            "UNDERSTANDING_FAILED",
                        ),
                    },
                    outcome=TraceOutcome.TECHNICAL_FAILURE,
                    error_type=ErrorType.LLM,
                    error_code=result.error_code.value,
                )
                return None, result

            try:
                validated = validate_candidate(
                    candidate,
                    original_question=question,
                )
            except SemanticQueryCannotAnswer as exc:
                result = _failure(
                    request_id,
                    QueryErrorCode.CANNOT_ANSWER,
                    message=str(exc),
                    stage="query_understanding",
                    internal_reason=exc.reason,
                )
                _safe_enrich(
                    self._trace_recorder,
                    attributes={
                        "chatbi.query_understanding.reason": exc.reason,
                    },
                    outcome=TraceOutcome.BUSINESS_REJECTION,
                    error_type=ErrorType.RETRIEVAL,
                    error_code=result.error_code.value,
                )
                return None, result
            except SemanticQueryStructureError as exc:
                result = _failure(
                    request_id,
                    QueryErrorCode.LLM_ERROR,
                    message=_QUERY_UNDERSTANDING_ERROR_MESSAGE,
                    stage="query_understanding",
                    internal_reason=exc.reason,
                )
                _safe_enrich(
                    self._trace_recorder,
                    attributes={
                        "chatbi.query_understanding.reason": exc.reason,
                    },
                    outcome=TraceOutcome.TECHNICAL_FAILURE,
                    error_type=ErrorType.LLM,
                    error_code=result.error_code.value,
                )
                return None, result
            except Exception as exc:
                result = _failure(
                    request_id,
                    QueryErrorCode.LLM_ERROR,
                    message=_QUERY_UNDERSTANDING_ERROR_MESSAGE,
                    stage="query_understanding",
                    internal_reason=_exception_reason(
                        exc,
                        "VALIDATION_FAILED",
                    ),
                )
                _safe_enrich(
                    self._trace_recorder,
                    attributes={
                        "chatbi.query_understanding.reason": _exception_reason(
                            exc,
                            "VALIDATION_FAILED",
                        ),
                    },
                    outcome=TraceOutcome.TECHNICAL_FAILURE,
                    error_type=ErrorType.LLM,
                    error_code=result.error_code.value,
                )
                return None, result

            _safe_enrich(
                self._trace_recorder,
                attributes={
                    "chatbi.query_understanding.query_type": validated.query_type.value,
                    "chatbi.query_understanding.metric_count": len(validated.metrics),
                    "chatbi.query_understanding.filter_count": len(validated.filters),
                    "chatbi.query_understanding.has_time": validated.time is not None,
                },
                outcome=TraceOutcome.SUCCESS,
            )
            return validated, None

    def _retrieval_failure_or_error(
        self,
        request_id: str,
        retrieval_request: Any,
        *,
        status: RetrievalStatus,
        attributes: dict[str, object],
        internal_reason: str | None = None,
    ) -> tuple[QueryContext | None, QueryErrorCode | None, str | None]:
        del request_id, retrieval_request
        error = QueryErrorCode.CONTEXT_ERROR
        _safe_enrich(
            self._trace_recorder,
            attributes={
                **attributes,
                "chatbi.retrieval.status": status.value,
                "chatbi.retrieval.fallback_used": False,
            },
            outcome=TraceOutcome.TECHNICAL_FAILURE,
            error_type=ErrorType.RETRIEVAL,
            error_code=error.value,
        )
        return None, error, internal_reason or status.value


def _resolve_request_id(request_id: str | None) -> tuple[str, bool]:
    if request_id is None:
        return str(uuid4()), True
    if not isinstance(request_id, str):
        return str(uuid4()), False
    normalized = request_id.strip()
    return (normalized or str(uuid4())), True


def _fallback_reason(warnings: tuple[str, ...]) -> str:
    """只保留已有 warning 的短摘要，避免日志写入完整 Prompt 或 Secret。"""

    if not warnings:
        return "unspecified"
    reason = warnings[0].replace("\r", " ").replace("\n", " ").strip()
    return reason[:256] or "unspecified"


def _failure(
    request_id: str,
    error_code: QueryErrorCode,
    *,
    message: str | None = None,
    stage: str | None = None,
    internal_reason: str | None = None,
) -> QueryFailure:
    return QueryFailure(
        request_id=request_id,
        error_code=error_code,
        error_message=message or _ERROR_MESSAGES[error_code],
        failure_stage=stage or _FAILURE_STAGES[error_code],
        internal_reason=internal_reason or error_code.value,
    )


def _request_shape(query: ValidatedSemanticQuery) -> RequestShape:
    if len(query.metrics) >= 2:
        return RequestShape.EXPLICIT_MULTI
    return RequestShape.BASELINE


def _exception_reason(exc: Exception, fallback: str) -> str:
    reason = getattr(exc, "reason", None)
    if isinstance(reason, str) and reason.strip() and reason.strip() != "LLM_ERROR":
        return reason.strip()[:128]
    return fallback
