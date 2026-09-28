"""产品级期间变化归因测试。"""

import unittest
from decimal import Decimal

from src.business_analysis.attribution import (
    AttributionError,
    calculate_product_attribution,
)
from src.business_analysis.contracts import AnalysisRequest, AnalysisTimeRange
from src.business_analysis.execution import TaskResult, TaskStatus
from src.online_query.query_understanding import TimeGranularity


class ProductAttributionTest(unittest.TestCase):
    def test_gross_profit_is_split_into_price_quantity_and_unit_cost(self) -> None:
        result = calculate_product_attribution(
            _request("人民币毛利"),
            (
                _overall("comparison-overall", 100),
                _overall("current-overall", 120),
                _products("comparison-products", sales=200, quantity=10, cost=100),
                _products("current-products", sales=240, quantity=12, cost=120),
            ),
        )

        product = result.top_products[0]
        self.assertEqual(result.total_change, Decimal(20))
        self.assertEqual(product.change, Decimal(20))
        self.assertEqual(
            [(item.name, item.amount) for item in product.factors],
            [
                ("实际成交单价", Decimal(0)),
                ("销量", Decimal(20)),
                ("单位成本", Decimal(0)),
            ],
        )
        self.assertTrue(result.to_payload()["reconciliation_passed"])

    def test_sales_attribution_does_not_include_cost(self) -> None:
        result = calculate_product_attribution(
            _request("人民币净销售额"),
            (
                _overall("comparison-overall", 200),
                _overall("current-overall", 240),
                _products("comparison-products", sales=200, quantity=10),
                _products("current-products", sales=240, quantity=12),
            ),
        )

        self.assertEqual(
            [item.name for item in result.top_products[0].factors],
            ["实际成交单价", "销量"],
        )
        self.assertEqual(result.total_change, Decimal(40))

    def test_cost_increase_reduces_gross_profit_and_reconciles(self) -> None:
        result = calculate_product_attribution(
            _request("人民币毛利"),
            (
                _overall("comparison-overall", 100),
                _overall("current-overall", 90),
                _products("comparison-products", sales=200, quantity=10, cost=100),
                _products("current-products", sales=200, quantity=10, cost=110),
            ),
        )

        cost = next(
            item for item in result.top_products[0].factors if item.name == "单位成本"
        )
        self.assertEqual(cost.amount, Decimal(-10))

    def test_new_product_gets_full_entry_contribution(self) -> None:
        result = calculate_product_attribution(
            _request("人民币净销售额"),
            (
                _overall("comparison-overall", 0),
                _overall("current-overall", 30),
                _products("comparison-products", rows=()),
                _products("current-products", rows=(("新品", 30, 3),)),
            ),
        )

        product = result.top_products[0]
        self.assertEqual(product.classification, "new_product")
        self.assertEqual(product.change, Decimal(30))
        self.assertEqual(product.factors[0].name, "新品进入")

    def test_reconciliation_failure_stops_with_specific_reason(self) -> None:
        with self.assertRaises(AttributionError) as raised:
            calculate_product_attribution(
                _request("人民币净销售额"),
                (
                    _overall("comparison-overall", 200),
                    _overall("current-overall", 241),
                    _products("comparison-products", sales=200, quantity=10),
                    _products("current-products", sales=240, quantity=12),
                ),
            )

        self.assertEqual(
            raised.exception.reason,
            "PERIOD_TOTAL_RECONCILIATION_FAILED",
        )

    def test_top_three_are_selected_in_overall_change_direction(self) -> None:
        products_old = (("A", 100, 1), ("B", 100, 1), ("C", 100, 1), ("D", 100, 1))
        products_new = (("A", 90, 1), ("B", 80, 1), ("C", 70, 1), ("D", 140, 1))
        result = calculate_product_attribution(
            _request("人民币净销售额"),
            (
                _overall("comparison-overall", 400),
                _overall("current-overall", 380),
                _products("comparison-products", rows=products_old),
                _products("current-products", rows=products_new),
            ),
        )

        self.assertEqual(
            [item.product_name for item in result.top_products],
            ["C", "B", "A"],
        )


def _request(metric: str) -> AnalysisRequest:
    return AnalysisRequest(
        metric_name=metric,
        current_period=AnalysisTimeRange("2025年3月", TimeGranularity.MONTH),
        comparison_period=AnalysisTimeRange("2025年2月", TimeGranularity.MONTH),
    )


def _overall(task_id: str, value: object) -> TaskResult:
    return TaskResult(
        task_id=task_id,
        status=TaskStatus.COMPLETED,
        columns=("value",),
        rows=((value,),),
        row_count=1,
    )


def _products(
    task_id: str,
    *,
    sales: object = 0,
    quantity: object = 0,
    cost: object | None = None,
    rows: tuple[tuple[object, ...], ...] | None = None,
) -> TaskResult:
    columns = ("产品", "人民币净销售额", "已完成销售数量")
    if cost is not None:
        columns += ("人民币销售成本",)
    if rows is None:
        row = ("标准产品", sales, quantity)
        if cost is not None:
            row += (cost,)
        rows = (row,)
    elif cost is not None:
        raise AssertionError("显式 rows 的成本列由调用者自行提供")
    return TaskResult(
        task_id=task_id,
        status=TaskStatus.COMPLETED,
        columns=columns,
        rows=rows,
        row_count=len(rows),
    )


if __name__ == "__main__":
    unittest.main()
