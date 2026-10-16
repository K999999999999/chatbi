"""Qdrant Asset Store（Qdrant 资产适配器）只读行为测试。"""

from dataclasses import dataclass
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.rag_offline.embedding import EmbeddedText, SparseEmbedding
from src.rag_offline.qdrant_store import QdrantAssetStore, QdrantStoreError


@dataclass
class _Point:
    payload: object


class _Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def scroll(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class QdrantAssetStoreTest(unittest.TestCase):
    def test_search_supports_any_of_values_in_payload_filter(self) -> None:
        class _Condition:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class _QueryClient:
            def __init__(self) -> None:
                self.kwargs = None

            def query_points(self, **kwargs):
                self.kwargs = kwargs
                return SimpleNamespace(points=())

        client = _QueryClient()
        store = QdrantAssetStore(client)
        store._load_models = lambda: SimpleNamespace(
            FieldCondition=_Condition,
            MatchValue=_Condition,
            MatchAny=_Condition,
            Filter=_Condition,
        )

        store.search(
            "column-build",
            EmbeddedText(
                dense=(1.0, 0.0),
                sparse=SparseEmbedding(indices=(1,), values=(1.0,)),
            ),
            limit=20,
            filter_payload={
                "schema_name": "mart_sales",
                "table_name": ("fct_sales_order_line", "dim_sales_region"),
            },
        )

        assert client.kwargs is not None
        conditions = client.kwargs["query_filter"].must
        self.assertEqual(conditions[0].match.value, "mart_sales")
        self.assertEqual(
            conditions[1].match.any,
            ["fct_sales_order_line", "dim_sales_region"],
        )

    def test_scroll_payloads_reads_all_pages_without_vectors_and_sorts(self) -> None:
        client = _Client(
            [
                (
                    [_Point({"document_id": "metric:b", "metric_name": "B"})],
                    "next-page",
                ),
                (
                    [_Point({"document_id": "metric:a", "metric_name": "A"})],
                    None,
                ),
            ]
        )
        store = QdrantAssetStore(client)

        payloads = store.scroll_payloads("metric-build", page_size=1)

        self.assertEqual(
            [payload["document_id"] for payload in payloads],
            ["metric:a", "metric:b"],
        )
        self.assertEqual(len(client.calls), 2)
        self.assertIsNone(client.calls[0]["offset"])
        self.assertEqual(client.calls[1]["offset"], "next-page")
        self.assertTrue(client.calls[0]["with_payload"])
        self.assertFalse(client.calls[0]["with_vectors"])

    def test_scroll_payloads_rejects_invalid_page_size(self) -> None:
        store = QdrantAssetStore(_Client([]))

        with self.assertRaisesRegex(QdrantStoreError, "分页大小"):
            store.scroll_payloads("metric-build", page_size=0)

    def test_scroll_payloads_rejects_repeated_cursor(self) -> None:
        client = _Client(
            [
                ([_Point({"document_id": "metric:a"})], "same"),
                ([_Point({"document_id": "metric:b"})], "same"),
            ]
        )
        store = QdrantAssetStore(client)

        with self.assertRaisesRegex(QdrantStoreError, "游标重复"):
            store.scroll_payloads("metric-build", page_size=1)

    def test_scroll_payloads_wraps_client_failure(self) -> None:
        class _BrokenClient:
            def scroll(self, **_):
                raise RuntimeError("qdrant down")

        store = QdrantAssetStore(_BrokenClient())

        with self.assertRaisesRegex(QdrantStoreError, "读取集合 Payload 失败"):
            store.scroll_payloads("metric-build")

    def test_connection_failure_hides_url_credentials_query_and_exception(self) -> None:
        url = "https://URL_USER_CANARY:URL_PASS_CANARY@qdrant.internal:6333/?token=QUERY_CANARY"
        api_key = "API_KEY_CANARY"

        class _BrokenQdrantClient:
            def __init__(self, **_kwargs):
                raise RuntimeError(f"{url} {api_key} EXCEPTION_CANARY")

        module = SimpleNamespace(QdrantClient=_BrokenQdrantClient)
        with patch.dict(sys.modules, {"qdrant_client": module}):
            with self.assertRaises(QdrantStoreError) as caught:
                QdrantAssetStore.connect(url=url, api_key=api_key)

        message = str(caught.exception)
        self.assertIn("连接", message)
        self.assertIn("RuntimeError", message)
        for canary in (
            "URL_USER_CANARY",
            "URL_PASS_CANARY",
            "QUERY_CANARY",
            api_key,
            "EXCEPTION_CANARY",
        ):
            self.assertNotIn(canary, message)
        self.assertIsNone(caught.exception.__cause__)
        self.assertTrue(caught.exception.__suppress_context__)

    def test_search_failure_hides_sensitive_client_exception(self) -> None:
        canaries = (
            "URL_USER_CANARY",
            "QUERY_CANARY",
            "API_KEY_CANARY",
            "EXCEPTION_CANARY",
        )

        class _BrokenClient:
            def query_points(self, **_kwargs):
                raise RuntimeError(" ".join(canaries))

        store = QdrantAssetStore(_BrokenClient())
        query = EmbeddedText(
            dense=(1.0, 0.0), sparse=SparseEmbedding(indices=(1,), values=(1.0,))
        )
        with self.assertRaises(QdrantStoreError) as caught:
            store.search("metric-build", query)

        self.assertIn("检索", str(caught.exception))
        self.assertIn("RuntimeError", str(caught.exception))
        for canary in canaries:
            self.assertNotIn(canary, str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)

    def test_legacy_search_failure_hides_sensitive_client_exception(self) -> None:
        canary = "LEGACY_SEARCH_EXCEPTION_CANARY"

        class _LegacyClient:
            def search(self, **_kwargs):
                raise RuntimeError(canary)

        store = QdrantAssetStore(_LegacyClient())
        query = EmbeddedText(
            dense=(1.0, 0.0),
            sparse=SparseEmbedding(indices=(1,), values=(1.0,)),
        )

        with self.assertRaises(QdrantStoreError) as caught:
            store.search("metric-build", query)

        self.assertIn("检索", str(caught.exception))
        self.assertIn("RuntimeError", str(caught.exception))
        self.assertNotIn(canary, str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)
        self.assertTrue(caught.exception.__suppress_context__)

    def test_close_failure_hides_sensitive_client_exception(self) -> None:
        canary = "CLOSE_EXCEPTION_CANARY"

        class _BrokenClient:
            def close(self):
                raise RuntimeError(canary)

        with self.assertRaises(QdrantStoreError) as caught:
            QdrantAssetStore(_BrokenClient()).close()

        self.assertIn("关闭客户端", str(caught.exception))
        self.assertIn("RuntimeError", str(caught.exception))
        self.assertNotIn(canary, str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)
        self.assertTrue(caught.exception.__suppress_context__)


if __name__ == "__main__":
    unittest.main()
