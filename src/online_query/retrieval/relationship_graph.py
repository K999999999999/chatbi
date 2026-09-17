"""Relationship Graph（关系图）的确定性解析与 Join Resolution（连接解析）。"""

from collections.abc import Iterable, Mapping
from dataclasses import replace
from types import MappingProxyType
from typing import Any

from ..contracts import JoinConstraint, JoinEdge, JoinPath, JoinResolution


class RelationshipGraphContractError(RuntimeError):
    """已发布 Relationship Graph 不满足在线解析 Contract。"""


class RelationshipGraphAmbiguousError(RuntimeError):
    """确定性关系规则无法选择唯一结果。"""


class RelationshipGraphUnreachableError(RuntimeError):
    """必需表无法通过已验证关系到达。"""


def parse_edges(graph: Mapping[str, Any]) -> tuple[JoinEdge, ...]:
    """把已发布关系图的 Foreign Key 事实解析为稳定 JoinEdge。"""

    raw_edges = graph.get("foreign_keys")
    if not isinstance(raw_edges, list):
        raise RelationshipGraphContractError("Relationship Graph 缺少 foreign_keys")
    edges: list[JoinEdge] = []
    for index, raw in enumerate(raw_edges, 1):
        if not isinstance(raw, Mapping):
            raise RelationshipGraphContractError(
                f"Relationship Graph 第 {index} 条边格式无效"
            )
        edge_id = _text(raw, "constraint_name", index)
        source_table = _qualified_from_graph(
            raw,
            "source_schema",
            "source_table",
            index,
        )
        target_table = _qualified_from_graph(
            raw,
            "target_schema",
            "target_table",
            index,
        )
        source_columns = _string_tuple(
            raw.get("source_columns"),
            "source_columns",
            index,
        )
        target_columns = _string_tuple(
            raw.get("target_columns"),
            "target_columns",
            index,
        )
        if len(source_columns) != len(target_columns):
            raise RelationshipGraphContractError(
                f"Relationship Graph 第 {index} 条边键数量不一致"
            )
        edges.append(
            JoinEdge(
                edge_id=edge_id,
                source_table=source_table,
                target_table=target_table,
                source_columns=source_columns,
                target_columns=target_columns,
                constraint_name=edge_id,
                direction="forward",
            )
        )
    return tuple(sorted(edges, key=lambda edge: edge.edge_id))


def validate_time_edge(time_field: Any, edges: tuple[JoinEdge, ...]) -> Any:
    """确认 time_field 使用关系图中的同一条时间 Join 边。"""

    matches = tuple(
        edge
        for edge in edges
        if edge.source_table == time_field.source_table
        and edge.target_table == time_field.target_table
        and edge.source_columns == (time_field.source_column,)
    )
    if not matches:
        raise RelationshipGraphContractError(
            "time_field 无法匹配已验证 Relationship Graph"
        )
    if len(matches) > 1:
        raise RelationshipGraphAmbiguousError("time_field 匹配到多条语义不同关系")
    return replace(time_field, edge_id=matches[0].edge_id)


def resolve_join_paths(
    anchor_table: str,
    target_tables: tuple[str, ...],
    edges: tuple[JoinEdge, ...],
    *,
    time_edge: str | None,
    time_target: str | None,
) -> JoinResolution:
    """只解析 Anchor 到目标表之间的唯一直接 FK 边。

    V1 不沿关系图做反向推断或多跳 BFS；目标表必须由事实表 Anchor
    直接通过 Foreign Key（外键）指向。
    """

    all_paths: list[JoinPath] = []
    chosen_joins: list[JoinEdge] = []
    unreachable: list[str] = []
    for target in target_tables:
        if target == anchor_table:
            continue
        direct_edges = tuple(
            edge
            for edge in edges
            if edge.source_table == anchor_table and edge.target_table == target
        )
        if target == time_target and time_edge is not None:
            time_edges = tuple(
                edge for edge in direct_edges if edge.edge_id == time_edge
            )
            if time_edges:
                direct_edges = time_edges
        if not direct_edges:
            unreachable.append(target)
            continue
        if len(direct_edges) > 1:
            raise RelationshipGraphAmbiguousError(
                f"目标表 {target} 存在多条无法唯一裁决的直接关系"
            )
        edge = direct_edges[0]
        path = JoinPath(
            tables=(anchor_table, target),
            edges=(edge,),
        )
        all_paths.append(path)
        chosen_joins.extend(path.edges)
    if unreachable:
        raise RelationshipGraphUnreachableError(
            "必需表不可达（只支持从事实表沿 Foreign Key（外键）正向展开）："
            f"{'、'.join(sorted(unreachable))}"
        )
    return JoinResolution(
        anchor_table=anchor_table,
        paths=tuple(all_paths),
        joins=_dedupe_edges(chosen_joins),
        unreachable_tables=(),
    )


