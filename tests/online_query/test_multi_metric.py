"""Multi-Metric Retrieval（多指标检索）确定性请求规划测试。"""

from types import MappingProxyType
import unittest

from src.online_query.contracts import (
    FallbackPolicy,
    MetricPlanStatus,
    RequestShape,
)
from src.online_query.multi_metric import (
    build_retrieval_request,
    classify_request_shape,
    plan_multi_metric_request,
)
from src.online_query.rag_runtime import MetricCatalog, MetricCatalogEntry


class MultiMetricPlanningTest(unittest.TestCase):
    def test_explicit_multi_shape_is_fail_closed(self) -> None:
        request = build_retrieval_request(
            "按客户类型统计已完成订单数、人民币销售额和毛利率"
        )

        self.assertEqual(request.request_shape, RequestShape.EXPLICIT_MULTI)
        self.assertEqual(request.fallback_policy, FallbackPolicy.FAIL_CLOSED)

    def test_grouping_list_and_text_match_are_not_multi_metric(self) -> None:
        cases = (
            "查询客户类型和销售区域",
            "客户名称中包含毛利率和销售额",
            "按客户类型和销售区域统计毛利率",
        )

        for question in cases:
            with self.subTest(question=question):
                self.assertEqual(
                    classify_request_shape(question),
                    RequestShape.BASELINE,
                )

    def test_unsupported_or_separate_scope_is_possible_multi(self) -> None:
        cases = (
            "不要销售额和毛利率",
            "分别查询销售额和毛利率",
            "3月销售额和4月毛利率",
        )

        for question in cases:
            with self.subTest(question=question):
                request = build_retrieval_request(question)
                self.assertEqual(request.request_shape, RequestShape.POSSIBLE_MULTI)
                self.assertEqual(
                    request.fallback_policy,
                    FallbackPolicy.FAIL_CLOSED,
                )

    def test_c05_maps_aliases_and_preserves_user_order(self) -> None:
        catalog = _catalog(
            _entry("已完成订单数"),
            _entry("人民币净销售额", aliases=("销售额", "人民币销售额")),
            _entry("毛利率", aliases=("毛利润率",)),
        )
        request = build_retrieval_request(
            "按客户类型统计已完成订单数、人民币销售额和毛利率"
        )

        plan = plan_multi_metric_request(request, catalog)

        self.assertEqual(plan.status, MetricPlanStatus.SUCCESS)
        self.assertEqual(
            [constraint.metric_name for constraint in plan.constraints],
            ["已完成订单数", "人民币净销售额", "毛利率"],
        )
        self.assertEqual(
            [constraint.requested_text for constraint in plan.constraints],
            ["已完成订单数", "人民币销售额", "毛利率"],
        )
        self.assertEqual(
            [constraint.ordinal for constraint in plan.constraints],
            [1, 2, 3],
        )

    def test_longest_overlap_does_not_swallow_independent_metric(self) -> None:
        catalog = _catalog(
            _entry("人民币毛利", aliases=("毛利",)),
            _entry("毛利率"),
        )
        request = build_retrieval_request("毛利和毛利率")

        plan = plan_multi_metric_request(request, catalog)

        self.assertEqual(plan.status, MetricPlanStatus.SUCCESS)
        self.assertEqual(
            [constraint.metric_name for constraint in plan.constraints],
            ["人民币毛利", "毛利率"],
        )

    def test_aliases_for_same_metric_are_deduplicated(self) -> None:
        catalog = _catalog(
            _entry("人民币净销售额", aliases=("销售额", "人民币销售额")),
        )
        request = build_retrieval_request("查询销售额和人民币销售额")

        plan = plan_multi_metric_request(request, catalog)

        self.assertEqual(plan.status, MetricPlanStatus.SUCCESS)
        self.assertEqual(len(plan.mentions), 2)
        self.assertEqual(len(plan.constraints), 1)
        self.assertEqual(plan.constraints[0].metric_name, "人民币净销售额")

    def test_unknown_list_item_rejects_whole_plan(self) -> None:
        catalog = _catalog(
            _entry("人民币净销售额", aliases=("销售额",)),
        )
        request = build_retrieval_request("查询销售额和未登记退货率")

        plan = plan_multi_metric_request(request, catalog)

        self.assertEqual(plan.status, MetricPlanStatus.NO_METRIC)
        self.assertIn("未登记退货率", plan.reason)

    def test_more_than_five_distinct_metrics_is_rejected(self) -> None:
        entries = tuple(_entry(f"测试指标{index}数") for index in range(1, 7))
        catalog = _catalog(*entries)
        request = build_retrieval_request(
            "查询" + "、".join(entry.metric_name for entry in entries)
        )

        plan = plan_multi_metric_request(request, catalog)

        self.assertEqual(plan.status, MetricPlanStatus.TOO_MANY)

    def test_filter_order_and_alias_differences_are_compatible(self) -> None:
        first = _entry(
            "指标一数",
            filters=("f.order_status = 'completed'", "f.channel = 'direct'"),
        )
        second = _entry(
            "指标二数",
            filters=("x.channel = 'direct'", "x.order_status = 'completed'"),
        )
        request = build_retrieval_request("查询指标一数和指标二数")

        plan = plan_multi_metric_request(request, _catalog(first, second))

        self.assertEqual(plan.status, MetricPlanStatus.SUCCESS)

    def test_source_time_or_filter_conflict_is_unsupported(self) -> None:
        base = _entry("指标一数")
        conflicts = (
            _entry("指标二数", data_source="mart_sales.other_fact"),
            _entry("指标二数", time_field="other.date_key -> dim_date.full_date"),
            _entry("指标二数", filters=("f.order_status = 'pending'",)),
        )

        for conflicting in conflicts:
            with self.subTest(metric=conflicting):
                request = build_retrieval_request("查询指标一数和指标二数")
                plan = plan_multi_metric_request(
                    request,
                    _catalog(base, conflicting),
                )
                self.assertEqual(
                    plan.status,
                    MetricPlanStatus.UNSUPPORTED_COMBINATION,
                )

    def test_invalid_filter_asset_is_reported(self) -> None:
        first = _entry("指标一数")
        second = _entry("指标二数", filters=("not valid =",))
        request = build_retrieval_request("查询指标一数和指标二数")

        plan = plan_multi_metric_request(request, _catalog(first, second))

        self.assertEqual(plan.status, MetricPlanStatus.INVALID_ASSET)

    def test_baseline_request_does_not_create_multi_plan(self) -> None:
        request = build_retrieval_request("只查询毛利率")

        plan = plan_multi_metric_request(request, _catalog(_entry("毛利率")))

        self.assertEqual(plan.status, MetricPlanStatus.NOT_MULTI)
        self.assertEqual(request.fallback_policy, FallbackPolicy.FAIL_CLOSED)


