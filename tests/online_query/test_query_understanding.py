"""Query Understanding（查询理解）Contract 和确定性校验测试。"""

from datetime import datetime
import unittest
from zoneinfo import ZoneInfo

from src.online_query.query_understanding import (
    FilterOperator,
    QueryType,
    SemanticQueryCannotAnswer,
    SemanticQueryStructureError,
    TimeGranularity,
    candidate_from_payload,
    validate_candidate,
)


QUERY_TIMEZONE = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 9, 17, 15, 30, tzinfo=QUERY_TIMEZONE)


class QueryUnderstandingContractTest(unittest.TestCase):
    def test_valid_payload_becomes_validated_query(self) -> None:
        candidate = candidate_from_payload(_payload())

        validated = validate_candidate(
            candidate,
            original_question="2025 年按客户类型统计销售额",
            now=NOW,
        )

        self.assertEqual(validated.query_type, QueryType.METRIC_ANALYSIS)
        self.assertEqual(validated.subjects, ("销售订单",))
        self.assertEqual(validated.metrics, ("销售额",))
        self.assertEqual(validated.dimensions, ("客户类型",))
        self.assertEqual(validated.original_question, "2025 年按客户类型统计销售额")
        self.assertIsNotNone(validated.time)
        assert validated.time is not None
        self.assertEqual(validated.time.granularity, TimeGranularity.YEAR)
        self.assertEqual(
            validated.time.start,
            datetime(2025, 1, 1, tzinfo=QUERY_TIMEZONE),
        )
        self.assertEqual(
            validated.time.end,
            datetime(2026, 1, 1, tzinfo=QUERY_TIMEZONE),
        )

    def test_candidate_payload_has_strict_top_level_shape(self) -> None:
        payload = _payload()
        payload.pop("metrics")

        with self.assertRaises(SemanticQueryStructureError):
            candidate_from_payload(payload)

        with self.assertRaises(SemanticQueryStructureError):
            candidate_from_payload({**_payload(), "formula": "SUM(amount)"})

    def test_candidate_arrays_are_non_empty_strings(self) -> None:
        for field in ("subjects", "metrics", "dimensions"):
            payload = _payload()
            payload[field] = ["有效", ""]

            with self.subTest(field=field), self.assertRaises(
                SemanticQueryStructureError
            ):
                candidate_from_payload(payload)

    def test_query_type_consistency_is_deterministic(self) -> None:
        cases = (
            (
                {**_payload(), "query_type": "entity_lookup", "metrics": []},
                None,
            ),
            (
                {**_payload(), "query_type": "metric_analysis", "metrics": []},
                SemanticQueryCannotAnswer,
            ),
            (
                {**_payload(), "query_type": "entity_lookup"},
                SemanticQueryCannotAnswer,
            ),
            (
                {**_payload(), "query_type": "unknown"},
                SemanticQueryCannotAnswer,
            ),
        )

        for payload, expected_error in cases:
            with self.subTest(payload=payload):
                candidate = candidate_from_payload(payload)
                if expected_error is None:
                    validated = validate_candidate(
                        candidate,
                        original_question="查询客户",
                        now=NOW,
                    )
                    self.assertEqual(validated.query_type, QueryType.ENTITY_LOOKUP)
                else:
                    with self.assertRaises(expected_error):
                        validate_candidate(
                            candidate,
                            original_question="查询内容",
                            now=NOW,
                        )

    def test_metric_limit_is_five_without_metric_count(self) -> None:
        payload = _payload()
        payload["metrics"] = ["指标一", "指标二", "指标三", "指标四", "指标五", "指标六"]

        candidate = candidate_from_payload(payload)
        with self.assertRaises(SemanticQueryCannotAnswer):
            validate_candidate(candidate, original_question="查询六个指标", now=NOW)

        self.assertNotIn("metric_count", candidate.__slots__)

    def test_filter_shape_and_allowed_operators(self) -> None:
        payload = _payload()
        payload["filters"] = [
            {
                "field_text": "客户类型",
                "operator": "equals",
                "values": ["Enterprise"],
            },
            {
                "field_text": "销售额",
                "operator": "gte",
                "values": ["10000"],
            },
            {
                "field_text": "区域",
                "operator": "in",
                "values": ["华东", "华南"],
            },
        ]

        candidate = candidate_from_payload(payload)
        validated = validate_candidate(
            candidate,
            original_question="查询 Enterprise 客户销售额",
            now=NOW,
        )

        self.assertEqual(validated.filters[0].operator, FilterOperator.EQUALS)
        self.assertEqual(validated.filters[0].values, ("Enterprise",))
        self.assertEqual(validated.filters[1].operator, FilterOperator.GTE)
        self.assertEqual(validated.filters[2].operator, FilterOperator.IN)
        self.assertEqual(validated.filters[2].values, ("华东", "华南"))

    def test_filter_values_follow_operator_cardinality(self) -> None:
        cases = (
            ("equals", []),
            ("equals", ["a", "b"]),
            ("in", []),
            ("gte", ["a", "b"]),
            ("contains", ["a"]),
        )

        for operator, values in cases:
            payload = _payload()
            payload["filters"] = [
                {
                    "field_text": "客户类型",
                    "operator": operator,
                    "values": values,
                }
            ]

            with self.subTest(operator=operator, values=values):
                with self.assertRaises(SemanticQueryStructureError):
                    candidate_from_payload(payload)

    def test_relative_time_uses_query_timezone_and_includes_today(self) -> None:
        payload = _payload()
        payload["time"] = {"text": "最近 7 天", "granularity": "day"}

        validated = validate_candidate(
            candidate_from_payload(payload),
            original_question="最近 7 天的销售额",
            now=NOW,
        )

        assert validated.time is not None
        self.assertEqual(
            validated.time.start,
            datetime(2026, 9, 11, tzinfo=QUERY_TIMEZONE),
        )
        self.assertEqual(
            validated.time.end,
            datetime(2026, 9, 18, tzinfo=QUERY_TIMEZONE),
        )

    def test_current_context_words_do_not_create_time_filter(self) -> None:
        for text in ("当前", "目前", "现在"):
            payload = _payload()
            payload["time"] = {"text": text, "granularity": "day"}

            with self.subTest(text=text):
                validated = validate_candidate(
                    candidate_from_payload(payload),
                    original_question=f"{text}已完成订单的销售额",
                    now=NOW,
                )

                self.assertIsNone(validated.time)

    def test_week_starts_on_monday(self) -> None:
        payload = _payload()
        payload["time"] = {"text": "上周", "granularity": "week"}

        validated = validate_candidate(
            candidate_from_payload(payload),
            original_question="上周的销售额",
            now=NOW,
        )

        assert validated.time is not None
        self.assertEqual(
            validated.time.start,
            datetime(2026, 9, 7, tzinfo=QUERY_TIMEZONE),
        )
        self.assertEqual(
            validated.time.end,
            datetime(2026, 9, 14, tzinfo=QUERY_TIMEZONE),
        )

    def test_absolute_quarter_uses_half_open_range(self) -> None:
        payload = _payload()
        payload["time"] = {
            "text": "2025 年第一季度",
            "granularity": "quarter",
        }

        validated = validate_candidate(
            candidate_from_payload(payload),
            original_question="2025 年第一季度的销售额",
            now=NOW,
        )

        assert validated.time is not None
        self.assertEqual(
            validated.time.start,
            datetime(2025, 1, 1, tzinfo=QUERY_TIMEZONE),
        )
        self.assertEqual(
            validated.time.end,
            datetime(2025, 4, 1, tzinfo=QUERY_TIMEZONE),
        )

    def test_absolute_quarter_accepts_numeric_and_q_forms(self) -> None:
        for text in ("2025 年第 1 季度", "2025Q1"):
            payload = _payload()
            payload["time"] = {"text": text, "granularity": "quarter"}

            with self.subTest(text=text):
                validated = validate_candidate(
                    candidate_from_payload(payload),
                    original_question=f"{text}的销售额",
                    now=NOW,
                )

                assert validated.time is not None
                self.assertEqual(
                    validated.time.start,
                    datetime(2025, 1, 1, tzinfo=QUERY_TIMEZONE),
                )
                self.assertEqual(
                    validated.time.end,
                    datetime(2025, 4, 1, tzinfo=QUERY_TIMEZONE),
                )

    def test_ambiguous_or_invalid_dates_cannot_answer(self) -> None:
        cases = (
            ("3 月", "month"),
            ("2025年2月30日", "day"),
            ("2025年3月1日至2025年2月28日", "day"),
            ("前一阵子", "day"),
            ("最近 0 天", "day"),
        )

        for text, granularity in cases:
            payload = _payload()
            payload["time"] = {"text": text, "granularity": granularity}

            with self.subTest(text=text):
                with self.assertRaises(SemanticQueryCannotAnswer):
                    validate_candidate(
                        candidate_from_payload(payload),
                        original_question=text,
                        now=NOW,
                    )

    def test_time_granularity_must_match_supported_expression(self) -> None:
        payload = _payload()
        payload["time"] = {"text": "去年", "granularity": "month"}

        with self.assertRaises(SemanticQueryCannotAnswer):
            validate_candidate(
                candidate_from_payload(payload),
                original_question="去年销售额",
                now=NOW,
            )


def _payload() -> dict[str, object]:
    return {
        "query_type": "metric_analysis",
        "subjects": ["销售订单"],
        "metrics": ["销售额"],
        "dimensions": ["客户类型"],
        "time": {"text": "2025年", "granularity": "year"},
        "filters": [],
    }


if __name__ == "__main__":
    unittest.main()
