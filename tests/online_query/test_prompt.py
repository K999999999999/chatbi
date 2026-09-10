"""Prompt（提示词）组装测试。"""

import unittest

from src.online_query.contracts import (
    MetricConstraint,
    QueryContext,
    RequestShape,
)
from src.online_query.prompt import build_prompt


class PromptTest(unittest.TestCase):
    def test_prompt_contains_rules_context_and_question(self) -> None:
        context = QueryContext(
            prompt_context='{"tables": [{"table_name": "fct_sales_order_line"}]}',
            allowed_tables=frozenset({"mart_sales.fct_sales_order_line"}),
            allowed_columns={
                "mart_sales.fct_sales_order_line": frozenset({"order_id"})
            },
        )

        prompt = build_prompt("查询已完成订单数", context)

        self.assertIn("只返回一条可执行的 PostgreSQL SQL", prompt)
        self.assertIn("CANNOT_ANSWER", prompt)
        self.assertIn("不得返回解释、分析过程、Markdown", prompt)
        self.assertIn("fct_sales_order_line", prompt)
        self.assertIn("查询已完成订单数", prompt)

    def test_multi_metric_prompt_requires_complete_ordered_shared_output(self) -> None:
        context = QueryContext(
            prompt_context=(
                "Dynamic Schema: {}"
                "\nIndicator Context: "
                '{"requested_metrics": [{"metric_name": "指标一数"}, '
                '{"metric_name": "指标二数"}]}'
            ),
            allowed_tables=frozenset({"mart_sales.fct_sales_order_line"}),
            allowed_columns={
                "mart_sales.fct_sales_order_line": frozenset({"order_id"})
            },
            request_shape=RequestShape.EXPLICIT_MULTI,
            metric_constraints=(
                _metric_constraint(1, "指标一数"),
                _metric_constraint(2, "指标二数"),
            ),
        )

        prompt = build_prompt("查询指标一数和指标二数", context)

        self.assertIn("按 Indicator Context 中 requested_metrics 的顺序输出全部指标", prompt)
        self.assertIn("严格使用对应的认证 formula 和 filters", prompt)
        self.assertIn("共享同一组用户日期、分组字段和普通筛选条件", prompt)
        self.assertIn("不得为了补齐指标自行加入其他资源", prompt)
        self.assertIn("不要使用 CTE、子查询、窗口函数、HAVING、集合运算或 OR", prompt)


def _metric_constraint(ordinal: int, name: str) -> MetricConstraint:
    return MetricConstraint(
        ordinal=ordinal,
        requested_text=name,
        document_id=f"metric:{name}",
        metric_name=name,
        formula="SUM(f.net_sales_amount_cny)",
        data_source="mart_sales.fct_sales_order_line",
        time_field="fct_sales_order_line.completion_date_key -> dim_date.full_date",
        filters=("f.order_status = 'completed'",),
        depends_on=(),
    )


if __name__ == "__main__":
    unittest.main()
