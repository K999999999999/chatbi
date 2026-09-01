"""FastAPI HTTP 适配层。"""

from typing import Protocol

from fastapi import FastAPI

from src.online_query.contracts import QueryRequest, QueryResult


class QueryService(Protocol):
    """API Adapter 依赖的最小查询服务接口。"""

    def query(self, request: QueryRequest) -> QueryResult:
        """执行一次在线查询。"""


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

    return app
