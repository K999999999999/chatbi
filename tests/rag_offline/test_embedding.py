"""Embedding Provider（向量化提供者）契约测试。"""

import unittest

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

        with self.assertRaisesRegex(EmbeddingError, "prepare_embedding_model.py"):
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


if __name__ == "__main__":
    unittest.main()
