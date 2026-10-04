"""Online Query 的 Prompt、SQL 生成、校验和数据库执行阶段。"""

from collections.abc import Callable
import logging
from hashlib import sha256
from typing import Any

from ..observability.contracts import ErrorType, TraceOutcome, TraceRecorder

from .contracts import (
    QueryContext,
    QueryErrorCode,
    QueryExecutor,
    QueryFailure,
    QueryResult,
    QuerySuccess,
    SQLGenerator,
)
from .database import DatabaseError, DatabaseQueryTimeout
from .prompt import build_prompt
from .result_metadata import build_result_metadata
from .query_trace import (
    enrich_failure_span as _enrich_failure_span,
    safe_enrich as _safe_enrich,
    safe_trace_scope as _safe_trace_scope,
)
from .query_understanding import ValidatedSemanticQuery
from .semantic_state import prepare_restoration_state, validate_restoration_sql


def _execute_query(
    *,
    sql_generator: SQLGenerator,
    query_executor: QueryExecutor,
    trace_recorder: TraceRecorder | None,
    request_id: str,
    question: str,
    semantic_query: ValidatedSemanticQuery | None,
    context: QueryContext,
    failure_factory: Callable[..., QueryFailure],
    validation_session_factory: Callable[..., Any],
    require_restorable: bool = False,
) -> QueryResult:
    """执行已完成 Request / Context 阶段的 SQL 查询。"""

    restoration_state = None
    if require_restorable:
        try:
            if semantic_query is None:
                raise ValueError("缺少语义")
            semantic_query, restoration_state = prepare_restoration_state(
                semantic_query, context
            )
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "History query semantic certification failed: error_type=%s",
                type(exc).__name__,
            )
            return failure_factory(request_id, QueryErrorCode.CONTEXT_ERROR)
    with _safe_trace_scope(trace_recorder, name="prompt.build"):
        try:
            prompt = build_prompt(
                semantic_query if semantic_query is not None else question,
                context,
                original_question=question if semantic_query is not None else None,
            )
        except Exception:
            result = failure_factory(request_id, QueryErrorCode.CONTEXT_ERROR)
            _enrich_failure_span(
                trace_recorder,
                result.error_code,
                ErrorType.RETRIEVAL,
            )
            return result
        _safe_enrich(
            trace_recorder,
            attributes={
                "chatbi.prompt.length": len(prompt),
                "chatbi.prompt.question_length": len(question),
                "chatbi.prompt.context_length": len(context.prompt_context),
            },
            outcome=TraceOutcome.SUCCESS,
        )

    with _safe_trace_scope(trace_recorder, name="llm.generate"):
        try:
            candidate = sql_generator.generate(prompt)
        except Exception:
            result = failure_factory(request_id, QueryErrorCode.LLM_ERROR)
            _enrich_failure_span(trace_recorder, result.error_code, ErrorType.LLM)
            return result

        if candidate == "CANNOT_ANSWER":
            result = failure_factory(request_id, QueryErrorCode.CANNOT_ANSWER)
            _enrich_failure_span(trace_recorder, result.error_code, ErrorType.LLM)
            return result
        _safe_enrich(trace_recorder, outcome=TraceOutcome.SUCCESS)

    with _safe_trace_scope(
        trace_recorder,
        name="candidate_scope.validate",
    ):
        try:
            validation_session = validation_session_factory(
                candidate,
                context,
                allow_expression_dimensions=require_restorable,
            )
            validation_session.validate_candidate_scope()
        except Exception as exc:
            if require_restorable:
                logging.getLogger(__name__).warning(
                    "History query SQL validation failed: stage=candidate_scope "
                    "error_type=%s",
                    type(exc).__name__,
                )
            result = failure_factory(request_id, QueryErrorCode.SQL_REJECTED)
            _enrich_failure_span(
                trace_recorder,
                result.error_code,
                ErrorType.SQL_GUARD,
            )
            return result
        _safe_enrich(trace_recorder, outcome=TraceOutcome.SUCCESS)

    with _safe_trace_scope(trace_recorder, name="sql.guard"):
        try:
            validated_sql = validation_session.validate_sql()
            if require_restorable:
                validate_restoration_sql(
                    validated_sql.sql, semantic_query, restoration_state, context
                )
        except Exception as exc:
            if require_restorable:
                logging.getLogger(__name__).warning(
                    "History query SQL validation failed: stage=sql_guard "
                    "error_type=%s",
                    type(exc).__name__,
                )
            result = failure_factory(request_id, QueryErrorCode.SQL_REJECTED)
            _enrich_failure_span(
                trace_recorder,
                result.error_code,
                ErrorType.SQL_GUARD,
            )
            return result
        _safe_enrich(
            trace_recorder,
            attributes={
                "chatbi.sql.sha256": sha256(
                    validated_sql.sql.encode("utf-8")
                ).hexdigest(),
            },
            outcome=TraceOutcome.SUCCESS,
        )

    with _safe_trace_scope(trace_recorder, name="database.execute"):
        try:
            data = query_executor.execute(validated_sql)
        except DatabaseQueryTimeout:
            result = failure_factory(request_id, QueryErrorCode.QUERY_TIMEOUT)
            _enrich_failure_span(
                trace_recorder,
                result.error_code,
                ErrorType.TIMEOUT,
            )
            return result
        except DatabaseError:
            result = failure_factory(request_id, QueryErrorCode.DATABASE_ERROR)
            _enrich_failure_span(
                trace_recorder,
                result.error_code,
                ErrorType.DATABASE,
            )
            return result
        except Exception:
            result = failure_factory(request_id, QueryErrorCode.DATABASE_ERROR)
            _enrich_failure_span(
                trace_recorder,
                result.error_code,
                ErrorType.DATABASE,
            )
            return result

        _safe_enrich(
            trace_recorder,
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
            semantic_query=semantic_query,
            restoration_state=restoration_state,
            result_metadata=build_result_metadata(
                validated_sql, data, context, semantic_query
            ),
        )
