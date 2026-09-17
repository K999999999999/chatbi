"""Prompt（提示词）组装测试。"""

import unittest

from src.online_query.contracts import (
    MetricConstraint,
    QueryContext,
    RequestShape,
)
from src.online_query.prompt import build_prompt
from src.online_query.query_understanding import (
    candidate_from_payload,
    validate_candidate,
)


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
        self.assertIn("只能使用用户明确请求的分组维度", prompt)
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

    def test_structured_prompt_contains_validated_time_and_filters(self) -> None:
        question = "请查询指定期间的客户销售情况"
        candidate = candidate_from_payload(
            {
                "query_type": "metric_analysis",
                "subjects": ["客户销售"],
                "metrics": ["销售额"],
                "dimensions": ["客户类型"],
                "time": {"text": "2025 年", "granularity": "year"},
                "filters": [
                    {
                        "field_text": "订单状态",
                        "operator": "equals",
                        "values": ["已完成"],
                    }
                ],
            }
        )
        semantic_query = validate_candidate(
            candidate,
            original_question=question,
        )

        prompt = build_prompt(semantic_query, self._context(), question)

        self.assertIn('"query_type":"metric_analysis"', prompt)
        self.assertIn('"metrics":["销售额"]', prompt)
        self.assertIn('"dimensions":["客户类型"]', prompt)
        self.assertIn('"start":"2025-01-01T00:00:00+08:00"', prompt)
        self.assertIn('"end":"2026-01-01T00:00:00+08:00"', prompt)
        self.assertIn('"operator":"equals"', prompt)
        self.assertIn('"values":["已完成"]', prompt)
        self.assertIn(question, prompt)

    def test_structured_prompt_does_not_reparse_or_replace_semantic_fields(self) -> None:
        candidate = candidate_from_payload(
            {
                "query_type": "entity_lookup",
                "subjects": ["客户"],
                "metrics": [],
                "dimensions": ["客户类型"],
                "time": None,
                "filters": [],
            }
        )
        semantic_query = validate_candidate(
            candidate,
            original_question="原始问题",
        )

        prompt = build_prompt(
            semantic_query,
            self._context(),
            "这段原始问题包含销售额，但结构化结果明确没有指标",
        )

        self.assertIn('"metrics":[]', prompt)
        self.assertIn('"query_type":"entity_lookup"', prompt)

    def _context(self) -> QueryContext:
        return QueryContext(
            prompt_context="DYNAMIC CONTEXT",
            allowed_tables=frozenset({"mart_sales.fct_sales_order_line"}),
            allowed_columns={
                "mart_sales.fct_sales_order_line": frozenset({"order_id"})
            },
        )


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
