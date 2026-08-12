"""构建并验收 Schema 的 Qdrant Dense + Sparse 离线索引。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.infrastructure.retrieval.bge_m3 import BGE_M3Encoder  # noqa: E402
from src.infrastructure.retrieval.column_loader import (  # noqa: E402
    load_column_documents,
)
from src.infrastructure.retrieval.qdrant_store import (  # noqa: E402
    QdrantStore,
    QdrantStoreError,
)
from src.infrastructure.retrieval.schema_indexer import (  # noqa: E402
    COLUMN_COLLECTION,
    TABLE_COLLECTION,
    SchemaIndexError,
    SchemaIndexer,
)
from src.infrastructure.retrieval.table_loader import load_table_documents  # noqa: E402


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


def payload_of(point: Any) -> dict[str, Any]:
    payload = getattr(point, "payload", None)
    if not isinstance(payload, dict):
        raise SchemaIndexError("Qdrant Point payload is missing")
    return payload


def vector_parts(point: Any) -> tuple[list[float], list[int], list[float]]:
    vectors = getattr(point, "vector", None)
    if not isinstance(vectors, dict):
        raise SchemaIndexError("Qdrant Point named vectors are missing")
    dense = vectors.get("dense")
    sparse = vectors.get("sparse")
    if not isinstance(dense, list):
        raise SchemaIndexError("Qdrant Point dense vector is missing")
    indices = getattr(sparse, "indices", None)
    values = getattr(sparse, "values", None)
    if isinstance(sparse, dict):
        indices = sparse.get("indices")
        values = sparse.get("values")
    if not isinstance(indices, list) or not isinstance(values, list):
        raise SchemaIndexError("Qdrant Point sparse vector is missing")
    return dense, indices, values


def point_matches(point: Any, **expected: str) -> bool:
    payload = payload_of(point)
    return all(payload.get(key) == value for key, value in expected.items())


def validate_index(
    *,
    encoder: BGE_M3Encoder,
    store: QdrantStore,
    indexer: SchemaIndexer,
    table_document_count: int,
    column_document_count: int,
    repeated_build: str,
) -> bool:
    table_point_count = store.count(TABLE_COLLECTION)
    column_point_count = store.count(COLUMN_COLLECTION)
    table_sample = store.retrieve(
        TABLE_COLLECTION,
        [indexer.deterministic_point_id("table", "dim_customers")],
        with_vectors=True,
    )
    column_sample = store.retrieve(
        COLUMN_COLLECTION,
        [indexer.deterministic_point_id("column", "sales_orders.net_amount")],
        with_vectors=True,
    )
    if len(table_sample) != 1 or len(column_sample) != 1:
        raise SchemaIndexError("required Qdrant payload samples are missing")

    dense_vector, sparse_indices, sparse_values = vector_parts(column_sample[0])
    column_payload = payload_of(column_sample[0])
    payload_passed = (
        column_payload.get("kind") == "column"
        and column_payload.get("table_name") == "sales_orders"
        and column_payload.get("column_name") == "net_amount"
        and column_payload.get("data_type") == "DECIMAL(12,2)"
        and "字段：net_amount" in str(column_payload.get("page_content"))
        and "含义：不含税收入" in str(column_payload.get("page_content"))
    )
    dense_passed = len(dense_vector) == encoder.dense_dimension
    sparse_passed = bool(sparse_indices) and bool(sparse_values) and len(sparse_indices) == len(
        sparse_values
    )

    query_embeddings = encoder.encode_texts(["销售收入", "销售订单", "net_amount"])
    dense_column_hits = store.query_dense(
        COLUMN_COLLECTION,
        query_embeddings[0].dense,
        limit=10,
    )
    dense_table_hits = store.query_dense(
        TABLE_COLLECTION,
        query_embeddings[1].dense,
        limit=10,
    )
    sparse_hits = store.query_sparse(
        COLUMN_COLLECTION,
        query_embeddings[2].sparse,
        limit=10,
    )
    dense_column_query = any(
        point_matches(point, kind="column", table_name="sales_orders", column_name="net_amount")
        for point in dense_column_hits
    )
    dense_table_query = any(
        point_matches(point, kind="table", table_name="sales_orders")
        for point in dense_table_hits
    )
    sparse_query = any(
        point_matches(point, kind="column", table_name="sales_orders", column_name="net_amount")
        for point in sparse_hits
    )

    print("BGE-M3:")
    print("- local_load: PASS")
    print(f"- dense_dimension: {encoder.dense_dimension}")
    print(f"- sparse: {'PASS' if sparse_passed else 'FAIL'}")
    print("Qdrant:")
    print(f"- schema_tables: {'PASS' if table_point_count == 5 else 'FAIL'} ({table_point_count})")
    print(f"- schema_columns: {'PASS' if column_point_count == 40 else 'FAIL'} ({column_point_count})")
    print("Index:")
    print(f"- table_document_count: {table_document_count}")
    print(f"- column_document_count: {column_document_count}")
    print(f"- table_point_count: {table_point_count}")
    print(f"- column_point_count: {column_point_count}")
    print("- deterministic_id: PASS")
    print(f"- repeated_build: {repeated_build}")
    print("Smoke Test:")
    print(f"- dense_table_query: {'PASS' if dense_table_query else 'FAIL'}")
    print(f"- dense_column_query: {'PASS' if dense_column_query else 'FAIL'}")
    print(f"- sparse_query: {'PASS' if sparse_query else 'FAIL'}")
    print(f"- payload: {'PASS' if payload_passed else 'FAIL'}")

    passed = (
        table_document_count == 5
        and column_document_count == 40
        and table_point_count == 5
        and column_point_count == 40
        and dense_passed
        and sparse_passed
        and payload_passed
        and dense_table_query
        and dense_column_query
        and sparse_query
        and repeated_build in {"PASS", "NOT_RUN"}
    )
    print(f"validation_result: {'PASS' if passed else 'FAIL'}")
    return passed


def print_failure(layer: str, status: str, error: Exception) -> int:
    print(f"failure_layer: {layer}")
    print(f"failure_reason: {type(error).__name__}")
    print(f"validation_result: {status}")
    return 2 if status == "BLOCKED" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the offline Schema Qdrant index")
    parser.add_argument(
        "--repeat",
        action="store_true",
        help="run a second upsert in the same process to verify idempotency",
    )
    args = parser.parse_args()

    env = load_env(ROOT / ".env")
    try:
        table_documents = load_table_documents(ROOT / "resources/schema/tables.json")
        column_documents = load_column_documents(ROOT / "resources/schema/columns.json")
    except Exception as exc:
        return print_failure("Loader", "FAIL", exc)

    try:
        model_dir = resolve_path(env.get("BGE_MODEL_DIR", "models/bge-m3"), root=ROOT)
        use_fp16 = env.get("BGE_USE_FP16", "false").lower() in {"1", "true", "yes"}
        encoder = BGE_M3Encoder(model_dir, use_fp16=use_fp16)
    except Exception as exc:
        print(f"table_document_count: {len(table_documents)}")
        print(f"column_document_count: {len(column_documents)}")
        return print_failure("Embedding", "BLOCKED", exc)

    try:
        store = QdrantStore(env.get("QDRANT_URL", "http://127.0.0.1:6333"))
    except QdrantStoreError as exc:
        return print_failure("Qdrant", "BLOCKED", exc)

    indexer = SchemaIndexer(encoder, store)
    try:
        indexer.build(table_documents, column_documents)
        repeated_build = "NOT_RUN"
        if args.repeat:
            indexer.build(table_documents, column_documents)
            repeated_build = "PASS"
        passed = validate_index(
            encoder=encoder,
            store=store,
            indexer=indexer,
            table_document_count=len(table_documents),
            column_document_count=len(column_documents),
            repeated_build=repeated_build,
        )
        return 0 if passed else 1
    except QdrantStoreError as exc:
        return print_failure("Qdrant", "FAIL", exc)
    except Exception as exc:
        return print_failure("Index/Validation", "FAIL", exc)


if __name__ == "__main__":
    raise SystemExit(main())
