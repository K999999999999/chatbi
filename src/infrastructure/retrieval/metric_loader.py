"""将权威指标目录加载为用于语义检索的 LangChain Document。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.documents import Document


EXPECTED_METRIC_COUNT = 5
METRIC_TYPES = {"atomic", "derived"}
REQUIRED_FIELDS = {
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


class MetricCatalogError(ValueError):
    """Metric Catalog 内容不符合 V1 结构或业务约束。"""


def load_metric_documents(path: str | Path) -> list[Document]:
    """读取 metrics.json，每个指标对象生成一个 Document。"""

    source_path = Path(path)
    try:
        data = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MetricCatalogError(f"metrics.json cannot be loaded: {type(exc).__name__}") from exc

    if not isinstance(data, list):
        raise MetricCatalogError("metrics.json must contain a JSON array")
    if len(data) != EXPECTED_METRIC_COUNT:
        raise MetricCatalogError(
            f"metrics.json must contain {EXPECTED_METRIC_COUNT} metrics, got {len(data)}"
        )

    documents: list[Document] = []
    metric_codes: set[str] = set()
    for index, item in enumerate(data):
        metric = _validate_metric(item, index=index)
        metric_code = str(metric["metric_code"])
        if metric_code in metric_codes:
            raise MetricCatalogError(f"duplicate metric_code: {metric_code}")
        metric_codes.add(metric_code)

        aliases = metric["aliases"]
        page_content = (
            f"指标名称：{metric['metric_name']}\n"
            f"别名：{'、'.join(aliases)}\n"
            f"业务定义：{metric['business_definition']}"
        )
        # metadata 有意保留完整 JSON 对象，供后续程序使用完整指标定义。
        documents.append(Document(page_content=page_content, metadata=dict(metric)))

    return documents


def _validate_metric(item: Any, *, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise MetricCatalogError(f"metric object at index {index} must be a JSON object")
    if set(item) != REQUIRED_FIELDS:
        missing = sorted(REQUIRED_FIELDS - set(item))
        extra = sorted(set(item) - REQUIRED_FIELDS)
        raise MetricCatalogError(
            f"metric object at index {index} has invalid fields; missing={missing}, extra={extra}"
        )

    for field in (
        "metric_code",
        "metric_name",
        "business_definition",
        "formula",
        "time_column",
        "unit",
    ):
        if not isinstance(item[field], str) or not item[field]:
            raise MetricCatalogError(f"metric {index} field {field} must be non-empty text")
    if item["metric_type"] not in METRIC_TYPES:
        raise MetricCatalogError(f"metric {index} has unsupported metric_type")
    for field in ("aliases", "filters", "depends_on"):
        if not isinstance(item[field], list) or not all(
            isinstance(value, str) for value in item[field]
        ):
            raise MetricCatalogError(f"metric {index} field {field} must be a string array")

    if item["metric_type"] == "atomic" and item["depends_on"] != []:
        raise MetricCatalogError(f"atomic metric {item['metric_code']} must have empty depends_on")
    if item["metric_type"] == "derived":
        if not item["depends_on"]:
            raise MetricCatalogError(
                f"derived metric {item['metric_code']} must have direct dependencies"
            )
        if item["filters"] != []:
            raise MetricCatalogError(f"derived metric {item['metric_code']} must have empty filters")

    return item
