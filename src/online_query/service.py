"""Online Query（在线查询）主链路编排。"""

from collections.abc import Callable
import logging
from uuid import uuid4

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
from .prompt import build_prompt
from .sql_guard import validate_candidate_scope, validate_sql


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
    ) -> None:
        self._sql_generator = sql_generator
        self._query_executor = query_executor
        self._context: QueryContext | None = None
        self._context_failed = False
        self._retrieval_provider = retrieval_provider
        try:
            self._context = context_loader()
        except Exception:
            self._context_failed = True

    def query(self, request: QueryRequest) -> QueryResult:
        request_id, request_id_valid = _resolve_request_id(request.request_id)
        if (
            not request_id_valid
            or not isinstance(request.question, str)
            or not request.question.strip()
        ):
            return _failure(request_id, QueryErrorCode.INVALID_REQUEST)

        context, context_error = self._resolve_context(
            request.question.strip(),
            request_id,
        )
        if context_error is not None:
            return _failure(request_id, context_error)
        if context is None:
            return _failure(request_id, QueryErrorCode.CONTEXT_ERROR)

        prompt = build_prompt(request.question.strip(), context)
        try:
            candidate = self._sql_generator.generate(prompt)
        except Exception:
            return _failure(request_id, QueryErrorCode.LLM_ERROR)

        if candidate == "CANNOT_ANSWER":
            return _failure(request_id, QueryErrorCode.CANNOT_ANSWER)

        try:
            validate_candidate_scope(candidate, context)
        except Exception:
            return _failure(request_id, QueryErrorCode.SQL_REJECTED)

        try:
            validated_sql = validate_sql(candidate, context)
        except Exception:
            return _failure(request_id, QueryErrorCode.SQL_REJECTED)

        try:
            data = self._query_executor.execute(validated_sql)
        except DatabaseQueryTimeout:
            return _failure(request_id, QueryErrorCode.QUERY_TIMEOUT)
        except DatabaseError:
            return _failure(request_id, QueryErrorCode.DATABASE_ERROR)
        except Exception:
            return _failure(request_id, QueryErrorCode.DATABASE_ERROR)

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

        try:
            result = self._retrieval_provider.retrieve(question)
        except Exception as exc:
            _LOGGER.warning(
                "Online Retrieval fallback: request_id=%s status=PROVIDER_EXCEPTION "
                "error_type=%s",
                request_id,
                type(exc).__name__,
            )
            return self._static_context_or_error()

        if result.status == RetrievalStatus.SUCCESS:
            try:
                return result.to_query_context(), None
            except ValueError as exc:
                _LOGGER.warning(
                    "Online Retrieval fallback: request_id=%s status=SUCCESS "
                    "asset_version=%s error_type=%s",
                    request_id,
                    result.asset_version,
                    type(exc).__name__,
                )
                return self._static_context_or_error()
        if result.status in _BUSINESS_RETRIEVAL_FAILURES:
            return None, QueryErrorCode.CANNOT_ANSWER
        _LOGGER.warning(
            "Online Retrieval fallback: request_id=%s status=%s asset_version=%s "
            "reason=%s",
            request_id,
            result.status.value,
            result.asset_version,
            _fallback_reason(result.warnings),
        )
        return self._static_context_or_error()

    def _static_context_or_error(
        self,
    ) -> tuple[QueryContext | None, QueryErrorCode | None]:
        if self._context_failed or self._context is None:
            return None, QueryErrorCode.CONTEXT_ERROR
        return self._context, None


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
