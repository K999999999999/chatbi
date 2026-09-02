"""结构导出保留字段值示例的测试。"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.metadata.export_schema import (
    CanonicalSchema,
    ColumnMetadata,
    MetadataExportError,
    TableMetadata,
    load_column_value_examples,
    project_columns,
)


class ExportSchemaTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
