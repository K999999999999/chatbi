"""RAG Offline Retrieval Evaluation 测试。"""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.rag_offline import (
    COLUMN_COLLECTION,
    METRIC_COLLECTION,
    TABLE_COLLECTION,
    EmbeddedText,
    RetrievalCase,
    SearchHit,
    SparseEmbedding,
    default_retrieval_cases,
    evaluate_retrieval,
    load_facts,
)


class _FakeEmbedding:
    dimension = 4
    config = {"provider": "test", "dimension": 4}

    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_query(self, text: str) -> EmbeddedText:
        self.queries.append(text)
        return EmbeddedText(
            dense=(1.0, 0.0, 0.0, 1.0),
            sparse=SparseEmbedding(indices=(1,), values=(1.0,)),
        )


class _FakeSearchStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def search(self, collection_name, query, *, limit=5, filter_payload=None):
        self.calls.append((collection_name, filter_payload))
        return (
            SearchHit(
                document_id="expected",
                score=1.0,
                payload={"document_id": "expected"},
            ),
        )


class RetrievalEvaluationTest(unittest.TestCase):
    def test_default_cases_cover_three_routes_and_value_examples(self) -> None:
        cases = default_retrieval_cases(load_facts())

        self.assertEqual(
            {case.collection for case in cases},
            {TABLE_COLLECTION, COLUMN_COLLECTION, METRIC_COLLECTION},
        )
        self.assertTrue(
            any(
                "completed" in case.query and case.collection == COLUMN_COLLECTION
                for case in cases
            )
        )
        self.assertTrue(any(case.filter_payload for case in cases))

    def test_evaluation_routes_each_case_to_its_declared_collection(self) -> None:
        embedding = _FakeEmbedding()
        store = _FakeSearchStore()
        cases = (
            RetrievalCase(
                case_id="table",
                collection=TABLE_COLLECTION,
                query="表",
                expected_document_ids=("expected",),
            ),
            RetrievalCase(
                case_id="column",
                collection=COLUMN_COLLECTION,
                query="字段",
                expected_document_ids=("expected",),
                filter_payload={"table_name": "fct_sales"},
            ),
        )

        summary = evaluate_retrieval(
            embedding,
            store,
            {
                TABLE_COLLECTION: "table-v1",
                COLUMN_COLLECTION: "column-v1",
                METRIC_COLLECTION: "metric-v1",
            },
            cases,
        )

        self.assertEqual(summary.total_cases, 2)
        self.assertEqual(summary.passed_cases, 2)
        self.assertEqual(summary.accuracy, 1.0)
        self.assertEqual(
            store.calls,
            [
                ("table-v1", None),
                ("column-v1", {"table_name": "fct_sales"}),
            ],
        )


if __name__ == "__main__":
    unittest.main()
