"""Check that Sales Mart initialization creates the exported descriptions."""

import json
import unittest
from pathlib import Path

from sqlglot import exp, parse

ROOT = Path(__file__).resolve().parents[2]


class SchemaDescriptionTest(unittest.TestCase):
    def test_initialization_schema_defines_all_exported_descriptions(self) -> None:
        tables = _generated_metadata("tables.json")
        columns = _generated_metadata("columns.json")
        schema_sql = (ROOT / "database/sales_mart/001_create_schema.sql").read_text(
            encoding="utf-8"
        )

        expected = {
            ("TABLE", table["table_name"]): table["description"]
            for table in tables
            if table.get("description")
        }
        expected.update(
            {
                ("COLUMN", column["table_name"], column["column_name"]): column[
                    "description"
                ]
                for column in columns
                if column.get("description")
            }
        )
        self.assertEqual(len(expected), len(tables) + len(columns))
        self.assertEqual(len(expected), 76)

        actual = _schema_comments(schema_sql)
        self.assertEqual(actual, expected)


def _schema_comments(schema_sql: str) -> dict[tuple[str, ...], str]:
    comments: dict[tuple[str, ...], str] = {}
    for statement in parse(schema_sql, read="postgres"):
        if not isinstance(statement, exp.Comment):
            continue

        kind = str(statement.args["kind"])
        target = statement.this
        if kind == "TABLE" and isinstance(target, exp.Table):
            identity = (kind, target.name)
        elif kind == "COLUMN" and isinstance(target, exp.Column):
            identity = (kind, target.table, target.name)
        else:
            raise AssertionError(f"不支持的 Schema COMMENT 目标：{target}")

        comments[identity] = str(statement.expression.this)

    return comments


def _generated_metadata(filename: str) -> list[dict[str, object]]:
    path = ROOT / "src/structure/generated" / filename
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise TypeError(f"generated/{filename} 必须是 JSON 数组")
    return records


if __name__ == "__main__":
    unittest.main()
