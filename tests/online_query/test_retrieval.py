"""Online Retrieval（在线检索）确定性链路测试。"""

import json
import unittest

from src.rag_offline.embedding import EmbeddedText, SparseEmbedding
from src.rag_offline.qdrant_store import SearchHit
from src.online_query.contracts import (
    FallbackPolicy,
    RequestShape,
    RetrievalConfig,
    RetrievalRequest,
    RetrievalStatus,
)
from src.online_query.query_understanding import (
    QueryType,
    ValidatedSemanticQuery,
    candidate_from_payload,
    validate_candidate,
)
from src.online_query.rag_runtime import (
    AssetSnapshot,
    RetrievalUnavailableError,
)
from src.online_query.retrieval import OnlineRetriever


class _FakeEmbedding:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_query(self, text: str) -> EmbeddedText:
        self.queries.append(text)
        return EmbeddedText(
            dense=(1.0, 0.0, 0.0, 1.0),
            sparse=SparseEmbedding(indices=(1,), values=(1.0,)),
        )


class _FakeStore:
    def __init__(self, tables, columns, metrics) -> None:
        self.tables = tables
        self.columns = columns
        self.metrics = metrics
        self.column_filters: list[dict[str, str]] = []

    def search(self, collection_name, query, *, limit=5, filter_payload=None):
        del query, limit
        if filter_payload is None:
            if collection_name == "table":
                return tuple(self.tables)
            if collection_name == "metric":
                return tuple(self.metrics)
            return ()
        self.column_filters.append(dict(filter_payload))
        table_name = filter_payload["table_name"]
        return tuple(self.columns.get(table_name, ()))


class _CombinedMetricStore(_FakeStore):
    def __init__(self, tables, columns, metric_hits) -> None:
        metrics = tuple(metric_hits)
        super().__init__(tables, columns, metrics)
        self.metric_hits = metrics
        self.metric_query_count = 0
        self.metric_limits: list[int] = []

    def search(self, collection_name, query, *, limit=5, filter_payload=None):
        if collection_name == "metric" and filter_payload is None:
            del query
            self.metric_query_count += 1
            self.metric_limits.append(limit)
            return self.metric_hits
        return super().search(
            collection_name,
            query,
            limit=limit,
            filter_payload=filter_payload,
        )


class _GroupingTableStore(_FakeStore):
    def __init__(self, tables, grouping_tables, columns, metrics) -> None:
        super().__init__(tables, columns, metrics)
        self.grouping_tables = grouping_tables

    def search(self, collection_name, query, *, limit=5, filter_payload=None):
        if filter_payload is None and collection_name == "table":
            if query.dense[1] == 1.0:
                return tuple(self.grouping_tables)
            return tuple(self.tables)
        return super().search(
            collection_name,
            query,
            limit=limit,
            filter_payload=filter_payload,
        )


class _RequiredColumnRecoveryStore(_FakeStore):
    def search(self, collection_name, query, *, limit=5, filter_payload=None):
        if filter_payload is not None and "column_name" in filter_payload:
            table_name = filter_payload["table_name"]
            column_name = filter_payload["column_name"]
            return tuple(
                hit
                for hit in self.columns.get(table_name, ())
                if hit.payload["metadata"]["column_name"] == column_name
            )
        if filter_payload is not None and collection_name == "column":
            table_name = filter_payload["table_name"]
            return tuple(self.columns.get(table_name, ()))[:1]
        return super().search(
            collection_name,
            query,
            limit=limit,
            filter_payload=filter_payload,
        )


class _GroupingEmbedding(_FakeEmbedding):
    def embed_query(self, text: str) -> EmbeddedText:
        self.queries.append(text)
        dense = (0.0, 1.0, 0.0, 0.0) if text == "技术路线" else (1.0, 0.0, 0.0, 1.0)
        return EmbeddedText(
            dense=dense, sparse=SparseEmbedding(indices=(1,), values=(1.0,))
        )


class _FakeRuntime:
    def __init__(self, snapshot: AssetSnapshot) -> None:
        self.snapshot = snapshot

    def get_snapshot(self) -> AssetSnapshot:
        return self.snapshot


class _UnavailableRuntime:
    def get_snapshot(self) -> AssetSnapshot:
        raise RetrievalUnavailableError("Qdrant unavailable")


def _hit(document_id, score, metadata, page_content=""):
    return SearchHit(
        document_id=document_id,
        score=score,
        payload={
            "document_id": document_id,
            "page_content": page_content,
            "metadata": metadata,
        },
    )


def _table(document_id, table_name, score, page_content=None):
    return _hit(
        document_id,
        score,
        {
            "doc_type": "TABLE",
            "schema_name": "mart_sales",
            "table_name": table_name,
            "table_type": "fact" if table_name.startswith("fct_") else "dimension",
        },
        page_content or f"表名：mart_sales.{table_name}",
    )


