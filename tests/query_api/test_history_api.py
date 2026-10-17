"""新增API身份、严格参数及公开载荷边界。"""

from contextlib import contextmanager
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
    HistoryTurn,
)
from src.query_api.history_codec import public_snapshot


def _malformed_analysis_snapshot():
    canary = "HISTORY_API_NESTED_SQL_CANARY"
    return {
        "version": 1,
        "kind": "analysis",
        "original_question": "毛利为什么变化？",
        "result": {
            "request_id": "analysis-request",
            "analysis_run_id": "analysis-run",
            "mode": "analysis",
            "report": {"title": "毛利变化", "sql": canary},
            "task_results": [],
        },
    }, canary


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


class CompatWriteStore(Store):
    def __init__(self, kind, requery_kind):
        self.kind = kind
        self.requery_kind = requery_kind
        self.writes = 0

    def header(self, owner, history_id):
        now = datetime(2026, 10, 4, tzinfo=UTC)
        return HistoryHeader(
            history_id,
            self.kind,
            "问题",
            "问题",
            now,
            now,
            0,
            0,
            None,
            None,
            "analysis-run" if self.kind == "analysis" else None,
            analysis_recovery_available=True,
        )

    def begin_attempt(self, *args, before_accept=None):
        before_accept("query")
        self.writes += 1
        raise AssertionError("admission rejection must precede the history write")

    def begin_analysis_attempt(self, *args, before_accept=None):
        before_accept("analysis")
        self.writes += 1
        raise AssertionError("admission rejection must precede the history write")

    def begin_requery(self, *args, before_accept=None):
        before_accept(self.requery_kind)
        self.writes += 1
        raise AssertionError("admission rejection must precede the history write")


class HistoryRuntime:
    epoch = "history-api-test"

    def check(self):
        pass

    @contextmanager
    def executing(self, history_id):
        del history_id
        yield


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


def test_reopening_invalid_analysis_snapshot_returns_controlled_unavailable_error():
    history_id = "81fc7ae0-e7c2-408c-bc62-28c2e506bf78"
    turn_id = "6cc90b65-f9c2-4f92-9f7f-f9c60a9f8970"
    snapshot, canary = _malformed_analysis_snapshot()

    class HistoryApplication:
        def turn(self, *_args):
            return HistoryTurn(
                id=turn_id,
                history_id=history_id,
                ordinal=1,
                question="毛利为什么变化？",
                status="succeeded",
                request_id="analysis-request",
                created_at=datetime(2026, 10, 4, tzinfo=UTC),
                public_error=None,
                snapshot=snapshot,
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
        response = client.get(f"/api/v1/histories/{history_id}/turns/{turn_id}")

    assert response.status_code == 422
    assert response.json()["error_code"] == "HISTORY_SNAPSHOT_UNAVAILABLE"
    assert canary not in response.text


def test_saving_invalid_analysis_snapshot_fails_before_persisting_copy():
    history_id = "81fc7ae0-e7c2-408c-bc62-28c2e506bf78"
    turn_id = "6cc90b65-f9c2-4f92-9f7f-f9c60a9f8970"
    snapshot, canary = _malformed_analysis_snapshot()

    class CorruptStore:
        copies = 0

        def copy_result(self, *_args):
            public_snapshot(snapshot)
            self.copies += 1

    class HistoryApplication:
        store = CorruptStore()

        def authorize(self, *_args):
            return None

    app = create_app(
        service=SimpleNamespace(),
        identity_provider=Provider(),
        policy_store=Policy(),
        audit_sink=Audit(),
        history_store=Store(),
        history_runtime=SimpleNamespace(check=lambda: None),
    )
    with TestClient(app) as client:
        history_application = HistoryApplication()
        app.state.history_application = history_application
        response = client.post(
            "/api/v1/saved-results",
            json={
                "history_id": history_id,
                "turn_id": turn_id,
                "title": "毛利分析",
            },
        )

    assert response.status_code == 422
    assert response.json()["error_code"] == "HISTORY_SNAPSHOT_UNAVAILABLE"
    assert canary not in response.text
    assert history_application.store.copies == 0


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


@pytest.mark.parametrize(
    ("entrypoint", "kind", "requery_kind"),
    [
        ("submit", "query", "query"),
        ("history_requery", "query", "query"),
        ("resume", "analysis", "analysis"),
        ("saved_requery", "analysis", "analysis"),
    ],
)
@pytest.mark.parametrize(
    ("block_reason", "expected_status", "expected_code"),
    [
        ("unready", 503, "SERVICE_NOT_READY"),
        ("full", 429, "EXECUTION_LIMIT_REACHED"),
    ],
)
def test_compat_history_writes_share_readiness_and_capacity_admission(
    entrypoint, kind, requery_kind, block_reason, expected_status, expected_code
):
    history_id = "81fc7ae0-e7c2-408c-bc62-28c2e506bf78"
    saved_id = "8ac78e47-48a2-4f19-81a2-352bd3b29ff0"
    store = CompatWriteStore(kind, requery_kind)
    app = create_app(
        service=SimpleNamespace(),
        identity_provider=Provider(),
        policy_store=Policy(),
        audit_sink=Audit(),
        history_store=store,
        history_runtime=HistoryRuntime(),
    )
    held = None
    with TestClient(app) as client:
        if block_reason == "unready":
            app.state.operations = None
        else:
            held = app.state.execution_runtime.reserve_owner(1)

        try:
            if entrypoint == "submit":
                response = client.post(
                    f"/api/v1/histories/{history_id}/turns",
                    json={
                        "question": "销售额",
                        "operation_id": "6cc90b65-f9c2-4f92-9f7f-f9c60a9f8970",
                        "expected_context_revision": 0,
                    },
                )
            elif entrypoint == "history_requery":
                response = client.post(
                    f"/api/v1/histories/{history_id}/requery",
                    json={"operation_id": "6cc90b65-f9c2-4f92-9f7f-f9c60a9f8970"},
                )
            elif entrypoint == "resume":
                response = client.post(
                    f"/api/v1/histories/{history_id}/resume",
                    json={
                        "operation_id": "6cc90b65-f9c2-4f92-9f7f-f9c60a9f8970",
                        "expected_record_revision": 0,
                    },
                )
            else:
                response = client.post(
                    f"/api/v1/saved-results/{saved_id}/requery",
                    json={"operation_id": "6cc90b65-f9c2-4f92-9f7f-f9c60a9f8970"},
                )
        finally:
            if held is not None:
                held.release()

    assert response.status_code == expected_status, response.text
    assert response.json()["error_code"] == expected_code
    assert store.writes == 0
