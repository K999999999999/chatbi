"""公共 SQL Guard 的指标口径与授权查询 / 分析链路回归。"""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.authorization.audit import InMemoryAuditSink
from src.authorization.contracts import AuthContext, StaticAuthorizationPolicyStore
from src.authorization.query_entry import AuthorizedQueryService
from src.business_analysis.contracts import AnalysisTask, AnalysisTaskType
from src.business_analysis.execution import (
    TaskExecutor,
    TaskSemanticAdapter,
    TaskStatus,
)
from src.online_query.context import load_query_context
from src.online_query.contracts import (
    MetricConstraint,
    OnlineRetrievalResult,
    QueryData,
    QueryErrorCode,
    QueryFailure,
    QueryRequest,
    QuerySuccess,
    RetrievalStatus,
)
from src.online_query.query_understanding import candidate_from_payload
from src.online_query.service import OnlineQueryService
from src.online_query.sql_guard import SQLRejectedError, validate_sql

FACT = "mart_sales.fct_sales_order_line"
METRICS = json.loads(
    (Path(__file__).parents[2] / "src/semantic/metrics.json").read_text()
)
SALES = next(metric for metric in METRICS if metric["name"] == "人民币净销售额")
VALID_SQL = (
    f"SELECT SUM(f.net_sales_amount_cny) AS sales FROM {FACT} f "
    "WHERE f.order_status = 'completed'"
)


def metric_context(metric=SALES):
    return replace(
        load_query_context(),
        metric_constraints=(
            MetricConstraint(
                ordinal=1,
                requested_text=metric["name"],
                document_id="metric:test",
                metric_name=metric["name"],
                formula=metric["formula"],
                data_source=metric["data_source"],
                time_field=metric["time_field"],
                filters=tuple(metric["filters"]),
                depends_on=tuple(metric["depends_on"]),
            ),
        ),
    )


@pytest.mark.parametrize("metric", METRICS, ids=lambda metric: metric["name"])
def test_registered_single_metric_template_passes_unchanged(metric):
    sql = metric["sql_template"]
    assert validate_sql(sql, metric_context(metric)).sql == sql


@pytest.mark.parametrize(
    "projection",
    [
        "AVG(f.net_sales_amount_cny)",
        "SUM(f.sales_cost_amount_cny)",
        "SUM(f.net_sales_amount_cny) + 1",
        "SUM(f.net_sales_amount_cny), COUNT(*)",
        "f.net_sales_amount_cny",
        "SUM(CASE WHEN f.order_status = 'completed' THEN f.net_sales_amount_cny END)",
    ],
)
def test_single_metric_rejects_changed_missing_or_extra_formula(projection):
    sql = f"SELECT {projection} FROM {FACT} f WHERE f.order_status = 'completed'"
    with pytest.raises(SQLRejectedError):
        validate_sql(sql, metric_context())


@pytest.mark.parametrize(
    "suffix",
    [
        "",
        "WHERE f.order_status = 'pending'",
        "WHERE f.order_status <> 'completed'",
        "WHERE f.order_id = 'completed'",
        "WHERE NOT (f.order_status = 'completed')",
        "WHERE f.order_status = 'completed' OR f.net_sales_amount_cny > 0",
        "WHERE (f.order_status = 'completed' AND f.net_sales_amount_cny > 0) OR TRUE",
        "WHERE f.net_sales_amount_cny > 0 HAVING COUNT(*) > 0",
        "HAVING MAX(CASE WHEN f.order_status = 'completed' THEN 1 ELSE 0 END) = 1",
    ],
)
def test_single_metric_rejects_missing_changed_or_bypassed_fixed_filter(suffix):
    sql = f"SELECT SUM(f.net_sales_amount_cny) FROM {FACT} f {suffix}"
    with pytest.raises(SQLRejectedError):
        validate_sql(sql, metric_context())


@pytest.mark.parametrize(
    "sql",
    [
        f"SELECT (sum((sales.net_sales_amount_cny))) AS total FROM {FACT} sales "
        "WHERE (sales.order_status = 'completed')",
        VALID_SQL + " AND f.net_sales_amount_cny > 0",
        VALID_SQL + " AND (f.net_sales_amount_cny > 0 OR f.quantity > 0)",
        f"SELECT f.customer_key, SUM(f.net_sales_amount_cny) AS total FROM {FACT} f "
        "WHERE f.order_status = 'completed' GROUP BY f.customer_key "
        "HAVING SUM(f.net_sales_amount_cny) > 100 ORDER BY total DESC LIMIT 5",
        f"SELECT EXTRACT(YEAR FROM d.full_date), SUM(f.net_sales_amount_cny) "
        f"FROM {FACT} f LEFT JOIN mart_sales.dim_date d "
        "ON f.completion_date_key = d.date_key WHERE f.order_status = 'completed' "
        "GROUP BY EXTRACT(YEAR FROM d.full_date)",
    ],
)
def test_single_metric_preserves_equivalent_formula_and_legal_user_conditions(sql):
    assert validate_sql(sql, metric_context()).sql == sql


