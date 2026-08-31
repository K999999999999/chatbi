"""Evaluation（评测）案例加载与结果比较测试。"""

import json
import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlglot import parse_one

from src.online_query.contracts import QueryData


class EvaluationCaseLoadingTest(unittest.TestCase):
    def test_loads_valid_cases_and_defaults_order_sensitive_to_false(self) -> None:
        from src.evaluation.evaluator import load_evaluation_cases

        with TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            path.write_text(
                json.dumps(
                    [
                        self._case("S01"),
                        self._case("S02", order_sensitive=True),
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            cases = load_evaluation_cases(path)

        self.assertEqual(len(cases), 2)
        self.assertTrue(cases[0].is_valid)
        self.assertFalse(cases[0].order_sensitive)
        self.assertTrue(cases[1].order_sensitive)

    def test_loads_current_twenty_case_standard_set(self) -> None:
        from src.evaluation.evaluator import load_evaluation_cases

        cases = load_evaluation_cases(Path("src/evaluation/eval_cases.json"))

        self.assertEqual(len(cases), 20)
        self.assertTrue(all(case.is_valid for case in cases))
        self.assertEqual(
            {case.category for case in cases},
            {"simple", "medium", "complex"},
        )

    def test_t01_gold_sql_returns_only_the_requested_sales_amount(self) -> None:
        from src.evaluation.evaluator import load_evaluation_cases

        cases = load_evaluation_cases(Path("src/evaluation/eval_cases.json"))
        case = next(case for case in cases if case.id == "T01")
        query = parse_one(case.expected_sql)

        self.assertEqual(len(query.expressions), 1)

    def test_preserves_one_invalid_record_for_later_invalid_case_result(self) -> None:
        from src.evaluation.evaluator import load_evaluation_cases

        with TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            record = self._case("S01")
            del record["question"]
            path.write_text(
                json.dumps([record], ensure_ascii=False),
                encoding="utf-8",
            )

            cases = load_evaluation_cases(path)

        self.assertEqual(len(cases), 1)
        self.assertFalse(cases[0].is_valid)
        self.assertEqual(cases[0].id, "S01")
        self.assertIn("question", cases[0].validation_error or "")

    def test_rejects_missing_invalid_non_array_and_empty_files(self) -> None:
        from src.evaluation.evaluator import EvaluationLoadError, load_evaluation_cases

        with TemporaryDirectory() as directory:
            root = Path(directory)
            missing = root / "missing.json"
            with self.assertRaises(EvaluationLoadError):
                load_evaluation_cases(missing)

            invalid_json = root / "invalid.json"
            invalid_json.write_text("{", encoding="utf-8")
            with self.assertRaises(EvaluationLoadError):
                load_evaluation_cases(invalid_json)

            non_array = root / "object.json"
            non_array.write_text("{}", encoding="utf-8")
            with self.assertRaises(EvaluationLoadError):
                load_evaluation_cases(non_array)

            empty = root / "empty.json"
            empty.write_text("[]", encoding="utf-8")
            with self.assertRaises(EvaluationLoadError):
                load_evaluation_cases(empty)

    def test_rejects_duplicate_case_ids(self) -> None:
        from src.evaluation.evaluator import EvaluationLoadError, load_evaluation_cases

        with TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            path.write_text(
                json.dumps([self._case("S01"), self._case("S01")]),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(EvaluationLoadError, "重复"):
                load_evaluation_cases(path)

    @staticmethod
    def _case(case_id: str, **extra: object) -> dict[str, object]:
        record: dict[str, object] = {
            "id": case_id,
            "schema_name": "mart_sales",
            "category": "simple",
            "question": "当前已完成订单数量是多少？",
            "description": "订单数量。",
            "expected_sql": "SELECT 1;",
        }
        record.update(extra)
        return record


class ResultComparisonTest(unittest.TestCase):
    def test_ignores_column_names_but_preserves_column_order(self) -> None:
        from src.evaluation.evaluator import results_match

        expected = self._data(("region", "sales"), (("华东", 100),))
        renamed = self._data(("地区", "销售额"), (("华东", 100),))
        reordered = self._data(("sales", "region"), ((100, "华东"),))

        self.assertTrue(results_match(renamed, expected))
        self.assertFalse(results_match(reordered, expected))

    def test_requires_same_column_and_row_counts(self) -> None:
        from src.evaluation.evaluator import results_match

        expected = self._data(("region", "sales"), (("华东", 100),))
        fewer_columns = self._data(("region",), (("华东",),))
        more_rows = self._data(
            ("region", "sales"),
            (("华东", 100), ("华南", 80)),
        )

        self.assertFalse(results_match(fewer_columns, expected))
        self.assertFalse(results_match(more_rows, expected))

    def test_ignores_row_order_by_default_and_preserves_duplicates(self) -> None:
        from src.evaluation.evaluator import results_match

        expected = self._data(("value",), ((1,), (1,), (2,)))
        reordered = self._data(("other_name",), ((2,), (1,), (1,)))
        wrong_duplicates = self._data(("value",), ((2,), (2,), (1,)))

        self.assertTrue(results_match(reordered, expected))
        self.assertFalse(results_match(wrong_duplicates, expected))

    def test_checks_row_order_when_order_sensitive(self) -> None:
        from src.evaluation.evaluator import results_match

        expected = self._data(("value",), ((1,), (2,)))
        reordered = self._data(("value",), ((2,), (1,)))

        self.assertTrue(results_match(reordered, expected))
        self.assertFalse(
            results_match(reordered, expected, order_sensitive=True)
        )

    def test_compares_nulls_and_non_numeric_values_exactly(self) -> None:
        from src.evaluation.evaluator import results_match

        expected = self._data(("a", "b"), ((None, "1"),))
        same = self._data(("x", "y"), ((None, "1"),))
        wrong_null = self._data(("a", "b"), ((0, "1"),))
        wrong_type = self._data(("a", "b"), ((None, 1),))

        self.assertTrue(results_match(same, expected))
        self.assertFalse(results_match(wrong_null, expected))
        self.assertFalse(results_match(wrong_type, expected))

    def test_uses_absolute_and_relative_numeric_tolerance(self) -> None:
        from src.evaluation.evaluator import results_match

        expected = self._data(
            ("small", "large"),
            ((Decimal("1.0"), Decimal(1000000)),),
        )
        within_tolerance = self._data(
            ("small", "large"),
            ((Decimal("1.0000005"), Decimal("1000000.5")),),
        )
        outside_tolerance = self._data(
            ("small", "large"),
            ((Decimal("1.00001"), Decimal(1000002)),),
        )

        self.assertTrue(results_match(within_tolerance, expected))
        self.assertFalse(results_match(outside_tolerance, expected))

    def test_rejects_truncated_results(self) -> None:
        from src.evaluation.evaluator import results_match

        expected = self._data(("value",), ((1,),))
        truncated = QueryData(
            columns=("value",),
            rows=((1,),),
            truncated=True,
        )

        self.assertFalse(results_match(truncated, expected))
        self.assertFalse(results_match(expected, truncated))

    @staticmethod
    def _data(
        columns: tuple[str, ...],
        rows: tuple[tuple[object, ...], ...],
    ) -> QueryData:
        return QueryData(columns=columns, rows=rows, truncated=False)


if __name__ == "__main__":
    unittest.main()