def _column(table_name, column_name, score):
    return _hit(
        f"column:mart_sales.{table_name}.{column_name}",
        score,
        {
            "doc_type": "COLUMN",
            "schema_name": "mart_sales",
            "table_name": table_name,
            "column_name": column_name,
            "data_type": "integer",
        },
        f"字段名：{column_name}（所属表：mart_sales.{table_name}）",
    )


def _metric(
    name,
    score,
    *,
    aliases=None,
    formula="SUM(f.net_sales_amount_cny - f.sales_cost_amount_cny)",
    data_source="mart_sales.fct_sales_order_line",
    time_field="fct_sales_order_line.completion_date_key -> dim_date.full_date",
    filters=("f.order_status = 'completed'",),
    depends_on=(),
):
    return _hit(
        f"metric:{name}",
        score,
        {
            "doc_type": "METRIC",
            "metric_name": name,
            "aliases": aliases or (),
            "level": "原子指标",
            "definition": f"{name}定义",
            "formula": formula,
            "data_source": data_source,
            "time_field": time_field,
            "filters": filters,
            "depends_on": depends_on,
            "notes": "按完成日期统计。",
        },
        f"指标名：{name}\n别名：{'、'.join(aliases or ())}\n指标定义：{name}定义",
    )


def _snapshot(store, embedding, graph):
    return AssetSnapshot(
        asset_version="build-v2",
        collection_names={"TABLE": "table", "COLUMN": "column", "METRIC": "metric"},
        relationship_graph=graph,
        manifest={"status": "READY"},
        embedding_provider=embedding,
        qdrant_store=store,
    )


def _sales_graph(*, include_region=True, include_date=True):
    edges = []
    if include_region:
        edges.append(
            {
                "constraint_name": "fk_region",
                "source_schema": "mart_sales",
                "source_table": "fct_sales_order_line",
                "source_columns": ["sales_region_key"],
                "target_schema": "mart_sales",
                "target_table": "dim_sales_region",
                "target_columns": ["sales_region_key"],
            }
        )
    if include_date:
        edges.append(
            {
                "constraint_name": "fk_completion_date",
                "source_schema": "mart_sales",
                "source_table": "fct_sales_order_line",
                "source_columns": ["completion_date_key"],
                "target_schema": "mart_sales",
                "target_table": "dim_date",
                "target_columns": ["date_key"],
            }
        )
    primary_keys = []
    if include_region:
        primary_keys.append(
            {
                "relationship_type": "primary_key",
                "schema_name": "mart_sales",
                "table_name": "dim_sales_region",
                "column_names": ["sales_region_key"],
                "constraint_name": "pk_dim_sales_region",
            }
        )
    if include_date:
        primary_keys.append(
            {
                "relationship_type": "primary_key",
                "schema_name": "mart_sales",
                "table_name": "dim_date",
                "column_names": ["date_key"],
                "constraint_name": "pk_dim_date",
            }
        )
    return {
        "foreign_keys": edges,
        "primary_keys": primary_keys,
        "unique_constraints": [],
    }


def _multi_metrics():
    return (
        _metric(
            "已完成订单数",
            0.98,
            formula="COUNT(DISTINCT f.order_id)",
        ),
        _metric(
            "人民币净销售额",
            0.97,
            aliases=("人民币销售额",),
            formula="SUM(f.net_sales_amount_cny)",
        ),
        _metric(
            "毛利率",
            0.96,
            formula=(
                "SUM(f.net_sales_amount_cny - f.sales_cost_amount_cny) "
                "/ NULLIF(SUM(f.net_sales_amount_cny), 0)"
            ),
        ),
    )


def _five_metrics():
    return (
        *_multi_metrics(),
        _metric(
            "人民币销售成本",
            0.95,
            formula="SUM(f.sales_cost_amount_cny)",
        ),
        _metric(
            "人民币毛利",
            0.94,
            formula="SUM(f.net_sales_amount_cny - f.sales_cost_amount_cny)",
        ),
    )


def _multi_tables():
    return (
        _table("table:fct", "fct_sales_order_line", 0.99),
        _table("table:customer", "dim_customer", 0.90, page_content="客户类型维度"),
        _table("table:date", "dim_date", 0.89, page_content="完成日期维度"),
    )


def _multi_columns(*, include_cost=True):
    fact_columns = [
        _column("fct_sales_order_line", "order_id", 0.99),
        _column("fct_sales_order_line", "net_sales_amount_cny", 0.98),
        _column("fct_sales_order_line", "order_status", 0.97),
        _column("fct_sales_order_line", "completion_date_key", 0.96),
        _column("fct_sales_order_line", "customer_key", 0.95),
    ]
    if include_cost:
        fact_columns.append(
            _column("fct_sales_order_line", "sales_cost_amount_cny", 0.94)
        )
    return {
        "fct_sales_order_line": tuple(fact_columns),
        "dim_customer": (
            _column("dim_customer", "customer_type", 0.93),
            _column("dim_customer", "customer_key", 0.92),
        ),
        "dim_date": (
            _column("dim_date", "full_date", 0.91),
            _column("dim_date", "date_key", 0.90),
        ),
    }


