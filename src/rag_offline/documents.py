"""Build TABLE、COLUMN、METRIC retrieval documents（检索文档）。"""

from collections.abc import Mapping
from dataclasses import dataclass
import json
from types import MappingProxyType
from typing import Any

from .sources import Facts


TABLE_COLLECTION = "TABLE"
COLUMN_COLLECTION = "COLUMN"
METRIC_COLLECTION = "METRIC"


@dataclass(frozen=True, slots=True)
class RetrievalDocument:
    """一份可写入向量集合的检索文档。"""

    document_id: str
    collection: str
    page_content: str
    metadata: Mapping[str, Any]

    def to_payload(self) -> dict[str, Any]:
        """转换成可直接作为向量库 payload 的 JSON 对象。"""

        payload = {
            "document_id": self.document_id,
            "collection": self.collection,
            "page_content": self.page_content,
            "metadata": _jsonable(self.metadata),
        }
        # 在边界处验证，避免不可序列化对象进入向量库。
        json.dumps(payload, ensure_ascii=False)
        return payload


def build_documents(facts: Facts) -> tuple[RetrievalDocument, ...]:
    """从已校验事实源生成三类检索文档，保持源顺序且不重复。"""

    return (
        *_build_table_documents(facts.tables),
        *_build_column_documents(facts.columns),
        *_build_metric_documents(facts.metrics),
    )


def _build_table_documents(
    tables: tuple[dict[str, Any], ...],
) -> tuple[RetrievalDocument, ...]:
    documents: list[RetrievalDocument] = []
    for table in tables:
        qualified = _qualified(table)
        lines = [f"表名：{qualified}"]
        table_type = table["table_type"]
        if table_type:
            lines.append(f"表类型：{table_type}")
        description = table["description"]
        if description:
            lines.append(f"业务含义：{description}")
        documents.append(
            RetrievalDocument(
                document_id=f"table:{qualified}",
                collection=TABLE_COLLECTION,
                page_content="\n".join(lines),
                metadata=_freeze(
                    {
                        "doc_type": "TABLE",
                        "schema_name": table["schema_name"],
                        "table_name": table["table_name"],
                        "table_type": table_type,
                    }
                ),
            )
        )
    return tuple(documents)


def _build_column_documents(
    columns: tuple[dict[str, Any], ...],
) -> tuple[RetrievalDocument, ...]:
    documents: list[RetrievalDocument] = []
    for column in columns:
        qualified = _qualified(column)
        lines = [
            f"字段名：{column['column_name']}（所属表：{qualified}）",
            f"数据类型：{column['data_type']}",
        ]
        key_attributes = []
        if column["is_primary_key"]:
            key_attributes.append("主键")
        if column["is_foreign_key"]:
            key_attributes.append("外键")
        if key_attributes:
            lines.append(f"键属性：{'/'.join(key_attributes)}")
        description = column["description"]
        if description:
            lines.append(f"字段含义：{description}")
        value_examples = column["value_examples"]
        if value_examples:
            lines.append(f"字段值示例：{'、'.join(value_examples)}")
        documents.append(
            RetrievalDocument(
                document_id=f"column:{qualified}.{column['column_name']}",
                collection=COLUMN_COLLECTION,
                page_content="\n".join(lines),
                metadata=_freeze(
                    {
                        "doc_type": "COLUMN",
                        "schema_name": column["schema_name"],
                        "table_name": column["table_name"],
                        "column_name": column["column_name"],
                        "data_type": column["data_type"],
                        "nullable": column["nullable"],
                        "is_primary_key": column["is_primary_key"],
                        "is_foreign_key": column["is_foreign_key"],
                    }
                ),
            )
        )
    return tuple(documents)


def _build_metric_documents(
    metrics: tuple[dict[str, Any], ...],
) -> tuple[RetrievalDocument, ...]:
    documents: list[RetrievalDocument] = []
    for metric in metrics:
        # page_content 是用于 Embedding（向量化）的检索文本，只保留指标识别和
        # 业务语义。公式、物理来源和时间口径属于结构化业务事实，放入 metadata，
        # 避免技术细节干扰语义召回，同时保留给在线程序和 LLM 使用。
        lines = [f"指标名：{metric['name']}"]
        aliases = metric["aliases"]
        if aliases:
            lines.append(f"别名：{'、'.join(aliases)}")
        level = metric["level"]
        if level:
            lines.append(f"指标层级：{level}")
        definition = metric["definition"]
        if definition:
            lines.append(f"指标定义：{definition}")
        documents.append(
            RetrievalDocument(
                document_id=f"metric:{metric['name']}",
                collection=METRIC_COLLECTION,
                page_content="\n".join(lines),
                metadata=_freeze(
                    {
                        "doc_type": "METRIC",
                        "metric_name": metric["name"],
                        "aliases": aliases,
                        "level": level,
                        "definition": definition,
                        "formula": metric["formula"],
                        "data_source": metric["data_source"],
                        "time_field": metric["time_field"],
                        "filters": metric["filters"],
                        "depends_on": metric["depends_on"],
                        "notes": metric["notes"],
                    }
                ),
            )
        )
    return tuple(documents)


def _qualified(record: dict[str, Any]) -> str:
    return f"{record['schema_name']}.{record['table_name']}"


def _freeze(metadata: dict[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(metadata)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
