"""R3 历史恢复允许的多指标日历表达式必须由语义 Guard 收口。"""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from src.online_query.context import load_query_context
from src.online_query.contracts import MetricConstraint
from src.online_query.query_understanding import (
    candidate_from_payload,
    validate_candidate,
)
from src.online_query.semantic_state import (
    SemanticCertificationError,
    SemanticSQLMismatch,
    prepare_restoration_state,
    validate_restoration_sql,
)
from src.online_query.sql_guard import SQLRejectedError, validate_sql
from src.online_query.sql_guard.sql_guard import _new_validation_session


ROOT = Path(__file__).resolve().parents[2]
METRIC_NAMES = ("人民币净销售额", "人民币毛利", "毛利率")


def _history_query_context():
    metrics = json.loads((ROOT / "src/semantic/metrics.json").read_text())
    columns = json.loads((ROOT / "src/structure/generated/columns.json").read_text())
    by_name = {metric["name"]: metric for metric in metrics}
    constraints = tuple(
        MetricConstraint(
            ordinal=index,
            requested_text=name,
            document_id=f"metric:{name}",
            metric_name=name,
            formula=by_name[name]["formula"],
            data_source=by_name[name]["data_source"],
            time_field=by_name[name]["time_field"],
            filters=tuple(by_name[name]["filters"]),
            depends_on=tuple(by_name[name]["depends_on"]),
        )
        for index, name in enumerate(METRIC_NAMES, 1)
    )
    return replace(
        load_query_context(),
        metric_constraints=constraints,
        semantic_facts={"metrics": metrics, "columns": columns},
    )


def _month_query():
    candidate = candidate_from_payload(
        {
            "query_type": "metric_analysis",
            "subjects": [],
            "metrics": list(METRIC_NAMES),
            "dimensions": ["月份"],
            "time": {"text": "2025年", "granularity": "year"},
            "filters": [
                {
                    "field_text": "订单状态",
                    "operator": "equals",
                    "values": ["已完成"],
                }
            ],
            "conditions": {
                "order_by": [],
                "row_limit": None,
                "aggregate_filters": [],
                "selection": None,
            },
        },
        require_restorable=True,
    )
    return validate_candidate(candidate, original_question="按月份列出2025年销售额")


def _calendar_sql(month_expression="EXTRACT(MONTH FROM d.full_date)"):
    return f"""
SELECT EXTRACT(YEAR FROM d.full_date) AS result_year,
       {month_expression} AS result_month,
       SUM(f.net_sales_amount_cny) AS net_sales,
       SUM(f.net_sales_amount_cny - f.sales_cost_amount_cny) AS gross_profit,
       SUM(f.net_sales_amount_cny - f.sales_cost_amount_cny)
           / NULLIF(SUM(f.net_sales_amount_cny), 0) AS gross_margin
FROM mart_sales.fct_sales_order_line AS f
LEFT JOIN mart_sales.dim_date AS d
  ON f.completion_date_key = d.date_key
WHERE f.order_status = 'completed' AND d.year = 2025
GROUP BY EXTRACT(YEAR FROM d.full_date), {month_expression}
ORDER BY result_year ASC NULLS LAST, result_month ASC NULLS LAST
""".strip()


def _validate_restorable_sql(sql, context, semantic, state):
    session = _new_validation_session(sql, context, allow_expression_dimensions=True)
    session.validate_candidate_scope()
    validated = session.validate_sql()
    validate_restoration_sql(validated.sql, semantic, state, context)


def test_calendar_expressions_require_restoration_semantic_certification():
    context = _history_query_context()
    semantic, state = prepare_restoration_state(_month_query(), context)
    sql = _calendar_sql()

    with pytest.raises(SQLRejectedError, match="非聚合输出必须是分组字段"):
        validate_sql(sql, context)

    _validate_restorable_sql(sql, context, semantic, state)

    transformed_month = _calendar_sql("LOWER(EXTRACT(MONTH FROM d.full_date))")
    with pytest.raises(SemanticSQLMismatch, match="时间分组缺少完整时期身份"):
        _validate_restorable_sql(transformed_month, context, semantic, state)


def test_unmapped_business_field_is_a_certification_failure():
    context = _history_query_context()
    semantic = replace(_month_query(), dimensions=("未认证字段",))

    with pytest.raises(SemanticCertificationError, match="业务字段没有认证映射"):
        prepare_restoration_state(semantic, context)
