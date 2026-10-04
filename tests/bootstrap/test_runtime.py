"""运行资源装配的安全门禁与获取失败释放。"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from src.bootstrap import analysis, readiness, runtime
from src.bootstrap.lifecycle import register_cleanup
from src.chatbi_control.database import ControlDatabaseMigrationError
from src.query_api.app import create_app


@pytest.fixture
def runtime_resources(monkeypatch):
    monkeypatch.setenv("CHATBI_ENV", "development")
    monkeypatch.setenv(
        "CHATBI_ADMIN_SECRET_KEY", "test-admin-secret-32-characters-long"
    )
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_DB", "chatbi_mvp")
    monkeypatch.setenv("POSTGRES_APP_USER", "chatbi_app")
    monkeypatch.setenv("POSTGRES_APP_PASSWORD", "test-app-password")
    monkeypatch.setenv("POSTGRES_CONTROL_DB", "chatbi_control")
    monkeypatch.setenv("POSTGRES_CONTROL_APP_USER", "chatbi_control_user")
    monkeypatch.setenv("POSTGRES_CONTROL_APP_PASSWORD", "test-control-password")
    monkeypatch.setenv("RAG_ONLINE_RETRIEVAL_ENABLED", "true")
    monkeypatch.delenv("CHATBI_IDENTITY_PROVIDER", raising=False)
    monkeypatch.delenv("CHATBI_IDENTITY_SUBJECT_ID", raising=False)
    monkeypatch.delenv("CHATBI_AUTH_POLICY_FILE", raising=False)
    monkeypatch.setattr(runtime, "load_local_environment", lambda: None)
    recorder = Mock()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    engine.dispose = Mock(wraps=engine.dispose)
    rag = Mock()
    analysis_application = Mock()
    monkeypatch.setattr(runtime, "create_trace_recorder", lambda: recorder)
    monkeypatch.setattr(runtime, "create_control_engine", lambda _: engine)
    monkeypatch.setattr(runtime, "HistoryRuntime", lambda *_: Mock())
    monkeypatch.setattr(runtime.RagRuntime, "from_environment", lambda: rag)
    monkeypatch.setattr(
        runtime, "build_analysis_application", lambda *_, **__: analysis_application
    )
    monkeypatch.setattr(readiness, "verify_control_schema", lambda _: None)
    return recorder, engine, rag, analysis_application


def test_production_checks_live_catalog_before_serving_and_releases_all(
    monkeypatch, runtime_resources
):
    monkeypatch.setenv("CHATBI_ENV", "production")
    recorder, engine, rag, application = runtime_resources
    app = create_app(runtime_factory=runtime.create_runtime)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        callback = rag.verify_production_ready.call_args.args[0]
        assert callback.__self__.__class__.__name__ == "PsycopgQueryExecutor"
    application.close.assert_called_once()
    rag.close.assert_called_once()
    engine.dispose.assert_called_once()
    recorder.shutdown.assert_called_once()


def test_control_schema_failure_refuses_startup_and_releases_resources(
    monkeypatch, runtime_resources
):
    recorder, engine, rag, application = runtime_resources
    check = Mock(side_effect=ControlDatabaseMigrationError("test missing checkpoint"))
    monkeypatch.setattr(readiness, "verify_control_schema", check)
    with pytest.raises(ControlDatabaseMigrationError, match="missing checkpoint"):
        with TestClient(create_app(runtime_factory=runtime.create_runtime)):
            pass
    application.close.assert_not_called()
    rag.close.assert_called_once()
    engine.dispose.assert_called_once()
    recorder.shutdown.assert_called_once()


def test_production_rag_failure_is_preserved_when_cleanup_fails(
    monkeypatch, runtime_resources, caplog
):
    monkeypatch.setenv("CHATBI_ENV", "production")
    recorder, engine, rag, _ = runtime_resources
    rag.verify_production_ready.side_effect = RuntimeError("test inconsistent asset")
    rag.close.side_effect = RuntimeError("sensitive-cleanup-text")
    with pytest.raises(RuntimeError, match="inconsistent asset"):
        with TestClient(create_app(runtime_factory=runtime.create_runtime)):
            pass
    engine.dispose.assert_called_once()
    recorder.shutdown.assert_called_once()
    assert "sensitive-cleanup-text" not in caplog.text


def test_production_rejects_disabled_rag(monkeypatch, runtime_resources):
    monkeypatch.setenv("CHATBI_ENV", "production")
    monkeypatch.setenv("RAG_ONLINE_RETRIEVAL_ENABLED", "false")
    with pytest.raises(RuntimeError, match="必须启用在线 RAG"):
        with TestClient(create_app(runtime_factory=runtime.create_runtime)):
            pass


def test_development_does_not_preload_rag(runtime_resources):
    _, _, rag, _ = runtime_resources
    with TestClient(create_app(runtime_factory=runtime.create_runtime)):
        rag.verify_production_ready.assert_not_called()
        rag.get_snapshot.assert_not_called()


def test_partial_assembly_closes_sync_and_async_http_clients(
    monkeypatch, runtime_resources
):
    recorder, engine, _, _ = runtime_resources
    sync_http = Mock()
    async_http = Mock(aclose=AsyncMock())
    monkeypatch.setattr(runtime, "DefaultHttpxClient", lambda: sync_http)
    monkeypatch.setattr(runtime, "DefaultAsyncHttpxClient", lambda: async_http)
    monkeypatch.setattr(
        runtime.PsycopgQueryExecutor,
        "from_env",
        Mock(side_effect=RuntimeError("test executor config failure")),
    )
    with pytest.raises(RuntimeError, match="executor config failure"):
        with TestClient(create_app(runtime_factory=runtime.create_runtime)):
            pass
    sync_http.close.assert_called_once()
    async_http.aclose.assert_awaited_once()
    engine.dispose.assert_called_once()
    recorder.shutdown.assert_called_once()


def test_missing_admin_secret_fails_before_acquiring_resources(
    monkeypatch, runtime_resources
):
    monkeypatch.delenv("CHATBI_ADMIN_SECRET_KEY")
    recorder, engine, _, _ = runtime_resources
    with pytest.raises(RuntimeError, match="必须显式设置"):
        with TestClient(create_app(runtime_factory=runtime.create_runtime)):
            pass
    engine.dispose.assert_not_called()
    recorder.shutdown.assert_not_called()


def test_analysis_builder_releases_engine_when_pool_creation_fails(monkeypatch):
    engine = Mock()
    config = Mock()
    config.app_connection_kwargs.return_value = {"host": "127.0.0.1"}
    monkeypatch.setattr(analysis, "_build_chat_model", Mock())
    monkeypatch.setattr(
        analysis.ControlDatabaseConfig, "from_environment", lambda *_, **__: config
    )
    monkeypatch.setattr(analysis, "create_control_engine", lambda _: engine)
    monkeypatch.setattr(
        analysis, "ConnectionPool", Mock(side_effect=RuntimeError("test pool failure"))
    )
    with pytest.raises(RuntimeError, match="pool failure"):
        analysis.build_analysis_application(Mock())
    engine.dispose.assert_called_once()


def test_analysis_builder_releases_pool_and_engine_when_application_fails(monkeypatch):
    engine = Mock()
    pool = Mock()
    config = Mock()
    config.app_connection_kwargs.return_value = {"host": "127.0.0.1"}
    monkeypatch.setattr(analysis, "_build_chat_model", Mock())
    monkeypatch.setattr(
        analysis.ControlDatabaseConfig, "from_environment", lambda *_, **__: config
    )
    monkeypatch.setattr(analysis, "create_control_engine", lambda _: engine)
    monkeypatch.setattr(analysis, "ConnectionPool", lambda *_, **__: pool)
    monkeypatch.setattr(
        analysis,
        "BusinessAnalysisApplication",
        Mock(side_effect=RuntimeError("test graph failure")),
    )
    with pytest.raises(RuntimeError, match="graph failure"):
        analysis.build_analysis_application(Mock())
    pool.close.assert_called_once()
    engine.dispose.assert_called_once()


def test_cleanup_failure_continues_and_repeated_close_is_safe(caplog):
    first = Mock()
    failing = Mock(side_effect=RuntimeError("sensitive-cleanup-text"))
    stack = ExitStack()
    register_cleanup(stack, "first", first)
    register_cleanup(stack, "failing", failing)
    stack.close()
    stack.close()
    first.assert_called_once()
    failing.assert_called_once()
    assert "sensitive-cleanup-text" not in caplog.text
