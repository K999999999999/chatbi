"""产品级期间变化归因的确定性计算。"""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Final

from .contracts import AnalysisRequest
from .execution import TaskResult, TaskStatus

_RECONCILIATION_TOLERANCE: Final = Decimal("0.000001")
_DISPLAY_QUANTUM: Final = Decimal("0.01")
_MONEY_COLUMNS: Final = {
    "人民币净销售额": frozenset(
        {
            "人民币净销售额",
            "净销售额",
            "人民币销售额",
            "销售额",
            "net_sales_cny",
            "net_sales_amount_cny",
        }
    ),
    "已完成销售数量": frozenset(
        {
            "已完成销售数量",
            "销售数量",
            "销量",
            "completed_sales_quantity",
            "sales_quantity",
            "quantity",
        }
    ),
    "人民币销售成本": frozenset(
        {
            "人民币销售成本",
            "销售成本",
            "人民币成本",
            "成本",
            "sales_cost_cny",
            "sales_cost_amount_cny",
        }
    ),
    "人民币毛利": frozenset(
        {
            "人民币毛利",
            "毛利",
            "人民币毛利润",
            "gross_profit_cny",
        }
    ),
}
_PRODUCT_COLUMNS: Final = frozenset({"产品", "产品名称", "product", "product_name"})


class AttributionError(ValueError):
    """输入证据不足、结构无效或贡献无法对账。"""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class FactorContribution:
    name: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class ProductContribution:
    product_name: str
    change: Decimal
    classification: str
    factors: tuple[FactorContribution, ...]


@dataclass(frozen=True, slots=True)
class BusinessAnalysisAttribution:
    metric_name: str
    current_period: str
    comparison_period: str
    comparison_value: Decimal
    current_value: Decimal
    total_change: Decimal
    products: tuple[ProductContribution, ...]
    top_products: tuple[ProductContribution, ...]

    @property
    def direction(self) -> str:
        if self.total_change > 0:
            return "increase"
        if self.total_change < 0:
            return "decrease"
        return "unchanged"

    def to_payload(self) -> dict[str, object]:
        """返回序列化友好的权威数值和程序选出的主要产品。"""

        return {
            "metric_name": self.metric_name,
            "comparison_period": self.comparison_period,
            "current_period": self.current_period,
            "comparison_value": _decimal_text(self.comparison_value),
            "current_value": _decimal_text(self.current_value),
            "total_change": _decimal_text(self.total_change),
            "direction": self.direction,
            "products": [
                {
                    "product_name": product.product_name,
                    "change": _decimal_text(product.change),
                    "effect_on_metric": _metric_effect(product.change),
                    "classification": product.classification,
                    "factors": [
                        {
                            "name": factor.name,
                            "amount": _decimal_text(factor.amount),
                            "effect_on_metric": _metric_effect(factor.amount),
                        }
                        for factor in product.factors
                    ],
                }
                for product in self.top_products
            ],
            "omitted_product_count": len(self.products) - len(self.top_products),
            "reconciliation_passed": True,
        }


@dataclass(frozen=True, slots=True)
class _ProductPeriod:
    net_sales: Decimal
    quantity: Decimal
    sales_cost: Decimal | None

    @property
    def gross_profit(self) -> Decimal | None:
        if self.sales_cost is None:
            return None
        return self.net_sales - self.sales_cost


def calculate_product_attribution(
    request: AnalysisRequest,
    task_results: tuple[TaskResult, ...],
) -> BusinessAnalysisAttribution:
    """读取固定 Task 结果、确定性拆分因素并验证所有层级对账。"""

    if request.metric_name not in {"人民币毛利", "人民币净销售额"}:
        raise AttributionError("目标指标不在归因范围内", reason="METRIC_UNSUPPORTED")
    results = {result.task_id: result for result in task_results}
    expected_ids = (
        "comparison-overall",
        "current-overall",
        "comparison-products",
        "current-products",
    )
    if len(results) != len(task_results) or any(
        key not in results for key in expected_ids
    ):
        raise AttributionError("归因 Task 结果不完整", reason="TASK_RESULTS_INCOMPLETE")
    for task_id in expected_ids:
        result = results[task_id]
        if result.status is not TaskStatus.COMPLETED or result.truncated:
            raise AttributionError(
                f"Task {task_id} 未完整成功",
                reason="TASK_RESULT_INCOMPLETE",
            )

    comparison_value = _overall_value(
        results["comparison-overall"],
        request.metric_name,
    )
    current_value = _overall_value(results["current-overall"], request.metric_name)
    comparison_products = _product_values(
        results["comparison-products"],
        request.metric_name,
    )
    current_products = _product_values(
        results["current-products"],
        request.metric_name,
    )
    _reconcile_period(
        comparison_products,
        comparison_value,
        request.metric_name,
        request.comparison_period.text,
    )
    _reconcile_period(
        current_products,
        current_value,
        request.metric_name,
        request.current_period.text,
    )

    product_contributions = tuple(
        _product_contribution(
            name,
            comparison_products.get(name),
            current_products.get(name),
            request.metric_name,
        )
        for name in sorted(set(comparison_products) | set(current_products))
    )
    total_change = current_value - comparison_value
    products_change = sum(
        (product.change for product in product_contributions), start=Decimal(0)
    )
    if abs(products_change - total_change) > _RECONCILIATION_TOLERANCE:
        raise AttributionError(
            "所有产品贡献无法与整体指标变化对账",
            reason="TOTAL_CHANGE_RECONCILIATION_FAILED",
        )
    top_products = _top_products(product_contributions, total_change)
    return BusinessAnalysisAttribution(
        metric_name=request.metric_name,
        current_period=request.current_period.text,
        comparison_period=request.comparison_period.text,
        comparison_value=comparison_value,
        current_value=current_value,
        total_change=total_change,
        products=product_contributions,
        top_products=top_products,
    )


