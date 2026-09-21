"""Evaluation（评测）可运行入口测试。"""

import json
import unittest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.business_analysis.application import BusinessAnalysisSuccess
from src.business_analysis.contracts import AnalysisPlan, AnalysisTask, AnalysisTaskType
from src.business_analysis.execution import TaskResult, TaskStatus
from src.business_analysis.reporting import BusinessAnalysisReport
from src.online_query.contracts import (
    OnlineRetrievalResult,
    QueryContext,
    QueryData,
    RetrievalRequest,
    RetrievalStatus,
    ValidatedSQL,
)
from src.online_query.query_understanding import candidate_from_payload


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


class _FakeAnalysisApplication:
    def __init__(self, result: BusinessAnalysisSuccess) -> None:
        self._result = result

    def analyze(self, question, *, request_id, auth_context):
        del question, request_id, auth_context
        return self._result


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


class _FailingRuntime:
    def __init__(self, message: str) -> None:
        self.message = message
        self.get_snapshot_calls = 0
        self.close_calls = 0

    def get_snapshot(self) -> object:
        self.get_snapshot_calls += 1
        raise RuntimeError(self.message)

    def close(self) -> None:
        self.close_calls += 1


class _SuccessfulRuntime:
    def __init__(self) -> None:
        self.get_snapshot_calls = 0
        self.close_calls = 0

    def get_snapshot(self) -> object:
        self.get_snapshot_calls += 1
        return object()

    def close(self) -> None:
        self.close_calls += 1


class _FakeQueryUnderstanding:
    def understand(self, question: str):
        return candidate_from_payload(
            {
                "query_type": "entity_lookup",
                "subjects": ["测试主题"],
                "metrics": [],
                "dimensions": [],
                "time": None,
                "filters": [],
            }
        )


class _FakeSemanticQueryUnderstanding:
    def understand(self, question: str):
        del question
        return candidate_from_payload(
            {
                "query_type": "metric_analysis",
                "subjects": [],
                "metrics": ["销售额"],
                "dimensions": [],
                "time": None,
                "filters": [],
            }
        )


