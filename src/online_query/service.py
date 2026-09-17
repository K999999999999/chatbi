"""Online Query（在线查询）主链路编排。"""

from collections.abc import Callable
from hashlib import sha256
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
    SQLGenerator,
)
from .database import DatabaseError, DatabaseQueryTimeout
from .prompt import build_prompt
from .query_trace import (
    enrich_failure_span as _enrich_failure_span,
    enrich_query_result as _enrich_query_result,
    safe_enrich as _safe_enrich,
    safe_trace_scope as _safe_trace_scope,
)
from .service_retrieval import resolve_retrieval_context as _resolve_retrieval_context
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
        provider = self._retrieval_provider
        if provider is None:
            if self._context_failed or self._context is None:
                return None, QueryErrorCode.CONTEXT_ERROR
            return self._context, None
        return _resolve_retrieval_context(
            provider,
            self._trace_recorder,
            question,
            request_id,
        )

def _resolve_request_id(request_id: str | None) -> tuple[str, bool]:
    if request_id is None:
        return str(uuid4()), True
    if not isinstance(request_id, str):
        return str(uuid4()), False
    normalized = request_id.strip()
    return (normalized or str(uuid4())), True


def _failure(request_id: str, error_code: QueryErrorCode) -> QueryFailure:
    return QueryFailure(
        request_id=request_id,
        error_code=error_code,
        error_message=_ERROR_MESSAGES[error_code],
    )
