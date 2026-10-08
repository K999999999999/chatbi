from threading import Event, Thread
from unittest.mock import Mock

import pytest

from src.online_query.contracts import ExecutionStopped, QueryErrorCode
from src.query_api.admission import (
    AdmissionRejected,
    SynchronousExecutionControl,
    admit,
)
from src.query_api.execution_runtime import ExecutionRuntime
from tests.operations_support import ready_operations
from types import SimpleNamespace


def test_deadline_cancels_database_without_releasing_a_live_work_lease():
    runtime = ExecutionRuntime(None, None)
    auth = SimpleNamespace(user_id=11)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                operations=ready_operations(), execution_runtime=runtime
            )
        )
    )
    started, finish, cancelled = Event(), Event(), Event()
    errors = []

    def work():
        try:
            with admit(request, auth, "req", seconds=0.05) as control:
                with control.register_database_cancel(cancelled.set):
                    started.set()
                    assert finish.wait(3)
                    control.checkpoint()
        except ExecutionStopped:
            errors.append("deadline")

    thread = Thread(target=work)
    thread.start()
    try:
        assert started.wait(2)
        assert cancelled.wait(2)
        assert runtime.active_total == 1
        with pytest.raises(AdmissionRejected) as busy:
            with admit(request, auth, "second", seconds=180):
                raise AssertionError("busy work must not enter")
        assert busy.value.result.error_code == QueryErrorCode.EXECUTION_LIMIT_REACHED
    finally:
        finish.set()
        thread.join(timeout=3)
        runtime.close()
    assert errors == ["deadline"]
    assert runtime.active_total == 0


def test_control_checks_total_deadline_without_calling_database():
    clock = [0.0]
    control = SynchronousExecutionControl(180, clock=lambda: clock[0])
    clock[0] = 180
    with pytest.raises(ExecutionStopped):
        control.checkpoint()


def test_unavailable_state_never_reserves_capacity():
    runtime = Mock()
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(operations=None, execution_runtime=runtime)
        )
    )
    with pytest.raises(AdmissionRejected) as error:
        with admit(request, SimpleNamespace(user_id=11), "req", seconds=180):
            raise AssertionError("unready work must not enter")
    assert error.value.result.error_code == QueryErrorCode.SERVICE_NOT_READY
    runtime.reserve_owner.assert_not_called()
