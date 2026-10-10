"""执行 Application 的稳定操作编号与并发重放。"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from time import monotonic
from types import SimpleNamespace
from uuid import uuid4

from src.authorization.contracts import AuthContext
from src.observability.contracts import ErrorType, QuerySource, TraceOutcome
from src.observability.tracing import create_in_memory_recorder
from src.query_api.execution import ExecutionApplication, _trace_result_classification
from src.query_api.execution_contracts import ExecutionRecord
from src.query_api.execution_runtime import ExecutionRuntime
from src.query_api.history_contracts import HistoryError


def test_background_trace_classifies_business_failure_timeout_and_technical_error():
    assert _trace_result_classification("completed", None) == (
        TraceOutcome.SUCCESS,
        None,
        None,
    )
    assert _trace_result_classification("failed", {"error_code": "CANNOT_ANSWER"}) == (
        TraceOutcome.BUSINESS_REJECTION,
        None,
        "CANNOT_ANSWER",
    )
    assert _trace_result_classification("failed", {"error_code": "QUERY_TIMEOUT"}) == (
        TraceOutcome.TIMEOUT,
        ErrorType.TIMEOUT,
        "QUERY_TIMEOUT",
    )
    assert _trace_result_classification("failed", {"error_code": "DATABASE_ERROR"}) == (
        TraceOutcome.TECHNICAL_FAILURE,
        ErrorType.DATABASE,
        "DATABASE_ERROR",
    )


class HistoryLease:
    def __init__(self, runtime, key):
        self.runtime, self.key = runtime, key

    def release(self):
        self.runtime.running.discard(self.key)


class HistoryRuntime:
    epoch = str(uuid4())

    def __init__(self):
        self.running = set()

    def check(self):
        return None

    def reserve(self, history_id):
        if history_id in self.running:
            raise HistoryError("HISTORY_BUSY", "busy", 409)
        self.running.add(history_id)
        return HistoryLease(self, history_id)


class Store:
    def __init__(self, history_id, lookup_entered, allow_lookup):
        self.history_id = history_id
        self.lookup_entered = lookup_entered
        self.allow_lookup = allow_lookup
        self.lookup_count = 0
        self.accept_count = 0
        self.records = {}
        self.execution_id = str(uuid4())
        self.turn_id = str(uuid4())

    def execution_by_operation(self, owner, operation_id, request_hash=None):
        del owner, request_hash
        self.lookup_count += 1
        if self.lookup_count == 1:
            self.lookup_entered.set()
            assert self.allow_lookup.wait(2)
        return self.records.get(operation_id)

    def header(self, owner, history_id):
        del owner
        return SimpleNamespace(
            id=history_id,
            kind="query",
            analysis_run_id=None,
            first_question="销售额",
            last_success_turn_id=None,
            analysis_recovery_available=True,
        )

    def begin_execution_attempt(self, **values):
        self.accept_count += 1
        now = datetime.now(UTC)
        execution = ExecutionRecord(
            id=self.execution_id,
            history_id=self.history_id,
            turn_id=self.turn_id,
            operation_id=values["operation_id"],
            mode="query",
            operation_kind="query",
            status="accepted",
            stop_reason=None,
            created_at=now,
            started_at=None,
            deadline_at=now + timedelta(seconds=180),
            stop_requested_at=None,
            finished_at=None,
            public_error=None,
        )
        turn = SimpleNamespace(question=values["question"], id=self.turn_id)
        accepted = SimpleNamespace(
            created=True,
            execution=execution,
            attempt=SimpleNamespace(token=object(), turn=turn),
        )
        self.records[values["operation_id"]] = execution
        return accepted

    def mark_execution_running(self, owner, execution_id):
        del owner, execution_id

    def execution(self, owner, execution_id):
        del owner
        return next(item for item in self.records.values() if item.id == execution_id)

    def finish_execution_attempt(self, owner, _token, _snapshot, error, execution_id):
        del owner
        for operation_id, record in self.records.items():
            if record.id == execution_id:
                self.records[operation_id] = replace(
                    record,
                    status="failed",
                    finished_at=datetime.now(UTC),
                    public_error=error,
                )
                return
        raise AssertionError("execution should have been accepted")


class HistoryApplication:
    def __init__(self, store, runtime, worker_entered, finish_worker):
        self.store, self.runtime = store, runtime
        self.worker_entered, self.finish_worker = worker_entered, finish_worker

    def authorize(self, *_args, **_kwargs):
        return None

    def header(self, auth, request_id, history_id):
        del auth, request_id
        return self.store.header(None, history_id)

    def turn(self, auth, request_id, history_id, turn_id):
        del auth, request_id, history_id
        return SimpleNamespace(id=turn_id, status="accepted", snapshot=None)

    def _execute_attempt(self, *_args, **_kwargs):
        self.worker_entered.set()
        assert self.finish_worker.wait(2)


def test_concurrent_same_operation_returns_one_accepted_execution():
    history_id = str(uuid4())
    operation_id = str(uuid4())
    lookup_entered, allow_lookup = Event(), Event()
    worker_entered, finish_worker = Event(), Event()
    store = Store(history_id, lookup_entered, allow_lookup)
    history_runtime = HistoryRuntime()
    runtime = ExecutionRuntime(history_runtime, None)
    application = ExecutionApplication(
        HistoryApplication(store, history_runtime, worker_entered, finish_worker),
        runtime,
    )
    auth = AuthContext("analyst", "test", user_id=41)
    results = []
    failures = []

    def submit():
        try:
            results.append(
                application.submit(
                    auth,
                    "request",
                    history_id,
                    operation_id,
                    mode="query",
                    question="销售额",
                    expected_context_revision=0,
                    reauthenticate=lambda: auth,
                )
            )
        except Exception as exc:  # noqa: BLE001 - propagate worker-thread failure to pytest
            failures.append(exc)

    first = Thread(target=submit)
    second = Thread(target=submit)
    first.start()
    assert lookup_entered.wait(2)
    second.start()
    deadline = monotonic() + 2
    while monotonic() < deadline:
        with runtime._condition:
            operation_state = runtime._operation_locks.get((auth.user_id, operation_id))
        if operation_state is not None and operation_state[1] == 2:
            break
        Event().wait(0.001)
    assert operation_state is not None and operation_state[1] == 2
    allow_lookup.set()
    first.join(timeout=2)
    second.join(timeout=2)

    try:
        assert not first.is_alive() and not second.is_alive()
        assert failures == []
        assert len(results) == 2
        assert {result.execution.id for result in results} == {store.execution_id}
        assert store.accept_count == 1
        assert store.lookup_count == 2
        assert worker_entered.wait(2)
        assert runtime.active_total == 1
    finally:
        finish_worker.set()
        runtime.close()


def test_background_execution_has_its_own_linked_trace_root():
    history_id = str(uuid4())
    operation_id = str(uuid4())
    allow_lookup, worker_entered, finish_worker = Event(), Event(), Event()
    allow_lookup.set()
    store = Store(history_id, Event(), allow_lookup)
    history_runtime = HistoryRuntime()
    runtime = ExecutionRuntime(history_runtime, None)
    recorder, exporter = create_in_memory_recorder()
    with recorder.query_trace(QuerySource.HTTP) as request_scope:
        request_trace_id = request_scope.trace_id
        carrier = request_scope.carrier
    application = ExecutionApplication(
        HistoryApplication(store, history_runtime, worker_entered, finish_worker),
        runtime,
        trace_recorder=recorder,
    )
    auth = AuthContext("analyst", "test", user_id=43)

    try:
        application.submit(
            auth,
            "request",
            history_id,
            operation_id,
            mode="query",
            question="销售额",
            expected_context_revision=0,
            reauthenticate=lambda: auth,
            trace_carrier=carrier,
        )
        assert worker_entered.wait(2)
        finish_worker.set()
        deadline = monotonic() + 2
        while monotonic() < deadline:
            roots = [
                span
                for span in exporter.get_finished_spans()
                if span.name == "query.request"
            ]
            if len(roots) >= 2:
                break
            Event().wait(0.001)
        worker_root = next(
            span
            for span in roots
            if span.attributes.get("chatbi.request.source")
            == QuerySource.EXECUTION.value
        )
        assert len(worker_root.links) == 1
        assert worker_root.links[0].context.trace_id == int(request_trace_id, 16)
        assert worker_root.attributes["chatbi.execution.kind"] == "query"
    finally:
        finish_worker.set()
        runtime.close()


def test_dispatch_failure_persists_terminal_state_and_releases_lease():
    history_id = str(uuid4())
    operation_id = str(uuid4())
    allow_lookup = Event()
    allow_lookup.set()
    store = Store(history_id, Event(), allow_lookup)
    history_runtime = HistoryRuntime()
    worker_entered, finish_worker = Event(), Event()
    runtime = ExecutionRuntime(history_runtime, None)

    def reject_submit(_lease, _work):
        raise RuntimeError("executor closed")

    runtime.submit = reject_submit
    application = ExecutionApplication(
        HistoryApplication(store, history_runtime, worker_entered, finish_worker),
        runtime,
    )
    auth = AuthContext("analyst", "test", user_id=42)
    try:
        try:
            application.submit(
                auth,
                "request",
                history_id,
                operation_id,
                mode="query",
                question="销售额",
                expected_context_revision=0,
                reauthenticate=lambda: auth,
            )
        except HistoryError as error:
            assert error.status == 503
            assert error.execution_id == store.execution_id
        else:
            raise AssertionError("dispatch refusal must be visible to the caller")

        persisted = store.execution(42, store.execution_id)
        assert persisted.status == "failed"
        assert persisted.public_error["error_code"] == "EXECUTION_UNAVAILABLE"
        assert runtime.active_total == 0
        assert history_runtime.running == set()
        assert not worker_entered.is_set()
    finally:
        runtime.close()


def test_acceptance_failure_releases_all_reserved_runtime_state():
    history_id = str(uuid4())
    operation_id = str(uuid4())
    allow_lookup = Event()
    allow_lookup.set()
    store = Store(history_id, Event(), allow_lookup)

    def fail_acceptance(**_values):
        raise HistoryError("HISTORY_STORAGE_UNAVAILABLE", "offline", 503)

    store.begin_execution_attempt = fail_acceptance
    history_runtime = HistoryRuntime()
    worker_entered, finish_worker = Event(), Event()
    runtime = ExecutionRuntime(history_runtime, None)
    application = ExecutionApplication(
        HistoryApplication(store, history_runtime, worker_entered, finish_worker),
        runtime,
    )
    auth = AuthContext("analyst", "test", user_id=43)
    try:
        try:
            application.submit(
                auth,
                "request",
                history_id,
                operation_id,
                mode="query",
                question="销售额",
                expected_context_revision=0,
                reauthenticate=lambda: auth,
            )
        except HistoryError as error:
            assert error.code == "HISTORY_STORAGE_UNAVAILABLE"
        else:
            raise AssertionError("storage outage must reject acceptance")

        assert runtime.active_total == 0
        assert history_runtime.running == set()
        assert store.records == {}
    finally:
        runtime.close()
