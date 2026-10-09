import subprocess
import sys
from unittest.mock import Mock

import pytest

from scripts.local_operations_status import read_status
from src.bootstrap.operations import ObservedModel, ProcessReadinessProbe
from src.bootstrap.operations_socket import OperationsSocket
from src.query_api.operations import DEPENDENCIES, OperationsState


def test_readiness_probe_import_does_not_load_http_application():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; from src.bootstrap.operations import ProcessReadinessProbe; "
                "assert 'src.query_api.app' not in sys.modules, 'HTTP application loaded by lightweight probe'"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_query_api_public_exports_keep_the_existing_app_identity():
    from src.query_api import QueryService, create_app
    from src.query_api.app import QueryService as DirectQueryService
    from src.query_api.app import create_app as direct_create_app

    assert QueryService is DirectQueryService
    assert create_app is direct_create_app


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
    server = OperationsSocket(dict, path=path)
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


def test_readiness_reports_qdrant_outage_as_qdrant_not_asset_failure(monkeypatch):
    from dataclasses import dataclass
    from pathlib import Path
    from types import SimpleNamespace

    from scripts import local_release
    from src.bootstrap import readiness
    from src.chatbi_control import database as control_database
    from src.online_query.database import PsycopgQueryExecutor
    from src.online_query.retrieval import rag_runtime
    from src.rag_offline import build, config, qdrant_store

    @dataclass(frozen=True)
    class FakeBuildConfig:
        output_dir: Path = Path("/isolated/rag")
        qdrant_timeout_seconds: int = 5
        qdrant_url: str = "http://qdrant:6333"
        qdrant_path: Path | None = None
        qdrant_api_key: str | None = None

        @classmethod
        def from_environment(cls):
            return cls()

    class FakeControlConfig:
        @classmethod
        def from_environment(cls, *, require_migrator):
            assert require_migrator is False
            return cls()

    monkeypatch.setenv("RAG_ONLINE_RETRIEVAL_ENABLED", "true")
    monkeypatch.setenv("CHATBI_LOCAL_OPERATIONS_ENABLED", "true")
    monkeypatch.setattr(control_database, "ControlDatabaseConfig", FakeControlConfig)
    monkeypatch.setattr(
        control_database,
        "create_control_engine",
        lambda _config: SimpleNamespace(dispose=lambda: None),
    )
    monkeypatch.setattr(readiness, "verify_control_schema", lambda _engine: None)
    monkeypatch.setattr(
        PsycopgQueryExecutor,
        "from_env",
        lambda: SimpleNamespace(verify_structure_metadata=lambda: None),
    )
    monkeypatch.setattr(config, "OfflineBuildConfig", FakeBuildConfig)
    published = object()
    monkeypatch.setattr(build, "load_published_asset", lambda _path: published)
    monkeypatch.setattr(rag_runtime, "_validate_manifest", lambda *_args: None)
    monkeypatch.setattr(rag_runtime, "_validate_provenance", lambda *_args: None)

    def unavailable_qdrant(**_kwargs):
        raise OSError("isolated Qdrant is unavailable")

    monkeypatch.setattr(
        qdrant_store.QdrantAssetStore, "connect", staticmethod(unavailable_qdrant)
    )
    monkeypatch.setattr(
        local_release,
        "verify_runtime",
        lambda _environment: (_ for _ in ()).throw(
            RuntimeError("full startup gate includes unrelated dependencies")
        ),
    )

    result = readiness.probe_dependencies()

    assert result == {
        "control_database": "ready",
        "business_database": "ready",
        "qdrant": "not_ready",
        "assets": "ready",
    }
