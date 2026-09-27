"""结构导出保留字段值示例的测试。"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Self

from scripts.metadata.export_schema import (
    CanonicalSchema,
    ColumnMetadata,
    MetadataExportError,
    TableMetadata,
    extract_schema,
    load_column_value_examples,
    project_columns,
)
from scripts.metadata.export_schema_models import EXPECTED_TABLES


class ExportSchemaTest(unittest.TestCase):
    def test_extract_schema_ignores_development_seed_metadata(self) -> None:
        connection = _CatalogConnection()

        model = extract_schema(connection)

        self.assertEqual(
            {table.table_name for table in model.tables},
            EXPECTED_TABLES,
        )
        self.assertNotIn(
            "dev_seed_metadata",
            {column.table_name for column in model.columns},
        )
        self.assertNotIn(
            "dev_seed_metadata",
            {
                item.table_name
                for item in (
                    *model.primary_keys,
                    *model.unique_constraints,
                    *model.foreign_keys,
                    *model.unique_indexes,
                )
            },
        )
        self.assertNotIn(
            "dev_seed_metadata",
            {item.referenced_table for item in model.foreign_keys},
        )

    def test_preserves_existing_column_value_examples(self) -> None:
        with TemporaryDirectory() as directory:
            columns_path = Path(directory) / "columns.json"
            columns_path.write_text(
                json.dumps(
                    [
                        {
                            "schema_name": "mart_sales",
                            "table_name": "fct_sales_order_line",
                            "column_name": "order_status",
                            "value_examples": ["completed", "pending"],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            examples = load_column_value_examples(columns_path)
            records = project_columns(_model(), examples)

        self.assertEqual(
            records[0]["value_examples"],
            ["completed", "pending"],
        )

    def test_rejects_invalid_existing_column_value_examples(self) -> None:
        with TemporaryDirectory() as directory:
            columns_path = Path(directory) / "columns.json"
            columns_path.write_text(
                json.dumps(
                    [
                        {
                            "schema_name": "mart_sales",
                            "table_name": "fct_sales_order_line",
                            "column_name": "order_status",
                            "value_examples": ["completed", "completed"],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(MetadataExportError, "value_examples"):
                load_column_value_examples(columns_path)


def _model() -> CanonicalSchema:
    return CanonicalSchema(
        schema_name="mart_sales",
        tables=(
            TableMetadata(
                schema_name="mart_sales",
                table_name="fct_sales_order_line",
                table_type="BASE TABLE",
                description="销售订单明细",
            ),
        ),
        columns=(
            ColumnMetadata(
                schema_name="mart_sales",
                table_name="fct_sales_order_line",
                column_name="order_status",
                ordinal_position=1,
                data_type="text",
                nullable=False,
                default=None,
                description="订单状态",
            ),
        ),
        primary_keys=(),
        unique_constraints=(),
        foreign_keys=(),
        unique_indexes=(),
    )


class _CatalogConnection:
    def cursor(self, *, row_factory: object) -> "_CatalogCursor":
        del row_factory
        return _CatalogCursor()


class _CatalogCursor:
    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        del args

    def execute(self, query: str, parameters: tuple[str, ...]) -> None:
        del parameters
        if "information_schema.tables" in query:
            self._rows = [
                _table_row(table_name)
                for table_name in sorted(EXPECTED_TABLES | {"dev_seed_metadata"})
            ]
        elif "pg_catalog.pg_index AS index_info" in query:
            self._rows = [
                _index_row("fct_sales_order_line", "uq_order"),
                _index_row("dev_seed_metadata", "dev_seed_metadata_pkey"),
            ]
        elif "pg_catalog.pg_constraint" in query:
            self._rows = [
                _constraint_row("fct_sales_order_line", "pk_fct", "p"),
                _constraint_row("dev_seed_metadata", "dev_seed_metadata_pkey", "p"),
                _constraint_row(
                    "fct_sales_order_line",
                    "fk_internal_seed_metadata",
                    "f",
                    referenced_table="dev_seed_metadata",
                ),
            ]
        elif "pg_catalog.pg_attribute" in query:
            self._rows = [
                _column_row("fct_sales_order_line", "order_id"),
                _column_row("dev_seed_metadata", "seed_version"),
            ]
        else:
            raise AssertionError(f"unexpected metadata query: {query}")

    def fetchall(self) -> list[dict[str, object]]:
        return self._rows


def _table_row(table_name: str) -> dict[str, object]:
    return {
        "schema_name": "mart_sales",
        "table_name": table_name,
        "table_type": "BASE TABLE",
        "description": None,
    }


def _column_row(table_name: str, column_name: str) -> dict[str, object]:
    return {
        "schema_name": "mart_sales",
        "table_name": table_name,
        "column_name": column_name,
        "ordinal_position": 1,
        "data_type": "text",
        "nullable": False,
        "default_value": None,
        "description": None,
        "identity_kind": "",
    }


def _constraint_row(
    table_name: str,
    constraint_name: str,
    constraint_type: str,
    *,
    referenced_table: str | None = None,
) -> dict[str, object]:
    return {
        "contype": constraint_type,
        "constraint_name": constraint_name,
        "schema_name": "mart_sales",
        "table_name": table_name,
        "column_names": ["order_id"],
        "referenced_schema": "mart_sales" if referenced_table else None,
        "referenced_table": referenced_table,
        "referenced_column_names": ["singleton"] if referenced_table else None,
    }


def _index_row(table_name: str, index_name: str) -> dict[str, object]:
    return {
        "schema_name": "mart_sales",
        "table_name": table_name,
        "index_name": index_name,
        "column_names": ["order_id"],
        "predicate": None,
    }


if __name__ == "__main__":
    unittest.main()
