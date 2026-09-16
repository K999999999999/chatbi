"""Evaluation（评测）可运行入口测试。"""

import json
import unittest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from src.online_query.contracts import (
    OnlineRetrievalResult,
    QueryContext,
    QueryData,
    RetrievalRequest,
    RetrievalStatus,
    ValidatedSQL,
)


class _FakeGenerator:
    def __init__(self, sql: str) -> None:
        self._sql = sql
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._sql


class _FakeExecutor:
    def __init__(self, data: QueryData) -> None:
        self._data = data
        self.calls: list[ValidatedSQL] = []

    def execute(self, sql: ValidatedSQL) -> QueryData:
        self.calls.append(sql)
        return self._data


class _FakeRetrievalProvider:
    def __init__(self, context: QueryContext) -> None:
        self._context = context
        self.requests: list[object] = []

    def retrieve(self, request: object) -> OnlineRetrievalResult:
        self.requests.append(request)
        return OnlineRetrievalResult(
            status=RetrievalStatus.SUCCESS,
            query_context=self._context,
        )


class EvaluationEntrypointTest(unittest.TestCase):
    def test_runs_same_online_service_and_writes_report(self) -> None:
        from src.evaluation.__main__ import run_cli

        with TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path = root / "cases.json"
            sql = "SELECT t.value FROM mart_sales.test_table AS t;"
            cases_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "S01",
                            "schema_name": "mart_sales",
                            "category": "simple",
                            "question": "测试问题",
                            "description": "测试",
                            "expected_sql": sql,
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            context_file = root / "context.json"
            context_file.write_text("[]", encoding="utf-8")
            output_dir = root / "reports"
            context = QueryContext(
                prompt_context="{}",
                allowed_tables=frozenset({"mart_sales.test_table"}),
                allowed_columns={
                    "mart_sales.test_table": frozenset({"value"})
                },
            )
            data = QueryData(
                columns=("value",),
                rows=((1,),),
                truncated=False,
            )
            generator = _FakeGenerator(sql)
            executor = _FakeExecutor(data)
            stdout = StringIO()
            stderr = StringIO()

            exit_code = run_cli(
                [
                    "--cases",
                    str(cases_path),
                    "--output-dir",
                    str(output_dir),
                ],
                environ={"LLM_MODEL": "test-model"},
                context_loader=lambda: context,
                generator_factory=lambda environ: generator,
                executor_factory=lambda environ: executor,
                git_state_reader=lambda project_root: ("abcdef123456", False),
                context_paths={"context": context_file},
                stdout=stdout,
                stderr=stderr,
            )

            reports = list(output_dir.glob("*.json"))
            summaries = list(output_dir.glob("*.md"))
            report = json.loads(reports[0].read_text(encoding="utf-8"))
            summary_report = summaries[0].read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(len(reports), 1)
        self.assertEqual(len(summaries), 1)
        self.assertEqual(report["summary"]["execution_accuracy"], 1.0)
        self.assertEqual(report["cases"][0]["status"], "PASS")
        self.assertIn("本次共评测 1 条：成功 1 条", summary_report)
        self.assertIn("本次未执行自动基线比较", summary_report)
        self.assertEqual(len(generator.prompts), 1)
        self.assertEqual(len(executor.calls), 2)
        self.assertIn("Execution Accuracy: 100.00%", stdout.getvalue())
        self.assertIn("Summary Report:", stdout.getvalue())

    def test_online_retrieval_mode_injects_provider(self) -> None:
        from src.evaluation.__main__ import run_cli

        with TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path, context_file, context, sql = self._files(root)
            output_dir = root / "reports"
            data = QueryData(
                columns=("value",),
                rows=((1,),),
                truncated=False,
            )
            provider = _FakeRetrievalProvider(context)

            exit_code = run_cli(
                [
                    "--cases",
                    str(cases_path),
                    "--output-dir",
                    str(output_dir),
                    "--online-retrieval",
                ],
                environ={
                    "LLM_MODEL": "test-model",
                    "RAG_ONLINE_RETRIEVAL_ENABLED": "true",
                },
                context_loader=lambda: context,
                generator_factory=lambda environ: _FakeGenerator(sql),
                executor_factory=lambda environ: _FakeExecutor(data),
                retrieval_factory=lambda: provider,
                git_state_reader=lambda project_root: ("abcdef123456", False),
                context_paths={"context": context_file},
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(provider.requests), 1)
        self.assertIsInstance(provider.requests[0], RetrievalRequest)

    def test_returns_nonzero_when_evaluation_has_failed_case(self) -> None:
        from src.evaluation.__main__ import run_cli

        with TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path, context_file, context, _ = self._files(root)
            output_dir = root / "reports"
            data = QueryData(
                columns=("value",),
                rows=((1,),),
                truncated=False,
            )
            stdout = StringIO()

            exit_code = run_cli(
                [
                    "--cases",
                    str(cases_path),
                    "--output-dir",
                    str(output_dir),
                ],
                environ={"LLM_MODEL": "test-model"},
                context_loader=lambda: context,
                generator_factory=lambda environ: _FakeGenerator("CANNOT_ANSWER"),
                executor_factory=lambda environ: _FakeExecutor(data),
                git_state_reader=lambda project_root: ("abcdef123456", False),
                context_paths={"context": context_file},
                stdout=stdout,
                stderr=StringIO(),
            )

            report_path = next(output_dir.glob("*.json"))
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(report["summary"]["passed"], 0)
        self.assertEqual(report["summary"]["failed"], 1)
        self.assertIn("Execution Accuracy: 0.00%", stdout.getvalue())

    def test_returns_nonzero_when_evaluation_has_invalid_case(self) -> None:
        from src.evaluation.__main__ import run_cli

        with TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path, context_file, context, sql = self._files(root)
            records = json.loads(cases_path.read_text(encoding="utf-8"))
            del records[0]["description"]
            cases_path.write_text(
                json.dumps(records),
                encoding="utf-8",
            )
            output_dir = root / "reports"
            stdout = StringIO()

            exit_code = run_cli(
                [
                    "--cases",
                    str(cases_path),
                    "--output-dir",
                    str(output_dir),
                ],
                environ={"LLM_MODEL": "test-model"},
                context_loader=lambda: context,
                generator_factory=lambda environ: _FakeGenerator(sql),
                executor_factory=lambda environ: _FakeExecutor(
                    QueryData(
                        columns=("value",),
                        rows=((1,),),
                        truncated=False,
                    )
                ),
                git_state_reader=lambda project_root: ("abcdef123456", False),
                context_paths={"context": context_file},
                stdout=stdout,
                stderr=StringIO(),
            )

            report_path = next(output_dir.glob("*.json"))
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertEqual(report["summary"]["invalid_cases"], 1)
        self.assertIn("Execution Accuracy: N/A", stdout.getvalue())

    def test_loads_explicit_baseline(self) -> None:
        from src.evaluation.__main__ import run_cli

        with TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path, context_file, context, sql = self._files(root)
            output_dir = root / "reports"
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "metadata": {
                            "test_set_hash": "different",
                            "reference_result_hash": "different",
                        },
                        "cases": [{"case_id": "S01", "status": "PASS"}],
                    }
                ),
                encoding="utf-8",
            )
            data = QueryData(
                columns=("value",),
                rows=((1,),),
                truncated=False,
            )

            exit_code = run_cli(
                [
                    "--cases",
                    str(cases_path),
                    "--output-dir",
                    str(output_dir),
                    "--baseline",
                    str(baseline),
                ],
                environ={"LLM_MODEL": "test-model"},
                context_loader=lambda: context,
                generator_factory=lambda environ: _FakeGenerator(sql),
                executor_factory=lambda environ: _FakeExecutor(data),
                git_state_reader=lambda project_root: ("abcdef123456", False),
                context_paths={"context": context_file},
                stdout=StringIO(),
                stderr=StringIO(),
            )

            report_path = next(output_dir.glob("*.json"))
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertFalse(report["baseline_comparison"]["comparable"])

    def test_returns_controlled_error_without_leaking_secret(self) -> None:
        from src.evaluation.__main__ import run_cli

        stderr = StringIO()
        exit_code = run_cli(
            ["--cases", "missing.json"],
            environ={
                "LLM_MODEL": "test-model",
                "LLM_API_KEY": "must-not-leak",
            },
            generator_factory=lambda environ: _FakeGenerator("SELECT 1"),
            executor_factory=lambda environ: _FakeExecutor(
                QueryData(columns=("value",), rows=((1,),), truncated=False)
            ),
            git_state_reader=lambda project_root: ("abcdef123456", False),
            stdout=StringIO(),
            stderr=stderr,
        )

        self.assertEqual(exit_code, 1)
        self.assertIn("ERROR:", stderr.getvalue())
        self.assertNotIn("must-not-leak", stderr.getvalue())

    @staticmethod
    def _files(
        root: Path,
    ) -> tuple[Path, Path, QueryContext, str]:
        cases_path = root / "cases.json"
        sql = "SELECT t.value FROM mart_sales.test_table AS t;"
        cases_path.write_text(
            json.dumps(
                [
                    {
                        "id": "S01",
                        "schema_name": "mart_sales",
                        "category": "simple",
                        "question": "测试问题",
                        "description": "测试",
                        "expected_sql": sql,
                    }
                ]
            ),
            encoding="utf-8",
        )
        context_file = root / "context.json"
        context_file.write_text("[]", encoding="utf-8")
        context = QueryContext(
            prompt_context="{}",
            allowed_tables=frozenset({"mart_sales.test_table"}),
            allowed_columns={
                "mart_sales.test_table": frozenset({"value"})
            },
        )
        return cases_path, context_file, context, sql


if __name__ == "__main__":
    unittest.main()
