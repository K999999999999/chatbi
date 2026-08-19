"""POC SQL Generator（SQL 生成器）实现。

默认提供一个无需外部模型的规则基线，便于先验证数据库结构、指标口径和执行链路。
同时提供一个可选的 HTTP Chat Completion 适配器；它只产生候选 SQL，不能绕过 SQL Guard。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.poc.context import PromptContext


class SqlGenerationError(RuntimeError):
    """SQL 候选生成失败。"""


class SqlGenerator(Protocol):
    """SQL 生成器的最小替换接口。"""

    def generate(self, context: PromptContext) -> str:
        """根据上下文生成一条 SQL 候选。"""


@dataclass(frozen=True)
class _Dimension:
    key: str
    select_expression: str
    group_expression: str
    order_expression: str
    join_clause: str


class RuleBasedSqlGenerator:
    """面向当前 5 个指标和固定维度的确定性 SQL 基线。

    它不是最终的自然语言理解方案，而是用于先证明：结构目录、指标文件、SQL Guard
    和真实数据库执行之间的契约可以闭环。后续可以把它替换成 LLM 适配器。
    """

    _METRIC_EXPRESSIONS = {
        "sales_quantity": "SUM(f.quantity) AS sales_quantity",
        "sales_revenue": "SUM(f.net_sales_amount_cny) AS sales_revenue",
        "sales_cost": "SUM(f.sales_cost_amount_cny) AS sales_cost",
        "gross_profit": (
            "SUM(f.net_sales_amount_cny) - SUM(f.sales_cost_amount_cny) "
            "AS gross_profit"
        ),
        "gross_margin": (
            "(SUM(f.net_sales_amount_cny) - SUM(f.sales_cost_amount_cny)) "
            "/ NULLIF(SUM(f.net_sales_amount_cny), 0) AS gross_margin"
        ),
    }

    def generate(self, context: PromptContext) -> str:
        metric_code = context.metric.metric_code
        try:
            metric_expression = self._METRIC_EXPRESSIONS[metric_code]
        except KeyError as exc:
            raise SqlGenerationError(f"规则基线不支持指标：{metric_code}") from exc

        dimensions = _detect_dimensions(context.question)
        date_filter = _detect_date_filter(context.question)
        date_group = _detect_date_group(context.question)
        if date_group and not any(item.key == "date" for item in dimensions):
            dimensions.append(date_group)

        select_parts = [item.select_expression for item in dimensions]
        select_parts.append(metric_expression)
        join_clauses = []
        if date_filter and not any(item.key == "date" for item in dimensions):
            join_clauses.append(_date_dimension().join_clause)
        for item in dimensions:
            if item.join_clause not in join_clauses:
                join_clauses.append(item.join_clause)
        where_parts = ["f.order_status = 'completed'"]
        if date_filter:
            where_parts.extend(date_filter)

        lines = ["SELECT"]
        lines.extend(
            _indent(item, comma=(index < len(select_parts) - 1))
            for index, item in enumerate(select_parts)
        )
        lines.append("FROM mart_sales.fct_sales_order_line AS f")
        lines.extend(join_clauses)
        lines.append("WHERE")
        lines.extend(
            _where_indent(item, add_and=index > 0)
            for index, item in enumerate(where_parts)
        )

        group_parts = [item.group_expression for item in dimensions]
        if group_parts:
            lines.append("GROUP BY")
            lines.extend(
                _indent(item, comma=(index < len(group_parts) - 1))
                for index, item in enumerate(group_parts)
            )
            lines.append("ORDER BY")
            lines.extend(
                _indent(item.order_expression, comma=(index < len(group_parts) - 1))
                for index, item in enumerate(dimensions)
            )
        return "\n".join(lines)


class HttpChatCompletionSqlGenerator:
    """可选的 Chat Completion（对话补全）HTTP 适配器。

    配置从环境变量读取，不把 API Key 写入仓库。默认不启用；只有显式选择该适配器时
    才会发起网络请求。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key:
            raise SqlGenerationError("缺少 LLM_API_KEY，不能启用 HTTP SQL 生成器")
        if not base_url:
            raise SqlGenerationError("缺少 LLM_BASE_URL，不能启用 HTTP SQL 生成器")
        if not model:
            raise SqlGenerationError("缺少 LLM_MODEL，不能启用 HTTP SQL 生成器")
        self.api_key = api_key
        self.endpoint = _completion_endpoint(base_url)
        self.model = model
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_environment(cls) -> "HttpChatCompletionSqlGenerator":
        timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
        return cls(
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=os.getenv("LLM_BASE_URL", ""),
            model=os.getenv("LLM_MODEL", ""),
            timeout_seconds=timeout,
        )

    def generate(self, context: PromptContext) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": "Return only one read-only PostgreSQL SELECT statement.",
                    },
                    {"role": "user", "content": context.render_prompt()},
                ],
            }
        ).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raise SqlGenerationError(
                f"LLM 请求失败，HTTP 状态码：{exc.code}"
            ) from exc
        except URLError as exc:
            raise SqlGenerationError("LLM 请求无法连接") from exc
        except TimeoutError as exc:
            raise SqlGenerationError("LLM 请求超时") from exc

        try:
            body = json.loads(raw)
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise SqlGenerationError("LLM 响应缺少可用 SQL 内容") from exc
        if not isinstance(content, str) or not content.strip():
            raise SqlGenerationError("LLM 返回了空 SQL")
        return clean_sql_output(content)


