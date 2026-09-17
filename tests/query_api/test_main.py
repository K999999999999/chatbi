"""Query API 真实服务组装和完整链路测试。"""

import json
import os
from pathlib import Path
import subprocess
import sys
from unittest import TestCase

from fastapi.testclient import TestClient

from src.online_query.context import load_query_context
from src.online_query.contracts import QueryData, ValidatedSQL
from src.online_query.service import OnlineQueryService
from src.query_api.app import create_app


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
        client = TestClient(create_app(service))

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

    def test_main_module_assembles_real_dependencies_without_connecting(self) -> None:
        root = Path(__file__).resolve().parents[2]
        environment = os.environ.copy()
        environment.update(
            {
                "LLM_API_KEY": "test-key",
                "LLM_BASE_URL": "http://127.0.0.1:1/v1",
                "LLM_MODEL": "test-model",
                "POSTGRES_HOST": "127.0.0.1",
                "POSTGRES_PORT": "5433",
                "POSTGRES_DB": "chatbi_mvp",
                "POSTGRES_APP_USER": "chatbi_app",
                "POSTGRES_APP_PASSWORD": "test-password",
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
