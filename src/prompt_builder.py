"""Prompt Builder（提示词构造器）：组装 Schema、规则、指标和 Few-shot。"""

from __future__ import annotations

from dataclasses import dataclass

from src.semantic import MetricCatalog
from src.structure import StructureCatalog


BUSINESS_RULES = """【关键业务规则】
1. 只查询 mart_sales Schema；不得访问 public、pg_catalog、information_schema 或其他 Schema。
2. 销售事实粒度是 fct_sales_order_line，每一行是一条销售订单明细。
3. 销售额、销量、销售成本、毛利和毛利率默认只统计
   fct_sales_order_line.order_status = 'completed' 的明细。
4. 销售额使用冻结的人民币字段 fct_sales_order_line.net_sales_amount_cny，
   不要重新用交易币种字段计算汇率。
5. 销售成本使用冻结的人民币字段 fct_sales_order_line.sales_cost_amount_cny。
6. 默认时间字段是 fct_sales_order_line.completion_date_key；按日历日期过滤或分组时关联
   mart_sales.dim_date。
7. 维度表必须按照 Schema 中声明的物理外键使用代理键关联，不要凭业务名称猜 Join 条件。
8. 指标定义中的 semantic_expression 是业务知识，不是可以直接粘贴执行的 SQL。
"""


ERROR_GUARDS = """【生成前检查】
1. 只生成一条 PostgreSQL SELECT 语句，不生成 INSERT、UPDATE、DELETE、DDL 或多条语句。
2. 不要使用 SELECT *，所有字段都必须来自给定 Schema。
3. 金额聚合优先使用指标知识中指定的 CNY 字段，不要把交易币种金额与 CNY 金额相加。
4. 有非聚合维度时，SELECT 中的每个非聚合字段都必须出现在 GROUP BY 中。
5. 日期区间使用 >= 起始边界和 < 结束边界，避免跨月、跨季度和跨年边界错误。
6. 如果问题无法由当前 Schema 和指标知识回答，输出 UNSUPPORTED，不要猜表、猜字段或编造 SQL。
"""


FEW_SHOT_EXAMPLES = """【Few-shot 示例】
示例 1
问题：查询 2025 年的销售额
SQL：SELECT SUM(f.net_sales_amount_cny) AS sales_revenue
FROM mart_sales.fct_sales_order_line AS f
JOIN mart_sales.dim_date AS d ON f.completion_date_key = d.date_key
WHERE f.order_status = 'completed'
  AND d.full_date >= DATE '2025-01-01'
  AND d.full_date < DATE '2026-01-01'

示例 2
问题：查询 2025 年各产品线的毛利
SQL：SELECT p.product_line AS product_line,
       SUM(f.net_sales_amount_cny) - SUM(f.sales_cost_amount_cny) AS gross_profit
FROM mart_sales.fct_sales_order_line AS f
JOIN mart_sales.dim_date AS d ON f.completion_date_key = d.date_key
JOIN mart_sales.dim_product AS p ON f.product_key = p.product_key
WHERE f.order_status = 'completed'
  AND d.full_date >= DATE '2025-01-01'
  AND d.full_date < DATE '2026-01-01'
GROUP BY p.product_line

示例 3
问题：查询 2025 年每月的销售额
SQL：SELECT d.year AS year, d.month AS month,
       SUM(f.net_sales_amount_cny) AS sales_revenue
FROM mart_sales.fct_sales_order_line AS f
JOIN mart_sales.dim_date AS d ON f.completion_date_key = d.date_key
WHERE f.order_status = 'completed'
  AND d.full_date >= DATE '2025-01-01'
  AND d.full_date < DATE '2026-01-01'
GROUP BY d.year, d.month
ORDER BY d.year, d.month
"""


@dataclass(frozen=True)
class PromptContext:
    """一轮 LLM SQL 生成所需的完整上下文。"""

    question: str
    structure_text: str
    metric_text: str
    metric_codes: tuple[str, ...] = ()

    def render_messages(self) -> tuple[str, str]:
        """返回教程中的 system message 和 user prompt。"""

        system_message = (
            "你是 ChatBI 的专业 PostgreSQL SQL 生成助手。"
            "你必须依据给定的 Schema 和指标知识生成查询，模型输出是不可信候选，"
            "只能输出一条 SQL 或 UNSUPPORTED。"
        )
        user_prompt = f"""【数据库 Schema】
{self.structure_text}

{BUSINESS_RULES}

【指标知识】
{self.metric_text}

{FEW_SHOT_EXAMPLES}

{ERROR_GUARDS}

【用户问题】
{self.question}

【最终输出要求】
只输出一条 PostgreSQL SELECT 语句，不要 Markdown 代码块、解释、注释或思考过程。
如果当前 Schema 和指标知识不足以回答，严格输出：UNSUPPORTED
"""
        return system_message, user_prompt

    def render_prompt(self) -> str:
        """兼容测试和调试场景，只返回 user prompt。"""

        return self.render_messages()[1]


class PromptBuilder:
    """根据结构目录和指标目录构造直连 LLM 的 Prompt。"""

    def __init__(
        self,
        structure: StructureCatalog,
        metrics: MetricCatalog,
    ) -> None:
        self.structure = structure
        self.metrics = metrics

    def build(self, question: str) -> PromptContext:
        normalized = question.strip()
        if not normalized:
            raise ValueError("用户问题不能为空")
        matched_codes = tuple(
            metric.metric_code for metric in self.metrics.match_question(normalized)
        )
        return PromptContext(
            question=normalized,
            structure_text=self.structure.render_prompt(),
            # 当前只有 5 个指标，全部注入即可；后续指标增多时再做检索裁剪。
            metric_text=self.metrics.render_prompt(self.metrics.metrics),
            metric_codes=matched_codes,
        )
