"""旧HTTP响应与持久快照共用的公开问数载荷编码。"""

from typing import Any

from pydantic import BaseModel

from src.business_analysis.application import BusinessAnalysisSuccess
from src.business_analysis.execution import TaskResult
from src.online_query.contracts import QueryErrorCode, QuerySuccess


class QueryResultPayload(BaseModel):
    request_id: str
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    result_metadata: dict[str, Any] | None = None


def query_payload(result: QuerySuccess) -> dict:
    return QueryResultPayload(
        request_id=result.request_id,
        sql=result.sql,
        columns=list(result.columns),
        rows=[list(row) for row in result.rows],
        row_count=result.row_count,
        truncated=result.truncated,
        result_metadata=result.result_metadata.to_payload()
        if result.result_metadata
        else None,
    ).model_dump(mode="json", exclude_none=True)


HTTP_STATUS_BY_ERROR = {
    "HISTORY_BUSY": 409,
    "HISTORY_STALE": 409,
    "HISTORY_OPERATION_CONFLICT": 409,
    "HISTORY_UNAVAILABLE": 404,
    "HISTORY_CONTEXT_INCOMPATIBLE": 422,
    "HISTORY_SNAPSHOT_UNAVAILABLE": 422,
    "HISTORY_RESULT_NOT_SAVABLE": 422,
    "HISTORY_SNAPSHOT_TOO_LARGE": 413,
    "HISTORY_STORAGE_UNAVAILABLE": 503,
    "HISTORY_SAVE_UNCONFIRMED": 503,
    QueryErrorCode.INVALID_REQUEST: 400,
    QueryErrorCode.AUTHENTICATION_REQUIRED: 401,
    QueryErrorCode.AUTHORIZATION_DENIED: 403,
    QueryErrorCode.AUTHENTICATION_UNAVAILABLE: 503,
    QueryErrorCode.CANNOT_ANSWER: 422,
    QueryErrorCode.SQL_REJECTED: 422,
    QueryErrorCode.LLM_ERROR: 502,
    QueryErrorCode.CONTEXT_ERROR: 503,
    QueryErrorCode.DATABASE_ERROR: 503,
    QueryErrorCode.QUERY_TIMEOUT: 504,
    QueryErrorCode.CONVERSATION_UNAVAILABLE: 404,
    QueryErrorCode.CLARIFICATION_REQUIRED: 422,
    QueryErrorCode.UNSUPPORTED_ANALYSIS: 422,
    QueryErrorCode.CONVERSATION_CONFLICT: 409,
}


class AnalysisSuccessResponse(BaseModel):
    """HTTP 经营分析成功响应。"""

    request_id: str
    analysis_run_id: str
    mode: str = "analysis"
    report: dict[str, Any]
    task_results: list[dict[str, Any]]


def analysis_task_result_payload(result: TaskResult) -> dict[str, object]:
    rows = [list(row) for row in result.rows[:100]]
    payload: dict[str, object] = {
        "task_id": result.task_id,
        "status": result.status.value,
        "columns": list(result.columns),
        "rows": rows,
        "row_count": result.row_count,
        "truncated": result.truncated or len(result.rows) > len(rows),
        "error": None,
    }
    if result.error is not None:
        payload["error"] = {
            "code": result.error.code,
            "message": result.error.message,
        }
    if result.result_metadata is not None:
        payload["result_metadata"] = result.result_metadata.to_payload()
    return payload


def analysis_payload(result: BusinessAnalysisSuccess, analysis_run_id: str) -> dict:
    return AnalysisSuccessResponse(
        request_id=result.request_id,
        analysis_run_id=analysis_run_id,
        report=result.report.to_payload(),
        task_results=[
            analysis_task_result_payload(task) for task in result.task_results
        ],
    ).model_dump(mode="json")
