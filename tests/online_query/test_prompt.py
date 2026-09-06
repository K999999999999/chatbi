"""Prompt（提示词）组装测试。"""

import unittest

from src.online_query.contracts import QueryContext
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


if __name__ == "__main__":
    unittest.main()
