"""Multi-Metric Retrieval（多指标检索）确定性请求规划测试。"""

from types import MappingProxyType
import unittest

from src.online_query.contracts import (
    FallbackPolicy,
    MetricHit,
    MetricPlanStatus,
    RetrievalRequest,
    RequestShape,
)
from src.online_query.query_understanding import (
    QueryType,
    ValidatedSemanticQuery,
)
from src.online_query.retrieval.multi_metric import (
    plan_retrieved_metrics,
)


class MultiMetricPlanningTest(unittest.TestCase):
    def test_explicit_multi_shape_is_fail_closed(self) -> None:
        request = _request(
            "按客户类型统计已完成订单数、人民币销售额和毛利率",
            metrics=("已完成订单数", "人民币销售额", "毛利率"),
        )

        self.assertEqual(request.request_shape, RequestShape.EXPLICIT_MULTI)
        self.assertEqual(request.fallback_policy, FallbackPolicy.FAIL_CLOSED)

    def test_shape_comes_from_structured_metric_count(self) -> None:
        request = _request(
            "查询客户类型和销售区域",
            metrics=("销售额", "毛利率"),
            dimensions=("客户类型", "销售区域"),
        )

        self.assertEqual(request.request_shape, RequestShape.EXPLICIT_MULTI)

    def test_unsupported_multi_scope_is_not_guessed_by_retrieval(self) -> None:
        request = _request(
            "分别查询销售额和毛利率",
            metrics=("销售额", "毛利率"),
        )

        self.assertEqual(request.request_shape, RequestShape.EXPLICIT_MULTI)
        self.assertEqual(request.fallback_policy, FallbackPolicy.FAIL_CLOSED)

    def test_c05_maps_aliases_and_preserves_user_order(self) -> None:
        catalog = _catalog(
            _entry("已完成订单数"),
            _entry("人民币净销售额", aliases=("销售额", "人民币销售额")),
            _entry("毛利率", aliases=("毛利润率",)),
        )
        request = _request(
            "按客户类型统计已完成订单数、人民币销售额和毛利率",
            metrics=("已完成订单数", "人民币销售额", "毛利率"),
        )

        plan = _plan(request, catalog)

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
        request = _request("毛利和毛利率", metrics=("毛利", "毛利率"))

        plan = _plan(request, catalog)

        self.assertEqual(plan.status, MetricPlanStatus.SUCCESS)
        self.assertEqual(
            [constraint.metric_name for constraint in plan.constraints],
            ["人民币毛利", "毛利率"],
        )

    def test_aliases_for_same_metric_are_deduplicated(self) -> None:
        catalog = _catalog(
            _entry("人民币净销售额", aliases=("销售额", "人民币销售额")),
        )
        request = _request(
            "查询销售额和人民币销售额",
            metrics=("销售额", "人民币销售额"),
        )

        plan = _plan(request, catalog)

        self.assertEqual(plan.status, MetricPlanStatus.SUCCESS)
        self.assertEqual(len(plan.mentions), 2)
        self.assertEqual(len(plan.constraints), 1)
        self.assertEqual(plan.constraints[0].metric_name, "人民币净销售额")

    def test_unknown_list_item_rejects_whole_plan(self) -> None:
        catalog = _catalog(
            _entry("人民币净销售额", aliases=("销售额",)),
        )
        request = _request(
            "查询销售额和未登记退货率",
            metrics=("销售额", "未登记退货率"),
        )

        plan = _plan(request, catalog)

        self.assertEqual(plan.status, MetricPlanStatus.NO_METRIC)
        self.assertIn("未登记退货率", plan.reason)

    def test_more_than_five_distinct_metrics_is_rejected(self) -> None:
        entries = tuple(_entry(f"测试指标{index}数") for index in range(1, 7))
        catalog = _catalog(*entries)
        request = _request(
            "查询" + "、".join(entry.metric_name for entry in entries),
            metrics=tuple(entry.metric_name for entry in entries),
        )

        plan = _plan(request, catalog)

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
        request = _request("查询指标一数和指标二数", metrics=("指标一数", "指标二数"))

        plan = _plan(request, _catalog(first, second))

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
                request = _request(
                    "查询指标一数和指标二数",
                    metrics=("指标一数", "指标二数"),
                )
                plan = _plan(request, _catalog(base, conflicting))
                self.assertEqual(
                    plan.status,
                    MetricPlanStatus.UNSUPPORTED_COMBINATION,
                )

    def test_invalid_filter_asset_is_reported(self) -> None:
        first = _entry("指标一数")
        second = _entry("指标二数", filters=("not valid =",))
        request = _request("查询指标一数和指标二数", metrics=("指标一数", "指标二数"))

        plan = _plan(request, _catalog(first, second))

        self.assertEqual(plan.status, MetricPlanStatus.INVALID_ASSET)

    def test_baseline_request_can_resolve_one_metric_from_hits(self) -> None:
        request = _request("只查询毛利率", metrics=("毛利率",))

        plan = _plan(request, _catalog(_entry("毛利率")))

        self.assertEqual(plan.status, MetricPlanStatus.SUCCESS)
        self.assertEqual(len(plan.constraints), 1)
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
) -> MetricHit:
    document_id = f"metric:{name}"
    metadata = MappingProxyType(
        {
            "doc_type": "METRIC",
            "metric_name": name,
            "aliases": aliases,
            "formula": formula,
            "data_source": data_source,
            "time_field": time_field,
            "filters": filters,
            "depends_on": (),
        }
    )
    return MetricHit(
        document_id=document_id,
        metric_name=name,
        score=0.9,
        rank=1,
        metadata=metadata,
        page_content=f"指标名：{name}",
    )


def _catalog(*entries: MetricHit) -> tuple[MetricHit, ...]:
    return entries


def _request(
    question: str,
    *,
    metrics: tuple[str, ...],
    dimensions: tuple[str, ...] = (),
) -> RetrievalRequest:
    query = ValidatedSemanticQuery(
        query_type=(QueryType.METRIC_ANALYSIS if metrics else QueryType.ENTITY_LOOKUP),
        subjects=("业务主题",),
        metrics=metrics,
        dimensions=dimensions,
        time=None,
        filters=(),
        original_question=question,
    )
    return RetrievalRequest(
        question=question,
        request_shape=(
            RequestShape.EXPLICIT_MULTI if len(metrics) >= 2 else RequestShape.BASELINE
        ),
        fallback_policy=FallbackPolicy.FAIL_CLOSED,
        semantic_query=query,
    )


def _plan(
    request: RetrievalRequest,
    catalog: tuple[MetricHit, ...],
):
    assert request.semantic_query is not None
    return plan_retrieved_metrics(
        request,
        tuple(catalog for _ in request.semantic_query.metrics),
    )


if __name__ == "__main__":
    unittest.main()
