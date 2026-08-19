import copy
import inspect
import unittest
from collections import Counter
from pathlib import Path

from langchain_core.documents import Document

from src.application.offline_pipeline import (
    ValidatedCatalogs,
    load_validated_catalogs,
    project_retrieval_records,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESOURCE_PATHS = {
    "tables": PROJECT_ROOT / "resources/schema/tables.json",
    "columns": PROJECT_ROOT / "resources/schema/columns.json",
    "relationships": PROJECT_ROOT / "resources/schema/relationships.json",
    "metrics": PROJECT_ROOT / "resources/semantic/sales/metrics.json",
}


def _load_current_catalogs() -> ValidatedCatalogs:
    return load_validated_catalogs(
        tables_path=RESOURCE_PATHS["tables"],
        columns_path=RESOURCE_PATHS["columns"],
        relationships_path=RESOURCE_PATHS["relationships"],
        metrics_path=RESOURCE_PATHS["metrics"],
    )


class RetrievalProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalogs = _load_current_catalogs()

    def test_current_validated_catalogs_project_successfully(self):
        records = project_retrieval_records(self.catalogs)

        self.assertEqual(len(records), 81)
        self.assertTrue(all(isinstance(record, Document) for record in records))

    def test_record_coverage_is_seven_tables_sixty_nine_columns_five_metrics(self):
        records = project_retrieval_records(self.catalogs)
        counts = Counter(record.metadata["record_type"] for record in records)

        self.assertEqual(counts, {"TABLE": 7, "COLUMN": 69, "METRIC": 5})

    def test_record_types_are_limited_to_formal_retrieval_objects(self):
        records = project_retrieval_records(self.catalogs)

        self.assertEqual(
            set(record.metadata["record_type"] for record in records),
            {"TABLE", "COLUMN", "METRIC"},
        )

    def test_relationship_catalog_produces_zero_documents(self):
        records = project_retrieval_records(self.catalogs)

        self.assertFalse(
            any(record.metadata["record_type"] == "RELATIONSHIP" for record in records)
        )

    def test_table_document_identity_and_source_trace(self):
        records = project_retrieval_records(self.catalogs)
        table_records = [record for record in records if record.metadata["record_type"] == "TABLE"]

        self.assertEqual(
            [
                (record.metadata["schema_name"], record.metadata["table_name"])
                for record in table_records
            ],
            [(table.schema_name, table.table_name) for table in self.catalogs.tables],
        )
        self.assertTrue(
            all(
                record.metadata["source_path"] == "resources/schema/tables.json"
                for record in table_records
            )
        )

    def test_column_document_identity_and_source_trace(self):
        records = project_retrieval_records(self.catalogs)
        column_records = [
            record for record in records if record.metadata["record_type"] == "COLUMN"
        ]

        self.assertEqual(
            [
                (
                    record.metadata["schema_name"],
                    record.metadata["table_name"],
                    record.metadata["column_name"],
                )
                for record in column_records
            ],
            [
                (column.schema_name, column.table_name, column.column_name)
                for column in self.catalogs.columns
            ],
        )
        self.assertTrue(
            all(
                record.metadata["source_path"] == "resources/schema/columns.json"
                for record in column_records
            )
        )

    def test_metric_document_identity_and_source_trace(self):
        records = project_retrieval_records(self.catalogs)
        metric_records = [
            record for record in records if record.metadata["record_type"] == "METRIC"
        ]

        self.assertEqual(
            [record.metadata["metric_code"] for record in metric_records],
            [metric.metric_code for metric in self.catalogs.metrics],
        )
        self.assertTrue(
            all(
                record.metadata["source_path"]
                == "resources/semantic/sales/metrics.json"
                for record in metric_records
            )
        )

    def test_source_paths_are_project_relative_and_portable(self):
        records = project_retrieval_records(self.catalogs)

        source_paths = {record.metadata["source_path"] for record in records}
        self.assertEqual(
            source_paths,
            {
                "resources/schema/tables.json",
                "resources/schema/columns.json",
                "resources/semantic/sales/metrics.json",
            },
        )
        self.assertTrue(all(not Path(path).is_absolute() for path in source_paths))
        self.assertTrue(all("\\" not in path for path in source_paths))
        self.assertTrue(all(":" not in path for path in source_paths))

    def test_table_page_content_uses_only_table_name_and_description(self):
        table = self.catalogs.tables[0]
        record = project_retrieval_records(self.catalogs)[0]

        self.assertEqual(
            record.page_content,
            f"table_name: {table.table_name}\ndescription: {table.description}",
        )
        self.assertTrue(record.page_content)

    def test_column_page_content_uses_only_column_name_and_description(self):
        column = self.catalogs.columns[0]
        records = project_retrieval_records(self.catalogs)
        record = next(
            record
            for record in records
            if record.metadata["record_type"] == "COLUMN"
            and record.metadata["column_name"] == column.column_name
            and record.metadata["table_name"] == column.table_name
        )

        self.assertEqual(
            record.page_content,
            f"column_name: {column.column_name}\ndescription: {column.description}",
        )
        self.assertNotIn("semantic_role", record.page_content)
        self.assertNotIn("time_role", record.page_content)
        self.assertNotIn("field_semantics", record.page_content)
        self.assertTrue(record.page_content)

    def test_metric_page_content_contains_formal_search_facts(self):
        metric = next(
            metric for metric in self.catalogs.metrics if metric.metric_code == "gross_margin"
        )
        records = project_retrieval_records(self.catalogs)
        record = next(
            record
            for record in records
            if record.metadata["record_type"] == "METRIC"
            and record.metadata["metric_code"] == metric.metric_code
        )

        self.assertEqual(
            record.page_content,
            "\n".join(
                [
                    f"metric_code: {metric.metric_code}",
                    f"metric_name: {metric.metric_name}",
                    f"aliases: {'; '.join(metric.aliases)}",
                    f"business_definition: {metric.business_definition}",
                    f"expression: {metric.expression}",
                ]
            ),
        )
        self.assertIn("gross_margin", record.page_content)
        self.assertIn("gross_profit / sales_revenue", record.page_content)
        self.assertTrue(record.page_content)

    def test_metric_metadata_preserves_structured_semantics(self):
        metric = next(
            metric for metric in self.catalogs.metrics if metric.metric_code == "gross_margin"
        )
        record = next(
            record
            for record in project_retrieval_records(self.catalogs)
            if record.metadata["record_type"] == "METRIC"
            and record.metadata["metric_code"] == metric.metric_code
        )

        self.assertEqual(record.metadata["metric_type"], metric.metric_type)
        self.assertEqual(record.metadata["filters"], list(metric.filters))
        self.assertEqual(record.metadata["depends_on"], list(metric.depends_on))
        self.assertEqual(
            record.metadata["default_time_column_identity"],
            metric.default_time_column_identity,
        )
        self.assertEqual(record.metadata["unit"], metric.unit)
        self.assertEqual(record.metadata["source_table"], metric.source_table)
        self.assertEqual(record.metadata["source_columns"], metric.source_columns)
        self.assertEqual(record.metadata["null_if"], metric.null_if)
        self.assertIsInstance(record.metadata["filters"], list)
        self.assertIsInstance(record.metadata["depends_on"], list)
        self.assertIsInstance(record.metadata["source_columns"], type(None))

        atomic_metric = next(
            metric for metric in self.catalogs.metrics if metric.metric_code == "sales_revenue"
        )
        atomic_record = next(
            record
            for record in project_retrieval_records(self.catalogs)
            if record.metadata["record_type"] == "METRIC"
            and record.metadata["metric_code"] == atomic_metric.metric_code
        )
        self.assertEqual(
            atomic_record.metadata["source_columns"],
            list(atomic_metric.source_columns),
        )
        self.assertIsInstance(atomic_record.metadata["source_columns"], list)

    def test_all_page_content_is_non_empty(self):
        records = project_retrieval_records(self.catalogs)

        self.assertTrue(all(record.page_content.strip() for record in records))

    def test_projection_does_not_mutate_validated_catalogs(self):
        before = copy.deepcopy(self.catalogs.model_dump(mode="python"))

        project_retrieval_records(self.catalogs)

        self.assertEqual(self.catalogs.model_dump(mode="python"), before)

    def test_projection_is_deterministic(self):
        first = [
            (record.page_content, record.metadata)
            for record in project_retrieval_records(self.catalogs)
        ]
        second = [
            (record.page_content, record.metadata)
            for record in project_retrieval_records(self.catalogs)
        ]

        self.assertEqual(first, second)

    def test_relationship_quantity_does_not_change_projection_count(self):
        altered_catalogs = copy.deepcopy(self.catalogs)
        altered_catalogs.relationships.unique_indexes = []

        self.assertEqual(
            len(project_retrieval_records(altered_catalogs)),
            len(project_retrieval_records(self.catalogs)),
        )

    def test_projection_module_has_no_embedding_qdrant_or_network_dependency(self):
        module_file = Path(inspect.getsourcefile(project_retrieval_records))
        source = module_file.read_text(encoding="utf-8").lower()

        for forbidden in ("flagembedding", "qdrant", "requests", "httpx", "urllib.request"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