def _multi_graph(*, reverse_customer=False, include_unique_keys=True):
    customer_edge = {
        "constraint_name": "fk_customer",
        "source_schema": "mart_sales",
        "source_table": (
            "dim_customer" if reverse_customer else "fct_sales_order_line"
        ),
        "source_columns": ["customer_key"],
        "target_schema": "mart_sales",
        "target_table": (
            "fct_sales_order_line" if reverse_customer else "dim_customer"
        ),
        "target_columns": ["customer_key"],
    }
    primary_keys = []
    if include_unique_keys:
        primary_keys = [
            {
                "relationship_type": "primary_key",
                "schema_name": "mart_sales",
                "table_name": "dim_customer",
                "column_names": ["customer_key"],
                "constraint_name": "pk_dim_customer",
            },
            {
                "relationship_type": "primary_key",
                "schema_name": "mart_sales",
                "table_name": "dim_date",
                "column_names": ["date_key"],
                "constraint_name": "pk_dim_date",
            },
        ]
    return {
        "foreign_keys": [
            customer_edge,
            {
                "constraint_name": "fk_completion_date",
                "source_schema": "mart_sales",
                "source_table": "fct_sales_order_line",
                "source_columns": ["completion_date_key"],
                "target_schema": "mart_sales",
                "target_table": "dim_date",
                "target_columns": ["date_key"],
            },
        ],
        "primary_keys": primary_keys,
        "unique_constraints": [],
        "unique_indexes": [],
    }


