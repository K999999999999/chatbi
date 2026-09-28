"""Business Analysis 标准案例格式测试。"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.evaluation.business_analysis_evaluation import (
    BusinessAnalysisEvaluationLoadError,
    load_business_analysis_cases,
)


class BusinessAnalysisEvaluationTest(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[2]
        self.cases = load_business_analysis_cases(
            root / "src" / "evaluation" / "business_analysis_cases.json"
        )

    def test_standard_cases_are_the_five_confirmed_period_comparisons(self) -> None:
        self.assertEqual(
            [case.case_id for case in self.cases],
            ["BA01", "BA02", "BA03", "BA04", "BA05"],
        )
        self.assertEqual(
            {case.expected_outcome for case in self.cases},
            {"plan", "clarification_required"},
        )
        clarify = [
            case
            for case in self.cases
            if case.expected_outcome == "clarification_required"
        ]
        self.assertEqual({case.case_id for case in clarify}, {"BA04", "BA05"})
        self.assertTrue(all(not case.expected_tasks for case in clarify))

    def test_success_cases_have_four_product_and_overall_reference_queries(
        self,
    ) -> None:
        planned = [case for case in self.cases if case.expected_outcome == "plan"]
        self.assertEqual(len(planned), 3)
        for case in planned:
            self.assertEqual(
                [task.key for task in case.expected_tasks],
                [
                    "comparison-overall",
                    "current-overall",
                    "comparison-products",
                    "current-products",
                ],
            )
            self.assertEqual(
                {task.task_type for task in case.expected_tasks},
                {case.required_task_types[0]},
            )
            self.assertTrue(
                all(task.period and task.expected_sql for task in case.expected_tasks)
            )
            self.assertEqual(
                set(case.required_evidence_tasks),
                {task.key for task in case.expected_tasks},
            )

    def test_ba01_keeps_original_question_and_data_supported_direction(self) -> None:
        case = self.cases[0]
        self.assertEqual(case.question, "2025年3月毛利为什么比2月下降？")
        self.assertEqual(case.expected_direction, "increase")
        self.assertEqual(case.expected_change, "18195.32")
        self.assertEqual(case.metric_name, "人民币毛利")
        self.assertEqual(case.comparison_period, "2025年2月")
        self.assertEqual(case.current_period, "2025年3月")

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


if __name__ == "__main__":
    unittest.main()
