"""执行额度覆盖 API 受理到后台 worker 的整个生命周期。"""

from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from time import monotonic, sleep
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.online_query.contracts import ExecutionStopReason
from src.query_api.execution_runtime import (
    ExecutionCapacityExceeded,
    ExecutionRuntime,
    ExecutionRuntimeClosed,
)


class Lease:
    def __init__(self, release=None):
        self.released = False
        self._release = release

    def release(self):
        if self.released:
            return
        self.released = True
        if self._release is not None:
            self._release()


class HistoryRuntime:
    def __init__(self):
        self.leases = {}

    def reserve(self, history_id):
        if history_id in self.leases:
            raise RuntimeError("history busy")
        lease = Lease(lambda: self.leases.pop(history_id, None))
        self.leases[history_id] = lease
        return lease


class AnalysisGuard:
    def __init__(self):
        self.leases = {}

    def reserve(self, auth, run_id):
        key = (auth, run_id)
        if key in self.leases:
            raise RuntimeError("analysis busy")
        lease = Lease(lambda: self.leases.pop(key, None))
        self.leases[key] = lease
        return lease


def test_quota_stays_reserved_until_worker_finishes_and_releases_history():
    histories = HistoryRuntime()
    runtime = ExecutionRuntime(
        histories, AnalysisGuard(), max_per_user=1, max_total=2
    )
    entered, finish = Event(), Event()
    first = runtime.reserve(7, "history-1")
    future = runtime.submit(first, lambda: (entered.set(), finish.wait(3)))
    assert entered.wait(2)

    with pytest.raises(ExecutionCapacityExceeded) as per_user:
        runtime.reserve(7, "history-2")
    assert per_user.value.scope == "user"
    with pytest.raises(RuntimeError, match="history busy"):
        histories.reserve("history-1")

    finish.set()
    future.result(timeout=3)
    assert first.released
    assert histories.leases == {}
    second = runtime.reserve(7, "history-2")
    second.release()
    runtime.close()


def test_process_quota_is_shared_across_query_and_analysis_reservations():
    histories = HistoryRuntime()
    analysis = AnalysisGuard()
    runtime = ExecutionRuntime(histories, analysis, max_per_user=1, max_total=1)
    query = runtime.reserve(1, "query-history")

    with pytest.raises(ExecutionCapacityExceeded) as process_limit:
        runtime.reserve(2, "analysis-history", auth="owner", analysis_run_id="run")
    assert process_limit.value.scope == "process"
    assert analysis.leases == {}

    query.release()
    accepted = runtime.reserve(2, "analysis-history", auth="owner", analysis_run_id="run")
    assert len(analysis.leases) == 1
    accepted.release()
    assert analysis.leases == {}
    runtime.close()


def test_analysis_guard_conflict_rolls_back_reserved_history_and_user_capacity():
    histories = HistoryRuntime()
    analysis = AnalysisGuard()
    analysis.leases[("owner", "run")] = Lease()
    runtime = ExecutionRuntime(histories, analysis, max_per_user=1, max_total=1)

    with pytest.raises(RuntimeError, match="analysis busy"):
        runtime.reserve(3, "history", auth="owner", analysis_run_id="run")
    assert histories.leases == {}

    # Failed lease acquisition must not strand the account or process quota.
    del analysis.leases[("owner", "run")]
    accepted = runtime.reserve(3, "history", auth="owner", analysis_run_id="run")
    accepted.release()
    runtime.close()


def test_close_stops_new_admissions_and_drains_an_active_worker():
    runtime = ExecutionRuntime(HistoryRuntime(), AnalysisGuard(), max_per_user=1, max_total=1)
    lease = runtime.reserve(1, "history")
    started, finish, closed = Event(), Event(), Event()
    future = runtime.submit(lease, lambda: (started.set(), finish.wait(3)))
    assert started.wait(2)

    closer = Thread(target=lambda: (runtime.close(), closed.set()))
    closer.start()
    deadline = monotonic() + 2
    while runtime.accepting and monotonic() < deadline:
        sleep(0.005)
    assert not runtime.accepting
    assert not closed.is_set()
    with pytest.raises(ExecutionRuntimeClosed):
        runtime.reserve(2, "late-history")

    finish.set()
    future.result(timeout=3)
    closer.join(timeout=3)
    assert closed.is_set()


