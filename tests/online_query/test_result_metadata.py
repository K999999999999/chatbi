"""实际查询服务的结果说明认证；外部生成/数据库使用最小固定替身。"""

from decimal import Decimal

import pytest

from src.online_query.context import load_query_context
from src.online_query.contracts import QueryData, QueryRequest, QuerySuccess
from src.online_query.query_understanding import QueryType, ValidatedSemanticQuery
from src.online_query.service import OnlineQueryService


class FixedGenerator:
    def __init__(self, sql):
        self.sql = sql
        self.calls = 0

    def generate(self, prompt):
        self.calls += 1
        return self.sql


class FixedExecutor:
    def __init__(self, columns, rows):
        self.columns, self.rows = columns, rows
        self.calls = 0

    def execute(self, sql):
        self.calls += 1
        return QueryData(self.columns, self.rows, False)


def query(
    sql,
    *,
    metric="人民币净销售额",
    columns=("arbitrary",),
    rows=((Decimal("1234567.895"),),),
    dimensions=(),
    time=None,
):
    generator = FixedGenerator(sql)
    executor = FixedExecutor(columns, rows)
    service = OnlineQueryService(generator, executor, context_loader=load_query_context)
    semantic = ValidatedSemanticQuery(
        QueryType.METRIC_ANALYSIS, (), (metric,), dimensions, time, (), "测试查询"
    )
    result = service.execute(QueryRequest("测试查询", semantic_query=semantic))
    assert isinstance(result, QuerySuccess)
    assert generator.calls == executor.calls == 1
    assert result.rows == rows
    return result


def test_sum_is_certified_by_expression_not_alias():
    result = query(
        "SELECT SUM(f.net_sales_amount_cny) AS arbitrary FROM mart_sales.fct_sales_order_line f WHERE f.order_status = 'completed'"
    )
    metadata = getattr(result, "result_metadata", None)
    assert metadata is not None, "查询成功应附带可信结果说明"
    column = metadata.to_payload()["columns"][0]
    assert column["certified"] is True
    assert column["semantic_name"] == "人民币净销售额"
    assert column["unit"] == {"key": "CNY", "label": "元"}


@pytest.mark.parametrize(
    "projection,condition",
    [
        ("SUM(f.sales_cost_amount_cny)", "f.order_status = 'completed'"),
        ("SUM(f.net_sales_amount_cny)", "f.order_status = 'pending'"),
    ],
)
def test_misleading_alias_does_not_certify_wrong_formula_or_filter(
    projection, condition
):
    result = query(
        f"SELECT {projection} AS arbitrary FROM mart_sales.fct_sales_order_line f WHERE {condition}"
    )
    metadata = getattr(result, "result_metadata", None)
    assert metadata is not None
    column = metadata.to_payload()["columns"][0]
    assert column["certified"] is False
    assert column["unit"] is None


def test_calendar_grouping_is_one_time_dimension_with_row_aligned_keys():
    result = query(
        "SELECT d.year AS y, d.month AS m, SUM(f.net_sales_amount_cny) AS arbitrary FROM mart_sales.fct_sales_order_line f LEFT JOIN mart_sales.dim_date d ON f.completion_date_key = d.date_key WHERE f.order_status = 'completed' AND d.year = 2025 GROUP BY d.year, d.month",
        columns=("y", "m", "arbitrary"),
        rows=((2025, 3, Decimal("20")), (2025, 1, Decimal("10"))),
        dimensions=("月份",),
    )
    payload = result.result_metadata.to_payload()
    assert [c["semantic_name"] for c in payload["columns"][:2]] == ["年份", "月份"]
    assert payload["time_axis"] == {
        "granularity": "month",
        "keys": ["2025-03-01", "2025-01-01"],
    }
    assert payload["scope"]["grouping"] == [
        {"semantic_name": "月份", "kind": "time", "column_indices": [0, 1]}
    ]
    assert payload["scope"]["time"]["start"] == "2025-01-01"
    assert payload["scope"]["time"]["end_exclusive"] == "2026-01-01"


def test_wrong_date_role_does_not_get_completion_date_label():
    result = query(
        "SELECT d.year AS y, SUM(f.net_sales_amount_cny) AS arbitrary FROM mart_sales.fct_sales_order_line f LEFT JOIN mart_sales.dim_date d ON f.order_date_key = d.date_key WHERE f.order_status = 'completed' GROUP BY d.year",
        columns=("y", "arbitrary"),
        rows=((2025, Decimal("10")),),
        dimensions=("年份",),
    )
    assert result.result_metadata.to_payload()["time_axis"] is None


def test_category_group_and_actual_filter_have_certified_physical_identity():
    result = query(
        "SELECT p.product_name AS item, SUM(f.net_sales_amount_cny) AS arbitrary FROM mart_sales.fct_sales_order_line f LEFT JOIN mart_sales.dim_product p ON f.product_key = p.product_key WHERE f.order_status = 'completed' AND p.product_line IN ('A', 'B') GROUP BY p.product_name",
        columns=("item", "arbitrary"),
        rows=(("产品A", Decimal("10")),),
        dimensions=("产品",),
    )
    payload = result.result_metadata.to_payload()
    assert payload["columns"][0]["semantic_name"] == "产品"
    assert payload["scope"]["grouping"] == [
        {"semantic_name": "产品", "kind": "category", "column_indices": [0]}
    ]
    assert payload["scope"]["filters"] == [
        {"label": "产品线", "operator": "IN", "values": ["A", "B"]}
    ]
    assert payload["scope"]["time_status"] == "unbounded"


