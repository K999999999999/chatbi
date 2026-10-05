"""当前SQL必须保持事先确定的完整业务条件，而非从SQL反推条件。"""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from src.online_query.context import load_query_context
from src.online_query.contracts import (
    QueryData,
    QueryFailure,
    QueryRequest,
    QuerySuccess,
)
from src.online_query.query_understanding import (
    candidate_from_payload,
    validate_candidate,
)
from src.online_query.service import OnlineQueryService


class FixedSQL:
    def __init__(self, sql):
        self.sql = sql

    def generate(self, prompt):
        return self.sql


class CountingDatabase:
    def __init__(self):
        self.calls = 0

    def execute(self, sql):
        self.calls += 1
        return QueryData(("product", "sales"), (("甲", "12.50"),), False)


def ranked_request():
    candidate = candidate_from_payload(
        {
            "query_type": "metric_analysis",
            "subjects": [],
            "metrics": ["人民币净销售额"],
            "dimensions": ["产品"],
            "time": None,
            "filters": [],
            "conditions": {
                "order_by": [
                    {
                        "target_kind": "metric",
                        "target": "人民币净销售额",
                        "direction": "desc",
                        "nulls": "first",
                    }
                ],
                "row_limit": 10,
                "aggregate_filters": [],
                "selection": None,
            },
        },
        require_restorable=True,
    )
    return QueryRequest(
        "销售额前10产品",
        semantic_query=validate_candidate(
            candidate, original_question="销售额前10产品"
        ),
        require_restorable=True,
    )


def published_context():
    # 无网络的当前发布事实夹具；生产由RetrievalContext提供同Contract事实。
    root = Path(__file__).resolve().parents[2] / "src"
    metrics = json.loads((root / "semantic/metrics.json").read_text())
    columns = json.loads((root / "structure/generated/columns.json").read_text())
    return replace(
        load_query_context(), semantic_facts={"metrics": metrics, "columns": columns}
    )


SQL = """SELECT p.product_name AS product, SUM(f.net_sales_amount_cny) AS sales
FROM mart_sales.fct_sales_order_line f LEFT JOIN mart_sales.dim_product p ON f.product_key=p.product_key
WHERE f.order_status='completed' GROUP BY p.product_name
ORDER BY sales DESC NULLS FIRST, product ASC NULLS LAST LIMIT 10"""


def test_wrong_business_limit_is_rejected_before_database():
    db = CountingDatabase()
    service = OnlineQueryService(
        FixedSQL(SQL.replace("LIMIT 10", "LIMIT 9")),
        db,
        context_loader=published_context,
    )
    result = service.execute(ranked_request())
    assert isinstance(result, QueryFailure), result
    assert result.error_code.value == "SQL_REJECTED"
    assert db.calls == 0


def test_history_success_has_complete_certified_state():
    db = CountingDatabase()
    service = OnlineQueryService(FixedSQL(SQL), db, context_loader=published_context)
    result = service.execute(ranked_request())
    assert isinstance(result, QuerySuccess), result
    assert result.restoration_state["semantic_query"]["conditions"]["row_limit"] == 10
    assert db.calls == 1


def test_history_provenance_survives_json_roundtrip():
    from src.online_query.semantic_state import prepare_restoration_state
    from src.query_api.history_codec import decode_query_state

    context = published_context()
    result = OnlineQueryService(
        FixedSQL(SQL), CountingDatabase(), context_loader=lambda: context
    ).execute(ranked_request())
    assert isinstance(result, QuerySuccess), result

    restored = decode_query_state(json.loads(json.dumps(result.restoration_state)))
    _, recertified = prepare_restoration_state(restored, context)

    assert recertified["provenance"] == result.restoration_state["provenance"]


def test_legacy_query_does_not_activate_history_condition_guard():
    db = CountingDatabase()
    service = OnlineQueryService(
        FixedSQL(SQL.replace("LIMIT 10", "LIMIT 9")),
        db,
        context_loader=published_context,
    )
    request = replace(ranked_request(), require_restorable=False)
    assert isinstance(service.execute(request), QuerySuccess)
    assert db.calls == 1


@pytest.mark.parametrize(
    "change",
    [
        lambda sql: sql.replace("DESC NULLS FIRST", "ASC NULLS LAST"),
        lambda sql: sql.replace(
            "p.product_name AS product", "p.product_code AS product"
        ).replace("GROUP BY p.product_name", "GROUP BY p.product_code"),
        lambda sql: sql.replace(
            "f.order_status='completed'",
            "f.order_status='completed' AND p.product_line='A'",
        ),
        lambda sql: sql.replace(" LIMIT 10", " LIMIT 10 OFFSET 1"),
    ],
)
def test_generated_sql_cannot_change_certified_conditions(change):
    db = CountingDatabase()
    service = OnlineQueryService(
        FixedSQL(change(SQL)), db, context_loader=published_context
    )
    assert isinstance(service.execute(ranked_request()), QueryFailure)
    assert db.calls == 0