def _overall_value(result: TaskResult, metric_name: str) -> Decimal:
    if len(result.columns) != 1 or len(result.rows) != 1 or len(result.rows[0]) != 1:
        raise AttributionError(
            f"整体指标 Task {result.task_id} 应返回一个数值",
            reason="OVERALL_RESULT_SHAPE_INVALID",
        )
    return _decimal(result.rows[0][0], result.task_id)


def _product_values(
    result: TaskResult,
    metric_name: str,
) -> dict[str, _ProductPeriod]:
    expected_metrics = (
        ("人民币净销售额", "已完成销售数量", "人民币销售成本")
        if metric_name == "人民币毛利"
        else ("人民币净销售额", "已完成销售数量")
    )
    indexes: dict[str, int] = {}
    product_index: int | None = None
    for index, column in enumerate(result.columns):
        normalized = _normalize_column(column)
        if normalized in {_normalize_column(item) for item in _PRODUCT_COLUMNS}:
            if product_index is not None:
                raise AttributionError(
                    f"产品 Task {result.task_id} 返回多个产品列",
                    reason="PRODUCT_COLUMN_AMBIGUOUS",
                )
            product_index = index
        for name in expected_metrics:
            aliases = _MONEY_COLUMNS[name]
            if normalized in {_normalize_column(alias) for alias in aliases}:
                if name in indexes:
                    raise AttributionError(
                        f"产品 Task {result.task_id} 的 {name} 列重复",
                        reason="METRIC_COLUMN_AMBIGUOUS",
                    )
                indexes[name] = index
    if product_index is None or set(indexes) != set(expected_metrics):
        raise AttributionError(
            f"产品 Task {result.task_id} 缺少产品或归因指标列",
            reason="PRODUCT_RESULT_COLUMNS_INVALID",
        )

    products: dict[str, _ProductPeriod] = {}
    for row in result.rows:
        if len(row) != len(result.columns):
            raise AttributionError(
                f"产品 Task {result.task_id} 的返回行宽度不一致",
                reason="PRODUCT_RESULT_SHAPE_INVALID",
            )
        raw_name = row[product_index]
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise AttributionError(
                f"产品 Task {result.task_id} 的产品名称为空",
                reason="PRODUCT_NAME_INVALID",
            )
        name = raw_name.strip()
        net_sales = _decimal(row[indexes["人民币净销售额"]], result.task_id)
        quantity = _decimal(row[indexes["已完成销售数量"]], result.task_id)
        sales_cost = (
            _decimal(row[indexes["人民币销售成本"]], result.task_id)
            if "人民币销售成本" in indexes
            else None
        )
        if quantity <= 0:
            raise AttributionError(
                f"产品 {name} 的销售数量必须大于零",
                reason="PRODUCT_QUANTITY_INVALID",
            )
        current = _ProductPeriod(net_sales, quantity, sales_cost)
        if name in products:
            previous = products[name]
            if previous.sales_cost is None or current.sales_cost is None:
                combined_cost = None
            else:
                combined_cost = previous.sales_cost + current.sales_cost
            products[name] = _ProductPeriod(
                net_sales=previous.net_sales + current.net_sales,
                quantity=previous.quantity + current.quantity,
                sales_cost=combined_cost,
            )
        else:
            products[name] = current
    return products


