import copy
import json
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from langchain_core.documents import Document
from qdrant_client.http.models import SparseVector

from src.application.offline_pipeline import (
    M4BuildError,
    POINT_ID_NAMESPACE,
    RepresentedRetrievalRecord,
    build_retrieval_assets,
    load_validated_catalogs,
    point_id_for_document,
    project_retrieval_records,
)
from src.infrastructure.offline_pipeline import (
    DENSE_DIMENSION,
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESOURCE_PATHS = {
    "tables": PROJECT_ROOT / "resources/schema/tables.json",
    "columns": PROJECT_ROOT / "resources/schema/columns.json",
    "metrics": PROJECT_ROOT / "resources/semantic/sales/metrics.json",
}


def _current_represented_records() -> list[RepresentedRetrievalRecord]:
    catalogs = load_validated_catalogs(
        tables_path=RESOURCE_PATHS["tables"],
        columns_path=RESOURCE_PATHS["columns"],
        relationships_path=PROJECT_ROOT / "resources/schema/relationships.json",
        metrics_path=RESOURCE_PATHS["metrics"],
    )
    return [
        RepresentedRetrievalRecord(
            document=document,
            dense=tuple(float(index) for index in range(DENSE_DIMENSION)),
            sparse={2: 0.2, 9: 0.9},
        )
        for document in project_retrieval_records(catalogs)
    ]


class _FakeCount:
    def __init__(self, count: int):
        self.count = count


class _FakeRecord:
    def __init__(self, point):
        self.id = point.id
        self.vector = copy.deepcopy(point.vector)
        self.payload = copy.deepcopy(point.payload)


class _FakeQdrantBackend:
    def __init__(self):
        self.collections: dict[str, dict[str, object]] = {}
        self.fail_on_upsert_collection: str | None = None
        self.corrupt_dense_collection: str | None = None
        self.upserted_collections: list[str] = []

    def create_collection(self, collection_name: str, **_kwargs):
        if collection_name in self.collections:
            raise RuntimeError(f"collection already exists: {collection_name}")
        self.collections[collection_name] = {"points": {}}
        return True

    def collection_exists(self, collection_name: str, **_kwargs) -> bool:
        return collection_name in self.collections

    def upsert(self, collection_name: str, points, **_kwargs):
        if collection_name == self.fail_on_upsert_collection:
            raise RuntimeError("fake upsert failure")
        point_map = self.collections[collection_name]["points"]
        for point in points:
            stored_point = copy.deepcopy(point)
            if collection_name == self.corrupt_dense_collection:
                stored_point.vector[DENSE_VECTOR_NAME] = [0.1]
            point_map[str(point.id)] = stored_point
        self.upserted_collections.append(collection_name)
        return True

    def count(self, collection_name: str, **_kwargs):
        return _FakeCount(len(self.collections[collection_name]["points"]))

    def scroll(self, collection_name: str, *, offset=None, limit=256, **_kwargs):
        points = list(self.collections[collection_name]["points"].values())
        start = 0 if offset is None else int(offset)
        selected = points[start : start + limit]
        next_offset = start + len(selected) if start + len(selected) < len(points) else None
        return [_FakeRecord(point) for point in selected], next_offset

    def delete_collection(self, collection_name: str, **_kwargs):
        self.collections.pop(collection_name, None)
        return True


def _document(record_type: str, **metadata) -> Document:
    return Document(
        page_content=f"{record_type.lower()} content",
        metadata={"record_type": record_type, "source_path": "resources/test.json", **metadata},
    )


def _records() -> list[RepresentedRetrievalRecord]:
    documents = [
        _document("TABLE", schema_name="mart_sales", table_name="orders"),
        _document(
            "COLUMN",
            schema_name="mart_sales",
            table_name="orders",
            column_name="order_id",
        ),
        _document("METRIC", metric_code="sales_revenue"),
    ]
    return [
        RepresentedRetrievalRecord(
            document=document,
            dense=tuple(float(index) for index in range(DENSE_DIMENSION)),
            sparse={9: 0.9, 2: 0.2},
        )
        for document in documents
    ]


class RetrievalAssetBuildingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = _FakeQdrantBackend()

    def _build(self, records=None, token="unit-build"):
        with patch(
            "src.application.offline_pipeline.create_qdrant_client",
            return_value=self.backend,
        ):
            return build_retrieval_assets(
                _records() if records is None else records,
                build_token=token,
            )

    def test_n_input_records_create_n_points_with_three_deterministic_routes(self):
        assets = self._build()

        self.assertEqual(
            (assets.table_count, assets.column_count, assets.metric_count),
            (1, 1, 1),
        )
        self.assertEqual(
            set(self.backend.collections),
            {
                "table_retrieval__candidate_unit-build",
                "column_retrieval__candidate_unit-build",
                "metric_retrieval__candidate_unit-build",
            },
        )
        self.assertEqual(sum((assets.table_count, assets.column_count, assets.metric_count)), 3)

    def test_current_record_types_are_routed_without_relationship_points(self):
        records = _records()
        assets = self._build(records)

        stored_types = []
        for collection in self.backend.collections.values():
            stored_types.extend(
                point.payload["metadata"]["record_type"]
                for point in collection["points"].values()
            )
        self.assertEqual(Counter(stored_types), Counter({"TABLE": 1, "COLUMN": 1, "METRIC": 1}))
        self.assertNotIn("RELATIONSHIP", stored_types)
        self.assertEqual(assets.total_count, len(records))

    def test_current_m1_to_m3_cardinality_is_stored_as_seven_sixty_nine_and_five(self):
        assets = self._build(_current_represented_records(), token="current-81")

        self.assertEqual(assets.table_count, 7)
        self.assertEqual(assets.column_count, 69)
        self.assertEqual(assets.metric_count, 5)
        self.assertEqual(assets.total_count, 81)
        self.assertEqual(
            sum(len(collection["points"]) for collection in self.backend.collections.values()),
            81,
        )

    def test_uuid5_point_id_is_stable_and_uses_unambiguous_identity_fields(self):
        table_a = _document("TABLE", schema_name="ab", table_name="c")
        table_b = _document("TABLE", schema_name="a", table_name="bc")

        self.assertEqual(point_id_for_document(table_a), point_id_for_document(table_a))
        self.assertNotEqual(point_id_for_document(table_a), point_id_for_document(table_b))
        self.assertNotEqual(
            point_id_for_document(table_a),
            point_id_for_document(_document("METRIC", metric_code="ab.c")),
        )

        canonical = json.dumps(
            ["TABLE", "ab", "c"],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        import uuid

        self.assertEqual(
            point_id_for_document(table_a),
            str(uuid.uuid5(POINT_ID_NAMESPACE, canonical)),
        )

    def test_dense_sparse_and_payload_are_mapped_without_vector_duplication(self):
        self._build()

        table_collection = self.backend.collections["table_retrieval__candidate_unit-build"]
        point = next(iter(table_collection["points"].values()))

        self.assertEqual(set(point.vector), {DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME})
        self.assertEqual(len(point.vector[DENSE_VECTOR_NAME]), DENSE_DIMENSION)
        self.assertIsInstance(point.vector[SPARSE_VECTOR_NAME], SparseVector)
        self.assertEqual(point.vector[SPARSE_VECTOR_NAME].indices, [2, 9])
        self.assertEqual(point.vector[SPARSE_VECTOR_NAME].values, [0.2, 0.9])
        self.assertEqual(point.payload["page_content"], "table content")
        self.assertEqual(point.payload["metadata"]["record_type"], "TABLE")
        self.assertEqual(point.payload["metadata"]["source_path"], "resources/test.json")
        self.assertNotIn(DENSE_VECTOR_NAME, point.payload)
        self.assertNotIn(SPARSE_VECTOR_NAME, point.payload)

    def test_structured_metric_metadata_survives_payload_round_trip(self):
        metric = _records()[-1]
        metric.document.metadata.update(
            {
                "filters": ["status = 'paid'"],
                "depends_on": ["sales_revenue"],
                "source_columns": None,
                "null_if": "sales = 0",
            }
        )

        self._build([metric])

        point = next(
            iter(self.backend.collections["metric_retrieval__candidate_unit-build"]["points"].values())
        )
        self.assertEqual(point.payload["metadata"]["filters"], ["status = 'paid'"])
        self.assertEqual(point.payload["metadata"]["depends_on"], ["sales_revenue"])
        self.assertIsNone(point.payload["metadata"]["source_columns"])
        self.assertEqual(point.payload["metadata"]["null_if"], "sales = 0")

    def test_invalid_record_type_fails_closed_without_assets(self):
        with self.assertRaises(M4BuildError):
            self._build([RepresentedRetrievalRecord(_document("RELATIONSHIP"), (0.1,) * DENSE_DIMENSION, {1: 0.1})])

        self.assertEqual(self.backend.collections, {})

    def test_backend_failure_cleans_candidates_and_preserves_previous_asset(self):
        self.backend.collections["table_retrieval"] = {"points": {"old": object()}}
        self.backend.fail_on_upsert_collection = "column_retrieval__candidate_failure-build"

        with self.assertRaises(M4BuildError):
            self._build(token="failure-build")

        self.assertIn("table_retrieval", self.backend.collections)
        self.assertNotIn("table_retrieval__candidate_failure-build", self.backend.collections)
        self.assertNotIn("column_retrieval__candidate_failure-build", self.backend.collections)
        self.assertNotIn("metric_retrieval__candidate_failure-build", self.backend.collections)

    def test_integrity_failure_cleans_candidates_without_partial_output(self):
        self.backend.corrupt_dense_collection = "table_retrieval__candidate_integrity-build"

        with self.assertRaises(M4BuildError):
            self._build(token="integrity-build")

        self.assertFalse(
            any(name.endswith("__candidate_integrity-build") for name in self.backend.collections)
        )

    def test_duplicate_point_identity_fails_before_backend_write(self):
        duplicate = _records()[0]
        with self.assertRaises(M4BuildError):
            self._build([duplicate, duplicate])

        self.assertEqual(self.backend.collections, {})


if __name__ == "__main__":
    unittest.main()
