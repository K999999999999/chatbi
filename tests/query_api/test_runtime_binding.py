"""通过真实 HTTP Adapter 验证延迟绑定与重复生命周期。"""

from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.authorization import (
    AuthService,
    InMemoryAuditSink,
    StaticAuthorizationPolicyStore,
    StaticIdentityProviderAdapter,
)
from src.online_query.contracts import QuerySuccess
from tests.operations_support import create_app
from src.query_api.runtime import RuntimeDependencies
from tests.operations_support import ready_operations


def test_runtime_factory_rejects_mixed_resource_ownership():
    factory = Mock()
    with pytest.raises(ValueError, match="不能混用"):
        create_app(runtime_factory=factory, admin_engine=Mock())
    factory.assert_not_called()


def test_lifespan_binds_current_service_and_releases_on_each_shutdown():
    entered = []
    released = []

    @contextmanager
    def factory():
        version = len(entered) + 1
        entered.append(version)
        service = Mock()
        service.execute.return_value = QuerySuccess(
            request_id="binding-test",
            sql="SELECT 1",
            columns=("version",),
            rows=((version,),),
            row_count=1,
            truncated=False,
        )
        try:
            yield RuntimeDependencies(
                operations=ready_operations(),
                service=service,
                audit_sink=InMemoryAuditSink(),
                identity_provider=StaticIdentityProviderAdapter(
                    identity_provider="test", subject_id="analyst"
                ),
                policy_store=StaticAuthorizationPolicyStore(
                    allowed_subjects=frozenset({"analyst"}), policy_version="test"
                ),
            )
        finally:
            released.append(version)

    app = create_app(runtime_factory=factory)
    assert entered == []
    with TestClient(app) as client:
        response = client.post("/api/v1/query", json={"question": "测试"})
        assert response.status_code == 200
        assert response.json()["rows"] == [[1]]
    assert app.state.query_service is None
    with TestClient(app) as client:
        response = client.post("/api/v1/query", json={"question": "测试"})
        assert response.json()["rows"] == [[2]]
    assert released == [1, 2]


def test_binding_failure_releases_runtime_and_clears_state():
    released = []

    def failing_analysis(_):
        raise RuntimeError("analysis assembly failed")

    @contextmanager
    def factory():
        try:
            yield RuntimeDependencies(
                operations=ready_operations(),
                service=Mock(),
                analysis_service_factory=failing_analysis,
            )
        finally:
            released.append(True)

    app = create_app(runtime_factory=factory)
    with pytest.raises(RuntimeError, match="analysis assembly failed"), TestClient(app):
        pass
    assert released == [True]
    assert app.state.query_service is None
    assert app.state.analysis_service is None


def test_invalid_execution_runtime_config_closes_direct_analysis_service():
    analysis_service = Mock()
    app = create_app(
        service=Mock(),
        trace_recorder=Mock(),
        history_store=Mock(),
        history_runtime=Mock(),
        analysis_service=analysis_service,
    )

    with (
        patch.dict("os.environ", {"CHATBI_EXECUTION_MAX_TOTAL": "0"}),
        pytest.raises(ValueError, match="正整数"),
        TestClient(app),
    ):
        pass

    analysis_service.close.assert_called_once_with()


def test_sqladmin_mount_uses_new_engine_after_repeated_lifespan():
    engines = []

    @contextmanager
    def factory():
        engine = create_engine("sqlite+pysqlite:///:memory:")
        engines.append(engine)
        sessions = sessionmaker(engine)
        try:
            yield RuntimeDependencies(
                operations=ready_operations(),
                service=Mock(),
                auth_service=AuthService(sessions),
                admin_engine=engine,
                admin_session_factory=sessions,
                admin_secret_key="test-admin-secret",
            )
        finally:
            engine.dispose()

    app = create_app(runtime_factory=factory)
    with TestClient(app) as client:
        assert client.get("/admin/", follow_redirects=False).status_code == 302
        assert app.state.sqladmin_engine is engines[0]
        assert (
            sum(getattr(route, "path", None) == "/admin" for route in app.routes) == 1
        )
    assert not hasattr(app.state, "sqladmin_engine")
    with TestClient(app) as client:
        assert client.get("/admin/", follow_redirects=False).status_code == 302
        assert app.state.sqladmin_engine is engines[1]
        assert (
            sum(getattr(route, "path", None) == "/admin" for route in app.routes) == 1
        )
    assert engines[0] is not engines[1]
