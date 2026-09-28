"""经营分析标准案例格式测试。"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.evaluation.business_analysis_evaluation import (
    BusinessAnalysisEvaluationLoadError,
    load_business_analysis_cases,
)


class BusinessAnalysisEvaluationTest(unittest.TestCase):
    def test_standard_cases_cover_success_clarification_and_refusal(self) -> None:
        root = Path(__file__).resolve().parents[2]
        cases = load_business_analysis_cases(
            root / "src" / "evaluation" / "business_analysis_cases.json"
        )
        self.assertEqual(len(cases), 10)
        self.assertEqual(
            {case.expected_outcome for case in cases},
            {"success", "clarification_required", "cannot_answer"},
        )
        self.assertEqual(cases[0].expected_task_count, 4)
        self.assertEqual(len(cases[0].expected_tasks), 4)
        self.assertTrue(
            all(
                task.purpose and task.period and task.metrics
                for task in cases[0].expected_tasks
            )
        )

    def test_loader_rejects_task_count_mismatch(self) -> None:
        payload = {
            "evaluation_rules": {"success": {}},
            "cases": [
                {
                    "id": "invalid",
                    "question": "比较销售额",
                    "expected_outcome": "success",
                    "expected_task_count": 2,
                    "expected_tasks": [
                        {
                            "key": "a",
                            "purpose": "查询销售额",
                            "period": "2025年",
                            "metrics": ["销售额"],
                            "dimension": "整体",
                        }
                    ],
                }
            ],
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(BusinessAnalysisEvaluationLoadError):
                load_business_analysis_cases(path)


if __name__ == "__main__":
    unittest.main()
