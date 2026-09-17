"""从 PostgreSQL mart_sales 结构生成当前 Sales Mart V1 Schema Metadata。

本 CLI 保留原有入口和输出 Contract；具体职责位于同目录的内部模块：

* ``export_schema_models``：模型、常量和输出名称；
* ``export_schema_input``：本地配置和已有字段示例；
* ``export_schema_database``：只读 PostgreSQL 系统目录读取；
* ``export_schema_output``：结构投影和 JSON 文件生成。

数据库连接期间只执行 SELECT，不创建、修改或删除数据库对象及数据。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import psycopg

from .export_schema_database import (
    COLUMNS_QUERY,
    CONSTRAINTS_QUERY,
    TABLES_QUERY,
    UNIQUE_INDEXES_QUERY,
    extract_schema,
)
from .export_schema_input import (
    connection_config,
    load_column_value_examples,
    load_env,
)
from .export_schema_models import (
    DEFAULT_OUTPUT_DIR,
    EXPECTED_TABLES,
    OUTPUT_FILES,
    ROOT,
    TARGET_SCHEMA,
    CanonicalSchema,
    ColumnIdentity,
    ColumnMetadata,
    ConstraintMetadata,
    ForeignKeyMetadata,
    MetadataExportError,
    TableMetadata,
    UniqueIndexMetadata,
)
from .export_schema_output import (
    project_columns,
    project_outputs,
    project_relationships,
    project_tables,
    render_json,
    write_outputs,
)


def export_schema(
    env_file: Path = ROOT / ".env",
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> CanonicalSchema:
    """连接一次 PostgreSQL，提取并写出当前 mart_sales Metadata。"""

    value_examples = load_column_value_examples(
        output_dir / OUTPUT_FILES["columns"]
    )
    env = load_env(env_file)
    with psycopg.connect(**connection_config(env)) as conn:
        model = extract_schema(conn)
    write_outputs(project_outputs(model, value_examples), output_dir)
    return model


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export the current mart_sales PostgreSQL schema metadata"
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=ROOT / ".env",
        help="path to the local PostgreSQL environment file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="directory for tables.json, columns.json, and relationships.json",
    )
    args = parser.parse_args()

    try:
        model = export_schema(args.env_file, args.output_dir)
    except (OSError, psycopg.Error, MetadataExportError, ValueError) as exc:
        print(f"metadata_export_result = FAIL: {type(exc).__name__}")
        return 1

    print(f"schema = {model.schema_name}")
    print(f"table_count = {len(model.tables)}")
    print(f"column_count = {len(model.columns)}")
    print(f"primary_key_count = {len(model.primary_keys)}")
    print(f"unique_constraint_count = {len(model.unique_constraints)}")
    print(f"foreign_key_count = {len(model.foreign_keys)}")
    print(f"unique_index_count = {len(model.unique_indexes)}")
    print("metadata_export_result = PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
