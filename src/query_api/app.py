"""FastAPI HTTP 适配层。"""

from typing import Any, Protocol

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StrictStr

from src.online_query.contracts import (
    QueryErrorCode,
    QueryFailure,
    QueryRequest,
    QueryResult,
    QuerySuccess,
)


_HTTP_STATUS_BY_ERROR = {
    QueryErrorCode.INVALID_REQUEST: 400,
    QueryErrorCode.CANNOT_ANSWER: 422,
    QueryErrorCode.SQL_REJECTED: 422,
    QueryErrorCode.LLM_ERROR: 502,
    QueryErrorCode.CONTEXT_ERROR: 503,
    QueryErrorCode.DATABASE_ERROR: 503,
    QueryErrorCode.QUERY_TIMEOUT: 504,
}


class QueryService(Protocol):
    """API Adapter 依赖的最小查询服务接口。"""

    def query(self, request: QueryRequest) -> QueryResult:
        """执行一次在线查询。"""


class QueryBody(BaseModel):
    """HTTP 查询请求体。"""

    model_config = ConfigDict(extra="forbid")

    question: StrictStr


class QuerySuccessResponse(BaseModel):
    """HTTP 查询成功响应。"""

    request_id: str
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool


class QueryFailureResponse(BaseModel):
    """HTTP 查询失败响应。"""

    request_id: str
    error_code: QueryErrorCode
    error_message: str


def create_app(service: QueryService) -> FastAPI:
    """创建绑定查询服务的 FastAPI 应用。"""

    app = FastAPI(
        title="ChatBI Query API",
        version="0.1.0",
    )
    app.state.query_service = service

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(RequestValidationError)
    def request_validation_error(
        request: Request,
        _: RequestValidationError,
    ) -> JSONResponse:
        result = service.query(
            QueryRequest(
                question="",
                request_id=request.headers.get("X-Request-ID"),
            )
        )
        return _result_response(result)

    @app.post(
        "/api/v1/query",
        response_model=QuerySuccessResponse,
        responses={
            400: {"model": QueryFailureResponse},
            422: {"model": QueryFailureResponse},
            502: {"model": QueryFailureResponse},
            503: {"model": QueryFailureResponse},
            504: {"model": QueryFailureResponse},
        },
    )
    def query(
        body: QueryBody,
        x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    ) -> JSONResponse:
        result = service.query(
            QueryRequest(question=body.question, request_id=x_request_id)
        )
        return _result_response(result)

    return app


def _result_response(result: QueryResult) -> JSONResponse:
    if isinstance(result, QuerySuccess):
        return JSONResponse(
            status_code=200,
            content=QuerySuccessResponse(
                request_id=result.request_id,
                sql=result.sql,
                columns=list(result.columns),
                rows=[list(row) for row in result.rows],
                row_count=result.row_count,
                truncated=result.truncated,
            ).model_dump(mode="json"),
        )
    if isinstance(result, QueryFailure):
        return JSONResponse(
            status_code=_HTTP_STATUS_BY_ERROR[result.error_code],
            content=QueryFailureResponse(
                request_id=result.request_id,
                error_code=result.error_code,
                error_message=result.error_message,
            ).model_dump(mode="json"),
        )
    raise RuntimeError("查询服务返回未知结果")