class EvaluationEntrypointTest(unittest.TestCase):
    def test_business_analysis_mode_writes_layered_report(self) -> None:
        from src.evaluation.__main__ import run_cli

        with TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path = root / "business-analysis-cases.json"
            sql = "SELECT t.value FROM mart_sales.test_table AS t;"
            cases_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "BA01",
                            "question": "按销售区域分析销售额。",
                            "expected": {
                                "outcome": "plan",
                                "min_tasks": 1,
                                "required_task_types": ["breakdown"],
                                "required_metrics": ["人民币净销售额"],
                                "required_dimensions": ["销售区域"],
                                "tasks": [
                                    {
                                        "key": "breakdown",
                                        "task_type": "breakdown",
                                        "metrics": ["人民币净销售额"],
                                        "dimensions": ["销售区域"],
                                        "depends_on": [],
                                        "expected_sql": sql,
                                    }
                                ],
                                "report": {
                                    "required_evidence_tasks": ["breakdown"],
                                    "expected_incomplete_tasks": [],
                                },
                            },
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
                allowed_columns={"mart_sales.test_table": frozenset({"value"})},
            )
            data = QueryData(
                columns=("value",),
                rows=((1,),),
                truncated=False,
            )
            analysis_result = BusinessAnalysisSuccess(
                request_id="analysis-evaluation-BA01",
                report=BusinessAnalysisReport(
                    title="销售额分析",
                    executive_summary="基于任务结果生成。",
                    key_findings=("存在销售额结果。",),
                    trend_judgment="无趋势任务。",
                    root_causes=(),
                    action_suggestions=(),
                    evidence_task_ids=("task_1",),
                    incomplete_tasks=(),
                ),
                task_results=(
                    TaskResult(
                        task_id="task_1",
                        status=TaskStatus.COMPLETED,
                        columns=("value",),
                        rows=((1,),),
                        row_count=1,
                    ),
                ),
                plan=AnalysisPlan(
                    tasks=(
                        AnalysisTask(
                            task_id="task_1",
                            task_type=AnalysisTaskType.BREAKDOWN,
                            description="按区域分析",
                            metrics=("人民币净销售额",),
                            dimensions=("销售区域",),
                            time_range=None,
                            filters=(),
                            depends_on=(),
                            expected_output="结构化结果",
                        ),
                    )
                ),
            )
            stdout = StringIO()
            exit_code = run_cli(
                [
                    "--business-analysis",
                    "--cases",
                    str(cases_path),
                    "--output-dir",
                    str(output_dir),
                ],
                environ={"LLM_MODEL": "test-model"},
                context_loader=lambda: context,
                generator_factory=lambda environ: _FakeGenerator(sql),
                executor_factory=lambda environ: _FakeExecutor(data),
                analysis_application_factory=lambda authorized, environ: (
                    _FakeAnalysisApplication(analysis_result)
                ),
                git_state_reader=lambda project_root: ("abcdef123456", False),
                context_paths={"context": context_file},
                stdout=stdout,
                stderr=StringIO(),
            )
            reports = list(output_dir.glob("*-business-analysis.json"))
            report = json.loads(reports[0].read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["summary"]["end_to_end_accuracy"], 1.0)
        self.assertIn(
            "Business Analysis End-to-End Accuracy: 100.00%", stdout.getvalue()
        )

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
                allowed_columns={"mart_sales.test_table": frozenset({"value"})},
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
                query_understanding_factory=lambda environ: _FakeQueryUnderstanding(),
                git_state_reader=lambda project_root: ("abcdef123456", False),
                context_paths={"context": context_file},
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(provider.requests), 1)
        self.assertIsInstance(provider.requests[0], RetrievalRequest)

    def test_online_retrieval_preflight_stops_before_cases(self) -> None:
        from src.evaluation.__main__ import run_cli

        with TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path, context_file, context, _ = self._files(root)
            output_dir = root / "reports"
            runtime = _FailingRuntime("发布文件不存在：current.json")
            executor_calls = 0
            generator_calls = 0
            stderr = StringIO()

            def executor_factory(environ: object) -> _FakeExecutor:
                nonlocal executor_calls
                executor_calls += 1
                raise AssertionError("RAG preflight 失败后不应创建 QueryExecutor")

            def generator_factory(environ: object) -> _FakeGenerator:
                nonlocal generator_calls
                generator_calls += 1
                raise AssertionError("RAG preflight 失败后不应创建 SQLGenerator")

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
                generator_factory=generator_factory,
                executor_factory=executor_factory,
                runtime_factory=lambda: runtime,
                git_state_reader=lambda project_root: ("abcdef123456", False),
                context_paths={"context": context_file},
                stdout=StringIO(),
                stderr=stderr,
            )

        self.assertEqual(exit_code, 1)
        self.assertEqual(runtime.get_snapshot_calls, 1)
        self.assertEqual(runtime.close_calls, 1)
        self.assertEqual(executor_calls, 0)
        self.assertEqual(generator_calls, 0)
        self.assertIn("在线 RAG 评测前置检查失败", stderr.getvalue())
        self.assertIn("current.json", stderr.getvalue())
        self.assertEqual(list(output_dir.glob("*")), [])

    def test_online_retrieval_reuses_preflight_runtime(self) -> None:
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
            runtime = _SuccessfulRuntime()
            provider = _FakeRetrievalProvider(context)

            with patch(
                "src.evaluation.__main__._build_online_retrieval_provider",
                return_value=provider,
            ) as build_provider:
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
                    runtime_factory=lambda: runtime,
                    query_understanding_factory=lambda environ: (
                        _FakeQueryUnderstanding()
                    ),
                    git_state_reader=lambda project_root: ("abcdef123456", False),
                    context_paths={"context": context_file},
                    stdout=StringIO(),
                    stderr=StringIO(),
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(runtime.get_snapshot_calls, 1)
        self.assertEqual(runtime.close_calls, 1)
        self.assertIs(build_provider.call_args.args[0], runtime)
        self.assertEqual(len(provider.requests), 1)

    def test_query_understanding_mode_writes_semantic_report_without_sql_chain(
        self,
    ) -> None:
        from src.evaluation.__main__ import run_cli

        with TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path = root / "query-understanding-cases.json"
            cases_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "Q01",
                            "question": "查询销售额",
                            "expected": {
                                "query_type": "metric_analysis",
                                "metrics": ["销售额"],
                                "dimensions": [],
                                "time": None,
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            output_dir = root / "reports"
            stdout = StringIO()

            exit_code = run_cli(
                [
                    "--query-understanding",
                    "--query-understanding-cases",
                    str(cases_path),
                    "--output-dir",
                    str(output_dir),
                ],
                environ={"LLM_MODEL": "test-model"},
                context_loader=lambda: (_ for _ in ()).throw(
                    AssertionError("semantic mode must not load SQL context")
                ),
                generator_factory=lambda environ: (_ for _ in ()).throw(
                    AssertionError("semantic mode must not create SQL generator")
                ),
                executor_factory=lambda environ: (_ for _ in ()).throw(
                    AssertionError("semantic mode must not create executor")
                ),
                query_understanding_factory=lambda environ: (
                    _FakeSemanticQueryUnderstanding()
                ),
                git_state_reader=lambda project_root: ("abcdef123456", False),
                stdout=stdout,
                stderr=StringIO(),
            )

            reports = list(output_dir.glob("*.json"))
            report = json.loads(reports[0].read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["summary"]["passed"], 1)
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertIn("Query Understanding Accuracy: 100.00%", stdout.getvalue())

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
            allowed_columns={"mart_sales.test_table": frozenset({"value"})},
        )
        return cases_path, context_file, context, sql


if __name__ == "__main__":
    unittest.main()