def test_same_operation_guard_serializes_replays_but_releases_its_key():
    runtime = ExecutionRuntime(HistoryRuntime(), AnalysisGuard())
    entered, release = Event(), Event()
    completed = Event()

    def first():
        with runtime.serialize_operation(12, "op-1"):
            entered.set()
            assert release.wait(2)

    def second():
        with runtime.serialize_operation(12, "op-1"):
            completed.set()

    one = Thread(target=first)
    two = Thread(target=second)
    one.start()
    assert entered.wait(2)
    two.start()
    assert not completed.wait(0.05)
    release.set()
    one.join(timeout=2)
    two.join(timeout=2)

    assert completed.is_set()
    assert runtime._operation_locks == {}
    runtime.close()


def _execution(deadline, *, status="running", stop_reason=None):
    now = datetime(2026, 10, 5, tzinfo=UTC)
    return SimpleNamespace(
        id=str(uuid4()),
        history_id=str(uuid4()),
        turn_id=str(uuid4()),
        operation_id=str(uuid4()),
        mode="query",
        operation_kind="query",
        status=status,
        stop_reason=stop_reason,
        created_at=now,
        started_at=now,
        deadline_at=deadline,
        stop_requested_at=None,
        finished_at=None,
        public_error=None,
    )


def test_deadline_monitor_persists_stop_then_signals_stopping_snapshot():
    now = datetime(2026, 10, 5, tzinfo=UTC)
    monotonic_now = [100.0]
    persisted = []

    def persist(reason):
        persisted.append(reason)
        return SimpleNamespace(status="stopping", stop_reason=reason)

    runtime = ExecutionRuntime(
        HistoryRuntime(),
        None,
        wall_clock=lambda: now,
        monotonic_clock=lambda: monotonic_now[0],
        monitor_interval=60,
    )
    lease = runtime.reserve(21, "deadline-history")
    execution = _execution(now + timedelta(seconds=5))
    runtime.attach_progress(lease, execution)
    control = runtime.bind_stop_control(
        lease, execution, lease._event_channel, persist_stop=persist, authorize=lambda: None
    )
    try:
        runtime.monitor_once()
        assert not control.stopped
        monotonic_now[0] = 105.0
        runtime.monitor_once()

        assert persisted == [ExecutionStopReason.DEADLINE_EXCEEDED.value]
        assert control.stopped
        subscription = runtime.subscribe(execution.id)
        assert subscription.snapshot["payload"]["status"] == "stopping"
        assert subscription.snapshot["payload"]["stop_reason"] == "deadline_exceeded"
        subscription.close()
    finally:
        lease.release()
        runtime.close()


def test_authorization_loss_monitor_fails_closed_and_keeps_worker_lease_until_return():
    class PermissionLost(Exception):
        status = 403

    now = datetime(2026, 10, 5, tzinfo=UTC)
    persisted = []
    durable_reason = [None]
    runtime = ExecutionRuntime(
        HistoryRuntime(),
        None,
        wall_clock=lambda: now,
        monotonic_clock=lambda: 1.0,
        monitor_interval=60,
    )
    lease = runtime.reserve(22, "auth-history")
    execution = _execution(now + timedelta(minutes=3))
    progress = runtime.attach_progress(lease, execution)
    control = runtime.bind_stop_control(
        lease,
        execution,
        progress,
        persist_stop=lambda reason: _persist_first_stop(
            persisted, durable_reason, reason
        ),
        authorize=lambda: (_ for _ in ()).throw(PermissionLost()),
    )
    entered, leave_downstream, cancelled = Event(), Event(), Event()

    def work():
        with control.register_database_cancel(cancelled.set):
            entered.set()
            assert leave_downstream.wait(3)

    future = runtime.submit(lease, work)
    try:
        assert entered.wait(2)
        runtime.monitor_once()
        assert persisted == [ExecutionStopReason.AUTHORIZATION_REVOKED.value]
        assert cancelled.wait(2)
        assert runtime.active_total == 1
        assert not lease.released
        assert runtime.request_stop(execution.id, "user_cancelled").stop_reason == "authorization_revoked"

        leave_downstream.set()
        future.result(timeout=3)
        assert lease.released
        assert runtime.active_total == 0
    finally:
        leave_downstream.set()
        runtime.close()


def _persist_first_stop(calls, durable_reason, reason):
    calls.append(reason)
    if durable_reason[0] is None:
        durable_reason[0] = reason
    return SimpleNamespace(status="stopping", stop_reason=durable_reason[0])
