"""验证 Schema 表级和字段级 Loader 的最小输出契约。"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.infrastructure.retrieval.column_loader import load_column_documents  # noqa: E402
from src.infrastructure.retrieval.metric_loader import (  # noqa: E402
    EXPECTED_METRIC_COUNT,
    MetricCatalogError,
    load_metric_documents,
)
from src.infrastructure.retrieval.table_loader import load_table_documents  # noqa: E402


def main() -> int:
    table_documents = load_table_documents(ROOT / "resources/schema/tables.json")
    column_documents = load_column_documents(ROOT / "resources/schema/columns.json")
    try:
        metric_documents = load_metric_documents(
            ROOT / "resources/semantic/sales/metrics.json"
        )
    except MetricCatalogError as exc:
        print(f"metric_catalog_validation = FAIL: {exc}")
        return 1

    table_count = len(table_documents)
    column_count = len(column_documents)
    metric_count = len(metric_documents)
    print(f"table_document_count = {table_count}")
    print(f"column_document_count = {column_count}")
    print(f"metric_document_count = {metric_count}")

    if table_documents:
        print(f"table_document_sample = {table_documents[0]!r}")
    if column_documents:
        print(f"column_document_sample = {column_documents[0]!r}")

    validation_passed = (
        table_count == 5
        and column_count == 40
        and metric_count == EXPECTED_METRIC_COUNT
    )
    print(f"validation_result = {'PASS' if validation_passed else 'FAIL'}")
    return 0 if validation_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