def test_unknown_projection_only_loses_its_own_certification():
    result = query(
        "SELECT SUM(f.net_sales_amount_cny) AS arbitrary, MAX(f.sales_cost_amount_cny) AS unknown FROM mart_sales.fct_sales_order_line f WHERE f.order_status = 'completed'",
        columns=("arbitrary", "unknown"),
        rows=((Decimal("10"), Decimal("20")),),
    )
    payload = result.result_metadata.to_payload()
    assert payload["columns"][0]["certified"] is True
    assert payload["columns"][1]["certified"] is False
    assert payload["status"] == "partial"


def test_hidden_grouping_is_not_presented_as_scalar_overall_total():
    result = query(
        "SELECT SUM(f.net_sales_amount_cny) AS arbitrary FROM mart_sales.fct_sales_order_line f WHERE f.order_status = 'completed' GROUP BY f.product_key"
    )
    assert (
        "GROUPING_UNCONFIRMED"
        in result.result_metadata.to_payload()["scope"]["warnings"]
    )


def test_month_without_year_or_actual_bounded_range_does_not_invent_time_axis():
    result = query(
        "SELECT d.month AS m, SUM(f.net_sales_amount_cny) AS arbitrary FROM mart_sales.fct_sales_order_line f LEFT JOIN mart_sales.dim_date d ON f.completion_date_key = d.date_key WHERE f.order_status = 'completed' GROUP BY d.month",
        columns=("m", "arbitrary"),
        rows=((3, Decimal("10")),),
        dimensions=("月份",),
    )
    assert result.result_metadata.to_payload()["time_axis"] is None


def test_result_metadata_payload_cannot_mutate_snapshot():
    result = query(
        "SELECT SUM(f.net_sales_amount_cny) AS arbitrary FROM mart_sales.fct_sales_order_line f WHERE f.order_status = 'completed'"
    )
    payload = result.result_metadata.to_payload()
    payload["columns"][0]["unit"]["label"] = "错误"
    assert result.result_metadata.to_payload()["columns"][0]["unit"]["label"] == "元"


def test_having_scope_is_not_claimed_complete():
    result = query(
        "SELECT p.product_name AS item, SUM(f.net_sales_amount_cny) AS arbitrary FROM mart_sales.fct_sales_order_line f LEFT JOIN mart_sales.dim_product p ON f.product_key=p.product_key WHERE f.order_status='completed' GROUP BY p.product_name HAVING SUM(f.net_sales_amount_cny)>10",
        columns=("item", "arbitrary"),
        rows=(("A", Decimal("20")),),
        dimensions=("产品",),
    )
    assert result.result_metadata.to_payload()["scope"]["status"] == "partial"


def test_bad_display_property_does_not_disable_other_valid_metrics(
    tmp_path, monkeypatch
):
    import json
    from pathlib import Path
    from src.semantic import result_display

    original = Path(result_display.__file__).parent
    semantic_root = tmp_path / "semantic"
    semantic_root.mkdir()
    for filename in ("metrics.json", "dimensions.json"):
        (semantic_root / filename).write_bytes((original / filename).read_bytes())
    structure = tmp_path / "structure" / "generated"
    structure.mkdir(parents=True)
    (structure / "columns.json").write_bytes(
        (original.parent / "structure/generated/columns.json").read_bytes()
    )
    traits = json.loads((original / "result_display.json").read_text())
    traits["metrics"]["人民币销售成本"]["unit"] = {"invalid": True}
    (semantic_root / "result_display.json").write_text(json.dumps(traits))
    monkeypatch.setattr(
        result_display, "__file__", str(semantic_root / "result_display.py")
    )
    result_display.load_display_facts.cache_clear()
    try:
        result = query(
            "SELECT SUM(f.net_sales_amount_cny) AS arbitrary FROM mart_sales.fct_sales_order_line f WHERE f.order_status='completed'"
        )
        assert result.result_metadata.to_payload()["columns"][0]["certified"] is True
    finally:
        result_display.load_display_facts.cache_clear()


def test_extra_join_predicate_still_rejected_before_execution_or_metadata():
    from src.online_query.contracts import QueryFailure, QueryErrorCode

    generator = FixedGenerator(
        "SELECT SUM(f.net_sales_amount_cny) AS arbitrary FROM mart_sales.fct_sales_order_line f LEFT JOIN mart_sales.dim_product p ON f.product_key=p.product_key AND p.product_line='A' WHERE f.order_status='completed'"
    )
    executor = FixedExecutor(("arbitrary",), ((Decimal("10"),),))
    service = OnlineQueryService(generator, executor, context_loader=load_query_context)
    semantic = ValidatedSemanticQuery(
        QueryType.METRIC_ANALYSIS, (), ("人民币净销售额",), (), None, (), "测试查询"
    )
    result = service.execute(QueryRequest("测试查询", semantic_query=semantic))
    assert isinstance(result, QueryFailure)
    assert result.error_code == QueryErrorCode.SQL_REJECTED
    assert executor.calls == 0
