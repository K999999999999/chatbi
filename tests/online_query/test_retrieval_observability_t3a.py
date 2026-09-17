"""T3A Retrieval detail spans and safe evidence tests."""

import unittest

from src.observability.contracts import QuerySource
from src.observability.tracing import create_in_memory_recorder
from src.online_query.retrieval.multi_metric import build_retrieval_request
from src.online_query.retrieval import OnlineRetriever
from src.online_query.contracts import RetrievalStatus

from tests.online_query.test_retrieval import (
    _CombinedMetricStore,
    _FakeEmbedding,
    _FakeRuntime,
    _multi_columns,
    _multi_graph,
    _multi_metrics,
    _multi_tables,
    _metric,
    _sales_graph,
    _snapshot,
    _table,
    _column,
    _FakeStore,
)


class T3ARetrievalObservabilityTest(unittest.TestCase):
    def test_baseline_records_detail_spans_and_safe_bounded_evidence(self) -> None:
        tables = (
            _table("table:fct", "fct_sales_order_line", 0.95),
            _table(
                "table:region",
                "dim_sales_region",
                0.85,
                page_content="销售区域维度正文不应进入 Trace",
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
            tables,
            columns,
            (_metric("毛利率", 0.97, aliases=("毛利润率",)),),
        )
        recorder, exporter = create_in_memory_recorder()
        retriever = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), _sales_graph())),
            trace_recorder=recorder,
        )

        with recorder.query_trace(QuerySource.INTERNAL):
            result = retriever.retrieve("按销售区域统计毛利率")

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        spans = exporter.get_finished_spans()
        names = [span.name for span in spans]
        required = (
            "asset.resolve",
            "embedding.query",
            "table.search",
            "metric.search",
            "column.search",
            "join.resolve",
            "context.assemble",
        )
        for name in required:
            self.assertIn(name, names)
        self.assertEqual(names[-1], "query.request")
        self.assertEqual({span.context.trace_id for span in spans}, {spans[-1].context.trace_id})

        table_search = next(span for span in spans if span.name == "table.search")
        self.assertEqual(table_search.attributes["chatbi.retrieval.candidate_count"], 3)
        join = next(span for span in spans if span.name == "join.resolve")
        self.assertIn("fk_region", join.attributes["chatbi.retrieval.join.edge_ids"])
        self.assertNotIn(
            "fk_completion_date",
            join.attributes["chatbi.retrieval.join.edge_ids"],
        )

        rendered = repr(spans)
        for forbidden in (
            "按销售区域统计毛利率",
            "销售区域维度正文不应进入 Trace",
            "SUM(f.net_sales_amount_cny - f.sales_cost_amount_cny)",
            "metadata",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_multimetric_keeps_one_comprehensive_metric_search(self) -> None:
        metrics = _multi_metrics()
        store = _CombinedMetricStore(_multi_tables(), _multi_columns(), metrics)
        recorder, exporter = create_in_memory_recorder()
        request = build_retrieval_request(
            "按客户类型统计已完成订单数、人民币销售额和毛利率"
        )
        retriever = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), _multi_graph())),
            trace_recorder=recorder,
        )

        with recorder.query_trace(QuerySource.INTERNAL):
            result = retriever.retrieve(request)

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        self.assertEqual(store.metric_query_count, 1)
        self.assertEqual(
            len([span for span in exporter.get_finished_spans() if span.name == "metric.search"]),
            1,
        )

    def test_trace_recorder_failure_is_fail_open(self) -> None:
        class BrokenRecorder:
            def span(self, *args, **kwargs):
                raise RuntimeError("trace failure")

            def enrich_current(self, *args, **kwargs):
                raise RuntimeError("trace failure")

        store = _FakeStore(
            (_table("table:customer", "dim_customer", 0.90),),
            {"dim_customer": (_column("dim_customer", "customer_id", 0.90),)},
            (),
        )
        result = OnlineRetriever(
            _FakeRuntime(_snapshot(store, _FakeEmbedding(), {"foreign_keys": []})),
            trace_recorder=BrokenRecorder(),
        ).retrieve("列出所有客户")

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)


if __name__ == "__main__":
    unittest.main()
