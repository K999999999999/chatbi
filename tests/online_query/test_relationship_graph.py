"""Relationship Graph（关系图）直接 FK-PK 边界测试。"""

import unittest

from src.online_query.relationship_graph import (
    RelationshipGraphAmbiguousError,
    RelationshipGraphUnreachableError,
    resolve_join_paths,
    parse_edges,
    validate_time_edge,
    validated_join_constraints,
)
from src.online_query.resource_retrieval import _TimeField


class RelationshipGraphDirectJoinTest(unittest.TestCase):
    def test_direct_forward_fk_to_pk_is_resolved(self) -> None:
        graph = _graph(
            edges=(_edge("fk_customer", "fct_sales", "dim_customer"),),
        )
        edges = parse_edges(graph)

        resolution = resolve_join_paths(
            "mart_sales.fct_sales",
            ("mart_sales.fct_sales", "mart_sales.dim_customer"),
            edges,
            time_edge=None,
            time_target=None,
        )

        self.assertEqual(
            resolution.paths[0].tables,
            (
                "mart_sales.fct_sales",
                "mart_sales.dim_customer",
            ),
        )
        constraints = validated_join_constraints(
            "mart_sales.fct_sales",
            resolution,
            graph,
        )
        self.assertEqual(len(constraints), 1)
        self.assertEqual(constraints[0].direction, "forward")

    def test_reverse_fk_is_not_inferred_as_a_join(self) -> None:
        edges = parse_edges(
            _graph(edges=(_edge("fk_customer", "dim_customer", "fct_sales"),))
        )

        with self.assertRaises(RelationshipGraphUnreachableError):
            resolve_join_paths(
                "mart_sales.fct_sales",
                ("mart_sales.fct_sales", "mart_sales.dim_customer"),
                edges,
                time_edge=None,
                time_target=None,
            )

    def test_bridge_and_multihop_path_is_not_traversed(self) -> None:
        graph = _graph(
            edges=(
                _edge("fk_bridge", "fct_sales", "bridge_customer"),
                _edge("fk_customer", "bridge_customer", "dim_customer"),
            ),
        )
        edges = parse_edges(graph)

        with self.assertRaises(RelationshipGraphUnreachableError):
            resolve_join_paths(
                "mart_sales.fct_sales",
                ("mart_sales.fct_sales", "mart_sales.dim_customer"),
                edges,
                time_edge=None,
                time_target=None,
            )

    def test_join_without_target_key_proof_is_rejected(self) -> None:
        graph = _graph(
            edges=(_edge("fk_customer", "fct_sales", "dim_customer"),),
            primary_keys=(),
        )
        edges = parse_edges(graph)
        resolution = resolve_join_paths(
            "mart_sales.fct_sales",
            ("mart_sales.fct_sales", "mart_sales.dim_customer"),
            edges,
            time_edge=None,
            time_target=None,
        )

        with self.assertRaises(RelationshipGraphUnreachableError):
            validated_join_constraints(
                "mart_sales.fct_sales",
                resolution,
                graph,
            )

    def test_multiple_direct_edges_are_ambiguous_without_time_selection(self) -> None:
        edges = parse_edges(
            _graph(
                edges=(
                    _edge("fk_customer", "fct_sales", "dim_customer"),
                    _edge("fk_customer_alt", "fct_sales", "dim_customer"),
                )
            )
        )

        with self.assertRaises(RelationshipGraphAmbiguousError):
            resolve_join_paths(
                "mart_sales.fct_sales",
                ("mart_sales.fct_sales", "mart_sales.dim_customer"),
                edges,
                time_edge=None,
                time_target=None,
            )

    def test_ambiguous_time_edges_are_rejected(self) -> None:
        edges = parse_edges(
            _graph(
                edges=(
                    _edge("fk_date_a", "fct_sales", "dim_date"),
                    _edge("fk_date_b", "fct_sales", "dim_date"),
                ),
                primary_keys=(
                    {
                        "relationship_type": "primary_key",
                        "schema_name": "mart_sales",
                        "table_name": "dim_date",
                        "column_names": ["customer_key"],
                        "constraint_name": "pk_dim_date",
                    },
                ),
            )
        )

        with self.assertRaises(RelationshipGraphAmbiguousError):
            validate_time_edge(
                _TimeField(
                    source_table="mart_sales.fct_sales",
                    source_column="customer_key",
                    target_table="mart_sales.dim_date",
                    filter_column="full_date",
                ),
                edges,
            )


def _edge(constraint_name: str, source_table: str, target_table: str) -> dict:
    return {
        "constraint_name": constraint_name,
        "source_schema": "mart_sales",
        "source_table": source_table,
        "source_columns": ["customer_key"],
        "target_schema": "mart_sales",
        "target_table": target_table,
        "target_columns": ["customer_key"],
    }


def _graph(
    *, edges: tuple[dict, ...], primary_keys: tuple[dict, ...] | None = None
) -> dict:
    keys = primary_keys
    if keys is None:
        keys = (
            {
                "relationship_type": "primary_key",
                "schema_name": "mart_sales",
                "table_name": "dim_customer",
                "column_names": ["customer_key"],
                "constraint_name": "pk_dim_customer",
            },
            {
                "relationship_type": "primary_key",
                "schema_name": "mart_sales",
                "table_name": "bridge_customer",
                "column_names": ["customer_key"],
                "constraint_name": "pk_bridge_customer",
            },
        )
    return {
        "foreign_keys": list(edges),
        "primary_keys": list(keys),
        "unique_constraints": [],
    }


if __name__ == "__main__":
    unittest.main()
