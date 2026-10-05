"""HTTP execution DTO, read authentication and browser CSRF boundary tests."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from src.authorization.contracts import AuthContext
from src.query_api.app import create_app
from src.query_api.browser import BrowserSettings
from src.query_api.execution import ExecutionView
from src.query_api.execution_contracts import ExecutionRecord
from src.query_api.history_contracts import HistoryHeader, HistoryTurn


class Provider:
    identity_provider = "test"

    def __init__(self):
        self.reads = 0

    def authenticate(self, _provider_input=None):
        return AuthContext(
            "analyst",
            self.identity_provider,
            user_id=11,
            permissions=frozenset({"query.execute"}),
        )

    def authenticate_readonly(self, _provider_input=None):
        self.reads += 1
        return self.authenticate(_provider_input)


class Policy:
    def authorize(self, *_args, **_kwargs):
        return SimpleNamespace(allowed=True, reason_code="AUTHORIZED", policy_version="test")


class Audit:
    def emit(self, _event):
        return None


class ExecutionApplication:
    def __init__(self, view):
        self.view = view
        self.calls = []

    def submit(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.view

    def requery(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.view

    def by_operation(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.view

    def get(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.view


def execution_view(status="running"):
    now = datetime(2026, 10, 5, tzinfo=UTC)
    history_id = str(uuid4())
    turn_id = str(uuid4())
    operation_id = str(uuid4())
    execution = ExecutionRecord(
        id=str(uuid4()),
        history_id=history_id,
        turn_id=turn_id,
        operation_id=operation_id,
        mode="query",
        operation_kind="query",
        status=status,
        stop_reason=None,
        created_at=now,
        started_at=now,
        deadline_at=now,
        finished_at=None,
        public_error=None,
    )
    history = HistoryHeader(
        history_id,
        "query",
        "销售额",
        "销售额",
        now,
        now,
        0,
        1,
        None,
        turn_id,
        None,
    )
    turn = HistoryTurn(
        turn_id,
        history_id,
        1,
        "销售额",
        "accepted",
        "request-id",
        now,
        None,
        None,
    )
    return ExecutionView(execution, history, turn)


def make_app(provider, *, browser_settings=None):
    app = create_app(
        service=SimpleNamespace(),
        identity_provider=provider,
        policy_store=Policy(),
        audit_sink=Audit(),
        browser_settings=browser_settings,
    )
    execution_app = ExecutionApplication(execution_view())
    return app, execution_app


def test_submit_returns_accepted_identity_and_strict_mode_payload():
    provider = Provider()
    app, execution_app = make_app(provider)
    with TestClient(app) as client:
        app.state.execution_application = execution_app
        response = client.post(
            f"/api/v1/histories/{uuid4()}/executions",
            json={
                "mode": "query",
                "question": "销售额",
                "operation_id": str(uuid4()),
                "expected_context_revision": 0,
            },
        )
        invalid = client.post(
            f"/api/v1/histories/{uuid4()}/executions",
            json={
                "mode": "query",
                "question": "销售额",
                "operation_id": str(uuid4()),
                "expected_context_revision": 0,
                "owner_user_id": 11,
            },
        )

    assert response.status_code == 202, response.text
    assert response.json()["execution"]["status"] == "running"
    assert "owner_user_id" not in response.json()["execution"]
    assert invalid.status_code == 400
    assert len(execution_app.calls) == 1


def test_execution_reads_use_readonly_identity_and_return_formal_turn():
    provider = Provider()
    app, execution_app = make_app(provider)
    execution_id = execution_app.view.execution.id
    operation_id = execution_app.view.execution.operation_id
    with TestClient(app) as client:
        app.state.execution_application = execution_app
        by_operation = client.get(
            f"/api/v1/executions/by-operation/{operation_id}"
        )
        by_id = client.get(f"/api/v1/executions/{execution_id}")

    assert by_operation.status_code == 200
    assert by_operation.json()["execution"]["id"] == execution_id
    assert by_id.status_code == 200
    assert by_id.json()["turn"]["status"] == "accepted"
    assert provider.reads == 2


def test_cookie_execution_write_requires_origin_and_browser_marker():
    provider = Provider()
    settings = BrowserSettings("http://127.0.0.1:5173", secure=False)
    app, execution_app = make_app(provider, browser_settings=settings)
    with TestClient(app) as client:
        app.state.execution_application = execution_app
        client.cookies.set("chatbi_web_session", "opaque")
        response = client.post(
            f"/api/v1/histories/{uuid4()}/executions",
            json={
                "mode": "query",
                "question": "销售额",
                "operation_id": str(uuid4()),
                "expected_context_revision": 0,
            },
        )

    assert response.status_code == 403
    assert not execution_app.calls