class RetrievalTest(unittest.TestCase):
    def test_metric_query_returns_dynamic_context_and_indicator_metadata(self) -> None:
        tables = (
            _table("table:fct", "fct_sales_order_line", 0.95),
            _table(
                "table:region", "dim_sales_region", 0.85, page_content="销售区域维度"
            ),
            _table("table:date", "dim_date", 0.80),
        )
        columns = {
            "fct_sales_order_line": (
                _column("fct_sales_order_line", "net_sales_amount_cny", 0.95),
                _column("fct_sales_order_line", "sales_cost_amount_cny", 0.94),
                _column("fct_sales_order_line", "completion_date_key", 0.93),
                _column("fct_sales_order_line", "order_status", 0.92),
            ),
            "dim_sales_region": (
                _column("dim_sales_region", "sales_region_key", 0.90),
                _column("dim_sales_region", "region_name", 0.89),
            ),
            "dim_date": (
                _column("dim_date", "date_key", 0.90),
                _column("dim_date", "full_date", 0.89),
            ),
        }
        store = _FakeStore(
            tables, columns, (_metric("毛利率", 0.97, aliases=("毛利润率",)),)
        )
        embedding = _FakeEmbedding()
        runtime = _FakeRuntime(_snapshot(store, embedding, _sales_graph()))

        result = OnlineRetriever(runtime).retrieve(
            _request(
                "按销售区域统计毛利率",
                metrics=("毛利率",),
                dimensions=("销售区域",),
                subjects=("销售",),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        self.assertEqual([metric.metric_name for metric in result.metrics], ["毛利率"])
        self.assertIn(
            "SUM(f.net_sales_amount_cny - f.sales_cost_amount_cny)",
            result.indicator_context,
        )
        self.assertIn("completion_date_key", result.indicator_context)
        dynamic_schema = json.loads(result.dynamic_schema)
        dynamic_columns = {
            column["column_name"] for column in dynamic_schema["columns"]
        }
        self.assertNotIn("full_date", dynamic_columns)
        self.assertNotIn("date_key", dynamic_columns)
        self.assertEqual(
            result.query_context.allowed_tables,
            frozenset(
                {
                    "mart_sales.fct_sales_order_line",
                    "mart_sales.dim_sales_region",
                }
            ),
        )
        self.assertTrue(all("table_name" in item for item in store.column_filters))
        self.assertEqual(
            [edge.edge_id for edge in result.join_path.joins],
            ["fk_region"],
        )

    def test_explicit_date_uses_metric_time_field_and_date_join(self) -> None:
        tables = (
            _table("table:fct", "fct_sales_order_line", 0.95),
            _table("table:date", "dim_date", 0.85, page_content="完成日期维度"),
        )
        columns = {
            "fct_sales_order_line": (
                _column("fct_sales_order_line", "net_sales_amount_cny", 0.95),
                _column("fct_sales_order_line", "sales_cost_amount_cny", 0.94),
                _column("fct_sales_order_line", "completion_date_key", 0.93),
                _column("fct_sales_order_line", "order_status", 0.92),
            ),
            "dim_date": (
                _column("dim_date", "date_key", 0.90),
                _column("dim_date", "full_date", 0.89),
            ),
        }
        store = _FakeStore(
            tables,
            columns,
            (_metric("毛利率", 0.97),),
        )

        result = OnlineRetriever(
            _FakeRuntime(
                _snapshot(
                    store,
                    _FakeEmbedding(),
                    _sales_graph(include_region=False, include_date=True),
                )
            )
        ).retrieve(
            _request(
                "查询指定期间毛利率",
                metrics=("毛利率",),
                subjects=("销售",),
                time=("2025 年", "year"),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        self.assertEqual(
            [edge.edge_id for edge in result.join_path.joins],
            ["fk_completion_date"],
        )
        dynamic_schema = json.loads(result.dynamic_schema)
        self.assertEqual(
            {table["table_name"] for table in dynamic_schema["tables"]},
            {"fct_sales_order_line", "dim_date"},
        )
        self.assertIn(
            "full_date",
            {column["column_name"] for column in dynamic_schema["columns"]},
        )

    def test_explicit_date_without_date_table_stops_before_context(self) -> None:
        tables = (_table("table:fct", "fct_sales_order_line", 0.95),)
        columns = {
            "fct_sales_order_line": (
                _column("fct_sales_order_line", "net_sales_amount_cny", 0.95),
                _column("fct_sales_order_line", "sales_cost_amount_cny", 0.94),
                _column("fct_sales_order_line", "completion_date_key", 0.93),
                _column("fct_sales_order_line", "order_status", 0.92),
            ),
        }
        store = _FakeStore(
            tables,
            columns,
            (_metric("毛利率", 0.97),),
        )

        result = OnlineRetriever(
            _FakeRuntime(
                _snapshot(
                    store,
                    _FakeEmbedding(),
                    _sales_graph(include_region=False, include_date=True),
                )
            )
        ).retrieve(
            _request(
                "查询指定期间毛利率",
                metrics=("毛利率",),
                subjects=("销售",),
                time=("2025 年", "year"),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.PARTIAL_UNREACHABLE)
        self.assertIsNone(result.query_context)
        self.assertIn("dim_date", result.warnings[0])

    def test_entity_query_can_continue_without_metric(self) -> None:
        tables = (_table("table:customer", "dim_customer", 0.90),)
        columns = {"dim_customer": (_column("dim_customer", "customer_id", 0.90),)}
        store = _FakeStore(tables, columns, ())
        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), {"foreign_keys": []}))
        ).retrieve(_request("列出所有客户", subjects=("客户",)))

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        self.assertEqual(result.metrics, ())
        self.assertEqual(result.indicator_context, "")

    def test_entity_query_skips_metric_collection(self) -> None:
        tables = (_table("table:customer", "dim_customer", 0.90),)
        columns = {"dim_customer": (_column("dim_customer", "customer_id", 0.90),)}
        store = _CombinedMetricStore(
            tables,
            columns,
            (_metric("人民币净销售额", 0.95),),
        )

        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), {"foreign_keys": []}))
        ).retrieve(_request("列出所有客户", subjects=("客户",)))

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        self.assertEqual(store.metric_query_count, 0)

    def test_structured_metric_is_used_when_original_question_has_no_metric_term(
        self,
    ) -> None:
        tables = (_table("table:fct", "fct_sales_order_line", 0.90),)
        store = _FakeStore(
            tables,
            {"fct_sales_order_line": _multi_columns()["fct_sales_order_line"]},
            (_metric("毛利率", 0.95),),
        )

        result = OnlineRetriever(
            _FakeRuntime(
                _snapshot(store, _FakeEmbedding(), _sales_graph(include_region=False))
            )
        ).retrieve(
            _request(
                "请按业务主题处理",
                subjects=("销售",),
                metrics=("毛利率",),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        self.assertEqual([item.metric_name for item in result.metrics], ["毛利率"])

    def test_structured_entity_query_does_not_infer_metric_from_original_question(
        self,
    ) -> None:
        tables = (_table("table:customer", "dim_customer", 0.90),)
        store = _CombinedMetricStore(
            tables,
            {"dim_customer": (_column("dim_customer", "customer_id", 0.90),)},
            (_metric("毛利率", 0.95),),
        )

        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), {"foreign_keys": []}))
        ).retrieve(
            _request(
                "统计包含金额字段的客户",
                subjects=("客户",),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        self.assertEqual(result.metrics, ())
        self.assertEqual(store.metric_query_count, 0)

    def test_structured_filter_field_is_used_for_column_retrieval(self) -> None:
        tables = (_table("table:customer", "dim_customer", 0.90),)
        embedding = _FakeEmbedding()
        store = _FakeStore(
            tables,
            {"dim_customer": (_column("dim_customer", "customer_status", 0.90),)},
            (),
        )

        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, embedding, {"foreign_keys": []}))
        ).retrieve(
            _request(
                "查询客户",
                subjects=("客户",),
                filters=("客户状态",),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        self.assertTrue(any("客户状态" in query for query in embedding.queries))

    def test_string_is_not_a_formal_online_retrieval_input(self) -> None:
        retriever = OnlineRetriever(_UnavailableRuntime())

        with self.assertRaises(TypeError):
            retriever.retrieve("列出所有客户")

    def test_metric_intent_with_no_metric_hit_stops_before_context(self) -> None:
        tables = (_table("table:customer", "dim_customer", 0.90),)
        columns = {"dim_customer": (_column("dim_customer", "customer_id", 0.90),)}
        store = _CombinedMetricStore(tables, columns, ())

        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), {"foreign_keys": []}))
        ).retrieve(_request("查询退货金额", metrics=("退货金额",), subjects=("订单",)))

        self.assertEqual(result.status, RetrievalStatus.NO_METRIC_HIT)
        self.assertIsNone(result.query_context)

    def test_column_candidates_recover_explicit_grouping_field(self) -> None:
        tables = (
            _table("table:fct", "fct_sales_order_line", 0.95),
            _table(
                "table:region",
                "dim_sales_region",
                0.85,
                page_content="销售区域维度",
            ),
        )
        columns = {
            "fct_sales_order_line": tuple(
                _column("fct_sales_order_line", f"fact_{index}", 0.99 - index * 0.01)
                for index in range(4)
            ),
            "dim_sales_region": (
                _column("dim_sales_region", "sales_region_code", 0.90),
                _column("dim_sales_region", "sales_region_name", 0.89),
                _column("dim_sales_region", "sales_region_key", 0.88),
            ),
        }
        store = _FakeStore(tables, columns, ())
        result = OnlineRetriever(
            _FakeRuntime(
                _snapshot(
                    store,
                    _FakeEmbedding(),
                    {
                        "foreign_keys": [
                            {
                                "constraint_name": "fk_region",
                                "source_schema": "mart_sales",
                                "source_table": "fct_sales_order_line",
                                "source_columns": ["sales_region_key"],
                                "target_schema": "mart_sales",
                                "target_table": "dim_sales_region",
                                "target_columns": ["sales_region_key"],
                            }
                        ],
                        "primary_keys": [
                            {
                                "relationship_type": "primary_key",
                                "schema_name": "mart_sales",
                                "table_name": "dim_sales_region",
                                "column_names": ["sales_region_key"],
                                "constraint_name": "pk_dim_sales_region",
                            }
                        ],
                        "unique_constraints": [],
                    },
                )
            ),
            config=RetrievalConfig(column_top_k=2),
        ).retrieve(
            _request(
                "按销售区域查询",
                dimensions=("销售区域",),
                subjects=("销售",),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        assert result.query_context is not None
        self.assertIn(
            "sales_region_name",
            result.query_context.allowed_columns.get(
                "mart_sales.dim_sales_region",
                frozenset(),
            ),
        )

    def test_required_columns_are_recovered_when_semantic_top_k_misses_them(
        self,
    ) -> None:
        store = _RequiredColumnRecoveryStore(
            _multi_tables(),
            _multi_columns(),
            _multi_metrics(),
        )

        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), _multi_graph()))
        ).retrieve(
            _request(
                "按客户类型统计已完成订单数、人民币销售额和毛利率",
                metrics=("已完成订单数", "人民币销售额", "毛利率"),
                dimensions=("客户类型",),
                subjects=("销售",),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        assert result.query_context is not None
        self.assertTrue(
            {
                "order_id",
                "net_sales_amount_cny",
                "sales_cost_amount_cny",
                "order_status",
            }
            <= result.query_context.allowed_columns["mart_sales.fct_sales_order_line"]
        )

    def test_grouping_table_is_added_by_dimension_query_when_main_top_k_misses_it(
        self,
    ) -> None:
        fact = _table("table:fct", "fct_sales_order_line", 0.95)
        product = _table(
            "table:product",
            "dim_product",
            0.85,
            page_content="产品维度：产品线、产品类别、技术路线",
        )
        columns = {
            "fct_sales_order_line": (
                _column("fct_sales_order_line", "order_id", 0.90),
            ),
            "dim_product": (_column("dim_product", "technology_route", 0.90),),
        }
        store = _GroupingTableStore(
            (fact,),
            (product,),
            columns,
            (),
        )
        result = OnlineRetriever(
            _FakeRuntime(
                _snapshot(
                    store,
                    _GroupingEmbedding(),
                    {
                        "foreign_keys": [
                            {
                                "constraint_name": "fk_product",
                                "source_schema": "mart_sales",
                                "source_table": "fct_sales_order_line",
                                "source_columns": ["product_key"],
                                "target_schema": "mart_sales",
                                "target_table": "dim_product",
                                "target_columns": ["product_key"],
                            }
                        ],
                        "primary_keys": [
                            {
                                "relationship_type": "primary_key",
                                "schema_name": "mart_sales",
                                "table_name": "dim_product",
                                "column_names": ["product_key"],
                                "constraint_name": "pk_dim_product",
                            }
                        ],
                        "unique_constraints": [],
                    },
                )
            )
        ).retrieve(
            _request(
                "按技术路线查询",
                dimensions=("技术路线",),
                subjects=("订单",),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        assert result.query_context is not None
        self.assertIn("mart_sales.dim_product", result.query_context.allowed_tables)

    def test_metric_candidates_are_not_passed_to_llm_when_ambiguous(self) -> None:
        tables = (_table("table:fct", "fct_sales_order_line", 0.90),)
        columns = {
            "fct_sales_order_line": (_column("fct_sales_order_line", "order_id", 0.90),)
        }
        metrics = (_metric("人民币毛利", 0.80), _metric("人民币净销售额", 0.79))
        store = _FakeStore(tables, columns, metrics)
        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), {"foreign_keys": []}))
        ).retrieve(_request("统计经营表现", metrics=("经营表现",), subjects=("经营",)))

        self.assertEqual(result.status, RetrievalStatus.AMBIGUOUS)
        self.assertEqual(result.metrics, ())
        self.assertIsNone(result.query_context)

    def test_longest_metric_alias_wins_over_nested_short_alias(self) -> None:
        tables = (_table("table:fct", "fct_sales_order_line", 0.90),)
        columns = {
            "fct_sales_order_line": (_column("fct_sales_order_line", "order_id", 0.90),)
        }
        metrics = (
            _metric("人民币毛利", 0.80, aliases=("毛利",)),
            _metric("毛利率", 0.79, aliases=("毛利润率",)),
        )
        store = _FakeStore(tables, columns, metrics)
        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), {"foreign_keys": []}))
        ).retrieve(_request("查询毛利率", metrics=("毛利率",), subjects=("销售",)))

        self.assertEqual(result.status, RetrievalStatus.NO_REQUIRED_COLUMN_HIT)
        self.assertEqual([metric.metric_name for metric in result.metrics], ["毛利率"])

    def test_missing_metric_filter_column_stops_before_dynamic_context(self) -> None:
        tables = (_table("table:fct", "fct_sales_order_line", 0.90),)
        columns = {
            "fct_sales_order_line": (
                _column("fct_sales_order_line", "net_sales_amount_cny", 0.90),
                _column("fct_sales_order_line", "sales_cost_amount_cny", 0.89),
                _column("fct_sales_order_line", "completion_date_key", 0.89),
            ),
            "dim_date": (_column("dim_date", "full_date", 0.88),),
        }
        store = _FakeStore(
            tables, columns, (_metric("毛利率", 0.95, aliases=("毛利率",)),)
        )
        result = OnlineRetriever(
            _FakeRuntime(
                _snapshot(store, _FakeEmbedding(), _sales_graph(include_region=False))
            )
        ).retrieve(_request("查询毛利率", metrics=("毛利率",), subjects=("销售",)))

        self.assertEqual(result.status, RetrievalStatus.NO_REQUIRED_COLUMN_HIT)
        self.assertIsNone(result.query_context)

    def test_unreachable_required_table_stops(self) -> None:
        tables = (
            _table("table:fct", "fct_sales_order_line", 0.90),
            _table("table:customer", "dim_customer", 0.85, page_content="客户维度"),
        )
        columns = {
            "fct_sales_order_line": (
                _column("fct_sales_order_line", "order_id", 0.90),
            ),
            "dim_customer": (_column("dim_customer", "customer_id", 0.89),),
        }
        store = _FakeStore(tables, columns, ())
        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), {"foreign_keys": []}))
        ).retrieve(
            _request(
                "按客户分析订单",
                dimensions=("客户",),
                subjects=("订单",),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.PARTIAL_UNREACHABLE)
        self.assertIsNone(result.query_context)

    def test_multi_metric_retrieval_builds_one_verified_query_context(self) -> None:
        metrics = _multi_metrics()
        store = _CombinedMetricStore(
            _multi_tables(),
            _multi_columns(),
            metrics,
        )
        embedding = _FakeEmbedding()
        question = "按客户类型统计已完成订单数、人民币销售额和毛利率"

        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, embedding, _multi_graph()))
        ).retrieve(
            _request(
                question,
                metrics=("已完成订单数", "人民币销售额", "毛利率"),
                dimensions=("客户类型",),
                subjects=("销售",),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        self.assertEqual(result.request_shape, RequestShape.EXPLICIT_MULTI)
        self.assertEqual(result.fallback_policy, FallbackPolicy.FAIL_CLOSED)
        self.assertEqual(
            [metric.metric_name for metric in result.metrics],
            ["已完成订单数", "人民币净销售额", "毛利率"],
        )
        self.assertEqual(store.metric_query_count, 3)
        self.assertEqual(store.metric_limits, [10, 10, 10])
        self.assertEqual(len(result.evidence.metric_queries), 3)
        self.assertEqual(
            [item.target_document_id for item in result.evidence.metric_queries],
            [metric.document_id for metric in metrics],
        )
        self.assertIn("已完成订单数", embedding.queries)
        self.assertIn("人民币销售额", embedding.queries)
        self.assertIn("毛利率", embedding.queries)
        self.assertNotIn("人民币销售额\n人民币净销售额", embedding.queries)
        indicator = json.loads(result.indicator_context)
        self.assertEqual(
            [item["metric_name"] for item in indicator["requested_metrics"]],
            ["已完成订单数", "人民币净销售额", "毛利率"],
        )
        assert result.query_context is not None
        self.assertEqual(
            result.query_context.request_shape,
            RequestShape.EXPLICIT_MULTI,
        )
        self.assertEqual(len(result.query_context.metric_constraints), 3)
        self.assertEqual(len(result.query_context.join_constraints), 1)
        self.assertTrue(
            all(
                item.direction == "forward"
                for item in result.query_context.join_constraints
            )
        )
        self.assertEqual(
            {item.uniqueness_basis for item in result.query_context.join_constraints},
            {"primary_key:pk_dim_customer"},
        )
        fact_columns = result.query_context.allowed_columns[
            "mart_sales.fct_sales_order_line"
        ]
        self.assertTrue(
            {
                "order_id",
                "net_sales_amount_cny",
                "sales_cost_amount_cny",
                "order_status",
            }
            <= fact_columns
        )

    def test_multi_metric_supports_five_requested_metrics(self) -> None:
        metrics = _five_metrics()
        store = _CombinedMetricStore(
            _multi_tables(),
            _multi_columns(),
            metrics,
        )

        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), _multi_graph()))
        ).retrieve(
            _request(
                "按客户类型统计已完成订单数、人民币销售额、人民币销售成本、人民币毛利和毛利率",
                metrics=(
                    "已完成订单数",
                    "人民币销售额",
                    "人民币销售成本",
                    "人民币毛利",
                    "毛利率",
                ),
                dimensions=("客户类型",),
                subjects=("销售",),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        self.assertEqual(len(result.metrics), 5)
        self.assertEqual(store.metric_query_count, 5)
        self.assertEqual(store.metric_limits, [10, 10, 10, 10, 10])
        self.assertIsNotNone(result.query_context)

    def test_multi_metric_rejects_more_than_five_before_column_search(self) -> None:
        metrics = (
            *_multi_metrics(),
            _metric("订单折扣额", 0.95),
            _metric("订单返利额", 0.94),
        )
        store = _CombinedMetricStore(
            _multi_tables(),
            _multi_columns(),
            metrics,
        )

        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), _multi_graph()))
        ).retrieve(
            _request(
                "按客户类型统计已完成订单数、人民币销售额、毛利率、订单折扣额和订单返利额",
                metrics=(
                    "已完成订单数",
                    "人民币销售额",
                    "毛利率",
                    "订单折扣额",
                    "订单返利额",
                ),
                dimensions=("客户类型",),
                subjects=("销售",),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        self.assertEqual(len(result.metrics), 5)

        too_many = (*metrics, _metric("订单税额", 0.93))
        store = _CombinedMetricStore(
            _multi_tables(),
            _multi_columns(),
            too_many,
        )
        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), _multi_graph()))
        ).retrieve(
            _request(
                "按客户类型统计已完成订单数、人民币销售额、毛利率、订单折扣额、订单返利额和订单税额",
                metrics=(
                    "已完成订单数",
                    "人民币销售额",
                    "毛利率",
                    "订单折扣额",
                    "订单返利额",
                    "订单税额",
                ),
                dimensions=("客户类型",),
                subjects=("销售",),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.AMBIGUOUS)
        self.assertEqual(result.internal_reason, "TOO_MANY_METRICS")
        self.assertEqual(store.metric_query_count, 6)
        self.assertEqual(store.metric_limits, [10, 10, 10, 10, 10, 10])
        self.assertEqual(store.column_filters, [])
        self.assertIsNone(result.query_context)

    def test_multi_metric_stops_when_one_combined_metric_candidate_misses(self) -> None:
        metrics = _multi_metrics()
        store = _CombinedMetricStore(
            _multi_tables(),
            _multi_columns(),
            (metrics[0], metrics[1]),
        )

        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), _multi_graph()))
        ).retrieve(
            _request(
                "按客户类型统计已完成订单数、人民币销售额和毛利率",
                metrics=("已完成订单数", "人民币销售额", "毛利率"),
                dimensions=("客户类型",),
                subjects=("销售",),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.AMBIGUOUS)
        self.assertEqual(result.internal_reason, "AMBIGUOUS")
        self.assertEqual(result.fallback_policy, FallbackPolicy.FAIL_CLOSED)
        self.assertEqual(store.metric_query_count, 3)
        self.assertEqual(store.metric_limits, [10, 10, 10])
        self.assertEqual(len(result.evidence.metric_queries), 3)
        self.assertEqual(
            [len(item.hits) for item in result.evidence.metric_queries],
            [2, 2, 2],
        )
        self.assertEqual(store.column_filters, [])
        self.assertIsNone(result.query_context)

    def test_multi_metric_stops_when_any_required_column_is_missing(self) -> None:
        metrics = _multi_metrics()
        store = _CombinedMetricStore(
            _multi_tables(),
            _multi_columns(include_cost=False),
            metrics,
        )

        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), _multi_graph()))
        ).retrieve(
            _request(
                "按客户类型统计已完成订单数、人民币销售额和毛利率",
                metrics=("已完成订单数", "人民币销售额", "毛利率"),
                dimensions=("客户类型",),
                subjects=("销售",),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.NO_REQUIRED_COLUMN_HIT)
        self.assertEqual(result.fallback_policy, FallbackPolicy.FAIL_CLOSED)
        self.assertTrue(
            any(
                "sales_cost_amount_cny" in warning and "毛利率" in warning
                for warning in result.warnings
            )
        )
        self.assertIsNone(result.query_context)

    def test_multi_metric_rejects_reverse_one_to_many_join(self) -> None:
        metrics = _multi_metrics()
        store = _CombinedMetricStore(
            _multi_tables(),
            _multi_columns(),
            metrics,
        )

        result = OnlineRetriever(
            _FakeRuntime(
                _snapshot(
                    store,
                    _FakeEmbedding(),
                    _multi_graph(reverse_customer=True),
                )
            )
        ).retrieve(
            _request(
                "按客户类型统计已完成订单数、人民币销售额和毛利率",
                metrics=("已完成订单数", "人民币销售额", "毛利率"),
                dimensions=("客户类型",),
                subjects=("销售",),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.PARTIAL_UNREACHABLE)
        self.assertIn("正向展开", result.warnings[0])
        self.assertIsNone(result.query_context)

    def test_multi_metric_rejects_join_without_uniqueness_proof(self) -> None:
        metrics = _multi_metrics()
        store = _CombinedMetricStore(
            _multi_tables(),
            _multi_columns(),
            metrics,
        )

        result = OnlineRetriever(
            _FakeRuntime(
                _snapshot(
                    store,
                    _FakeEmbedding(),
                    _multi_graph(include_unique_keys=False),
                )
            )
        ).retrieve(
            _request(
                "按客户类型统计已完成订单数、人民币销售额和毛利率",
                metrics=("已完成订单数", "人民币销售额", "毛利率"),
                dimensions=("客户类型",),
                subjects=("销售",),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.PARTIAL_UNREACHABLE)
        self.assertIn("唯一约束", result.warnings[0])
        self.assertIsNone(result.query_context)

    def test_multi_metric_technical_failure_is_fail_closed(self) -> None:
        result = OnlineRetriever(_UnavailableRuntime()).retrieve(
            _request(
                "统计订单数、销售额和毛利率",
                metrics=("订单数", "销售额", "毛利率"),
                subjects=("订单",),
            )
        )

        self.assertEqual(result.status, RetrievalStatus.RETRIEVAL_UNAVAILABLE)
        self.assertEqual(result.fallback_policy, FallbackPolicy.FAIL_CLOSED)
        self.assertIsNone(result.query_context)

    def test_dynamic_context_is_json_serializable(self) -> None:
        tables = (_table("table:customer", "dim_customer", 0.90),)
        columns = {"dim_customer": (_column("dim_customer", "customer_id", 0.90),)}
        store = _FakeStore(tables, columns, ())
        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), {"foreign_keys": []}))
        ).retrieve(_request("列出所有客户", subjects=("客户",)))

        json.loads(result.dynamic_schema)
        self.assertIsNotNone(result.query_context)