def test_entity_selection_distinct_and_default_order_are_restorable():
    candidate = candidate_from_payload(
        {
            "query_type": "entity_lookup",
            "subjects": ["客户"],
            "metrics": [],
            "dimensions": [],
            "time": None,
            "filters": [],
            "conditions": {
                "order_by": [],
                "row_limit": None,
                "aggregate_filters": [],
                "selection": {"fields": ["客户名称"], "distinct": True},
            },
        },
        require_restorable=True,
    )
    request = QueryRequest(
        "列出客户名称",
        semantic_query=validate_candidate(candidate, original_question="列出客户名称"),
        require_restorable=True,
    )
    sql = "SELECT DISTINCT c.customer_name FROM mart_sales.dim_customer c ORDER BY c.customer_name ASC NULLS LAST"
    db = CountingDatabase()
    service = OnlineQueryService(FixedSQL(sql), db, context_loader=published_context)
    result = service.execute(request)
    assert isinstance(result, QuerySuccess), result
    assert (
        result.restoration_state["semantic_query"]["conditions"]["selection"][
            "distinct"
        ]
        is True
    )
    assert result.restoration_state["semantic_query"]["conditions"]["order_by"] == []
    service = OnlineQueryService(
        FixedSQL(sql.replace("DISTINCT ", "")), db, context_loader=published_context
    )
    assert isinstance(service.execute(request), QueryFailure)
    assert db.calls == 1


def test_rank_without_a_certified_order_asks_for_clarification_before_sql():
    from src.online_query.semantic_state import (
        SemanticCertificationError,
        prepare_restoration_state,
    )

    payload = {
        "query_type": "metric_analysis",
        "subjects": [],
        "metrics": ["人民币净销售额"],
        "dimensions": ["产品"],
        "time": None,
        "filters": [],
        "conditions": {
            "order_by": [],
            "row_limit": 10,
            "aggregate_filters": [],
            "selection": None,
        },
    }
    candidate = candidate_from_payload(payload, require_restorable=True)
    semantic = validate_candidate(candidate, original_question="前10个产品")

    class Understanding:
        def understand_history(self, _question):
            return candidate

    db = CountingDatabase()
    result = OnlineQueryService(
        FixedSQL(SQL),
        db,
        context_loader=published_context,
        query_understanding=Understanding(),
    ).execute(QueryRequest("前10个产品", require_restorable=True))

    assert isinstance(result, QueryFailure)
    assert result.error_code.value == "CLARIFICATION_REQUIRED"
    assert result.error_message == "请明确排名依据"
    assert db.calls == 0
    with pytest.raises(SemanticCertificationError, match="缺少明确排序依据"):
        prepare_restoration_state(semantic, published_context())


def test_existing_single_metric_having_is_preserved_and_not_replaced_by_where():
    from src.online_query.restoration_conditions import AggregateFilter

    original = ranked_request()
    semantic = replace(
        original.semantic_query,
        restoration_conditions=replace(
            original.semantic_query.restoration_conditions,
            aggregate_filters=(AggregateFilter("人民币净销售额", "gt", ("100",)),),
        ),
    )
    request = replace(original, semantic_query=semantic)
    sql = SQL.replace("ORDER BY", "HAVING SUM(f.net_sales_amount_cny)>100 ORDER BY")
    db = CountingDatabase()
    service = OnlineQueryService(FixedSQL(sql), db, context_loader=published_context)
    result = service.execute(request)
    assert isinstance(result, QuerySuccess), result
    assert result.restoration_state["semantic_query"]["conditions"][
        "aggregate_filters"
    ][0]["values"] == ["100"]
    bad = SQL.replace(
        "f.order_status='completed'",
        "f.order_status='completed' AND f.net_sales_amount_cny>100",
    )
    assert isinstance(
        OnlineQueryService(FixedSQL(bad), db, context_loader=published_context).execute(
            request
        ),
        QueryFailure,
    )
    assert db.calls == 1


def test_synthetic_unknown_join_key_cannot_certify_restorable_state():
    context = published_context()
    facts = {
        "metrics": context.semantic_facts["metrics"],
        "columns": [dict(c) for c in context.semantic_facts["columns"]],
    }
    for column in facts["columns"]:
        if (
            column["table_name"] == "dim_product"
            and column["column_name"] == "product_key"
        ):
            column["data_type"] = "UNKNOWN"
    db = CountingDatabase()
    result = OnlineQueryService(
        FixedSQL(SQL), db, context_loader=lambda: replace(context, semantic_facts=facts)
    ).execute(ranked_request())
    assert isinstance(result, QueryFailure) and db.calls == 0


def test_completed_status_filter_uses_certified_existing_metric_value():
    from dataclasses import replace
    from src.online_query.query_understanding import FilterOperator, ValidatedFilter

    request = ranked_request()
    semantic = replace(
        request.semantic_query,
        filters=(ValidatedFilter("订单状态", FilterOperator.EQUALS, ("已完成",)),),
    )
    request = replace(request, question="列出已完成订单销售额", semantic_query=semantic)
    sql = SQL.replace("f.order_status='completed'", "f.order_status='completed'")
    db = CountingDatabase()
    result = OnlineQueryService(
        FixedSQL(sql), db, context_loader=published_context
    ).execute(request)
    assert isinstance(result, QuerySuccess), result
    assert result.restoration_state["provenance"]["bindings"]["订单状态"][
        "column"
    ].endswith("order_status")
    assert db.calls == 1
