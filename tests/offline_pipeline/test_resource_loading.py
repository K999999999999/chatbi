import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.application.offline_pipeline import (
    M1ValidationError,
    ValidatedCatalogs,
    load_validated_catalogs,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESOURCE_FILES = {
    "tables": PROJECT_ROOT / "resources/schema/tables.json",
    "columns": PROJECT_ROOT / "resources/schema/columns.json",
    "relationships": PROJECT_ROOT / "resources/schema/relationships.json",
    "metrics": PROJECT_ROOT / "resources/semantic/sales/metrics.json",
}


def _copy_resources(destination: Path) -> dict[str, Path]:
    paths = {
        name: destination / source.name for name, source in RESOURCE_FILES.items()
    }
    for name, source in RESOURCE_FILES.items():
        shutil.copyfile(source, paths[name])
    return paths


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load(paths: dict[str, Path]) -> ValidatedCatalogs:
    return load_validated_catalogs(
        tables_path=paths["tables"],
        columns_path=paths["columns"],
        relationships_path=paths["relationships"],
        metrics_path=paths["metrics"],
    )


class ResourceLoadingTests(unittest.TestCase):
    def test_current_resources_load_as_complete_catalogs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = _copy_resources(Path(temporary_directory))

            catalogs = _load(paths)

        self.assertEqual(len(catalogs.tables), 7)
        self.assertEqual(len(catalogs.columns), 69)
        self.assertEqual(len(catalogs.metrics), 5)
        self.assertEqual(catalogs.relationships.schema_version, 1)

    def test_missing_resource_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = _copy_resources(Path(temporary_directory))
            paths["metrics"].unlink()

            with self.assertRaises(M1ValidationError):
                _load(paths)

    def test_invalid_json_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = _copy_resources(Path(temporary_directory))
            paths["tables"].write_text("{", encoding="utf-8")

            with self.assertRaises(M1ValidationError):
                _load(paths)

    def test_invalid_resource_shape_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = _copy_resources(Path(temporary_directory))
            tables = _read_json(paths["tables"])
            tables[0]["unexpected"] = "not part of the resource contract"
            _write_json(paths["tables"], tables)

            with self.assertRaises(M1ValidationError):
                _load(paths)

    def test_duplicate_table_identity_fails(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = _copy_resources(Path(temporary_directory))
            tables = _read_json(paths["tables"])
            tables.append(copy.deepcopy(tables[0]))
            _write_json(paths["tables"], tables)

            with self.assertRaises(M1ValidationError):
                _load(paths)

    def test_duplicate_column_identity_fails(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = _copy_resources(Path(temporary_directory))
            columns = _read_json(paths["columns"])
            columns.append(copy.deepcopy(columns[0]))
            _write_json(paths["columns"], columns)

            with self.assertRaises(M1ValidationError):
                _load(paths)

    def test_duplicate_metric_identity_fails(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = _copy_resources(Path(temporary_directory))
            metrics = _read_json(paths["metrics"])
            metrics.append(copy.deepcopy(metrics[0]))
            _write_json(paths["metrics"], metrics)

            with self.assertRaises(M1ValidationError):
                _load(paths)

    def test_column_table_reference_must_exist(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = _copy_resources(Path(temporary_directory))
            columns = _read_json(paths["columns"])
            columns[0]["table_name"] = "missing_table"
            _write_json(paths["columns"], columns)

            with self.assertRaises(M1ValidationError):
                _load(paths)

    def test_metric_physical_mapping_must_exist(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = _copy_resources(Path(temporary_directory))
            metrics = _read_json(paths["metrics"])
            metrics[0]["source_columns"] = ["missing_column"]
            _write_json(paths["metrics"], metrics)

            with self.assertRaises(M1ValidationError):
                _load(paths)

    def test_metric_dependency_must_exist(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = _copy_resources(Path(temporary_directory))
            metrics = _read_json(paths["metrics"])
            metrics[3]["depends_on"].append("missing_metric")
            _write_json(paths["metrics"], metrics)

            with self.assertRaises(M1ValidationError):
                _load(paths)

    def test_metric_dependency_cycle_fails(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = _copy_resources(Path(temporary_directory))
            metrics = _read_json(paths["metrics"])
            metrics[3]["depends_on"] = ["gross_margin"]
            _write_json(paths["metrics"], metrics)

            with self.assertRaises(M1ValidationError):
                _load(paths)

    def test_relationship_source_reference_must_exist(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = _copy_resources(Path(temporary_directory))
            relationships = _read_json(paths["relationships"])
            relationships["foreign_keys"][0]["table_name"] = "missing_table"
            _write_json(paths["relationships"], relationships)

            with self.assertRaises(M1ValidationError):
                _load(paths)

    def test_relationship_target_reference_must_exist(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = _copy_resources(Path(temporary_directory))
            relationships = _read_json(paths["relationships"])
            relationships["foreign_keys"][0]["referenced_table"] = "missing_table"
            _write_json(paths["relationships"], relationships)

            with self.assertRaises(M1ValidationError):
                _load(paths)

    def test_legacy_resources_are_not_scanned_or_used_as_fallback(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory)
            paths = _copy_resources(destination)
            shutil.copyfile(paths["tables"], destination / "legacy_tables.json")

            self.assertIsInstance(_load(paths), ValidatedCatalogs)

            paths["tables"].unlink()
            with self.assertRaises(M1ValidationError):
                _load(paths)

    def test_failure_does_not_return_partial_catalogs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = _copy_resources(Path(temporary_directory))
            metrics = _read_json(paths["metrics"])
            metrics[0]["source_columns"] = ["missing_column"]
            _write_json(paths["metrics"], metrics)

            with self.assertRaises(M1ValidationError) as raised:
                result = _load(paths)

        self.assertNotIsInstance(locals().get("result"), ValidatedCatalogs)
        self.assertTrue(str(raised.exception))


if __name__ == "__main__":
    unittest.main()