def validated_join_constraints(
    anchor_table: str,
    resolution: JoinResolution,
    graph: Mapping[str, Any],
) -> tuple[JoinConstraint, ...]:
    """只允许从事实表 Anchor 正向连接到有唯一性证明的目标表。"""

    if not resolution.joins:
        return ()
    unique_keys = _graph_unique_keys(graph)
    for path in resolution.paths:
        current = anchor_table
        for edge in path.edges:
            if edge.direction != "forward" or edge.source_table != current:
                raise RelationshipGraphUnreachableError(
                    "Join 必须从事实表 Anchor 沿 Foreign Key（外键）正向展开"
                )
            current = edge.target_table

    constraints: list[JoinConstraint] = []
    for edge in resolution.joins:
        basis = unique_keys.get((edge.target_table, edge.target_columns))
        if basis is None:
            raise RelationshipGraphUnreachableError(
                f"Join 目标缺少 Primary Key / Unique Constraint（主键/唯一约束）证明："
                f"{edge.target_table}({', '.join(edge.target_columns)})"
            )
        constraints.append(
            JoinConstraint(
                source_table=edge.source_table,
                source_columns=edge.source_columns,
                target_table=edge.target_table,
                target_columns=edge.target_columns,
                uniqueness_basis=basis,
                direction="forward",
            )
        )
    return tuple(constraints)


def _graph_unique_keys(
    graph: Mapping[str, Any],
) -> Mapping[tuple[str, tuple[str, ...]], str]:
    """读取无条件 Primary Key / Unique Constraint；V1 不采信 Unique Index。"""

    result: dict[tuple[str, tuple[str, ...]], str] = {}
    for section, prefix in (
        ("primary_keys", "primary_key"),
        ("unique_constraints", "unique_constraint"),
    ):
        records = graph.get(section)
        if not isinstance(records, list):
            raise RelationshipGraphContractError(f"Relationship Graph 缺少 {section}")
        for index, raw in enumerate(records, 1):
            if not isinstance(raw, Mapping):
                raise RelationshipGraphContractError(
                    f"Relationship Graph {section} 第 {index} 条记录格式无效"
                )
            table = _qualified_from_graph(
                raw,
                "schema_name",
                "table_name",
                index,
            )
            columns = _string_tuple(
                raw.get("column_names"),
                "column_names",
                index,
            )
            constraint_name = _text(raw, "constraint_name", index)
            result[(table, columns)] = f"{prefix}:{constraint_name}"
    return MappingProxyType(result)


def _dedupe_edges(edges: Iterable[JoinEdge]) -> tuple[JoinEdge, ...]:
    result: list[JoinEdge] = []
    seen: set[tuple[str, str]] = set()
    for edge in edges:
        key = (edge.edge_id, edge.direction)
        if key not in seen:
            seen.add(key)
            result.append(edge)
    return tuple(result)


def _qualified_from_graph(
    raw: Mapping[str, Any],
    schema_key: str,
    table_key: str,
    index: int,
) -> str:
    schema = _text(raw, schema_key, index)
    table = _text(raw, table_key, index)
    return f"{schema}.{table}"


def _text(raw: Mapping[str, Any], key: str, index: int) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RelationshipGraphContractError(
            f"Relationship Graph 第 {index} 条边缺少 {key}"
        )
    return value.strip()


def _string_tuple(value: Any, key: str, index: int) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise RelationshipGraphContractError(
            f"Relationship Graph 第 {index} 条边的 {key} 无效"
        )
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise RelationshipGraphContractError(
            f"Relationship Graph 第 {index} 条边的 {key} 无效"
        )
    return tuple(item.strip() for item in value)
