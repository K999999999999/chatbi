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
        self.subscription = None
        self.observer_checks = 0

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

    def subscribe(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.view, self.subscription

    def authorize_observer(self, *args, **kwargs):
        self.observer_checks += 1
        return self.view.execution


class EventSubscription:
    def __init__(self, execution_id, history_id, turn_id, events):
        self.snapshot = {
            "version": 1,
            "execution_id": execution_id,
            "history_id": history_id,
            "turn_id": turn_id,
            "sequence": 0,
            "draft_generation": 0,
            "type": "snapshot",
            "payload": {
                "status": "running",
                "stage": None,
                "completed_tasks": 0,
                "total_tasks": None,
                "stop_reason": None,
                "draft_generation": 0,
            },
        }
        self.events = tuple(events)
        self.closed = False

    def read(self, _timeout=None):
        events, self.events = self.events, ()
        return events

    def close(self):
        self.closed = True


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


def test_event_stream_sends_atomic_snapshot_then_events_and_rechecks_permission():
    provider = Provider()
    app, execution_app = make_app(provider)
    execution = execution_app.view.execution
    execution_app.subscription = EventSubscription(
        execution.id,
        execution.history_id,
        execution.turn_id,
        (
            {
                "version": 1,
                "execution_id": execution.id,
                "history_id": execution.history_id,
                "turn_id": execution.turn_id,
                "sequence": 1,
                "draft_generation": 0,
                "type": "progress",
                "payload": {"stage": "query_execution"},
            },
            {
                "version": 1,
                "execution_id": execution.id,
                "history_id": execution.history_id,
                "turn_id": execution.turn_id,
                "sequence": 2,
                "draft_generation": 0,
                "type": "terminal",
                "payload": {"status": "succeeded"},
            },
        ),
    )
    with TestClient(app) as client:
        app.state.execution_application = execution_app
        response = client.get(f"/api/v1/executions/{execution.id}/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-accel-buffering"] == "no"
    assert response.text.index('"type":"snapshot"') < response.text.index('"sequence":1')
    assert '"stage":"query_execution"' in response.text
    assert '"type":"terminal"' in response.text
    assert execution_app.observer_checks == 3
    assert execution_app.subscription.closed


def test_event_stream_closes_with_auth_lost_without_private_snapshot():
    class ExpiringProvider(Provider):
        def authenticate_readonly(self, _provider_input=None):
            self.reads += 1
            auth = self.authenticate(_provider_input)
            if self.reads > 1:
                return AuthContext(
                    "other",
                    self.identity_provider,
                    user_id=12,
                    permissions=frozenset({"query.execute"}),
                )
            return auth

    provider = ExpiringProvider()
    app, execution_app = make_app(provider)
    execution = execution_app.view.execution
    execution_app.subscription = EventSubscription(
        execution.id, execution.history_id, execution.turn_id, ()
    )
    with TestClient(app) as client:
        app.state.execution_application = execution_app
        response = client.get(f"/api/v1/executions/{execution.id}/events")

    assert response.status_code == 200
    assert '"type":"auth_lost"' in response.text
    assert '"type":"snapshot"' not in response.text
    assert '"stage"' not in response.text
    assert execution_app.subscription.closed


def test_event_stream_rechecks_identity_before_heartbeat_after_snapshot():
    class HeartbeatExpiringProvider(Provider):
        def authenticate_readonly(self, _provider_input=None):
            self.reads += 1
            auth = self.authenticate(_provider_input)
            if self.reads > 2:
                return AuthContext(
                    "other",
                    self.identity_provider,
                    user_id=12,
                    permissions=frozenset({"query.execute"}),
                )
            return auth

    provider = HeartbeatExpiringProvider()
    app, execution_app = make_app(provider)
    execution = execution_app.view.execution
    execution_app.subscription = EventSubscription(
        execution.id, execution.history_id, execution.turn_id, ()
    )
    with TestClient(app) as client:
        app.state.execution_application = execution_app
        response = client.get(f"/api/v1/executions/{execution.id}/events")

    assert response.status_code == 200
    assert response.text.count('"type":"snapshot"') == 1
    assert '"type":"auth_lost"' in response.text
    assert response.text.index('"type":"snapshot"') < response.text.index('"type":"auth_lost"')
    assert execution_app.subscription.closed
    assert provider.reads == 3


def test_event_stream_after_channel_cleanup_uses_persisted_terminal_snapshot():
    provider = Provider()
    app, execution_app = make_app(provider)
    execution_app.view = execution_view(status="succeeded")
    execution = execution_app.view.execution
    with TestClient(app) as client:
        app.state.execution_application = execution_app
        response = client.get(f"/api/v1/executions/{execution.id}/events")

    assert response.status_code == 200
    assert '"type":"snapshot"' in response.text
    assert '"status":"succeeded"' in response.text
    assert '"stage":null' in response.text
    assert execution_app.observer_checks == 1


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
