"""RAG Offline Relationship Graph（关系图）生成与校验测试。"""

import json
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from src.rag_offline import RelationshipGraphError, build_relationship_graph, load_facts


class RelationshipGraphTest(unittest.TestCase):
    def test_builds_graph_from_generated_facts(self) -> None:
        facts = load_facts()

        graph = build_relationship_graph(facts)

        raw_foreign_keys = [
            item
            for item in facts.relationships
            if item["relationship_type"] == "foreign_key"
        ]
        self.assertEqual(graph.edge_count, len(raw_foreign_keys))
        self.assertEqual(len(graph.nodes), len(facts.tables))
        self.assertEqual(graph.primary_keys[0]["relationship_type"], "primary_key")
        serialized = graph.to_dict()
        self.assertEqual(len(serialized["foreign_keys"]), graph.edge_count)
        self.assertIsInstance(serialized["nodes"][0], str)

    def test_builds_valid_temporary_graph(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)

            facts = load_facts(root, root / "metrics.json")
            graph = build_relationship_graph(facts)

        self.assertEqual(graph.nodes, ("mart_sales.dim_date", "mart_sales.fct_sales"))
        self.assertEqual(len(graph.primary_keys), 2)
        self.assertEqual(graph.edge_count, 1)
        edge = graph.to_dict()["foreign_keys"][0]
        self.assertEqual(edge["source_table"], "fct_sales")
        self.assertEqual(edge["target_table"], "dim_date")
        self.assertEqual(edge["source_columns"], ["completion_date_key"])
        self.assertEqual(edge["target_columns"], ["date_key"])

    def test_graph_order_is_independent_of_source_order(self) -> None:
        facts = load_facts()

        original = build_relationship_graph(facts)
        reversed_graph = build_relationship_graph(
            replace(facts, relationships=tuple(reversed(facts.relationships)))
        )

        self.assertEqual(original.to_dict(), reversed_graph.to_dict())

    def test_generated_graph_preserves_all_sales_date_edges(self) -> None:
        graph = build_relationship_graph(load_facts())

        date_edges = {
            tuple(edge["source_columns"])
            for edge in graph.foreign_keys
            if edge["source_table"] == "fct_sales_order_line"
            and edge["target_table"] == "dim_date"
        }

        self.assertEqual(
            date_edges,
            {
                ("order_date_key",),
                ("confirmation_date_key",),
                ("completion_date_key",),
            },
        )

    def test_rejects_duplicate_foreign_key_identity(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            relationships = json.loads(
                (root / "relationships.json").read_text(encoding="utf-8")
            )
            relationships.append(relationships[0])
            (root / "relationships.json").write_text(
                json.dumps(relationships, ensure_ascii=False),
                encoding="utf-8",
            )
            facts = load_facts(root, root / "metrics.json")

            with self.assertRaisesRegex(RelationshipGraphError, "重复关系"):
                build_relationship_graph(facts)

    def test_rejects_unknown_relationship_type(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            relationships = json.loads(
                (root / "relationships.json").read_text(encoding="utf-8")
            )
            relationships[0]["relationship_type"] = "polymorphic"
            (root / "relationships.json").write_text(
                json.dumps(relationships, ensure_ascii=False),
                encoding="utf-8",
            )
            facts = load_facts(root, root / "metrics.json")

            with self.assertRaisesRegex(RelationshipGraphError, "未知类型"):
                build_relationship_graph(facts)

    def test_rejects_foreign_key_missing_column(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            relationships = json.loads(
                (root / "relationships.json").read_text(encoding="utf-8")
            )
            relationships.append(
                {
                    "relationship_type": "foreign_key",
                    "schema_name": "mart_sales",
                    "table_name": "fct_sales",
                    "column_names": ["missing_column"],
                    "referenced_schema": "mart_sales",
                    "referenced_table": "dim_date",
                    "referenced_column_names": ["date_key"],
                    "constraint_name": "fk_bad",
                }
            )
            (root / "relationships.json").write_text(
                json.dumps(relationships, ensure_ascii=False),
                encoding="utf-8",
            )
            facts = load_facts(root, root / "metrics.json")

            with self.assertRaisesRegex(RelationshipGraphError, "不存在的字段"):
                build_relationship_graph(facts)

    def test_rejects_foreign_key_not_targeting_key(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            relationships = json.loads(
                (root / "relationships.json").read_text(encoding="utf-8")
            )
            relationships[2]["referenced_column_names"] = ["full_date"]
            (root / "relationships.json").write_text(
                json.dumps(relationships, ensure_ascii=False),
                encoding="utf-8",
            )
            facts = load_facts(root, root / "metrics.json")

            with self.assertRaisesRegex(RelationshipGraphError, "必须匹配主键"):
                build_relationship_graph(facts)


def _write_facts(root: Path) -> None:
    _write_tables(root)
    _write_columns(root)
    _write_relationships(root)
    (root / "metrics.json").write_text(
        json.dumps(
            [
                {
                    "name": "已完成订单数",
                    "level": "原子指标",
                    "aliases": [],
                    "definition": "已完成状态的订单数量。",
                    "formula": "COUNT(*)",
                    "data_source": "mart_sales.fct_sales",
                    "depends_on": [],
                    "filters": [],
                    "notes": "",
                    "time_field": "fct_sales.completion_date_key -> dim_date.full_date",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_tables(root: Path) -> None:
    (root / "tables.json").write_text(
        json.dumps(
            [
                {
                    "schema_name": "mart_sales",
                    "table_name": "dim_date",
                    "table_type": "BASE TABLE",
                    "description": "日期维度表",
                },
                {
                    "schema_name": "mart_sales",
                    "table_name": "fct_sales",
                    "table_type": "BASE TABLE",
                    "description": "销售事实表",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_columns(root: Path) -> None:
    (root / "columns.json").write_text(
        json.dumps(
            [
                {
                    "schema_name": "mart_sales",
                    "table_name": "dim_date",
                    "column_name": "date_key",
                    "data_type": "int",
                    "description": "日期代理键",
                },
                {
                    "schema_name": "mart_sales",
                    "table_name": "dim_date",
                    "column_name": "full_date",
                    "data_type": "date",
                    "description": "自然日期",
                },
                {
                    "schema_name": "mart_sales",
                    "table_name": "fct_sales",
                    "column_name": "order_id",
                    "data_type": "text",
                    "description": "订单标识",
                },
                {
                    "schema_name": "mart_sales",
                    "table_name": "fct_sales",
                    "column_name": "completion_date_key",
                    "data_type": "int",
                    "description": "完成日期代理键",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_relationships(root: Path) -> None:
    (root / "relationships.json").write_text(
        json.dumps(
            [
                {
                    "relationship_type": "primary_key",
                    "schema_name": "mart_sales",
                    "table_name": "dim_date",
                    "column_names": ["date_key"],
                    "constraint_name": "dim_date_pkey",
                },
                {
                    "relationship_type": "primary_key",
                    "schema_name": "mart_sales",
                    "table_name": "fct_sales",
                    "column_names": ["order_id"],
                    "constraint_name": "fct_sales_pkey",
                },
                {
                    "relationship_type": "foreign_key",
                    "schema_name": "mart_sales",
                    "table_name": "fct_sales",
                    "column_names": ["completion_date_key"],
                    "referenced_schema": "mart_sales",
                    "referenced_table": "dim_date",
                    "referenced_column_names": ["date_key"],
                    "constraint_name": "fk_fct_sales_date",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
