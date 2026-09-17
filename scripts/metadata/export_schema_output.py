"""Metadata Export 的结构投影和 JSON 文件生成。"""

from collections.abc import Mapping
import json
from pathlib import Path
from typing import Any

from .export_schema_models import (
    OUTPUT_FILES,
    CanonicalSchema,
    ColumnIdentity,
)


def project_tables(model: CanonicalSchema) -> list[dict[str, Any]]:
    """将统一模型投影为 tables.json。"""

    return [
        {
            "schema_name": table.schema_name,
            "table_name": table.table_name,
            "table_type": table.table_type,
            "description": table.description,
        }
        for table in model.tables
    ]


def project_columns(
    model: CanonicalSchema,
    value_examples_by_column: Mapping[ColumnIdentity, tuple[str, ...]] | None = None,
) -> list[dict[str, Any]]:
    """将统一模型投影为 columns.json，并保留已有字段值示例。"""

    examples = {} if value_examples_by_column is None else value_examples_by_column
    records: list[dict[str, Any]] = []
    for column in model.columns:
        record: dict[str, Any] = {
            "schema_name": column.schema_name,
            "table_name": column.table_name,
            "column_name": column.column_name,
            "ordinal_position": column.ordinal_position,
            "data_type": column.data_type,
            "nullable": column.nullable,
            "default": column.default,
            "description": column.description,
            "is_primary_key": column.is_primary_key,
            "is_foreign_key": column.is_foreign_key,
            "is_identity": column.is_identity,
            "identity_generation": column.identity_generation,
        }
        value_examples = examples.get(
            (column.schema_name, column.table_name, column.column_name),
            (),
        )
        if value_examples:
            record["value_examples"] = list(value_examples)
        records.append(record)
    return records


def project_relationships(model: CanonicalSchema) -> list[dict[str, Any]]:
    """将统一模型投影为可直接切片的独立关系记录。"""

    records: list[dict[str, Any]] = []
    records.extend(
        {
            "relationship_type": "primary_key",
            "schema_name": item.schema_name,
            "table_name": item.table_name,
            "column_names": list(item.column_names),
            "constraint_name": item.constraint_name,
        }
        for item in model.primary_keys
    )
    records.extend(
        {
            "relationship_type": "unique_constraint",
            "schema_name": item.schema_name,
            "table_name": item.table_name,
            "column_names": list(item.column_names),
            "constraint_name": item.constraint_name,
        }
        for item in model.unique_constraints
    )
    records.extend(
        {
            "relationship_type": "foreign_key",
            "schema_name": item.schema_name,
            "table_name": item.table_name,
            "column_names": list(item.column_names),
            "referenced_schema": item.referenced_schema,
            "referenced_table": item.referenced_table,
            "referenced_column_names": list(item.referenced_column_names),
            "constraint_name": item.constraint_name,
        }
        for item in model.foreign_keys
    )
    records.extend(
        {
            "relationship_type": "unique_index",
            "schema_name": item.schema_name,
            "table_name": item.table_name,
            "index_name": item.index_name,
            "column_names": list(item.column_names),
            "predicate": item.predicate,
        }
        for item in model.unique_indexes
    )
    return records


def project_outputs(
    model: CanonicalSchema,
    value_examples_by_column: Mapping[ColumnIdentity, tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    """从同一个 Canonical Schema Model 生成三份输出对象。"""

    return {
        "tables": project_tables(model),
        "columns": project_columns(model, value_examples_by_column),
        "relationships": project_relationships(model),
    }


def render_json(value: Any) -> str:
    """以固定格式序列化 JSON，保证重复导出内容稳定。"""

    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def write_outputs(outputs: dict[str, Any], output_dir: Path) -> None:
    """写入三份正式 Schema Metadata（结构元数据）资源。"""

    output_dir.mkdir(parents=True, exist_ok=True)
    for key, filename in OUTPUT_FILES.items():
        path = output_dir / filename
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(render_json(outputs[key]))
