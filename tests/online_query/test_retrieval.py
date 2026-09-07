"""Online Retrieval（在线检索）确定性链路测试。"""

import json
import unittest

from src.rag_offline.embedding import EmbeddedText, SparseEmbedding
from src.rag_offline.qdrant_store import SearchHit
from src.online_query.contracts import RetrievalConfig, RetrievalStatus
from src.online_query.rag_runtime import AssetSnapshot
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


class _GroupingEmbedding(_FakeEmbedding):
    def embed_query(self, text: str) -> EmbeddedText:
        self.queries.append(text)
        dense = (0.0, 1.0, 0.0, 0.0) if text == "技术路线" else (1.0, 0.0, 0.0, 1.0)
        return EmbeddedText(dense=dense, sparse=SparseEmbedding(indices=(1,), values=(1.0,)))


class _FakeRuntime:
    def __init__(self, snapshot: AssetSnapshot) -> None:
        self.snapshot = snapshot

    def get_snapshot(self) -> AssetSnapshot:
        return self.snapshot


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


def _metric(name, score, *, aliases=None):
    return _hit(
        f"metric:{name}",
        score,
        {
            "doc_type": "METRIC",
            "metric_name": name,
            "aliases": aliases or (),
            "level": "原子指标",
            "definition": f"{name}定义",
            "formula": "SUM(f.net_sales_amount_cny - f.sales_cost_amount_cny)",
            "data_source": "mart_sales.fct_sales_order_line",
            "time_field": "fct_sales_order_line.completion_date_key -> dim_date.full_date",
            "filters": ("f.order_status = 'completed'",),
            "depends_on": (),
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
    return {"foreign_keys": edges}


class RetrievalTest(unittest.TestCase):
    def test_metric_query_returns_dynamic_context_and_indicator_metadata(self) -> None:
        tables = (
            _table("table:fct", "fct_sales_order_line", 0.95),
            _table("table:region", "dim_sales_region", 0.85, page_content="销售区域维度"),
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
        store = _FakeStore(tables, columns, (_metric("毛利率", 0.97, aliases=("毛利润率",)),))
        embedding = _FakeEmbedding()
        runtime = _FakeRuntime(_snapshot(store, embedding, _sales_graph()))

        result = OnlineRetriever(runtime).retrieve("按销售区域统计毛利率")

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        self.assertEqual([metric.metric_name for metric in result.metrics], ["毛利率"])
        self.assertIn("SUM(f.net_sales_amount_cny - f.sales_cost_amount_cny)", result.indicator_context)
        self.assertIn("completion_date_key", result.indicator_context)
        self.assertIn("full_date", result.dynamic_schema)
        self.assertIn("date_key", result.dynamic_schema)
        self.assertEqual(
            result.query_context.allowed_tables,
            frozenset(
                {
                    "mart_sales.fct_sales_order_line",
                    "mart_sales.dim_sales_region",
                    "mart_sales.dim_date",
                }
            ),
        )
        self.assertTrue(all("table_name" in item for item in store.column_filters))
        self.assertEqual(len(result.join_path.joins), 2)

    def test_entity_query_can_continue_without_metric(self) -> None:
        tables = (_table("table:customer", "dim_customer", 0.90),)
        columns = {
            "dim_customer": (_column("dim_customer", "customer_id", 0.90),)
        }
        store = _FakeStore(tables, columns, ())
        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), {"foreign_keys": []}))
        ).retrieve("列出所有客户")

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        self.assertEqual(result.metrics, ())
        self.assertEqual(result.indicator_context, "")

    def test_grouping_column_is_preserved_when_fact_columns_fill_global_top_k(self) -> None:
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
                        ]
                    },
                )
            ),
            config=RetrievalConfig(column_top_k=2),
        ).retrieve("按销售区域查询")

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        assert result.query_context is not None
        self.assertIn(
            "sales_region_name",
            result.query_context.allowed_columns["mart_sales.dim_sales_region"],
        )

    def test_grouping_table_is_added_by_dimension_query_when_main_top_k_misses_it(self) -> None:
        fact = _table("table:fct", "fct_sales_order_line", 0.95)
        product = _table(
            "table:product",
            "dim_product",
            0.85,
            page_content="产品维度：产品线、产品类别、技术路线",
        )
        columns = {
            "fct_sales_order_line": (_column("fct_sales_order_line", "order_id", 0.90),),
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
                        ]
                    },
                )
            )
        ).retrieve("按技术路线查询")

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
        ).retrieve("统计经营表现")

        self.assertEqual(result.status, RetrievalStatus.AMBIGUOUS)
        self.assertEqual(result.metrics, ())
        self.assertIsNone(result.query_context)

    def test_longest_metric_alias_wins_over_nested_short_alias(self) -> None:
        tables = (_table("table:fct", "fct_sales_order_line", 0.90),)
        columns = {
            "fct_sales_order_line": (
                _column("fct_sales_order_line", "order_id", 0.90),
            )
        }
        metrics = (
            _metric("人民币毛利", 0.80, aliases=("毛利",)),
            _metric("毛利率", 0.79, aliases=("毛利润率",)),
        )
        store = _FakeStore(tables, columns, metrics)
        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), {"foreign_keys": []}))
        ).retrieve("查询毛利率")

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
        store = _FakeStore(tables, columns, (_metric("毛利率", 0.95, aliases=("毛利率",)),))
        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), _sales_graph(include_region=False)))
        ).retrieve("查询毛利率")

        self.assertEqual(result.status, RetrievalStatus.NO_REQUIRED_COLUMN_HIT)
        self.assertIsNone(result.query_context)

    def test_unreachable_required_table_stops(self) -> None:
        tables = (
            _table("table:fct", "fct_sales_order_line", 0.90),
            _table("table:customer", "dim_customer", 0.85, page_content="客户维度"),
        )
        columns = {
            "fct_sales_order_line": (_column("fct_sales_order_line", "order_id", 0.90),),
            "dim_customer": (_column("dim_customer", "customer_id", 0.89),),
        }
        store = _FakeStore(tables, columns, ())
        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), {"foreign_keys": []}))
        ).retrieve("按客户分析订单")

        self.assertEqual(result.status, RetrievalStatus.PARTIAL_UNREACHABLE)
        self.assertIsNone(result.query_context)

    def test_dynamic_context_is_json_serializable(self) -> None:
        tables = (_table("table:customer", "dim_customer", 0.90),)
        columns = {
            "dim_customer": (_column("dim_customer", "customer_id", 0.90),)
        }
        store = _FakeStore(tables, columns, ())
        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), {"foreign_keys": []}))
        ).retrieve("列出所有客户")

        json.loads(result.dynamic_schema)
        self.assertIsNotNone(result.query_context)


if __name__ == "__main__":
    unittest.main()
