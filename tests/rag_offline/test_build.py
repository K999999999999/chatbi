"""RAG Offline Build 编排、发布保护和评测路由测试。"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.rag_offline import (
    COLUMN_COLLECTION,
    METRIC_COLLECTION,
    TABLE_COLLECTION,
    BuildSummary,
    EmbeddedText,
    QdrantStoreError,
    SparseEmbedding,
    build_offline_assets,
    load_facts,
    load_published_asset,
)
from tests.rag_offline.test_relationships import _write_facts


class _FakeEmbedding:
    dimension = 4
    config = {
        "provider": "test",
        "model": "deterministic",
        "dimension": 4,
    }

    def __init__(self) -> None:
        self.document_texts: list[str] = []

    def embed_documents(self, texts):
        self.document_texts.extend(texts)
        return tuple(
            EmbeddedText(
                dense=(float(index), 0.0, 0.0, 1.0),
                sparse=SparseEmbedding(indices=(index,), values=(1.0,)),
            )
            for index, _ in enumerate(texts, 1)
        )

    def embed_query(self, text):
        return EmbeddedText(
            dense=(1.0, 0.0, 0.0, 1.0),
            sparse=SparseEmbedding(indices=(1,), values=(1.0,)),
        )


class _FakeStore:
    def __init__(self, fail_when_name_contains: str | None = None) -> None:
        self.collections: dict[str, tuple[str, ...]] = {}
        self.deleted: list[str] = []
        self.fail_when_name_contains = fail_when_name_contains

    def create_collection(self, collection_name: str, dimension: int) -> None:
        self._maybe_fail(collection_name)
        self.collections[collection_name] = ()

    def upsert_documents(self, collection_name, documents, embeddings) -> None:
        self._maybe_fail(collection_name)
        self.collections[collection_name] = tuple(
            document.document_id for document in documents
        )

    def validate_collection(self, collection_name, expected_count, probe) -> None:
        self._maybe_fail(collection_name)
        self.assert_count(collection_name, expected_count)

    def delete_collection(self, collection_name: str) -> None:
        self.deleted.append(collection_name)
        self.collections.pop(collection_name, None)

    def assert_count(self, collection_name: str, expected_count: int) -> None:
        if len(self.collections.get(collection_name, ())) != expected_count:
            raise AssertionError(collection_name)

    def _maybe_fail(self, collection_name: str) -> None:
        if (
            self.fail_when_name_contains
            and self.fail_when_name_contains in collection_name
        ):
            raise QdrantStoreError(f"injected failure: {collection_name}")


class BuildTest(unittest.TestCase):
    def test_build_publishes_three_collections_and_graph(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            output_root = root / "assets"
            source_root.mkdir()
            _write_facts(source_root)
            facts = load_facts(source_root, source_root / "metrics.json")
            embedding = _FakeEmbedding()
            store = _FakeStore()

            summary = build_offline_assets(
                embedding,
                store,
                facts=facts,
                output_dir=output_root,
                build_id="build-001",
            )
            published = load_published_asset(output_root)

        self.assertIsInstance(summary, BuildSummary)
        self.assertEqual(summary.status, "PUBLISHED")
        self.assertEqual(summary.table_document_count, 2)
        self.assertEqual(summary.column_document_count, 4)
        self.assertEqual(summary.metric_document_count, 1)
        self.assertEqual(summary.relationship_edge_count, 1)
        self.assertEqual(
            dict(summary.collections_reloaded),
            {
                TABLE_COLLECTION: True,
                COLUMN_COLLECTION: True,
                METRIC_COLLECTION: True,
            },
        )
        self.assertTrue(summary.published)
        self.assertEqual(published.build_id, "build-001")
        self.assertEqual(
            set(published.collection_names),
            {TABLE_COLLECTION, COLUMN_COLLECTION, METRIC_COLLECTION},
        )
        self.assertEqual(len(published.relationship_graph["foreign_keys"]), 1)
        self.assertEqual(len(store.collections), 3)

    def test_only_page_content_is_sent_to_embedding(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            embedding = _FakeEmbedding()

            summary = build_offline_assets(
                embedding,
                _FakeStore(),
                structure_dir=root,
                metrics_path=root / "metrics.json",
                output_dir=root / "assets",
                build_id="build-002",
            )

        self.assertTrue(summary.published)
        self.assertEqual(len(embedding.document_texts), 7)
        self.assertTrue(all(text.strip() for text in embedding.document_texts))
        self.assertTrue(all("doc_type" not in text for text in embedding.document_texts))

    def test_failure_keeps_previous_current_pointer(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            output_root = root / "assets"
            first_store = _FakeStore()
            first = build_offline_assets(
                _FakeEmbedding(),
                first_store,
                structure_dir=root,
                metrics_path=root / "metrics.json",
                output_dir=output_root,
                build_id="build-good",
            )
            pointer_before = (output_root / "current.json").read_text(
                encoding="utf-8"
            )
            failed_store = _FakeStore(fail_when_name_contains="_column__")
            second = build_offline_assets(
                _FakeEmbedding(),
                failed_store,
                structure_dir=root,
                metrics_path=root / "metrics.json",
                output_dir=output_root,
                build_id="build-bad",
            )
            pointer_after = (output_root / "current.json").read_text(
                encoding="utf-8"
            )

        self.assertTrue(first.published)
        self.assertEqual(second.status, "FAILED")
        self.assertFalse(second.published)
        self.assertEqual(second.failure_count, 1)
        self.assertEqual(second.failure_category, "VECTOR_STORE")
        self.assertEqual(pointer_after, pointer_before)
        self.assertEqual(failed_store.collections, {})
        self.assertGreaterEqual(len(failed_store.deleted), 1)

    def test_dimension_mismatch_fails_before_publish(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)

            summary = build_offline_assets(
                _FakeEmbedding(),
                _FakeStore(),
                structure_dir=root,
                metrics_path=root / "metrics.json",
                output_dir=root / "assets",
                expected_dimension=1024,
                build_id="build-dimension-bad",
            )

        self.assertEqual(summary.status, "FAILED")
        self.assertEqual(summary.failure_category, "VALIDATION")
        self.assertFalse(summary.published)

    def test_repeated_builds_use_new_physical_collections_without_duplicate_docs(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            output_root = root / "assets"
            store = _FakeStore()

            build_offline_assets(
                _FakeEmbedding(),
                store,
                structure_dir=root,
                metrics_path=root / "metrics.json",
                output_dir=output_root,
                build_id="build-a",
            )
            build_offline_assets(
                _FakeEmbedding(),
                store,
                structure_dir=root,
                metrics_path=root / "metrics.json",
                output_dir=output_root,
                build_id="build-b",
            )

            current = json.loads(
                (output_root / "current.json").read_text(encoding="utf-8")
            )

        self.assertEqual(current["build_id"], "build-b")
        self.assertEqual(len(store.collections), 6)
        for document_ids in store.collections.values():
            self.assertEqual(len(document_ids), len(set(document_ids)))

    def test_existing_build_id_fails_without_deleting_published_version(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            output_root = root / "assets"
            first = build_offline_assets(
                _FakeEmbedding(),
                _FakeStore(),
                structure_dir=root,
                metrics_path=root / "metrics.json",
                output_dir=output_root,
                build_id="build-existing",
            )
            manifest_path = output_root / "build-existing" / "manifest.json"
            manifest_before = manifest_path.read_text(encoding="utf-8")

            second = build_offline_assets(
                _FakeEmbedding(),
                _FakeStore(),
                structure_dir=root,
                metrics_path=root / "metrics.json",
                output_dir=output_root,
                build_id="build-existing",
            )
            published = load_published_asset(output_root)
            manifest_after = manifest_path.read_text(encoding="utf-8")

        self.assertTrue(first.published)
        self.assertEqual(second.status, "FAILED")
        self.assertEqual(second.failure_category, "VALIDATION")
        self.assertEqual(published.build_id, "build-existing")
        self.assertEqual(manifest_after, manifest_before)


if __name__ == "__main__":
    unittest.main()
