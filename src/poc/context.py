"""POC 查询上下文：结构元数据和指标定义的最小组合。"""

from __future__ import annotations

from dataclasses import dataclass

from src.poc.semantic import MetricCatalog, MetricDefinition
from src.poc.structure import StructureCatalog


BUSINESS_RULES = """Business rules:
1. Query only mart_sales tables. Never use public tables.
2. The fact grain is one sales order line.
3. Sales metrics include only fct_sales_order_line.order_status = 'completed'.
4. Sales revenue uses frozen CNY net_sales_amount_cny.
5. Sales cost uses frozen CNY sales_cost_amount_cny.
6. Use completion_date_key for the default sales metric time; join dim_date when filtering or grouping by calendar date.
7. Join dimensions through the physical surrogate-key foreign keys declared in the schema metadata.
8. The semantic expression is business knowledge, not executable SQL text.
"""


@dataclass(frozen=True)
class PromptContext:
    """传给 SQL Generator（SQL 生成器）的完整上下文。"""

    question: str
    metric: MetricDefinition
    structure_text: str
    metric_text: str
    business_rules: str = BUSINESS_RULES

    def render_prompt(self) -> str:
        return f"""You generate one read-only PostgreSQL SELECT statement for ChatBI.
Return SQL only. Do not return Markdown fences, explanations, comments, or multiple statements.
Use only tables and columns from the supplied mart_sales schema.

{self.business_rules}

Metric context:
{self.metric_text}

Database structure:
{self.structure_text}

User question:
{self.question}
"""


class ContextBuilder:
    """根据用户问题匹配一个指标并构造 SQL 上下文。"""

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
        metric = self.metrics.require_single(normalized)
        return PromptContext(
            question=normalized,
            metric=metric,
            structure_text=self.structure.render_prompt(),
            metric_text=self.metrics.render_prompt((metric,)),
        )
