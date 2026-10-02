"""Query API 真实服务组装和完整链路测试。"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import TestCase

from fastapi.testclient import TestClient

from src.online_query.context import load_query_context
from src.online_query.contracts import QueryData, ValidatedSQL
from src.online_query.service import OnlineQueryService
from tests.query_api.support import create_test_app


class _FixedSQLGenerator:
    def __init__(self, sql: str) -> None:
        self.sql = sql
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.sql


class _FixedQueryExecutor:
    def __init__(self) -> None:
        self.sqls: list[ValidatedSQL] = []

    def execute(self, sql: ValidatedSQL) -> QueryData:
        self.sqls.append(sql)
        return QueryData(
            columns=("completed_order_count",),
            rows=((7,),),
            truncated=False,
        )


class QueryApiIntegrationTest(TestCase):
    def test_http_query_uses_real_online_query_service_chain(self) -> None:
        root = Path(__file__).resolve().parents[2]
        metrics = json.loads(
            (root / "src" / "semantic" / "metrics.json").read_text(encoding="utf-8")
        )
        sql = metrics[0]["sql_template"]
        generator = _FixedSQLGenerator(sql)
        executor = _FixedQueryExecutor()
        service = OnlineQueryService(
            generator,
            executor,
            context_loader=load_query_context,
        )
        self.assertFalse(hasattr(service, "query"))
        client = TestClient(create_test_app(service))

        response = client.post(
            "/api/v1/query",
            json={"question": "当前已完成订单数是多少？"},
            headers={"X-Request-ID": "api-e2e-test"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["request_id"], "api-e2e-test")
        self.assertEqual(response.json()["row_count"], 1)
        self.assertEqual(response.json()["rows"], [[7]])
        self.assertEqual([item.sql for item in executor.sqls], [sql])
        self.assertEqual(len(generator.prompts), 1)

    def test_main_module_creates_application_without_connecting(self) -> None:
        root = Path(__file__).resolve().parents[2]
        environment = os.environ.copy()
        environment.update(
            {
                "CHATBI_ENV": "development",
                "LLM_API_KEY": "test-key",
                "LLM_BASE_URL": "http://127.0.0.1:1/v1",
                "LLM_MODEL": "test-model",
                "POSTGRES_HOST": "127.0.0.1",
                "POSTGRES_PORT": "5433",
                "POSTGRES_DB": "chatbi_mvp",
                "POSTGRES_APP_USER": "chatbi_app",
                "POSTGRES_APP_PASSWORD": "test-password",
                "POSTGRES_CONTROL_DB": "chatbi_control",
                "POSTGRES_CONTROL_APP_USER": "chatbi_control_user",
                "POSTGRES_CONTROL_APP_PASSWORD": "test-control-password",
                "CHATBI_ADMIN_SECRET_KEY": "test-admin-secret",
                "PYTHONPATH": str(root),
            }
        )
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from fastapi import FastAPI; "
                    "from src.query_api.main import app; "
                    "assert isinstance(app, FastAPI); "
                    "print('API_APP_READY')"
                ),
            ],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("API_APP_READY", result.stdout)

    def test_production_startup_verifies_rag_and_live_database_schema(self) -> None:
        root = Path(__file__).resolve().parents[2]
        environment = _main_environment(root, "production")
        script = """
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from src.bootstrap import readiness, runtime
from src.query_api.main import app
rag = Mock()
engine = create_engine('sqlite+pysqlite:///:memory:')
with (
    patch.object(readiness, 'verify_control_schema'),
    patch.object(runtime, 'create_control_engine', return_value=engine),
    patch.object(runtime.RagRuntime, 'from_environment', return_value=rag),
    patch.object(runtime, 'build_analysis_application', return_value=Mock()),
):
    with TestClient(app) as client:
        assert client.get('/health').status_code == 200
    callback = rag.verify_production_ready.call_args.args[0]
    assert callback.__self__.__class__.__name__ == 'PsycopgQueryExecutor'
print('PRODUCTION_RAG_READY_GATE_VERIFIED')
"""

        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PRODUCTION_RAG_READY_GATE_VERIFIED", result.stdout)

    def test_production_startup_rejects_static_retrieval_mode(self) -> None:
        root = Path(__file__).resolve().parents[2]
        environment = _main_environment(root, "production")
        environment["RAG_ONLINE_RETRIEVAL_ENABLED"] = "false"
        script = """
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from src.bootstrap import readiness, runtime
from src.query_api.main import app
engine = create_engine('sqlite+pysqlite:///:memory:')
with (
    patch.object(readiness, 'verify_control_schema'),
    patch.object(runtime, 'create_control_engine', return_value=engine),
):
    try:
        with TestClient(app):
            pass
    except RuntimeError as exc:
        assert '必须启用在线 RAG' in str(exc)
    else:
        raise AssertionError('production static retrieval unexpectedly started')
print('PRODUCTION_STATIC_RETRIEVAL_REJECTED')
"""

        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PRODUCTION_STATIC_RETRIEVAL_REJECTED", result.stdout)


def _main_environment(root: Path, environment_name: str) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "CHATBI_ENV": environment_name,
            "RAG_ONLINE_RETRIEVAL_ENABLED": "true",
            "LLM_API_KEY": "test-key",
            "LLM_BASE_URL": "http://127.0.0.1:1/v1",
            "LLM_MODEL": "test-model",
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": "5433",
            "POSTGRES_DB": "chatbi_mvp",
            "POSTGRES_APP_USER": "chatbi_app",
            "POSTGRES_APP_PASSWORD": "test-password",
            "POSTGRES_CONTROL_DB": "chatbi_control",
            "POSTGRES_CONTROL_APP_USER": "chatbi_control_user",
            "POSTGRES_CONTROL_APP_PASSWORD": "test-control-password",
            "CHATBI_ADMIN_SECRET_KEY": "test-admin-secret-key-32-characters",
            "PYTHONPATH": str(root),
        }
    )
    return environment
