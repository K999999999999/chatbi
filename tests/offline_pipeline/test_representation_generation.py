import copy
import unittest
from collections import Counter, defaultdict
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
from langchain_core.documents import Document

from src.application.offline_pipeline import (
    M3GenerationError,
    RepresentedRetrievalRecord,
    generate_retrieval_representations,
    load_validated_catalogs,
    project_retrieval_records,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESOURCE_PATHS = {
    "tables": PROJECT_ROOT / "resources/schema/tables.json",
    "columns": PROJECT_ROOT / "resources/schema/columns.json",
    "relationships": PROJECT_ROOT / "resources/schema/relationships.json",
    "metrics": PROJECT_ROOT / "resources/semantic/sales/metrics.json",
}
MODEL_PATH = PROJECT_ROOT / "models/bge-m3"


def _load_current_documents() -> list[Document]:
    catalogs = load_validated_catalogs(
        tables_path=RESOURCE_PATHS["tables"],
        columns_path=RESOURCE_PATHS["columns"],
        relationships_path=RESOURCE_PATHS["relationships"],
        metrics_path=RESOURCE_PATHS["metrics"],
    )
    return project_retrieval_records(catalogs)


def _fake_encoded_values(texts: list[str]) -> tuple[list[tuple[float, ...]], list[dict[int, float]]]:
    dense = [tuple(float(index + dimension) for dimension in range(4)) for index, _ in enumerate(texts)]
    sparse = [{index + 100: 0.1} for index, _ in enumerate(texts)]
    return dense, sparse


class RetrievalRepresentationGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.documents = _load_current_documents()

    def _generate_with_fake(self, documents: list[Document] | None = None):
        input_documents = self.documents if documents is None else documents
        with patch(
            "src.application.offline_pipeline.encode_bge_m3",
            side_effect=lambda texts, **_: _fake_encoded_values(texts),
        ):
            return generate_retrieval_representations(
                input_documents,
                model_path=MODEL_PATH,
            )

    def test_current_m2_records_generate_one_bundle_per_document(self):
        represented = self._generate_with_fake()

        self.assertEqual(len(represented), len(self.documents))
        self.assertTrue(
            all(isinstance(item, RepresentedRetrievalRecord) for item in represented)
        )
        self.assertTrue(all(item.document is document for item, document in zip(represented, self.documents)))
        self.assertTrue(all(item.dense for item in represented))
        self.assertTrue(all(item.sparse for item in represented))

    def test_current_record_coverage_remains_seven_tables_sixty_nine_columns_five_metrics(self):
        represented = self._generate_with_fake()
        counts = Counter(item.document.metadata["record_type"] for item in represented)

        self.assertEqual(counts, {"TABLE": 7, "COLUMN": 69, "METRIC": 5})
        self.assertEqual(len(represented), 81)

    def test_production_cardinality_is_n_not_a_hardcoded_current_count(self):
        documents = self.documents[:2]

        represented = self._generate_with_fake(documents)

        self.assertEqual(len(represented), len(documents))
        self.assertEqual([item.document for item in represented], documents)

    def test_relationships_do_not_produce_representation_records(self):
        represented = self._generate_with_fake()

        self.assertFalse(
            any(item.document.metadata["record_type"] == "RELATIONSHIP" for item in represented)
        )

    def test_encoder_receives_one_ordered_batch(self):
        encoder = Mock(return_value=_fake_encoded_values([document.page_content for document in self.documents]))

        with patch("src.application.offline_pipeline.encode_bge_m3", encoder):
            generate_retrieval_representations(
                self.documents,
                model_path=MODEL_PATH,
                device="cpu",
                batch_size=8,
            )

        encoder.assert_called_once()
        texts = encoder.call_args.args[0]
        self.assertEqual(texts, [document.page_content for document in self.documents])
        self.assertEqual(encoder.call_args.kwargs["device"], "cpu")
        self.assertEqual(encoder.call_args.kwargs["batch_size"], 8)

    def test_document_identity_order_and_metadata_are_preserved(self):
        before = [
            (document.page_content, copy.deepcopy(document.metadata))
            for document in self.documents
        ]

        represented = self._generate_with_fake()

        self.assertEqual(
            [item.document for item in represented],
            self.documents,
        )
        self.assertEqual(
            [
                (item.document.page_content, item.document.metadata)
                for item in represented
            ],
            before,
        )

    def test_repeated_deterministic_fake_encoding_preserves_mapping(self):
        first = self._generate_with_fake()
        second = self._generate_with_fake()

        self.assertEqual(
            [(item.document, item.dense, item.sparse) for item in first],
            [(item.document, item.dense, item.sparse) for item in second],
        )

    def test_dense_count_mismatch_fails_without_partial_output(self):
        def wrong_dense(texts: list[str], **_):
            dense, sparse = _fake_encoded_values(texts)
            return dense[:-1], sparse

        with patch("src.application.offline_pipeline.encode_bge_m3", side_effect=wrong_dense):
            with self.assertRaises(M3GenerationError):
                generate_retrieval_representations(
                    self.documents,
                    model_path=MODEL_PATH,
                )

    def test_sparse_count_mismatch_fails_without_partial_output(self):
        def wrong_sparse(texts: list[str], **_):
            dense, sparse = _fake_encoded_values(texts)
            return dense, sparse[:-1]

        with patch("src.application.offline_pipeline.encode_bge_m3", side_effect=wrong_sparse):
            with self.assertRaises(M3GenerationError):
                generate_retrieval_representations(
                    self.documents,
                    model_path=MODEL_PATH,
                )

    def test_inconsistent_dense_dimension_fails_closed(self):
        dense, sparse = _fake_encoded_values(self.documents[:2])
        dense[1] = (0.1,)

        with patch(
            "src.application.offline_pipeline.encode_bge_m3",
            return_value=(dense, sparse[:2]),
        ):
            with self.assertRaises(M3GenerationError):
                generate_retrieval_representations(
                    self.documents[:2],
                    model_path=MODEL_PATH,
                )

    def test_missing_dense_fails_closed(self):
        with patch(
            "src.application.offline_pipeline.encode_bge_m3",
            return_value=(None, [{1: 0.1}] * len(self.documents)),
        ):
            with self.assertRaises(M3GenerationError):
                generate_retrieval_representations(
                    self.documents,
                    model_path=MODEL_PATH,
                )

    def test_missing_sparse_fails_closed(self):
        with patch(
            "src.application.offline_pipeline.encode_bge_m3",
            return_value=([(0.1,)] * len(self.documents), None),
        ):
            with self.assertRaises(M3GenerationError):
                generate_retrieval_representations(
                    self.documents,
                    model_path=MODEL_PATH,
                )

    def test_empty_record_representation_fails_closed(self):
        dense, sparse = _fake_encoded_values(self.documents)
        sparse[10] = {}

        with patch(
            "src.application.offline_pipeline.encode_bge_m3",
            return_value=(dense, sparse),
        ):
            with self.assertRaises(M3GenerationError):
                generate_retrieval_representations(
                    self.documents,
                    model_path=MODEL_PATH,
                )

    def test_encoder_exception_fails_without_partial_output(self):
        with patch(
            "src.application.offline_pipeline.encode_bge_m3",
            side_effect=RuntimeError("encoder failed"),
        ):
            with self.assertRaises(M3GenerationError):
                generate_retrieval_representations(
                    self.documents,
                    model_path=MODEL_PATH,
                )

    def test_invalid_record_type_fails_closed(self):
        invalid_document = Document(
            page_content="relationship",
            metadata={"record_type": "RELATIONSHIP"},
        )

        with self.assertRaises(M3GenerationError):
            self._generate_with_fake([invalid_document])


class BgeM3InfrastructureTests(unittest.TestCase):
    def test_flagembedding_output_is_normalized_to_neutral_python_values(self):
        raw_dense = np.asarray(
            [[np.float32(0.1), np.float32(0.2)], [np.float32(0.3), np.float32(0.4)]],
            dtype=np.float32,
        )
        raw_sparse = [
            defaultdict(float, {"16731": np.float32(0.2314297)}),
            defaultdict(float, {"10159": np.float32(0.18141289)}),
        ]
        fake_model = Mock()
        fake_model.encode.return_value = {
            "dense_vecs": raw_dense,
            "lexical_weights": raw_sparse,
            "colbert_vecs": None,
        }

        with patch(
            "src.infrastructure.offline_pipeline.BGEM3FlagModel",
            return_value=fake_model,
        ) as model_factory:
            from src.infrastructure.offline_pipeline import encode_bge_m3

            dense, sparse = encode_bge_m3(
                ["a", "b"],
                model_path=MODEL_PATH,
                device="cpu",
            )

        model_factory.assert_called_once()
        self.assertEqual(
            dense,
            [
                (float(np.float32(0.1)), float(np.float32(0.2))),
                (float(np.float32(0.3)), float(np.float32(0.4))),
            ],
        )
        self.assertEqual(sparse, [{16731: float(np.float32(0.2314297))}, {10159: float(np.float32(0.18141289))}])
        self.assertTrue(all(type(key) is int for item in sparse for key in item))
        self.assertTrue(all(type(value) is float for item in sparse for value in item.values()))

        model_kwargs = fake_model.encode.call_args.kwargs
        self.assertTrue(model_kwargs["return_dense"])
        self.assertTrue(model_kwargs["return_sparse"])
        self.assertFalse(model_kwargs["return_colbert_vecs"])

    def test_colbert_output_is_rejected_if_it_is_not_disabled(self):
        fake_model = Mock()
        fake_model.encode.return_value = {
            "dense_vecs": np.asarray([[0.1]], dtype=np.float32),
            "lexical_weights": [defaultdict(float, {"1": np.float32(0.1)})],
            "colbert_vecs": [np.asarray([[0.1]], dtype=np.float32)],
        }

        with patch(
            "src.infrastructure.offline_pipeline.BGEM3FlagModel",
            return_value=fake_model,
        ):
            from src.infrastructure.offline_pipeline import encode_bge_m3

            with self.assertRaises(ValueError):
                encode_bge_m3(
                    ["a"],
                    model_path=MODEL_PATH,
                    device="cpu",
                )


if __name__ == "__main__":
    unittest.main()
