"""Embedding Provider（向量化提供者）契约测试。"""

import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock
from types import SimpleNamespace
from unittest.mock import patch

from src.rag_offline.embedding import (
    BgeM3EmbeddingProvider,
    EmbeddingError,
)


class _FakeModel:
    def __init__(self) -> None:
        self.document_calls: list[tuple[tuple[str, ...], dict[str, object]]] = []
        self.query_calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def encode(self, texts, **kwargs):
        self.document_calls.append((tuple(texts), kwargs))
        return {
            "dense_vecs": [[float(index)] * 4 for index, _ in enumerate(texts, 1)],
            "lexical_weights": [{9: 0.2, 3: 0.8} for _ in texts],
        }

    def encode_queries(self, texts, **kwargs):
        self.query_calls.append((tuple(texts), kwargs))
        return {
            "dense_vecs": [[0.1] * 4 for _ in texts],
            "lexical_weights": [{2: 1.0} for _ in texts],
        }


class EmbeddingProviderTest(unittest.TestCase):
    def test_model_metadata_records_the_pinned_revision(self) -> None:
        provider = BgeM3EmbeddingProvider(
            model_name_or_path="local-test",
            model=_FakeModel(),
        )

        self.assertEqual(
            provider.config["revision"],
            "5617a9f61b028005a4858fdac845db406aefb181",
        )

    def test_model_loading_requires_a_prepared_local_snapshot(self) -> None:
        provider = BgeM3EmbeddingProvider(model_name_or_path="missing-model")

        with self.assertRaisesRegex(EmbeddingError, "src.bootstrap prepare-model"):
            provider._load_model()

    def test_bge_adapter_parses_dense_and_sparse_outputs(self) -> None:
        model = _FakeModel()
        provider = BgeM3EmbeddingProvider(
            model_name_or_path="local-test",
            model=model,
        )

        # 覆盖真实模型固定的 1024 维约束，测试桩只需返回最小维度。
        provider.MODEL_DIMENSION = 4
        documents = provider.embed_documents(["字段正文"])
        query = provider.embed_query("查询问题")

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].dense, (1.0, 1.0, 1.0, 1.0))
        self.assertEqual(documents[0].sparse.indices, (3, 9))
        self.assertEqual(documents[0].sparse.values, (0.8, 0.2))
        self.assertEqual(query.dimension, 4)
        self.assertEqual(model.document_calls[0][0], ("字段正文",))
        self.assertEqual(model.query_calls[0][0], ("查询问题",))

    def test_rejects_wrong_model_dimension(self) -> None:
        model = _FakeModel()
        provider = BgeM3EmbeddingProvider(
            model_name_or_path="local-test",
            model=model,
        )

        with self.assertRaisesRegex(EmbeddingError, "维度"):
            provider.embed_documents(["正文"])

    def test_rejects_empty_text(self) -> None:
        provider = BgeM3EmbeddingProvider(
            model_name_or_path="local-test",
            model=_FakeModel(),
        )

        with self.assertRaisesRegex(EmbeddingError, "不能为空"):
            provider.embed_documents([""])

    def test_concurrent_first_load_constructs_one_shared_model(self) -> None:
        worker_count = 4
        provider = BgeM3EmbeddingProvider(model_name_or_path="prepared-model")
        provider.MODEL_DIMENSION = 4
        start = Barrier(worker_count)
        construction_started = Event()
        allow_construction = Event()
        count_lock = Lock()
        construction_count = 0
        model = _FakeModel()

        def construct(*_args, **_kwargs):
            nonlocal construction_count
            with count_lock:
                construction_count += 1
            construction_started.set()
            if not allow_construction.wait(timeout=3):
                raise RuntimeError("test construction gate timed out")
            return model

        namespace = SimpleNamespace(BGEM3FlagModel=construct)
        with patch("src.rag_offline.embedding.Path.is_dir", return_value=True):
            with patch.dict("sys.modules", {"FlagEmbedding": namespace}):
                with ThreadPoolExecutor(max_workers=worker_count) as pool:
                    futures = [
                        pool.submit(
                            lambda: (start.wait(timeout=3), provider._load_model())[1]
                        )
                        for _ in range(worker_count)
                    ]
                    self.assertTrue(construction_started.wait(timeout=3))
                    allow_construction.set()
                    loaded = [future.result(timeout=3) for future in futures]

        self.assertEqual(construction_count, 1)
        self.assertTrue(all(value is model for value in loaded))
        self.assertIs(provider._load_model(), model)

    def test_failed_first_load_releases_lock_for_a_later_attempt(self) -> None:
        provider = BgeM3EmbeddingProvider(model_name_or_path="prepared-model")
        model = _FakeModel()
        calls = 0

        def construct(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("temporary model initialization failure")
            return model

        namespace = SimpleNamespace(BGEM3FlagModel=construct)
        with patch("src.rag_offline.embedding.Path.is_dir", return_value=True):
            with patch.dict("sys.modules", {"FlagEmbedding": namespace}):
                with self.assertRaisesRegex(EmbeddingError, "无法加载 Embedding 模型"):
                    provider._load_model()
                self.assertIs(provider._load_model(), model)

        self.assertEqual(calls, 2)

    def test_model_inference_is_not_serialized_by_the_load_lock(self) -> None:
        barrier = Barrier(2)

        class _ConcurrentModel:
            def encode(self, texts, **_kwargs):
                barrier.wait(timeout=2)
                return {
                    "dense_vecs": [[0.1] * 4 for _ in texts],
                    "lexical_weights": [{1: 1.0} for _ in texts],
                }

        provider = BgeM3EmbeddingProvider(
            model_name_or_path="injected-model",
            model=_ConcurrentModel(),
        )
        provider.MODEL_DIMENSION = 4
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(provider.embed_documents, (("第一段",), ("第二段",)))
            )

        self.assertEqual([len(result) for result in results], [1, 1])


if __name__ == "__main__":
    unittest.main()
