"""新增API身份、严格参数及公开载荷边界。"""

from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.authorization.contracts import AuthContext, AuthorizationDecision
from src.query_api.app import create_app
from src.query_api.history_contracts import HistoryHeader


class Provider:
    identity_provider = "local-test"

    def authenticate(self, request):
        return AuthContext(
            "local:1",
            self.identity_provider,
            user_id=1,
            permissions=frozenset({"query.execute"}),
        )


class Policy:
    def authorize(self, context, **kwargs):
        return AuthorizationDecision(True, "AUTHORIZED", "test")


class Audit:
    def emit(self, event):
        pass


class Store:
    def create(self, owner, kind, question, operation):
        now = datetime(2026, 10, 4, tzinfo=UTC)
        return HistoryHeader(
            "81fc7ae0-e7c2-408c-bc62-28c2e506bf78",
            kind,
            question,
            question,
            now,
            now,
            0,
            0,
            None,
            None,
            None,
        )


def test_create_history_returns_no_private_owner_or_state():
    app = create_app(
        service=SimpleNamespace(),
        identity_provider=Provider(),
        policy_store=Policy(),
        audit_sink=Audit(),
        history_store=Store(),
        history_runtime=SimpleNamespace(check=lambda: None),
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/histories",
            json={
                "kind": "query",
                "first_question": "销售额",
                "operation_id": "6cc90b65-f9c2-4f92-9f7f-f9c60a9f8970",
            },
        )
    assert response.status_code == 201, response.text
    assert response.json()["kind"] == "query"
    assert "owner_user_id" not in response.json()
    assert "query_state" not in response.json()
    assert response.headers["cache-control"] == "no-store"
