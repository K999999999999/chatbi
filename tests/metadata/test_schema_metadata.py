"""验证当前 mart_sales PostgreSQL Schema Metadata（结构元数据）。"""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.metadata.export_schema import (  # noqa: E402
    EXPECTED_TABLES,
    TARGET_SCHEMA,
    connection_config,
    extract_schema,
    export_schema,
    load_env,
    project_outputs,
    render_json,
)


class SchemaMetadataTest(unittest.TestCase):
    """只读核对 PostgreSQL 实际结构与元数据导出结果。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.env = load_env(ROOT / ".env")
        cls.connection = psycopg.connect(**connection_config(cls.env))
        cls.model = extract_schema(cls.connection)
        cls.repeat_model = extract_schema(cls.connection)
        cls.outputs = project_outputs(cls.model)
        cls.repeat_outputs = project_outputs(cls.repeat_model)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.connection.close()

    def test_tables_are_exactly_the_current_sales_mart_tables(self) -> None:
        actual = self._query_table_names()
        self.assertEqual(EXPECTED_TABLES, actual)
        self.assertEqual(EXPECTED_TABLES, {item["table_name"] for item in self.outputs["tables"]})
        self.assertTrue(
            all(item["schema_name"] == TARGET_SCHEMA for item in self.outputs["tables"])
        )
        self.assertFalse(
            any(item["schema_name"] == "public" for item in self.outputs["tables"])
        )
        for column in self.outputs["columns"]:
            self.assertEqual(TARGET_SCHEMA, column["schema_name"])
        for relation_group in (
            "primary_keys",
            "unique_constraints",
            "foreign_keys",
            "unique_indexes",
        ):
            for relation in self.outputs["relationships"][relation_group]:
                self.assertEqual(TARGET_SCHEMA, relation["schema_name"])
                if "referenced_schema" in relation:
                    self.assertEqual(TARGET_SCHEMA, relation["referenced_schema"])

    def test_tables_json_is_the_canonical_projection(self) -> None:
        self.assertTrue(
            all(item["table_type"] == "BASE TABLE" for item in self.outputs["tables"])
        )

    def test_columns_match_postgresql_columns_exactly(self) -> None:
        actual_columns = self._query_columns()
        exported_columns = {
            (item["schema_name"], item["table_name"], item["column_name"]): item
            for item in self.outputs["columns"]
        }

        self.assertEqual(set(actual_columns), set(exported_columns))
        self.assertEqual(
            {item["table_name"] for item in self.outputs["tables"]},
            {item["table_name"] for item in self.outputs["columns"]},
        )

        for key, actual in actual_columns.items():
            exported = exported_columns[key]
            for field in (
                "schema_name",
                "table_name",
                "column_name",
                "ordinal_position",
                "data_type",
                "nullable",
                "default",
                "description",
            ):
                self.assertEqual(actual[field], exported[field], f"{key}:{field}")

    def test_relationships_match_postgresql_constraints_and_indexes(self) -> None:
        actual = self._query_relationships()
        self.assertEqual(actual, self.outputs["relationships"])
        self.assertNotIn("semantic_relationships", actual)

        role_playing_dates = {
            (
                item["table_name"],
                tuple(item["column_names"]),
                item["referenced_table"],
                tuple(item["referenced_column_names"]),
            )
            for item in actual["foreign_keys"]
        }
        self.assertEqual(
            {
                (
                    "fct_sales_order_line",
                    (column_name,),
                    "dim_date",
                    ("date_key",),
                )
                for column_name in (
                    "order_date_key",
                    "confirmation_date_key",
                    "completion_date_key",
                )
            },
            {
                item
                for item in role_playing_dates
                if item[0] == "fct_sales_order_line"
                and item[2] == "dim_date"
            },
        )

    def test_scd2_physical_columns_and_unique_objects_are_present(self) -> None:
        columns = {
            item["table_name"]: {
                column["column_name"]
                for column in self.outputs["columns"]
                if column["table_name"] == item["table_name"]
            }
            for item in self.outputs["tables"]
        }
        for table_name, business_id in (
            ("dim_customer", "customer_id"),
            ("dim_product", "product_id"),
        ):
            self.assertTrue(
                {
                    table_name.removeprefix("dim_") + "_key",
                    business_id,
                    "valid_from",
                    "valid_to",
                    "is_current",
                }.issubset(columns[table_name])
            )

        relationships = self.outputs["relationships"]
        unique_constraints = {
            (item["table_name"], tuple(item["column_names"]))
            for item in relationships["unique_constraints"]
        }
        self.assertIn(("dim_customer", ("customer_id", "valid_from")), unique_constraints)
        self.assertIn(("dim_product", ("product_id", "valid_from")), unique_constraints)

        unique_indexes = {
            item["index_name"]: item for item in relationships["unique_indexes"]
        }
        self.assertIn("ux_dim_customer_current", unique_indexes)
        self.assertIn("ux_dim_product_current", unique_indexes)

    def test_repeated_extraction_and_rendering_are_byte_stable(self) -> None:
        first_rendered = {
            key: render_json(value) for key, value in self.outputs.items()
        }
        second_rendered = {
            key: render_json(value) for key, value in self.repeat_outputs.items()
        }
        self.assertEqual(first_rendered, second_rendered)
        for key, content in first_rendered.items():
            self.assertEqual(
                hashlib.sha256(content.encode("utf-8")).hexdigest(),
                hashlib.sha256(second_rendered[key].encode("utf-8")).hexdigest(),
            )

    def test_exporter_repeated_runs_are_stable_in_a_temporary_output(self) -> None:
        with TemporaryDirectory() as temporary_dir:
            output_dir = Path(temporary_dir)
            export_schema(ROOT / ".env", output_dir)
            first = {
                filename: (output_dir / filename).read_bytes()
                for filename in ("tables.json", "columns.json", "relationships.json")
            }
            export_schema(ROOT / ".env", output_dir)
            second = {
                filename: (output_dir / filename).read_bytes()
                for filename in ("tables.json", "columns.json", "relationships.json")
            }
        self.assertEqual(first, second)

    def _query_table_names(self) -> set[str]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """,
                (TARGET_SCHEMA,),
            )
            return {str(row[0]) for row in cursor.fetchall()}

    def _query_columns(self) -> dict[tuple[str, str, str], dict[str, Any]]:
        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    n.nspname AS schema_name,
                    c.relname AS table_name,
                    a.attname AS column_name,
                    a.attnum AS ordinal_position,
                    pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
                    NOT a.attnotnull AS nullable,
                    pg_catalog.pg_get_expr(ad.adbin, ad.adrelid) AS default_value,
                    pg_catalog.col_description(c.oid, a.attnum) AS description
                FROM pg_catalog.pg_attribute AS a
                JOIN pg_catalog.pg_class AS c ON c.oid = a.attrelid
                JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
                LEFT JOIN pg_catalog.pg_attrdef AS ad
                  ON ad.adrelid = a.attrelid
                 AND ad.adnum = a.attnum
                WHERE n.nspname = %s
                  AND c.relkind = 'r'
                  AND a.attnum > 0
                  AND NOT a.attisdropped
                ORDER BY c.relname, a.attnum
                """,
                (TARGET_SCHEMA,),
            )
            return {
                (str(row["schema_name"]), str(row["table_name"]), str(row["column_name"])): {
                    "schema_name": str(row["schema_name"]),
                    "table_name": str(row["table_name"]),
                    "column_name": str(row["column_name"]),
                    "ordinal_position": int(row["ordinal_position"]),
                    "data_type": str(row["data_type"]),
                    "nullable": bool(row["nullable"]),
                    "default": (
                        str(row["default_value"])
                        if row["default_value"] is not None
                        else None
                    ),
                    "description": (
                        str(row["description"])
                        if row["description"] is not None
                        else None
                    ),
                }
                for row in cursor.fetchall()
            }

    def _query_relationships(self) -> dict[str, Any]:
        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    c.contype,
                    n.nspname AS schema_name,
                    r.relname AS table_name,
                    ARRAY(
                        SELECT a.attname
                        FROM unnest(c.conkey) WITH ORDINALITY AS key_columns(attnum, ordinality)
                        JOIN pg_catalog.pg_attribute AS a
                          ON a.attrelid = c.conrelid
                         AND a.attnum = key_columns.attnum
                        ORDER BY key_columns.ordinality
                    ) AS column_names,
                    referenced_n.nspname AS referenced_schema,
                    referenced_r.relname AS referenced_table,
                    ARRAY(
                        SELECT referenced_a.attname
                        FROM unnest(c.confkey) WITH ORDINALITY AS referenced_key_columns(attnum, ordinality)
                        JOIN pg_catalog.pg_attribute AS referenced_a
                          ON referenced_a.attrelid = c.confrelid
                         AND referenced_a.attnum = referenced_key_columns.attnum
                        ORDER BY referenced_key_columns.ordinality
                    ) AS referenced_column_names
                FROM pg_catalog.pg_constraint AS c
                JOIN pg_catalog.pg_class AS r ON r.oid = c.conrelid
                JOIN pg_catalog.pg_namespace AS n ON n.oid = r.relnamespace
                LEFT JOIN pg_catalog.pg_class AS referenced_r ON referenced_r.oid = c.confrelid
                LEFT JOIN pg_catalog.pg_namespace AS referenced_n
                  ON referenced_n.oid = referenced_r.relnamespace
                WHERE n.nspname = %s
                  AND c.contype IN ('p', 'u', 'f')
                ORDER BY r.relname, c.contype, c.conname
                """,
                (TARGET_SCHEMA,),
            )
            primary_keys: list[dict[str, Any]] = []
            unique_constraints: list[dict[str, Any]] = []
            foreign_keys: list[dict[str, Any]] = []
            for row in cursor.fetchall():
                base = {
                    "schema_name": str(row["schema_name"]),
                    "table_name": str(row["table_name"]),
                    "column_names": [str(value) for value in row["column_names"]],
                }
                if row["contype"] == "p":
                    primary_keys.append(base)
                elif row["contype"] == "u":
                    unique_constraints.append(base)
                else:
                    foreign_keys.append(
                        {
                            **base,
                            "referenced_schema": str(row["referenced_schema"]),
                            "referenced_table": str(row["referenced_table"]),
                            "referenced_column_names": [
                                str(value) for value in row["referenced_column_names"]
                            ],
                        }
                    )

            cursor.execute(
                """
                SELECT
                    n.nspname AS schema_name,
                    table_r.relname AS table_name,
                    index_r.relname AS index_name,
                    ARRAY(
                        SELECT a.attname
                        FROM unnest(index_info.indkey) WITH ORDINALITY AS index_columns(attnum, ordinality)
                        JOIN pg_catalog.pg_attribute AS a
                          ON a.attrelid = index_info.indrelid
                         AND a.attnum = index_columns.attnum
                        ORDER BY index_columns.ordinality
                    ) AS column_names,
                    pg_catalog.pg_get_expr(index_info.indpred, index_info.indrelid) AS predicate
                FROM pg_catalog.pg_index AS index_info
                JOIN pg_catalog.pg_class AS table_r ON table_r.oid = index_info.indrelid
                JOIN pg_catalog.pg_namespace AS n ON n.oid = table_r.relnamespace
                JOIN pg_catalog.pg_class AS index_r ON index_r.oid = index_info.indexrelid
                LEFT JOIN pg_catalog.pg_constraint AS constraint_info
                  ON constraint_info.conindid = index_info.indexrelid
                WHERE n.nspname = %s
                  AND index_info.indisunique
                  AND constraint_info.oid IS NULL
                ORDER BY table_r.relname, index_r.relname
                """,
                (TARGET_SCHEMA,),
            )
            unique_indexes = [
                {
                    "schema_name": str(row["schema_name"]),
                    "table_name": str(row["table_name"]),
                    "index_name": str(row["index_name"]),
                    "column_names": [str(value) for value in row["column_names"]],
                    "predicate": (
                        str(row["predicate"])
                        if row["predicate"] is not None
                        else None
                    ),
                }
                for row in cursor.fetchall()
            ]

        primary_keys.sort(
            key=lambda item: (item["table_name"], tuple(item["column_names"]))
        )
        unique_constraints.sort(
            key=lambda item: (item["table_name"], tuple(item["column_names"]))
        )
        foreign_keys.sort(
            key=lambda item: (
                item["table_name"],
                tuple(item["column_names"]),
                item["referenced_schema"],
                item["referenced_table"],
                tuple(item["referenced_column_names"]),
            )
        )
        unique_indexes.sort(
            key=lambda item: (
                item["table_name"],
                item["index_name"],
                tuple(item["column_names"]),
            )
        )
        return {
            "schema_version": 1,
            "primary_keys": primary_keys,
            "unique_constraints": unique_constraints,
            "foreign_keys": foreign_keys,
            "unique_indexes": unique_indexes,
        }


if __name__ == "__main__":
    unittest.main()
