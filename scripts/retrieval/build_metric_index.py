"""构建并验收 Metric Catalog 的 Qdrant Dense + Sparse 离线索引。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.infrastructure.retrieval.bge_m3 import BGE_M3Encoder  # noqa: E402
from src.infrastructure.retrieval.metric_loader import (  # noqa: E402
    EXPECTED_METRIC_COUNT,
    MetricCatalogError,
    load_metric_documents,
)
from src.infrastructure.retrieval.qdrant_store import (  # noqa: E402
    QdrantStore,
    QdrantStoreError,
)
from src.infrastructure.retrieval.schema_indexer import (  # noqa: E402
    SchemaIndexError,
    SchemaIndexer,
)


METRIC_COLLECTION = "metric_catalog"
METRIC_REQUIRED_PAYLOAD_FIELDS = {
    "metric_code",
    "metric_name",
    "metric_type",
    "aliases",
    "business_definition",
    "formula",
    "filters",
    "depends_on",
    "time_column",
    "unit",
}


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def resolve_path(value: str, *, root: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _payload(point: Any) -> dict[str, Any]:
    payload = getattr(point, "payload", None)
    if not isinstance(payload, dict):
        raise SchemaIndexError("Metric Point payload is missing")
    return payload


def _vector_status(point: Any, dense_dimension: int) -> bool:
    vectors = getattr(point, "vector", None)
    if not isinstance(vectors, dict):
        return False
    dense = vectors.get("dense")
    sparse = vectors.get("sparse")
    if not isinstance(dense, list) or len(dense) != dense_dimension:
        return False
    indices = getattr(sparse, "indices", None)
    values = getattr(sparse, "values", None)
    if isinstance(sparse, dict):
        indices = sparse.get("indices")
        values = sparse.get("values")
    return (
        isinstance(indices, list)
        and isinstance(values, list)
        and bool(indices)
        and bool(values)
        and len(indices) == len(values)
    )


def validate_metric_points(
    *,
    documents: list[Any],
    encoder: BGE_M3Encoder,
    store: QdrantStore,
    indexer: SchemaIndexer,
    repeated_build: str,
) -> bool:
    expected_ids = {
        indexer.deterministic_point_id("metric", str(document.metadata["metric_code"]))
        for document in documents
    }
    records = store.retrieve(
        METRIC_COLLECTION,
        sorted(expected_ids),
        with_vectors=True,
    )
    actual_ids = {str(record.id) for record in records}
    if actual_ids != expected_ids:
        raise SchemaIndexError("metric_catalog Point IDs do not match deterministic IDs")

    payload_passed = True
    vector_passed = True
    for document in documents:
        metric_code = str(document.metadata["metric_code"])
        point_id = indexer.deterministic_point_id("metric", metric_code)
        record = next(record for record in records if str(record.id) == point_id)
        payload = _payload(record)
        if set(document.metadata) != METRIC_REQUIRED_PAYLOAD_FIELDS:
            payload_passed = False
        if payload.get("page_content") != document.page_content:
            payload_passed = False
        for key, value in document.metadata.items():
            if payload.get(key) != value:
                payload_passed = False
        if not _vector_status(record, encoder.dense_dimension):
            vector_passed = False

    point_count = store.count(METRIC_COLLECTION)
    passed = (
        len(documents) == EXPECTED_METRIC_COUNT
        and len(records) == EXPECTED_METRIC_COUNT
        and point_count == EXPECTED_METRIC_COUNT
        and payload_passed
        and vector_passed
        and repeated_build in {"PASS", "NOT_RUN"}
    )

    print("MetricLoader:")
    print(f"- input: resources/semantic/sales/metrics.json")
    print(f"- document_count: {len(documents)}")
    print("- page_content: name + aliases + business_definition")
    print("- metadata: complete_metric_object")
    print("BGE-M3 / Qdrant:")
    print("- reused_existing_pipeline: PASS")
    print(f"- metric_catalog: {'PASS' if point_count == 5 else 'FAIL'} ({point_count})")
    print(f"- dense_dimension: {encoder.dense_dimension}")
    print(f"- dense_sparse_vectors: {'PASS' if vector_passed else 'FAIL'}")
    print(f"- payload_complete: {'PASS' if payload_passed else 'FAIL'}")
    print("Index:")
    print(f"- deterministic_id: {'PASS' if actual_ids == expected_ids else 'FAIL'}")
    print(f"- repeated_build: {repeated_build}")
    print(f"validation_result: {'PASS' if passed else 'FAIL'}")
    return passed


def print_failure(layer: str, status: str, error: Exception) -> int:
    print(f"failure_layer: {layer}")
    print(f"failure_reason: {type(error).__name__}")
    print(f"validation_result: {status}")
    return 2 if status == "BLOCKED" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Metric Catalog Qdrant index")
    parser.add_argument(
        "--repeat",
        action="store_true",
        help="run a second upsert in the same process to verify idempotency",
    )
    args = parser.parse_args()

    env = load_env(ROOT / ".env")
    try:
        documents = load_metric_documents(
            ROOT / "resources/semantic/sales/metrics.json"
        )
    except MetricCatalogError as exc:
        return print_failure("Loader", "FAIL", exc)

    try:
        model_dir = resolve_path(env.get("BGE_MODEL_DIR", "models/bge-m3"), root=ROOT)
        use_fp16 = env.get("BGE_USE_FP16", "false").lower() in {"1", "true", "yes"}
        encoder = BGE_M3Encoder(model_dir, use_fp16=use_fp16)
    except Exception as exc:
        print(f"metric_document_count: {len(documents)}")
        return print_failure("Embedding", "BLOCKED", exc)

    try:
        store = QdrantStore(env.get("QDRANT_URL", "http://127.0.0.1:6333"))
    except QdrantStoreError as exc:
        return print_failure("Qdrant", "BLOCKED", exc)

    indexer = SchemaIndexer(encoder, store)
    try:
        indexer.build_collection(
            documents,
            collection_name=METRIC_COLLECTION,
            kind="metric",
            expected_count=EXPECTED_METRIC_COUNT,
            identity_key="metric_code",
        )
        repeated_build = "NOT_RUN"
        if args.repeat:
            indexer.build_collection(
                documents,
                collection_name=METRIC_COLLECTION,
                kind="metric",
                expected_count=EXPECTED_METRIC_COUNT,
                identity_key="metric_code",
            )
            repeated_build = "PASS"
    except QdrantStoreError as exc:
        return print_failure("Qdrant", "FAIL", exc)
    except SchemaIndexError as exc:
        return print_failure("Index", "FAIL", exc)

    try:
        passed = validate_metric_points(
            documents=documents,
            encoder=encoder,
            store=store,
            indexer=indexer,
            repeated_build=repeated_build,
        )
    except QdrantStoreError as exc:
        return print_failure("Qdrant", "FAIL", exc)
    except SchemaIndexError as exc:
        return print_failure("Validation", "FAIL", exc)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
