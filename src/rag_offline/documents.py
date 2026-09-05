"""Build TABLE、COLUMN、METRIC retrieval documents（检索文档）。"""

from collections.abc import Mapping
from dataclasses import dataclass
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
        formula = metric["formula"]
        if formula:
            lines.append(f"业务公式：{formula}")
        data_source = metric["data_source"]
        if data_source:
            lines.append(f"数据来源：{data_source}")
        time_field = metric["time_field"]
        if time_field:
            lines.append(f"时间口径：{time_field}")
        filters = metric["filters"]
        if filters:
            lines.append(f"过滤条件：{'；'.join(filters)}")
        depends_on = metric["depends_on"]
        if depends_on:
            lines.append(f"依赖指标：{'、'.join(depends_on)}")
        notes = metric["notes"]
        if notes:
            lines.append(f"注意事项：{notes}")
        documents.append(
            RetrievalDocument(
                document_id=f"metric:{metric['name']}",
                collection=METRIC_COLLECTION,
                page_content="\n".join(lines),
                metadata=_freeze(
                    {
                        "doc_type": "METRIC",
                        "metric_name": metric["name"],
                        "level": level,
                        "data_source": data_source,
                        "depends_on": depends_on,
                    }
                ),
            )
        )
    return tuple(documents)


def _qualified(record: dict[str, Any]) -> str:
    return f"{record['schema_name']}.{record['table_name']}"


def _freeze(metadata: dict[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(metadata)