def clean_sql_output(raw_sql: str) -> str:
    """去除模型常见的 Markdown 代码围栏，不放宽 SQL Guard。"""

    cleaned = raw_sql.strip()
    cleaned = re.sub(r"^```(?:sql|postgresql)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _detect_dimensions(question: str) -> list[_Dimension]:
    dimensions: list[_Dimension] = []
    if "产品线" in question:
        dimensions.append(
            _Dimension(
                key="product_line",
                select_expression="p.product_line AS product_line",
                group_expression="p.product_line",
                order_expression="p.product_line",
                join_clause=(
                    "JOIN mart_sales.dim_product AS p "
                    "ON f.product_key = p.product_key"
                ),
            )
        )
    if "产品类别" in question or "产品分类" in question:
        dimensions.append(
            _Dimension(
                key="product_category",
                select_expression="p.product_category AS product_category",
                group_expression="p.product_category",
                order_expression="p.product_category",
                join_clause=(
                    "JOIN mart_sales.dim_product AS p "
                    "ON f.product_key = p.product_key"
                ),
            )
        )
    if "技术路线" in question:
        dimensions.append(
            _Dimension(
                key="technology_route",
                select_expression="p.technology_route AS technology_route",
                group_expression="p.technology_route",
                order_expression="p.technology_route",
                join_clause=(
                    "JOIN mart_sales.dim_product AS p "
                    "ON f.product_key = p.product_key"
                ),
            )
        )
    if "客户类型" in question:
        dimensions.append(
            _Dimension(
                key="customer_type",
                select_expression="c.customer_type AS customer_type",
                group_expression="c.customer_type",
                order_expression="c.customer_type",
                join_clause=(
                    "JOIN mart_sales.dim_customer AS c "
                    "ON f.customer_key = c.customer_key"
                ),
            )
        )
    if "客户区域" in question or "客户大区" in question:
        dimensions.append(
            _Dimension(
                key="customer_region",
                select_expression="c.customer_region AS customer_region",
                group_expression="c.customer_region",
                order_expression="c.customer_region",
                join_clause=(
                    "JOIN mart_sales.dim_customer AS c "
                    "ON f.customer_key = c.customer_key"
                ),
            )
        )
    if "国家" in question:
        dimensions.append(
            _Dimension(
                key="country",
                select_expression="c.country AS country",
                group_expression="c.country",
                order_expression="c.country",
                join_clause=(
                    "JOIN mart_sales.dim_customer AS c "
                    "ON f.customer_key = c.customer_key"
                ),
            )
        )
    if "销售区域" in question or "销售大区" in question:
        dimensions.append(
            _Dimension(
                key="sales_region",
                select_expression="r.sales_region_name AS sales_region_name",
                group_expression="r.sales_region_name",
                order_expression="r.sales_region_name",
                join_clause=(
                    "JOIN mart_sales.dim_sales_region AS r "
                    "ON f.sales_region_key = r.sales_region_key"
                ),
            )
        )

    if ("区域" in question or "大区" in question) and not any(
        marker in question
        for marker in ("客户区域", "客户大区", "销售区域", "销售大区")
    ):
        raise SqlGenerationError("请明确使用客户区域或销售区域")
    return _deduplicate_dimensions(dimensions)


def _detect_date_filter(question: str) -> list[str] | None:
    year_match = re.search(r"(20\d{2})\s*年", question)
    relative_terms = ("最近", "本月", "上月", "今年", "去年", "本季度", "上季度")
    if not year_match:
        if any(term in question for term in relative_terms):
            raise SqlGenerationError("规则基线只支持明确年份，请暂时使用 YYYY 年查询")
        return None

    year = int(year_match.group(1))
    quarter_match = re.search(r"(?:第\s*)?([1-4])\s*季度|Q([1-4])", question, re.IGNORECASE)
    if quarter_match:
        quarter = int(quarter_match.group(1) or quarter_match.group(2))
        start_month = (quarter - 1) * 3 + 1
        start = date(year, start_month, 1)
        end = date(year + 1, 1, 1) if quarter == 4 else date(year, start_month + 3, 1)
        return _date_bounds(start, end)

    month_match = re.search(r"(1[0-2]|[1-9])\s*月", question)
    if month_match:
        month = int(month_match.group(1))
        start = date(year, month, 1)
        end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        return _date_bounds(start, end)

    return _date_bounds(date(year, 1, 1), date(year + 1, 1, 1))


def _detect_date_group(question: str) -> _Dimension | None:
    if any(term in question for term in ("按月", "按月份", "每月", "各月")):
        return _date_dimension("month")
    if any(term in question for term in ("按季度", "每季度", "各季度")):
        return _date_dimension("quarter")
    if any(term in question for term in ("按年", "每年", "各年份")):
        return _date_dimension("year")
    return None


def _date_dimension(group: str | None = None) -> _Dimension:
    if group == "month":
        return _Dimension(
            key="date",
            select_expression="d.year AS year, d.month AS month",
            group_expression="d.year, d.month",
            order_expression="d.year, d.month",
            join_clause=(
                "JOIN mart_sales.dim_date AS d "
                "ON f.completion_date_key = d.date_key"
            ),
        )
    if group == "quarter":
        return _Dimension(
            key="date",
            select_expression="d.year AS year, d.quarter AS quarter",
            group_expression="d.year, d.quarter",
            order_expression="d.year, d.quarter",
            join_clause=(
                "JOIN mart_sales.dim_date AS d "
                "ON f.completion_date_key = d.date_key"
            ),
        )
    if group == "year":
        return _Dimension(
            key="date",
            select_expression="d.year AS year",
            group_expression="d.year",
            order_expression="d.year",
            join_clause=(
                "JOIN mart_sales.dim_date AS d "
                "ON f.completion_date_key = d.date_key"
            ),
        )
    return _Dimension(
        key="date",
        select_expression="d.full_date AS full_date",
        group_expression="d.full_date",
        order_expression="d.full_date",
        join_clause=(
            "JOIN mart_sales.dim_date AS d "
            "ON f.completion_date_key = d.date_key"
        ),
    )


def _date_bounds(start: date, end: date) -> list[str]:
    return [
        f"d.full_date >= DATE '{start.isoformat()}'",
        f"d.full_date < DATE '{end.isoformat()}'",
    ]


def _deduplicate_dimensions(dimensions: list[_Dimension]) -> list[_Dimension]:
    result: list[_Dimension] = []
    seen: set[str] = set()
    for dimension in dimensions:
        if dimension.key not in seen:
            result.append(dimension)
            seen.add(dimension.key)
    return result


def _indent(value: str, comma: bool) -> str:
    return f"  {value}{',' if comma else ''}"


def _where_indent(value: str, add_and: bool) -> str:
    return f"  {'AND ' if add_and else ''}{value}"


def _completion_endpoint(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/chat/completions") else normalized + "/chat/completions"