def _request(
    question: str,
    *,
    subjects: tuple[str, ...],
    metrics: tuple[str, ...] = (),
    dimensions: tuple[str, ...] = (),
    time: tuple[str, str] | None = None,
    filters: tuple[str, ...] = (),
) -> RetrievalRequest:
    candidate = candidate_from_payload(
        {
            "query_type": "metric_analysis" if metrics else "entity_lookup",
            "subjects": list(subjects),
            "metrics": list(metrics),
            "dimensions": list(dimensions),
            "time": (
                {"text": time[0], "granularity": time[1]} if time is not None else None
            ),
            "filters": [
                {
                    "field_text": field_text,
                    "operator": "equals",
                    "values": ["已完成"],
                }
                for field_text in filters
            ],
        }
    )
    if len(metrics) <= 5:
        semantic_query = validate_candidate(
            candidate,
            original_question=question,
        )
    else:
        semantic_query = ValidatedSemanticQuery(
            query_type=QueryType.METRIC_ANALYSIS,
            subjects=subjects,
            metrics=metrics,
            dimensions=dimensions,
            time=None,
            filters=(),
            original_question=question,
        )
    return RetrievalRequest(
        question=question,
        request_shape=(
            RequestShape.EXPLICIT_MULTI if len(metrics) >= 2 else RequestShape.BASELINE
        ),
        fallback_policy=FallbackPolicy.FAIL_CLOSED,
        semantic_query=semantic_query,
    )


if __name__ == "__main__":
    unittest.main()
