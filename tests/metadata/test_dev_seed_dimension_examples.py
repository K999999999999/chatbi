"""Keep development dimension members aligned with generated column metadata."""

import json
import re
import unittest
from pathlib import Path

from sqlglot import exp, parse_one

ROOT = Path(__file__).resolve().parents[2]
MANAGED_DIMENSION_TABLES = frozenset(
    {
        "dim_currency",
        "dim_customer",
        "dim_product",
        "dim_sales_region",
    }
)


class DevelopmentSeedDimensionExamplesTest(unittest.TestCase):
    def test_seed_dimension_members_match_columns_value_examples(self) -> None:
        seed_path = ROOT / "database" / "dev" / "seed_sales_mart.sql"
        columns_path = ROOT / "src" / "structure" / "generated" / "columns.json"
        seed_sql = seed_path.read_text(encoding="utf-8")
        columns = json.loads(columns_path.read_text(encoding="utf-8"))

        seed_values = _seed_values_by_column(seed_sql)
        checked_columns = 0
        for column in columns:
            if (
                column["table_name"] not in MANAGED_DIMENSION_TABLES
                or "value_examples" not in column
            ):
                continue

            identity = (column["table_name"], column["column_name"])
            self.assertIn(identity, seed_values, f"Seed 缺少受管维度字段 {identity}")
            self.assertEqual(
                set(seed_values[identity]),
                set(column["value_examples"]),
                f"Seed 与 columns.json 的维度成员不一致：{identity}",
            )
            checked_columns += 1

        self.assertGreater(checked_columns, 0, "没有检查到受管维度字段")


def _seed_values_by_column(seed_sql: str) -> dict[tuple[str, str], set[str]]:
    statements = re.findall(
        r"INSERT\s+INTO\s+mart_sales\.(?:dim_currency|dim_customer|dim_product|dim_sales_region)"
        r"\b.*?;",
        seed_sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    values_by_column: dict[tuple[str, str], set[str]] = {}
    for statement_sql in statements:
        statement = parse_one(statement_sql, read="postgres")
        target = statement.this
        table_name = target.this.name
        columns = [column.name for column in target.expressions]
        values = statement.expression
        if not isinstance(values, exp.Values):
            raise TypeError(f"受管维度 Seed 必须使用显式 VALUES：{table_name}")

        for index, column_name in enumerate(columns):
            member_values = {
                row.expressions[index].this
                for row in values.expressions
                if isinstance(row.expressions[index], exp.Literal)
                and row.expressions[index].is_string
            }
            if member_values:
                values_by_column[(table_name, column_name)] = member_values

    return values_by_column


if __name__ == "__main__":
    unittest.main()
