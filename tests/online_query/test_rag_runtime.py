"""RAG Runtime（在线 RAG 运行时）资产快照测试。"""

from pathlib import Path
import unittest
from unittest.mock import Mock

from src.rag_offline.build import COLLECTIONS, PublishedAsset, PublishedAssetError
from src.rag_offline.config import OfflineBuildConfig
from src.rag_offline.qdrant_store import QdrantStoreError
from src.online_query.rag_runtime import (
    AssetUnavailableError,
    EmbeddingUnavailableError,
    RagRuntime,
    RetrievalUnavailableError,
)


class _FakeStore:
    def __init__(
        self,
        counts: dict[str, int] | None = None,
        *,
        missing: set[str] | None = None,
    ) -> None:
        self.counts = counts or {}
        self.missing = missing or set()
        self.scroll_count = 0
        self.close_count = 0

    def collection_exists(self, name: str) -> bool:
        return name not in self.missing

    def count(self, name: str) -> int:
        return self.counts.get(name, 1)

    def close(self) -> None:
        self.close_count += 1


class _FakeEmbedding:
    dimension = 4


class RagRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = OfflineBuildConfig(
            output_dir=Path("runtime-test-assets"),
            qdrant_url=None,
            qdrant_path=None,
            model_name_or_path="model",
            embedding_dimension=4,
        )

    def test_current_build_is_loaded_once_and_cached_by_build_id(self) -> None:
        asset_one = _asset("build-one")
        asset_two = _asset("build-two")
        loader = Mock(side_effect=[asset_one, asset_one, asset_two])
        stores = [_FakeStore(_counts()), _FakeStore(_counts())]
        store_factory = Mock(side_effect=stores)
        embedding_factory = Mock(return_value=_FakeEmbedding())
        runtime = RagRuntime(
            self.config,
            asset_loader=loader,
            store_factory=store_factory,
            embedding_factory=embedding_factory,
        )

        first = runtime.get_snapshot()
        second = runtime.get_snapshot()
        third = runtime.get_snapshot()

        self.assertIs(first, second)
        self.assertIsNot(first, third)
        self.assertEqual(first.asset_version, "build-one")
        self.assertEqual(third.asset_version, "build-two")
        self.assertEqual(loader.call_count, 3)
        self.assertEqual(store_factory.call_count, 2)
        self.assertEqual(embedding_factory.call_count, 2)
        self.assertEqual(stores[0].scroll_count, 0)
        self.assertEqual(stores[1].scroll_count, 0)

        runtime.close()
        self.assertEqual(stores[0].close_count, 1)
        self.assertEqual(stores[1].close_count, 1)

    def test_manifest_model_or_dimension_mismatch_is_asset_error(self) -> None:
        asset = _asset("bad-build", dimension=8, model="other-model")
        store_factory = Mock()
        runtime = RagRuntime(
            self.config,
            asset_loader=lambda _: asset,
            store_factory=store_factory,
            embedding_factory=lambda *_: _FakeEmbedding(),
        )

        with self.assertRaises(AssetUnavailableError):
            runtime.get_snapshot()

        store_factory.assert_not_called()

    def test_collection_missing_or_count_mismatch_closes_store(self) -> None:
        store = _FakeStore(missing={"TABLE-build"})
        runtime = RagRuntime(
            self.config,
            asset_loader=lambda _: _asset("build"),
            store_factory=lambda _: store,
            embedding_factory=lambda *_: _FakeEmbedding(),
        )

        with self.assertRaises(AssetUnavailableError):
            runtime.get_snapshot()

        self.assertEqual(store.close_count, 1)

    def test_qdrant_failure_is_classified_as_retrieval_unavailable(self) -> None:
        runtime = RagRuntime(
            self.config,
            asset_loader=lambda _: _asset("build"),
            store_factory=Mock(side_effect=QdrantStoreError("qdrant down")),
            embedding_factory=lambda *_: _FakeEmbedding(),
        )

        with self.assertRaises(RetrievalUnavailableError):
            runtime.get_snapshot()

    def test_embedding_failure_is_classified_and_store_is_closed(self) -> None:
        store = _FakeStore(_counts())
        runtime = RagRuntime(
            self.config,
            asset_loader=lambda _: _asset("build"),
            store_factory=lambda _: store,
            embedding_factory=Mock(
                side_effect=EmbeddingUnavailableError("model unavailable")
            ),
        )

        with self.assertRaises(EmbeddingUnavailableError):
            runtime.get_snapshot()

        self.assertEqual(store.close_count, 1)

    def test_invalid_published_file_is_asset_error(self) -> None:
        runtime = RagRuntime(
            self.config,
            asset_loader=Mock(side_effect=PublishedAssetError("invalid current")),
            store_factory=Mock(),
            embedding_factory=Mock(),
        )

        with self.assertRaises(AssetUnavailableError):
            runtime.get_snapshot()


def _asset(
    build_id: str,
    *,
    dimension: int = 4,
    model: str = "model",
) -> PublishedAsset:
    collection_names = {
        collection: f"{collection}-{build_id}"
        for collection in COLLECTIONS
    }
    manifest = {
        "status": "READY",
        "build_id": build_id,
        "collections": {
            collection: {
                "name": collection_names[collection],
                "document_count": 1,
            }
            for collection in COLLECTIONS
        },
        "embedding": {
            "model": model,
            "dimension": dimension,
        },
    }
    return PublishedAsset(
        build_id=build_id,
        manifest_path=Path("manifest.json"),
        collection_names=collection_names,
        relationship_graph={"foreign_keys": []},
        manifest=manifest,
    )


def _counts() -> dict[str, int]:
    return {
        "table-build-one": 1,
        "column-build-one": 1,
        "metric-build-one": 1,
        "table-build-two": 1,
        "column-build-two": 1,
        "metric-build-two": 1,
        "table-build": 1,
        "column-build": 1,
        "metric-build": 1,
    }


if __name__ == "__main__":
    unittest.main()
