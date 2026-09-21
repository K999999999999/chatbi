"""Business Analysis 标准案例和确定性评测器测试。"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.business_analysis.contracts import (
    AnalysisPlanCandidate,
    AnalysisSemanticCatalog,
    AnalysisTaskCandidate,
    AnalysisTaskType,
)
from src.business_analysis.runtime import load_analysis_context
from src.evaluation.business_analysis_evaluation import (
    BusinessAnalysisEvaluationLoadError,
    evaluate_business_analysis_plans,
    load_business_analysis_cases,
)


class BusinessAnalysisEvaluationTest(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[2]
        self.cases = load_business_analysis_cases(
            root / "src" / "evaluation" / "business_analysis_cases.json"
        )
        self.context = load_analysis_context()
        self.catalog = AnalysisSemanticCatalog.from_records(
            self.context.metric_records,
            self.context.dimensions,
        )

    def test_standard_cases_cover_analysis_shapes_and_ambiguity(self) -> None:
        self.assertEqual(len(self.cases), 5)
        self.assertEqual(
            {case.expected_outcome for case in self.cases},
            {"plan", "clarification_required"},
        )
        results = evaluate_business_analysis_plans(
            self.cases,
            _CaseDecomposer(),
            self.context,
            self.catalog,
        )

        self.assertTrue(all(result.passed for result in results))
        ambiguous = next(
            result for result in results if result.case_id == "ambiguous-profit"
        )
        self.assertTrue(ambiguous.passed)

    def test_standard_cases_include_executable_task_references(self) -> None:
        planned = [case for case in self.cases if case.expected_outcome == "plan"]

        self.assertEqual(len(planned), 4)
        self.assertTrue(all(case.expected_tasks for case in planned))
        self.assertTrue(
            all(
                task.expected_sql and task.metrics
                for case in planned
                for task in case.expected_tasks
            )
        )
        self.assertEqual(
            next(
                case for case in self.cases if case.case_id == "ambiguous-profit"
            ).expected_tasks,
            (),
        )

    def test_evaluator_detects_missing_breakdown_dimension(self) -> None:
        case = next(
            case
            for case in self.cases
            if case.case_id == "breakdown-sales-region-q1-2025"
        )
        results = evaluate_business_analysis_plans(
            (case,),
            _MissingDimensionDecomposer(),
            self.context,
            self.catalog,
        )

        self.assertFalse(results[0].passed)
        self.assertEqual(results[0].reason_code, "DIMENSION_MISSING")
        self.assertNotIn("SELECT", results[0].failure_reason or "")

    def test_loader_rejects_unknown_report_task_reference(self) -> None:
        record = {
            "id": "invalid-report-reference",
            "question": "分析销售额",
            "expected": {
                "outcome": "plan",
                "min_tasks": 1,
                "required_task_types": ["baseline"],
                "required_metrics": ["人民币净销售额"],
                "required_dimensions": [],
                "tasks": [
                    {
                        "key": "sales",
                        "task_type": "baseline",
                        "metrics": ["人民币净销售额"],
                        "dimensions": [],
                        "depends_on": [],
                        "expected_sql": "SELECT 1;",
                    }
                ],
                "report": {
                    "required_evidence_tasks": ["missing"],
                    "expected_incomplete_tasks": [],
                },
            },
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps([record], ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(BusinessAnalysisEvaluationLoadError):
                load_business_analysis_cases(path)


class _CaseDecomposer:
    def decompose(self, question, context):
        del context
        if question == "最近利润为什么下降？":
            return _plan(
                task_id="ambiguous",
                task_type=AnalysisTaskType.TREND,
                metrics=("利润",),
            )
        if "按销售区域" in question:
            return _plan(
                task_id="breakdown",
                task_type=AnalysisTaskType.BREAKDOWN,
                dimensions=("销售区域",),
            )
        if "产品线" in question:
            return AnalysisPlanCandidate(
                tasks=(
                    _task(
                        "trend",
                        AnalysisTaskType.TREND,
                        dimensions=("月份",),
                    ),
                    _task(
                        "product-line",
                        AnalysisTaskType.BREAKDOWN,
                        dimensions=("产品线",),
                        depends_on=("trend",),
                    ),
                )
            )
        if "2024年和2025年" in question:
            return _plan(
                task_id="compare",
                task_type=AnalysisTaskType.COMPARISON,
                dimensions=("年份",),
            )
        return _plan(
            task_id="trend",
            task_type=AnalysisTaskType.TREND,
            dimensions=("月份",),
        )


class _MissingDimensionDecomposer:
    def decompose(self, question, context):
        del question, context
        return _plan(task_id="breakdown", task_type=AnalysisTaskType.BREAKDOWN)


def _plan(
    *,
    task_id: str,
    task_type: AnalysisTaskType,
    metrics: tuple[str, ...] = ("销售额",),
    dimensions: tuple[str, ...] = (),
) -> AnalysisPlanCandidate:
    return AnalysisPlanCandidate(
        tasks=(
            _task(
                task_id,
                task_type,
                metrics=metrics,
                dimensions=dimensions,
            ),
        )
    )


def _task(
    task_id: str,
    task_type: AnalysisTaskType,
    *,
    metrics: tuple[str, ...] = ("销售额",),
    dimensions: tuple[str, ...] = (),
    depends_on: tuple[str, ...] = (),
) -> AnalysisTaskCandidate:
    return AnalysisTaskCandidate(
        task_id=task_id,
        task_type=task_type,
        description="查询业务指标",
        metrics=metrics,
        dimensions=dimensions,
        time_range=None,
        filters=(),
        depends_on=depends_on,
        expected_output="结构化结果",
    )


if __name__ == "__main__":
    unittest.main()
