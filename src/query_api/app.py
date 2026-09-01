"""FastAPI HTTP 适配层。"""

from typing import Any, Protocol

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StrictStr

from src.online_query.contracts import QueryRequest, QueryResult, QuerySuccess


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

    @app.post("/api/v1/query", response_model=QuerySuccessResponse)
    def query(
        body: QueryBody,
        x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    ) -> JSONResponse:
        result = service.query(
            QueryRequest(question=body.question, request_id=x_request_id)
        )
        if not isinstance(result, QuerySuccess):
            raise RuntimeError("T2 只支持成功响应")
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

    return app
