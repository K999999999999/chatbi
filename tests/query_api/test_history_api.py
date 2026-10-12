"""新增API身份、严格参数及公开载荷边界。"""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from fastapi.testclient import TestClient

from src.authorization.contracts import AuthContext, AuthorizationDecision
from tests.operations_support import create_app
from src.query_api.history_contracts import (
    HistoryError,
    HistoryFailureKind,
    HistoryHeader,
)


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


@pytest.mark.parametrize(
    ("code", "failure_kind", "expected_status"),
    [
        ("EXECUTION_UNAVAILABLE", None, 404),
        ("EXECUTION_SUBSCRIBER_LIMIT", None, 429),
        (
            "EXECUTION_UNAVAILABLE",
            HistoryFailureKind.EXECUTION_RUNTIME_UNAVAILABLE,
            503,
        ),
        ("HISTORY_RESULT_NOT_SAVABLE", None, 422),
        (
            "HISTORY_RESULT_NOT_SAVABLE",
            HistoryFailureKind.ANALYSIS_ALREADY_COMPLETED,
            409,
        ),
        ("UNRECOGNIZED_ERROR", None, 500),
        ("EXECUTION_UNAVAILABLE", "UNRECOGNIZED_FAILURE", 500),
    ],
)
def test_history_error_http_status_is_mapped_from_code_and_failure_kind(
    code, failure_kind, expected_status
):
    class RaisingHistoryApplication:
        def header(self, *_args):
            raise HistoryError(
                code,
                "受控错误",
                failure_kind=failure_kind,
            )

    app = create_app(
        service=SimpleNamespace(),
        identity_provider=Provider(),
        policy_store=Policy(),
        audit_sink=Audit(),
        history_store=Store(),
        history_runtime=SimpleNamespace(check=lambda: None),
    )
    with TestClient(app) as client:
        app.state.history_application = RaisingHistoryApplication()
        response = client.get("/api/v1/histories/81fc7ae0-e7c2-408c-bc62-28c2e506bf78")

    assert response.status_code == expected_status, response.text
    assert response.json()["error_code"] == code
    assert "failure_kind" not in response.json()


def test_persisted_context_error_keeps_error_code_http_mapping():
    history_id = "81fc7ae0-e7c2-408c-bc62-28c2e506bf78"

    class HistoryApplication:
        def submit_query(self, *_args, **_kwargs):
            return SimpleNamespace(
                id="turn-1",
                public_error={
                    "request_id": "request-1",
                    "error_code": "CONTEXT_ERROR",
                    "error_message": "上下文不可用",
                },
            )

    app = create_app(
        service=SimpleNamespace(),
        identity_provider=Provider(),
        policy_store=Policy(),
        audit_sink=Audit(),
        history_store=Store(),
        history_runtime=SimpleNamespace(check=lambda: None),
    )
    with TestClient(app) as client:
        app.state.history_application = HistoryApplication()
        response = client.post(
            f"/api/v1/histories/{history_id}/turns",
            json={
                "question": "销售额",
                "operation_id": "6cc90b65-f9c2-4f92-9f7f-f9c60a9f8970",
                "expected_context_revision": 0,
            },
        )

    assert response.status_code == 503, response.text
    assert response.json()["error_code"] == "CONTEXT_ERROR"
