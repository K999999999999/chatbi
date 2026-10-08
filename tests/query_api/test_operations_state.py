from datetime import UTC, datetime

import pytest

from src.query_api.operations import DEPENDENCIES, OperationsState


def test_fault_recovery_and_stale_results_are_distinct_from_liveness():
    clock = [0.0]
    state = OperationsState(clock=lambda: clock[0])
    assert not state.ready
    state.record_checks(dict.fromkeys(DEPENDENCIES, "ready"))
    assert state.ready
    state.record_checks({**dict.fromkeys(DEPENDENCIES, "ready"), "qdrant": "not_ready"})
    assert state.snapshot()["status"] == "not_ready"
    state.record_checks(dict.fromkeys(DEPENDENCIES, "ready"))
    clock[0] = 30
    assert (
        state.snapshot(detailed=True)["details"]["dependencies"]["qdrant"] == "unknown"
    )
    assert not state.ready
    state.record_checks(dict.fromkeys(DEPENDENCIES, "ready"))
    assert state.ready


def test_model_evidence_expires_and_software_failure_does_not_replace_it():
    clock = [0.0]
    wall = datetime(2026, 10, 8, tzinfo=UTC)
    state = OperationsState(clock=lambda: clock[0], wall_clock=lambda: wall)
    state.record_model(True)
    state.record_checks(dict.fromkeys(DEPENDENCIES, "not_ready"))
    assert state.snapshot(detailed=True)["details"]["model"]["status"] == "success"
    state.record_model(False)
    model = state.snapshot(detailed=True)["details"]["model"]
    assert model == {
        "status": "failure",
        "checked_at": wall.isoformat(),
        "failure_code": "MODEL_CALL_FAILED",
    }
    clock[0] = 900
    assert state.snapshot(detailed=True)["details"]["model"]["status"] == "unknown"
    assert "details" not in state.snapshot()


def test_unknown_or_incomplete_probe_fields_cannot_enter_public_state():
    state = OperationsState()
    with pytest.raises(ValueError):
        state.record_checks({"control_database": "password=unsafe"})
    assert not state.ready
