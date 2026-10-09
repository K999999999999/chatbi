import sys
from unittest.mock import Mock

import pytest

from scripts.local_operations_status import read_status
from src.bootstrap.operations import ObservedModel, ProcessReadinessProbe
from src.bootstrap.operations_socket import OperationsSocket
from src.query_api.operations import DEPENDENCIES, OperationsState


def test_probe_timeout_is_terminated_and_next_probe_can_recover():
    probe = ProcessReadinessProbe(
        command=[sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.1
    )
    assert set(probe().values()) == {"unknown"}
    recovered = ProcessReadinessProbe(
        command=[
            sys.executable,
            "-c",
            "import json; print(json.dumps(dict.fromkeys("
            + repr(DEPENDENCIES)
            + ', "ready")))',
        ]
    )
    assert set(recovered().values()) == {"ready"}


def test_local_socket_reads_live_snapshot_and_removes_only_owned_socket(tmp_path):
    path = str(tmp_path / "status.sock")
    state = OperationsState()
    server = OperationsSocket(lambda: state.snapshot(detailed=True), path=path)
    server.start()
    try:
        assert (tmp_path / "status.sock").stat().st_mode & 0o777 == 0o600
        assert read_status(path)["status"] == "unknown"
        state.record_checks(dict.fromkeys(DEPENDENCIES, "ready"))
        assert read_status(path)["status"] == "ready"
        assert "model" in read_status(path)["details"]
    finally:
        server.close()
    assert not (tmp_path / "status.sock").exists()


def test_observer_counts_actual_model_success_and_failure_without_payloads():
    state = OperationsState()
    model = Mock()
    observed = ObservedModel(model, state.record_model)
    observed.invoke("private question")
    assert state.snapshot(detailed=True)["details"]["model"]["status"] == "success"
    model.invoke.side_effect = RuntimeError("private secret")
    with pytest.raises(RuntimeError):
        observed.invoke("private question")
    status = state.snapshot(detailed=True)
    assert status["details"]["model"]["status"] == "failure"
    assert "private" not in repr(status)


def test_observed_model_forwards_stream_and_records_success_after_completion():
    state = OperationsState()
    model = Mock()
    model.stream.return_value = iter(["private response"])
    observed = ObservedModel(model, state.record_model)

    stream = observed.stream("private question")
    assert next(stream) == "private response"
    assert state.snapshot(detailed=True)["details"]["model"]["status"] == "unknown"
    assert list(stream) == []
    model.stream.assert_called_once_with("private question")

    status = state.snapshot(detailed=True)
    assert status["details"]["model"]["status"] == "success"
    assert "private" not in repr(status)


def test_observed_model_records_stream_iteration_failure_without_payloads():
    state = OperationsState()
    model = Mock()

    def failed_stream(_prompt):
        yield "private partial response"
        raise RuntimeError("private exception")

    model.stream.side_effect = failed_stream
    observed = ObservedModel(model, state.record_model)

    with pytest.raises(RuntimeError, match="private exception"):
        list(observed.stream("private question"))

    status = state.snapshot(detailed=True)
    assert status["details"]["model"]["status"] == "failure"
    assert "private" not in repr(status)


def test_observed_model_reports_unsupported_stream_as_failure():
    state = OperationsState()
    observed = ObservedModel(object(), state.record_model)

    with pytest.raises(TypeError, match="不支持流式调用"):
        observed.stream("private question")

    status = state.snapshot(detailed=True)
    assert status["details"]["model"]["status"] == "failure"
    assert "private" not in repr(status)


def test_observed_model_reports_stream_start_failure_without_payloads():
    state = OperationsState()
    model = Mock()
    model.stream.side_effect = RuntimeError("private exception")
    observed = ObservedModel(model, state.record_model)

    with pytest.raises(RuntimeError, match="private exception"):
        observed.stream("private question")

    status = state.snapshot(detailed=True)
    assert status["details"]["model"]["status"] == "failure"
    assert "private" not in repr(status)


def test_backup_projection_is_bounded_and_does_not_echo_untrusted_fields(tmp_path):
    import json
    from datetime import UTC, datetime
    from src.bootstrap.backup_status import read_backup_status

    path = tmp_path / "backup.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "last_success": datetime.now(UTC).isoformat(),
                "failure_code": "password=private",
                "private": "secret",
            }
        )
    )
    result = read_backup_status(path)
    assert result["overdue"] is False
    assert "private" not in repr(result)
    path.write_text("x" * 4097)
    assert read_backup_status(path)["status"] == "unknown"
    path.unlink()
    path.symlink_to(tmp_path / "missing")
    assert read_backup_status(path)["status"] == "unknown"


def test_status_socket_refuses_unknown_existing_file(tmp_path):
    path = tmp_path / "status.sock"
    path.write_text("user content")
    server = OperationsSocket(lambda: {}, path=path)
    with pytest.raises(RuntimeError):
        server.start()
    server.close()
    assert path.read_text() == "user content"


def test_backup_without_success_still_shows_safe_failure(tmp_path):
    import json
    from src.bootstrap.backup_status import read_backup_status

    path = tmp_path / "backup.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "last_success": None,
                "failure_code": "BACKUP_KEY_UNAVAILABLE",
            }
        )
    )
    assert read_backup_status(path) == {
        "status": "unknown",
        "last_success": None,
        "overdue": True,
        "failure_code": "BACKUP_KEY_UNAVAILABLE",
    }