def test_single_metric_requires_every_fixed_filter():
    context = metric_context()
    constraint = replace(
        context.metric_constraints[0],
        filters=("f.order_status = 'completed' AND f.quantity > 0",),
    )
    context = replace(context, metric_constraints=(constraint,))
    with pytest.raises(SQLRejectedError):
        validate_sql(VALID_SQL, context)
    assert validate_sql(VALID_SQL + " AND f.quantity > 0", context).sql == (
        VALID_SQL + " AND f.quantity > 0"
    )


def test_explicit_context_without_metric_constraints_keeps_existing_behavior():
    sql = f"SELECT SUM(f.net_sales_amount_cny) FROM {FACT} f"
    assert validate_sql(sql, load_query_context()).sql == sql


def test_single_metric_without_fixed_filters_accepts_formula_without_where():
    context = metric_context()
    constraint = replace(context.metric_constraints[0], filters=())
    context = replace(context, metric_constraints=(constraint,))
    sql = f"SELECT SUM(f.net_sales_amount_cny) FROM {FACT} f"
    assert validate_sql(sql, context).sql == sql


@pytest.fixture
def authorized_chain():
    # 隔离真实模型、检索外部资源和数据库；保留真实授权、Service 与 SQL Guard。
    generator = Mock()
    executor = Mock()
    executor.execute.return_value = QueryData(("sales",), ((100,),), False)
    retrieval = Mock()
    retrieval.retrieve.return_value = OnlineRetrievalResult(
        status=RetrievalStatus.SUCCESS, query_context=metric_context()
    )
    understanding = Mock()
    understanding.understand.return_value = candidate_from_payload(
        {
            "query_type": "metric_analysis",
            "subjects": ["销售"],
            "metrics": ["人民币净销售额"],
            "dimensions": [],
            "time": None,
            "filters": [],
        }
    )
    online = OnlineQueryService(
        generator,
        executor,
        retrieval_provider=retrieval,
        query_understanding=understanding,
    )
    authorized = AuthorizedQueryService(
        online,
        StaticAuthorizationPolicyStore(frozenset({"analyst"}), "test-v1"),
        audit_sink=InMemoryAuditSink(),
    ).bind(AuthContext(subject_id="analyst", identity_provider="test"))
    return authorized, generator, executor


@pytest.mark.parametrize(
    "sql",
    [
        f"SELECT SUM(f.net_sales_amount_cny) FROM {FACT} f",
        VALID_SQL.replace("SUM(", "AVG("),
        VALID_SQL + " OR TRUE",
    ],
)
def test_authorized_query_rejects_bad_single_metric_before_database(
    authorized_chain, sql
):
    query, generator, executor = authorized_chain
    generator.generate.return_value = sql
    result = query.query(QueryRequest("已完成销售额", request_id="metric-query"))
    assert isinstance(result, QueryFailure)
    assert result.error_code == QueryErrorCode.SQL_REJECTED
    executor.execute.assert_not_called()


@pytest.mark.parametrize(
    "sql",
    [
        f"SELECT SUM(f.net_sales_amount_cny) FROM {FACT} f",
        VALID_SQL.replace("SUM(", "AVG("),
        VALID_SQL + " OR TRUE",
    ],
)
def test_analysis_task_uses_same_guard_and_does_not_execute_bad_sql(
    authorized_chain, sql
):
    query, generator, executor = authorized_chain
    generator.generate.return_value = sql
    task = AnalysisTask(
        task_id="sales",
        task_type=AnalysisTaskType.BASELINE,
        description="查询已完成销售额",
        metrics=("人民币净销售额",),
        dimensions=(),
        time_range=None,
        filters=(),
        depends_on=(),
        expected_output="销售总额",
    )
    result = TaskExecutor(query, TaskSemanticAdapter()).execute_one(task)
    assert result.status == TaskStatus.FAILED
    assert result.error.code == QueryErrorCode.SQL_REJECTED.value
    executor.execute.assert_not_called()


def test_authorized_query_executes_valid_single_metric(authorized_chain):
    query, generator, executor = authorized_chain
    generator.generate.return_value = VALID_SQL
    result = query.query(QueryRequest("已完成销售额", request_id="metric-query"))
    assert isinstance(result, QuerySuccess)
    assert result.rows == ((100,),)
    executor.execute.assert_called_once()


def test_analysis_task_executes_valid_single_metric(authorized_chain):
    query, generator, executor = authorized_chain
    generator.generate.return_value = VALID_SQL
    task = AnalysisTask(
        task_id="sales",
        task_type=AnalysisTaskType.BASELINE,
        description="查询已完成销售额",
        metrics=("人民币净销售额",),
        dimensions=(),
        time_range=None,
        filters=(),
        depends_on=(),
        expected_output="销售总额",
    )
    result = TaskExecutor(query, TaskSemanticAdapter()).execute_one(task)
    assert result.status == TaskStatus.COMPLETED
    assert result.rows == ((100,),)
    executor.execute.assert_called_once()
