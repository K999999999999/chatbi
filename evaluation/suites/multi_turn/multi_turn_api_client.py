"""通过 in-process Query API Application 运行多轮评测请求。"""

from typing import Any

from fastapi.testclient import TestClient

from src.authorization import (
    InMemoryAuditSink,
    StaticAuthorizationPolicyStore,
    StaticIdentityProviderAdapter,
)
from src.online_query.contracts import (
    QueryErrorCode,
    QueryFailure,
    QuerySuccess,
)
from src.query_api.app import create_app
from src.query_api.conversation import InMemoryConversationStore
from src.query_api.execution_runtime import ExecutionRuntime
from src.query_api.operations import DEPENDENCIES, OperationsState

from .multi_turn_evaluation import ConversationResponse


class QueryApiConversationClient:
    """复用正式认证、授权、会话 Application 和 Online Query 路由。"""

    def __init__(
        self,
        service: object,
        *,
        query_understanding: object | None,
        subject_id: str = "evaluation-test",
    ) -> None:
        identity_provider = StaticIdentityProviderAdapter(
            identity_provider="test",
            subject_id=subject_id,
        )
        operations = OperationsState(clock=lambda: 0.0)
        operations.record_checks(dict.fromkeys(DEPENDENCIES, "ready"))
        self._execution_runtime = ExecutionRuntime(None, None)
        app = create_app(
            service,
            identity_provider=identity_provider,
            policy_store=StaticAuthorizationPolicyStore(
                allowed_subjects=frozenset({subject_id}),
                policy_version="evaluation-test-policy-v1",
            ),
            audit_sink=InMemoryAuditSink(),
            conversation_store=InMemoryConversationStore(),
            query_understanding=query_understanding,
            operations=operations,
        )
        # This in-process evaluation runtime has no lifespan factory; give the
        # synchronous Query route the same explicit ready/capacity boundary as
        # the isolated HTTP test applications.
        app.state.execution_runtime = self._execution_runtime
        self._client = TestClient(app)

    def query(
        self,
        question: str,
        *,
        conversation_id: str | None,
        request_id: str,
    ) -> ConversationResponse:
        payload: dict[str, Any] = {"question": question}
        if conversation_id is not None:
            payload["conversation_id"] = conversation_id
        response = self._client.post(
            "/api/v1/query",
            json=payload,
            headers={"X-Request-ID": request_id},
        )
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("Query API 返回格式无效")

        if "error_code" in body:
            result = QueryFailure(
                request_id=str(body.get("request_id", request_id)),
                error_code=QueryErrorCode(str(body["error_code"])),
                error_message=str(body.get("error_message", "查询失败")),
            )
            value = body.get("conversation_id")
            return ConversationResponse(
                result=result,
                conversation_id=value if isinstance(value, str) and value else None,
            )

        if "rows" not in body or "columns" not in body:
            raise ValueError("Query API 响应缺少查询结果")
        rows = body["rows"]
        columns = body["columns"]
        if not isinstance(rows, list) or not isinstance(columns, list):
            raise ValueError("Query API 结果格式无效")
        result = QuerySuccess(
            request_id=str(body.get("request_id", request_id)),
            sql=str(body.get("sql", "")),
            columns=tuple(str(column) for column in columns),
            rows=tuple(tuple(row) for row in rows),
            row_count=int(body.get("row_count", len(rows))),
            truncated=bool(body.get("truncated", False)),
        )
        value = body.get("conversation_id")
        return ConversationResponse(
            result=result,
            conversation_id=value if isinstance(value, str) and value else None,
        )

    def close(self) -> None:
        self._client.close()
        self._execution_runtime.close()


__all__ = ["QueryApiConversationClient"]
