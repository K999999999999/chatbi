"""Production schema comparison tests."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.metadata.export_schema_models import (
    CanonicalSchema,
    ColumnMetadata,
    TableMetadata,
)
from scripts.metadata.export_schema_output import project_outputs
from src.structure.runtime_schema import (
    StructureMetadataMismatchError,
    verify_catalog_matches_metadata,
)


class RuntimeSchemaTest(unittest.TestCase):
    def test_matches_catalog_and_ignores_manual_value_examples(self) -> None:
        model = _schema()
        outputs = project_outputs(model)
        outputs["columns"][0]["value_examples"] = ["manual-example"]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_metadata(root, outputs)

            with patch(
                "src.structure.runtime_schema.extract_schema",
                return_value=model,
            ):
                verify_catalog_matches_metadata(object(), root)

    def test_rejects_column_or_relationship_mismatch(self) -> None:
        model = _schema()
        outputs = project_outputs(model)
        outputs["columns"][0]["data_type"] = "text"
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_metadata(root, outputs)

            with patch(
                "src.structure.runtime_schema.extract_schema",
                return_value=model,
            ):
                with self.assertRaisesRegex(
                    StructureMetadataMismatchError,
                    "columns 与 Structure Metadata 不一致",
                ):
                    verify_catalog_matches_metadata(object(), root)

    def test_rejects_missing_metadata_file(self) -> None:
        with TemporaryDirectory() as directory:
            with patch(
                "src.structure.runtime_schema.extract_schema",
                return_value=_schema(),
            ):
                with self.assertRaisesRegex(
                    StructureMetadataMismatchError,
                    "缺少 Structure Metadata：tables",
                ):
                    verify_catalog_matches_metadata(object(), Path(directory))


def _schema() -> CanonicalSchema:
    return CanonicalSchema(
        schema_name="mart_sales",
        tables=(
            TableMetadata(
                schema_name="mart_sales",
                table_name="dim_date",
                table_type="BASE TABLE",
                description="Date dimension",
            ),
        ),
        columns=(
            ColumnMetadata(
                schema_name="mart_sales",
                table_name="dim_date",
                column_name="date_key",
                ordinal_position=1,
                data_type="integer",
                nullable=False,
                default=None,
                description="Date key",
                is_primary_key=True,
            ),
        ),
        primary_keys=(),
        unique_constraints=(),
        foreign_keys=(),
        unique_indexes=(),
    )


def _write_metadata(root: Path, outputs: dict[str, object]) -> None:
    for name, value in outputs.items():
        (root / f"{name}.json").write_text(
            json.dumps(value, ensure_ascii=False),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
