"""Online Query（在线查询）主链路编排。"""

from collections.abc import Callable
from hashlib import sha256
import logging
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
    QueryContext,
    QueryErrorCode,
    QueryExecutor,
    QueryFailure,
    QueryRequest,
    QueryResult,
    QuerySuccess,
    RetrievalProvider,
    RetrievalStatus,
    SQLGenerator,
)
from .database import DatabaseError, DatabaseQueryTimeout
from .multi_metric import build_retrieval_request
from .prompt import build_prompt
from .query_trace import (
    enrich_failure_span as _enrich_failure_span,
    enrich_query_result as _enrich_query_result,
    safe_enrich as _safe_enrich,
    safe_trace_scope as _safe_trace_scope,
)
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


class OnlineQueryService:
    """同步执行一次自然语言查询完整链路。"""

    def __init__(
        self,
        sql_generator: SQLGenerator,
        query_executor: QueryExecutor,
        *,
        context_loader: Callable[[], QueryContext] = load_query_context,
        retrieval_provider: RetrievalProvider | None = None,
        trace_recorder: TraceRecorder | None = None,
    ) -> None:
        self._sql_generator = sql_generator
        self._query_executor = query_executor
        self._context: QueryContext | None = None
        self._context_failed = False
        self._retrieval_provider = retrieval_provider
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

        context, context_error = self._resolve_context(
            request.question.strip(),
            request_id,
        )
        if context_error is not None:
            return _failure(request_id, context_error)
        if context is None:
            return _failure(request_id, QueryErrorCode.CONTEXT_ERROR)

        with _safe_trace_scope(self._trace_recorder, name="prompt.build"):
            try:
                prompt = build_prompt(request.question.strip(), context)
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
    ) -> tuple[QueryContext | None, QueryErrorCode | None]:
        if self._retrieval_provider is None:
            if self._context_failed or self._context is None:
                return None, QueryErrorCode.CONTEXT_ERROR
            return self._context, None

        with _safe_trace_scope(self._trace_recorder, name="retrieval.plan"):
            try:
                retrieval_request = build_retrieval_request(question)
            except Exception:
                error = QueryErrorCode.CONTEXT_ERROR
                _enrich_failure_span(
                    self._trace_recorder,
                    error,
                    ErrorType.RETRIEVAL,
                )
                return None, error
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
                    return resolved_context, None
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
                return None, error
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
            )

    def _retrieval_failure_or_error(
        self,
        request_id: str,
        retrieval_request: Any,
        *,
        status: RetrievalStatus,
        attributes: dict[str, object],
    ) -> tuple[QueryContext | None, QueryErrorCode | None]:
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
        return None, error


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


def _failure(request_id: str, error_code: QueryErrorCode) -> QueryFailure:
    return QueryFailure(
        request_id=request_id,
        error_code=error_code,
        error_message=_ERROR_MESSAGES[error_code],
    )