def _reconcile_period(
    products: dict[str, _ProductPeriod],
    overall_value: Decimal,
    metric_name: str,
    period: str,
) -> None:
    if metric_name == "人民币毛利":
        product_total = sum(
            (value.gross_profit or Decimal(0) for value in products.values()),
            start=Decimal(0),
        )
    else:
        product_total = sum(
            (value.net_sales for value in products.values()),
            start=Decimal(0),
        )
    if abs(product_total - overall_value) > _RECONCILIATION_TOLERANCE:
        raise AttributionError(
            f"{period} 产品汇总与整体指标不一致",
            reason="PERIOD_TOTAL_RECONCILIATION_FAILED",
        )


def _product_contribution(
    product_name: str,
    comparison: _ProductPeriod | None,
    current: _ProductPeriod | None,
    metric_name: str,
) -> ProductContribution:
    if comparison is None:
        change = _period_metric(current, metric_name)
        return ProductContribution(
            product_name,
            change,
            "new_product",
            (FactorContribution("新品进入", change),),
        )
    if current is None:
        change = -_period_metric(comparison, metric_name)
        return ProductContribution(
            product_name,
            change,
            "exited_product",
            (FactorContribution("产品退出", change),),
        )

    old_price = comparison.net_sales / comparison.quantity
    new_price = current.net_sales / current.quantity
    mean_quantity = (comparison.quantity + current.quantity) / Decimal(2)
    if metric_name == "人民币净销售额":
        factors = (
            FactorContribution(
                "实际成交单价",
                (new_price - old_price) * mean_quantity,
            ),
            FactorContribution(
                "销量",
                (current.quantity - comparison.quantity)
                * (old_price + new_price)
                / Decimal(2),
            ),
        )
    else:
        if comparison.sales_cost is None or current.sales_cost is None:
            raise AttributionError(
                f"产品 {product_name} 缺少单位成本输入",
                reason="PRODUCT_COST_MISSING",
            )
        old_unit_cost = comparison.sales_cost / comparison.quantity
        new_unit_cost = current.sales_cost / current.quantity
        factors = (
            FactorContribution(
                "实际成交单价",
                (new_price - old_price) * mean_quantity,
            ),
            FactorContribution(
                "销量",
                (current.quantity - comparison.quantity)
                * ((old_price - old_unit_cost) + (new_price - new_unit_cost))
                / Decimal(2),
            ),
            FactorContribution(
                "单位成本",
                -(new_unit_cost - old_unit_cost) * mean_quantity,
            ),
        )
    change = _period_metric(current, metric_name) - _period_metric(
        comparison,
        metric_name,
    )
    factor_total = sum((factor.amount for factor in factors), start=Decimal(0))
    if abs(factor_total - change) > _RECONCILIATION_TOLERANCE:
        raise AttributionError(
            f"产品 {product_name} 的因素贡献无法对账",
            reason="PRODUCT_FACTOR_RECONCILIATION_FAILED",
        )
    return ProductContribution(product_name, change, "continuing", factors)


def _period_metric(value: _ProductPeriod | None, metric_name: str) -> Decimal:
    if value is None:
        return Decimal(0)
    if metric_name == "人民币毛利":
        gross_profit = value.gross_profit
        if gross_profit is None:
            raise AttributionError("产品缺少销售成本", reason="PRODUCT_COST_MISSING")
        return gross_profit
    return value.net_sales


def _top_products(
    products: tuple[ProductContribution, ...],
    total_change: Decimal,
) -> tuple[ProductContribution, ...]:
    if total_change > 0:
        selected = (item for item in products if item.change > 0)
        ordered = sorted(selected, key=lambda item: (-item.change, item.product_name))
    elif total_change < 0:
        selected = (item for item in products if item.change < 0)
        ordered = sorted(selected, key=lambda item: (item.change, item.product_name))
    else:
        ordered = []
    return tuple(ordered[:3])


def _normalize_column(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", value.casefold())


def _decimal(value: object, task_id: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise AttributionError(
            f"Task {task_id} 返回了无效数值",
            reason="NUMERIC_VALUE_INVALID",
        )
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise AttributionError(
            f"Task {task_id} 返回了无效数值",
            reason="NUMERIC_VALUE_INVALID",
        ) from None
    if not result.is_finite():
        raise AttributionError(
            f"Task {task_id} 返回了非有限数值",
            reason="NUMERIC_VALUE_INVALID",
        )
    return result


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _metric_effect(value: Decimal) -> str:
    if value > 0:
        return "increases_target_metric"
    if value < 0:
        return "decreases_target_metric"
    return "no_change_to_target_metric"


def format_money(value: Decimal) -> str:
    rounded = value.quantize(_DISPLAY_QUANTUM, rounding=ROUND_HALF_UP)
    return f"{rounded:,.2f} 元"
