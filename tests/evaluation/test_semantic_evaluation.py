"""Query Understanding 语义评测 Contract 和执行测试。"""

import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from src.evaluation.semantic_evaluation import (
    QueryUnderstandingEvaluation,
    create_query_understanding_report,
    evaluate_query_understanding,
    load_query_understanding_cases,
    render_query_understanding_report,
    write_query_understanding_report,
)
from src.online_query.query_understanding import candidate_from_payload


class _AdapterFailure(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__("secret prompt detail")
        self.reason = reason


class SemanticEvaluationTest(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[2]
        self.cases = load_query_understanding_cases(
            root / "src" / "evaluation" / "query_understanding_cases.json"
        )

    def test_cases_cover_no_time_and_explicit_time_boundaries(self) -> None:
        self.assertEqual(len(self.cases), 6)
        no_time = next(
            case for case in self.cases if case.id == "current-context-no-time"
        )
        self.assertIsNone(no_time.expected.time)

        five_metric = next(
            case for case in self.cases if case.id == "five-metric-no-time"
        )
        self.assertEqual(len(five_metric.expected.metrics), 5)
        self.assertIsNone(five_metric.expected.time)

        explicit_time = next(
            case for case in self.cases if case.id == "today-explicit-time"
        )
        self.assertIsNotNone(explicit_time.expected.time)

    def test_evaluator_compares_structured_semantics(self) -> None:
        class ExpectedAdapter:
            def understand(self, question: str):
                return next(
                    case.expected for case in self.cases if case.question == question
                )

            def __init__(self, cases):
                self.cases = cases

        results = evaluate_query_understanding(
            self.cases,
            ExpectedAdapter(self.cases),
        )

        self.assertEqual(len(results), 6)
        self.assertTrue(all(result.passed for result in results))
        self.assertTrue(all(result.reason_code is None for result in results))

    def test_evaluator_detects_model_time_overclassification(self) -> None:
        target = next(
            case for case in self.cases if case.id == "current-context-no-time"
        )
        wrong_candidate = candidate_from_payload(
            {
                "query_type": target.expected.query_type.value,
                "subjects": [],
                "metrics": list(target.expected.metrics),
                "dimensions": list(target.expected.dimensions),
                "time": {"text": "当前", "granularity": "day"},
                "filters": [],
            }
        )

        class OneWrongAdapter:
            def understand(self, question: str):
                if question == target.question:
                    return wrong_candidate
                return target.expected

        result = next(
            item
            for item in evaluate_query_understanding(
                (target,),
                OneWrongAdapter(),
            )
            if item.case_id == target.id
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.reason_code, "TIME_MISMATCH")
        self.assertIn("time", result.failure_reason or "")

    def test_evaluator_preserves_adapter_reason_without_raw_exception(self) -> None:
        class BrokenAdapter:
            def understand(self, question: str):
                del question
                raise _AdapterFailure("RESPONSE_NOT_JSON")

        result = evaluate_query_understanding(
            (self.cases[0],),
            BrokenAdapter(),
        )[0]

        self.assertFalse(result.passed)
        self.assertEqual(result.reason_code, "RESPONSE_NOT_JSON")
        self.assertNotIn("secret prompt detail", result.failure_reason or "")

    def test_semantic_report_contains_safe_reason_summary(self) -> None:
        report = create_query_understanding_report(
            (
                QueryUnderstandingEvaluation(case_id="A", passed=True),
                QueryUnderstandingEvaluation(
                    case_id="B",
                    passed=False,
                    failure_reason="结构化查询未通过确定性校验",
                    reason_code="TIME_NOT_NORMALIZABLE",
                ),
            ),
            git_commit="abcdef123456",
            git_dirty=False,
            model="test-model",
            cases_path=Path("query-understanding-cases.json"),
            created_at=datetime(2026, 9, 18, tzinfo=UTC),
        )

        summary = report.get("summary")
        self.assertIsInstance(summary, dict)
        assert isinstance(summary, dict)
        self.assertEqual(
            summary["reason_code_counts"],
            {"TIME_NOT_NORMALIZABLE": 1},
        )
        markdown = render_query_understanding_report(report)
        self.assertIn("TIME_NOT_NORMALIZABLE", markdown)
        self.assertNotIn("query-understanding-cases.json", markdown)

        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_query_understanding_report(
                report,
                root / "report.json",
                root / "report.md",
            )
            self.assertTrue((root / "report.json").exists())
            self.assertTrue((root / "report.md").exists())


if __name__ == "__main__":
    unittest.main()