def _entry(
    name: str,
    *,
    aliases: tuple[str, ...] = (),
    formula: str = "SUM(f.net_sales_amount_cny)",
    data_source: str = "mart_sales.fct_sales_order_line",
    time_field: str = (
        "fct_sales_order_line.completion_date_key -> dim_date.full_date"
    ),
    filters: tuple[str, ...] = ("f.order_status = 'completed'",),
) -> MetricCatalogEntry:
    document_id = f"metric:{name}"
    payload = MappingProxyType(
        {
            "document_id": document_id,
            "metric_name": name,
        }
    )
    return MetricCatalogEntry(
        document_id=document_id,
        metric_name=name,
        aliases=aliases,
        formula=formula,
        data_source=data_source,
        time_field=time_field,
        filters=filters,
        depends_on=(),
        page_content=f"指标名：{name}",
        payload=payload,
    )


def _catalog(*entries: MetricCatalogEntry) -> MetricCatalog:
    by_document = {entry.document_id: entry for entry in entries}
    by_label = {}
    for entry in entries:
        for label in (entry.metric_name, *entry.aliases):
            by_label[label.casefold()] = entry
    return MetricCatalog(
        entries=entries,
        by_document_id=MappingProxyType(by_document),
        by_label=MappingProxyType(by_label),
    )


if __name__ == "__main__":
    unittest.main()
