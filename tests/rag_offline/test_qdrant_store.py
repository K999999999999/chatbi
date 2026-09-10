"""Qdrant Asset Store（Qdrant 资产适配器）只读行为测试。"""

from dataclasses import dataclass
import unittest

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


if __name__ == "__main__":
    unittest.main()
