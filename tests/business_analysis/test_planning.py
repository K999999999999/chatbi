"""Business Analysis 计划 Contract 和校验测试。"""

import unittest

from src.business_analysis.contracts import (
    AnalysisPlanCannotAnswer,
    AnalysisPlanClarificationRequired,
    AnalysisPlanStructureError,
    AnalysisRequestCandidate,
    AnalysisSemanticCatalog,
    AnalysisTimeRange,
)
from src.business_analysis.planning import (
    MAX_ANALYSIS_DEPTH,
    MAX_ANALYSIS_TASKS,
    build_comparison_plan,
    plan_from_payload,
    request_from_payload,
    validate_analysis_plan,
)
from src.online_query.query_understanding import TimeGranularity


class AnalysisPlanningTest(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = AnalysisSemanticCatalog.from_records(
            (
                {
                    "name": "人民币净销售额",
                    "aliases": ["销售额", "营收"],
                },
                {
                    "name": "人民币毛利",
                    "aliases": ["毛利"],
                },
                {
                    "name": "人民币销售成本",
                    "aliases": ["销售成本", "成本"],
                },
                {
                    "name": "已完成销售数量",
                    "aliases": ["销售数量", "销量"],
                },
            ),
            ("销售区域", "产品线", "产品"),
        )

    def test_gross_profit_request_generates_only_four_fixed_query_tasks(self) -> None:
        candidate = request_from_payload(
            {
                "metric_text": "毛利",
                "current_period": {"text": "2025年3月", "granularity": "month"},
                "comparison_period": {"text": "2025年2月", "granularity": "month"},
            }
        )

        request, plan = build_comparison_plan(
            candidate,
            self.catalog,
            question="2025年3月毛利为什么比2月下降？",
        )

        self.assertEqual(request.metric_name, "人民币毛利")
        self.assertEqual(len(plan.tasks), 4)
        self.assertEqual(
            [task.metrics for task in plan.tasks],
            [
                ("人民币毛利",),
                ("人民币毛利",),
                ("人民币净销售额", "已完成销售数量", "人民币销售成本"),
                ("人民币净销售额", "已完成销售数量", "人民币销售成本"),
            ],
        )
        self.assertEqual(
            [task.dimensions for task in plan.tasks], [(), (), ("产品",), ("产品",)]
        )
        self.assertEqual(
            [task.time_range.text for task in plan.tasks],
            ["2025年2月", "2025年3月", "2025年2月", "2025年3月"],
        )

    def test_sales_request_uses_only_revenue_and_quantity_factors(self) -> None:
        candidate = AnalysisRequestCandidate(
            metric_text="销售额",
            current_period=AnalysisTimeRange("2025年3月", TimeGranularity.MONTH),
            comparison_period=AnalysisTimeRange("2025年2月", TimeGranularity.MONTH),
        )

        _, plan = build_comparison_plan(
            candidate,
            self.catalog,
            question="2025年3月销售额比2月增加多少？",
        )

        self.assertEqual(
            [task.metrics for task in plan.tasks],
            [
                ("人民币净销售额",),
                ("人民币净销售额",),
                ("人民币净销售额", "已完成销售数量"),
                ("人民币净销售额", "已完成销售数量"),
            ],
        )

    def test_explicit_unsupported_region_breakdown_is_rejected(self) -> None:
        candidate = AnalysisRequestCandidate(
            metric_text="毛利",
            current_period=AnalysisTimeRange("2025年3月", TimeGranularity.MONTH),
            comparison_period=AnalysisTimeRange("2025年2月", TimeGranularity.MONTH),
        )

        with self.assertRaises(AnalysisPlanCannotAnswer) as raised:
            build_comparison_plan(
                candidate,
                self.catalog,
                question="2025年3月毛利为什么比2月下降？请按销售区域拆解原因。",
            )

        self.assertEqual(raised.exception.reason, "DIMENSION_UNSUPPORTED")

    def test_unresolved_metric_or_missing_period_requires_clarification(self) -> None:
        missing_metric = AnalysisRequestCandidate(
            metric_text="利润",
            current_period=AnalysisTimeRange("2025年", TimeGranularity.YEAR),
            comparison_period=AnalysisTimeRange("2024年", TimeGranularity.YEAR),
        )
        with self.assertRaisesRegex(AnalysisPlanClarificationRequired, "指标"):
            build_comparison_plan(
                missing_metric,
                self.catalog,
                question="2025年利润比2024年下降多少？",
            )

        missing_period = AnalysisRequestCandidate(
            metric_text="毛利",
            current_period=AnalysisTimeRange("本月", TimeGranularity.MONTH),
            comparison_period=None,
        )
        with self.assertRaisesRegex(AnalysisPlanClarificationRequired, "时期"):
            build_comparison_plan(
                missing_period,
                self.catalog,
                question="本月毛利为什么变化？",
            )

    def test_request_rejects_model_added_task_fields_and_same_periods(self) -> None:
        payload = {
            "metric_text": "毛利",
            "current_period": {"text": "2025年3月", "granularity": "month"},
            "comparison_period": {"text": "2025年2月", "granularity": "month"},
            "dimensions": ["销售区域"],
        }
        with self.assertRaises(AnalysisPlanStructureError):
            request_from_payload(payload)

        same_period = AnalysisRequestCandidate(
            metric_text="毛利",
            current_period=AnalysisTimeRange("2025年3月", TimeGranularity.MONTH),
            comparison_period=AnalysisTimeRange("2025年3月", TimeGranularity.MONTH),
        )
        with self.assertRaisesRegex(AnalysisPlanClarificationRequired, "不能相同"):
            build_comparison_plan(
                same_period,
                self.catalog,
                question="2025年3月毛利变化",
            )

    def test_request_rejects_hallucinated_period_or_missing_product_semantics(
        self,
    ) -> None:
        candidate = AnalysisRequestCandidate(
            metric_text="毛利",
            current_period=AnalysisTimeRange("2025年3月", TimeGranularity.MONTH),
            comparison_period=AnalysisTimeRange("2024年2月", TimeGranularity.MONTH),
        )
        with self.assertRaisesRegex(
            AnalysisPlanClarificationRequired,
            "无法从用户问题中确认",
        ):
            build_comparison_plan(
                candidate,
                self.catalog,
                question="2025年3月毛利为什么比2月下降？",
            )

        incomplete_catalog = AnalysisSemanticCatalog.from_records(
            (
                {"name": "人民币毛利", "aliases": ["毛利"]},
                {"name": "人民币净销售额", "aliases": ["销售额"]},
            ),
            (),
        )
        valid_periods = AnalysisRequestCandidate(
            metric_text="毛利",
            current_period=AnalysisTimeRange("2025年3月", TimeGranularity.MONTH),
            comparison_period=AnalysisTimeRange("2025年2月", TimeGranularity.MONTH),
        )
        with self.assertRaisesRegex(AnalysisPlanCannotAnswer, "缺少必要指标"):
            build_comparison_plan(
                valid_periods,
                incomplete_catalog,
                question="2025年3月毛利为什么比2月下降？",
            )

    def test_valid_plan_canonicalizes_metrics_and_keeps_dependencies(self) -> None:
        candidate = plan_from_payload(
            {
                "tasks": [
                    _task(
                        "root",
                        "baseline",
                        metrics=["销售额"],
                        expected_output="整体销售额趋势",
                    ),
                    _task(
                        "region",
                        "breakdown",
                        metrics=["毛利"],
                        dimensions=["销售区域"],
                        depends_on=["root"],
                        expected_output="区域毛利拆解",
                    ),
                ]
            }
        )

        plan = validate_analysis_plan(candidate, self.catalog)

        self.assertEqual(plan.tasks[0].metrics, ("人民币净销售额",))
        self.assertEqual(plan.tasks[1].metrics, ("人民币毛利",))
        self.assertEqual(plan.tasks[1].depends_on, ("root",))

    def test_unresolved_metric_requires_clarification_instead_of_guessing(self) -> None:
        candidate = plan_from_payload(
            {"tasks": [_task("root", "baseline", metrics=["利润"])]}
        )

        with self.assertRaises(AnalysisPlanClarificationRequired) as raised:
            validate_analysis_plan(candidate, self.catalog)

        self.assertEqual(raised.exception.reason, "METRIC_NOT_UNIQUE")

    def test_unknown_dimension_cannot_answer(self) -> None:
        candidate = plan_from_payload(
            {
                "tasks": [
                    _task(
                        "root",
                        "breakdown",
                        dimensions=["未知维度"],
                    )
                ]
            }
        )

        with self.assertRaises(AnalysisPlanCannotAnswer) as raised:
            validate_analysis_plan(candidate, self.catalog)

        self.assertEqual(raised.exception.reason, "DIMENSION_NOT_FOUND")

    def test_duplicate_and_cyclic_dependencies_are_rejected(self) -> None:
        duplicate = plan_from_payload(
            {
                "tasks": [
                    _task("same", "baseline"),
                    _task("same", "baseline"),
                ]
            }
        )
        with self.assertRaisesRegex(AnalysisPlanCannotAnswer, "Task ID"):
            validate_analysis_plan(duplicate, self.catalog)

        cyclic = plan_from_payload(
            {
                "tasks": [
                    _task("a", "baseline", depends_on=["b"]),
                    _task("b", "baseline", depends_on=["a"]),
                ]
            }
        )
        with self.assertRaisesRegex(AnalysisPlanCannotAnswer, "循环"):
            validate_analysis_plan(cyclic, self.catalog)

    def test_depth_and_task_limits_are_checked_before_execution(self) -> None:
        tasks = [_task("root", "baseline")]
        previous = "root"
        for index in range(1, MAX_ANALYSIS_DEPTH + 2):
            task_id = f"level-{index}"
            tasks.append(_task(task_id, "breakdown", depends_on=[previous]))
            previous = task_id
        with self.assertRaisesRegex(AnalysisPlanCannotAnswer, "下钻深度"):
            validate_analysis_plan(
                plan_from_payload({"tasks": tasks}),
                self.catalog,
            )

        too_many = [
            _task(f"task-{index}", "baseline")
            for index in range(MAX_ANALYSIS_TASKS + 1)
        ]
        with self.assertRaisesRegex(AnalysisPlanCannotAnswer, "Task 数量"):
            validate_analysis_plan(
                plan_from_payload({"tasks": too_many}),
                self.catalog,
            )

    def test_plan_contract_rejects_physical_sql_and_unknown_fields(self) -> None:
        payload = {"tasks": [_task("root", "baseline")]}
        payload["sql"] = "SELECT 1"
        with self.assertRaises(AnalysisPlanStructureError):
            plan_from_payload(payload)

        task = _task("root", "baseline")
        task["sql"] = "SELECT 1"
        with self.assertRaises(AnalysisPlanStructureError):
            plan_from_payload({"tasks": [task]})

    def test_plan_contract_rejects_non_string_enum_values(self) -> None:
        task = _task("root", "baseline")
        task["task_type"] = []
        with self.assertRaises(AnalysisPlanStructureError):
            plan_from_payload({"tasks": [task]})

        task = _task("root", "baseline")
        task["time_range"] = {"text": "本月", "granularity": []}
        with self.assertRaises(AnalysisPlanStructureError):
            plan_from_payload({"tasks": [task]})


def _task(
    task_id: str,
    task_type: str,
    *,
    metrics: list[str] | None = None,
    dimensions: list[str] | None = None,
    depends_on: list[str] | None = None,
    expected_output: str = "结果",
) -> dict[str, object]:
    return {
        "task_id": task_id,
        "task_type": task_type,
        "description": "查询业务指标",
        "metrics": metrics or ["销售额"],
        "dimensions": dimensions or [],
        "time_range": None,
        "filters": [],
        "depends_on": depends_on or [],
        "expected_output": expected_output,
    }


if __name__ == "__main__":
    unittest.main()
