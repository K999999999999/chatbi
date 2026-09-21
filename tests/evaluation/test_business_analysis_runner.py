"""经营分析 Golden Set Runner（黄金测试集运行器）测试。"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.authorization import AuthContext
from src.business_analysis.application import BusinessAnalysisSuccess
from src.business_analysis.contracts import (
    AnalysisPlan,
    AnalysisTask,
    AnalysisTaskType,
)
from src.business_analysis.execution import TaskResult, TaskStatus
from src.business_analysis.reporting import BusinessAnalysisReport
from src.evaluation.business_analysis_evaluation import load_business_analysis_cases
from src.evaluation.business_analysis_runner import (
    BusinessAnalysisCaseStatus,
    run_business_analysis_evaluation,
)
from src.online_query.context import load_query_context
from src.online_query.contracts import QueryData


class BusinessAnalysisRunnerTest(unittest.TestCase):
    def test_runs_golden_case_and_scores_plan_tasks_and_report_evidence(self) -> None:
        cases = self._load_case(
            {
                "id": "region-breakdown",
                "question": "2025年第一季度按销售区域分析销售额。",
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
                            "expected_sql": (
                                "SELECT SUM(f.net_sales_amount_cny) "
                                "FROM mart_sales.fct_sales_order_line AS f;"
                            ),
                        }
                    ],
                    "report": {
                        "required_evidence_tasks": ["breakdown"],
                        "expected_incomplete_tasks": [],
                    },
                },
            }
        )
        actual = QueryData(
            columns=("sales_region_name", "net_sales_cny"),
            rows=(("华东", 100),),
            truncated=False,
        )
        plan = AnalysisPlan(
            tasks=(
                AnalysisTask(
                    task_id="task_1",
                    task_type=AnalysisTaskType.BREAKDOWN,
                    description="按销售区域分析销售额",
                    metrics=("人民币净销售额",),
                    dimensions=("销售区域",),
                    time_range=None,
                    filters=(),
                    depends_on=(),
                    expected_output="结构化结果",
                ),
            )
        )
        application = _FakeApplication(
            BusinessAnalysisSuccess(
                request_id="analysis-evaluation-region-breakdown",
                report=_report(evidence=("task_1",)),
                task_results=(
                    TaskResult(
                        task_id="task_1",
                        status=TaskStatus.COMPLETED,
                        columns=actual.columns,
                        rows=actual.rows,
                        row_count=1,
                    ),
                ),
                plan=plan,
            )
        )

        run = run_business_analysis_evaluation(
            cases,
            application,
            _FakeExecutor(actual),
            load_query_context(),
            AuthContext(subject_id="evaluation-test", identity_provider="test"),
        )

        self.assertEqual(run.cases[0].status, BusinessAnalysisCaseStatus.PASS)
        self.assertEqual(run.summary.plan_accuracy, 1.0)
        self.assertEqual(run.summary.task_execution_accuracy, 1.0)
        self.assertEqual(run.summary.report_grounded_accuracy, 1.0)
        self.assertEqual(run.summary.end_to_end_accuracy, 1.0)

    def test_marks_report_evidence_mismatch_as_failure(self) -> None:
        cases = self._load_case(
            {
                "id": "region-breakdown",
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
                            "expected_sql": (
                                "SELECT SUM(f.net_sales_amount_cny) "
                                "FROM mart_sales.fct_sales_order_line AS f;"
                            ),
                        }
                    ],
                    "report": {
                        "required_evidence_tasks": ["breakdown"],
                        "expected_incomplete_tasks": [],
                    },
                },
            }
        )
        plan = _plan()
        result = BusinessAnalysisSuccess(
            request_id="analysis-evaluation-region-breakdown",
            report=_report(evidence=()),
            task_results=(
                TaskResult(
                    task_id="task_1",
                    status=TaskStatus.COMPLETED,
                    columns=("value",),
                    rows=((1,),),
                    row_count=1,
                ),
            ),
            plan=plan,
        )

        run = run_business_analysis_evaluation(
            cases,
            _FakeApplication(result),
            _FakeExecutor(QueryData(columns=("value",), rows=((1,),), truncated=False)),
            load_query_context(),
            AuthContext(subject_id="evaluation-test", identity_provider="test"),
        )

        self.assertEqual(run.cases[0].status, BusinessAnalysisCaseStatus.FAIL)
        self.assertFalse(run.cases[0].report_passed)
        self.assertEqual(run.cases[0].reason_code, "REPORT_EVIDENCE_MISSING")

    @staticmethod
    def _load_case(record: dict[str, object]):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            path.write_text(json.dumps([record], ensure_ascii=False), encoding="utf-8")
            return load_business_analysis_cases(path)


class _FakeApplication:
    def __init__(self, result: BusinessAnalysisSuccess) -> None:
        self.result = result

    def analyze(self, question, *, request_id, auth_context):
        del question, request_id, auth_context
        return self.result


class _FakeExecutor:
    def __init__(self, result: QueryData) -> None:
        self.result = result

    def execute(self, validated_sql):
        del validated_sql
        return self.result


def _plan() -> AnalysisPlan:
    return AnalysisPlan(
        tasks=(
            AnalysisTask(
                task_id="task_1",
                task_type=AnalysisTaskType.BREAKDOWN,
                description="按销售区域分析销售额",
                metrics=("人民币净销售额",),
                dimensions=("销售区域",),
                time_range=None,
                filters=(),
                depends_on=(),
                expected_output="结构化结果",
            ),
        )
    )


def _report(*, evidence: tuple[str, ...]) -> BusinessAnalysisReport:
    return BusinessAnalysisReport(
        title="销售区域分析",
        executive_summary="基于查询结果生成。",
        key_findings=("华东销售额最高。",),
        trend_judgment="需要结合趋势任务判断。",
        root_causes=(),
        action_suggestions=(),
        evidence_task_ids=evidence,
        incomplete_tasks=(),
    )


if __name__ == "__main__":
    unittest.main()
