"""Build deterministic Relationship Graph（关系图）from relationships.json."""

from dataclasses import dataclass
from typing import Any

from .sources import Facts


class RelationshipGraphError(RuntimeError):
    """关系事实无法转成可信的关系图。"""


@dataclass(frozen=True, slots=True)
class RelationshipGraph:
    """保留全部表、键约束和外键 Join Edge 的结构化关系图。"""

    nodes: tuple[str, ...]
    primary_keys: tuple[dict[str, Any], ...]
    unique_constraints: tuple[dict[str, Any], ...]
    unique_indexes: tuple[dict[str, Any], ...]
    foreign_keys: tuple[dict[str, Any], ...]

    @property
    def edge_count(self) -> int:
        return len(self.foreign_keys)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": list(self.nodes),
            "primary_keys": [_jsonable(item) for item in self.primary_keys],
            "unique_constraints": [_jsonable(item) for item in self.unique_constraints],
            "unique_indexes": [_jsonable(item) for item in self.unique_indexes],
            "foreign_keys": [_jsonable(item) for item in self.foreign_keys],
        }


def build_relationship_graph(facts: Facts) -> RelationshipGraph:
    """从已校验事实源生成确定性关系图，并校验每个关系端点。"""

    tables = {_qualified(table) for table in facts.tables}
    columns_by_table = _columns_by_table(facts)
    key_constraints_by_table = _collect_key_constraints(facts.relationships, tables)

    primary_keys: list[dict[str, Any]] = []
    unique_constraints: list[dict[str, Any]] = []
    unique_indexes: list[dict[str, Any]] = []
    foreign_keys: list[dict[str, Any]] = []
    seen_primary: set[str] = set()
    seen_unique: set[str] = set()
    seen_indexes: set[str] = set()
    seen_foreign: set[str] = set()

    for index, relationship in enumerate(facts.relationships, 1):
        relationship_type = _required_text(relationship, "relationship_type", index)
        schema_name = _required_text(relationship, "schema_name", index)
        table_name = _required_text(relationship, "table_name", index)
        table_key = f"{schema_name}.{table_name}"
        if table_key not in tables:
            raise RelationshipGraphError(
                f"relationships 第 {index} 条引用了不存在的表：{table_key}"
            )
        column_names = _required_columns(relationship, "column_names", index)
        _validate_columns_exist(
            table_key,
            column_names,
            columns_by_table,
            f"relationships 第 {index} 条",
        )

        if relationship_type in {"primary_key", "unique_constraint"}:
            constraint_name = _required_text(relationship, "constraint_name", index)
            record = {
                "relationship_type": relationship_type,
                "schema_name": schema_name,
                "table_name": table_name,
                "column_names": column_names,
                "constraint_name": constraint_name,
            }
            identity = f"{table_key}:{constraint_name}"
            if relationship_type == "primary_key":
                _add_unique(primary_keys, seen_primary, record, identity)
            else:
                _add_unique(unique_constraints, seen_unique, record, identity)
            continue

        if relationship_type == "unique_index":
            index_name = _required_text(relationship, "index_name", index)
            record = {
                "relationship_type": relationship_type,
                "schema_name": schema_name,
                "table_name": table_name,
                "index_name": index_name,
                "column_names": column_names,
                "predicate": relationship.get("predicate"),
            }
            _add_unique(
                unique_indexes, seen_indexes, record, f"{table_key}:{index_name}"
            )
            continue

        if relationship_type != "foreign_key":
            raise RelationshipGraphError(
                f"relationships 第 {index} 条存在未知类型：{relationship_type}"
            )

        referenced_schema = _required_text(relationship, "referenced_schema", index)
        referenced_table = _required_text(relationship, "referenced_table", index)
        referenced_key = f"{referenced_schema}.{referenced_table}"
        if referenced_key not in tables:
            raise RelationshipGraphError(
                f"relationships 第 {index} 条引用了不存在的表：{referenced_key}"
            )
        referenced_columns = _required_columns(
            relationship,
            "referenced_column_names",
            index,
        )
        _validate_columns_exist(
            referenced_key,
            referenced_columns,
            columns_by_table,
            f"relationships 第 {index} 条",
        )
        _validate_referenced_key(
            referenced_key,
            referenced_columns,
            key_constraints_by_table,
            index,
        )
        constraint_name = _required_text(relationship, "constraint_name", index)
        record = {
            "relationship_type": "foreign_key",
            "constraint_name": constraint_name,
            "source_schema": schema_name,
            "source_table": table_name,
            "source_columns": column_names,
            "target_schema": referenced_schema,
            "target_table": referenced_table,
            "target_columns": referenced_columns,
        }
        _add_unique(
            foreign_keys,
            seen_foreign,
            record,
            f"{table_key}:{constraint_name}",
        )

    return RelationshipGraph(
        nodes=tuple(sorted(tables)),
        primary_keys=tuple(sorted(primary_keys, key=_record_sort_key)),
        unique_constraints=tuple(sorted(unique_constraints, key=_record_sort_key)),
        unique_indexes=tuple(sorted(unique_indexes, key=_record_sort_key)),
        foreign_keys=tuple(sorted(foreign_keys, key=_record_sort_key)),
    )


def _collect_key_constraints(
    relationships: tuple[dict[str, Any], ...],
    tables: set[str],
) -> dict[str, tuple[tuple[str, ...], ...]]:
    result: dict[str, list[tuple[str, ...]]] = {}
    for index, relationship in enumerate(relationships, 1):
        relationship_type = relationship.get("relationship_type")
        if relationship_type not in {"primary_key", "unique_constraint"}:
            continue
        schema = relationship.get("schema_name")
        table = relationship.get("table_name")
        if not isinstance(schema, str) or not isinstance(table, str):
            raise RelationshipGraphError(
                f"relationships 第 {index} 条键约束缺少有效的表身份"
            )
        key = f"{schema}.{table}"
        if key not in tables:
            raise RelationshipGraphError(
                f"relationships 第 {index} 条引用了不存在的表：{key}"
            )
        result.setdefault(key, []).append(tuple(_string_list(relationship, index)))
    return {key: tuple(values) for key, values in result.items()}


def _validate_referenced_key(
    table_key: str,
    columns: tuple[str, ...],
    key_constraints_by_table: dict[str, tuple[tuple[str, ...], ...]],
    index: int,
) -> None:
    key_columns = key_constraints_by_table.get(table_key, ())
    if columns not in key_columns:
        raise RelationshipGraphError(
            f"relationships 第 {index} 条外键目标 {table_key} "
            f"必须匹配主键或唯一约束：{'、'.join(columns)}"
        )


def _columns_by_table(facts: Facts) -> dict[str, frozenset[str]]:
    result: dict[str, set[str]] = {}
    for column in facts.columns:
        table_key = f"{column['schema_name']}.{column['table_name']}"
        result.setdefault(table_key, set()).add(column["column_name"])
    return {key: frozenset(values) for key, values in result.items()}


def _validate_columns_exist(
    table_key: str,
    column_names: tuple[str, ...],
    columns_by_table: dict[str, frozenset[str]],
    label: str,
) -> None:
    known = columns_by_table.get(table_key, frozenset())
    missing = [column for column in column_names if column not in known]
    if missing:
        raise RelationshipGraphError(
            f"{label} 引用 {table_key} 不存在的字段：{'、'.join(missing)}"
        )


def _add_unique(
    records: list[dict[str, Any]],
    seen: set[str],
    record: dict[str, Any],
    identity: str,
) -> None:
    if identity in seen:
        raise RelationshipGraphError(f"relationships 存在重复关系：{identity}")
    seen.add(identity)
    records.append(record)


def _required_text(record: dict[str, Any], field: str, index: int) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise RelationshipGraphError(f"relationships 第 {index} 条缺少有效的 {field}")
    return value.strip()


def _required_columns(
    record: dict[str, Any],
    field: str,
    index: int,
) -> tuple[str, ...]:
    values = _string_list(record, index, field)
    if not values:
        raise RelationshipGraphError(f"relationships 第 {index} 条的 {field} 不能为空")
    return values


def _string_list(
    record: dict[str, Any],
    index: int,
    field: str = "column_names",
) -> tuple[str, ...]:
    value = record.get(field)
    if not isinstance(value, list) or not value:
        raise RelationshipGraphError(
            f"relationships 第 {index} 条的 {field} 必须是字符串数组"
        )
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise RelationshipGraphError(
                f"relationships 第 {index} 条的 {field} 不能包含空值"
            )
        normalized.append(item.strip())
    return tuple(normalized)


def _qualified(record: dict[str, Any]) -> str:
    return f"{record['schema_name']}.{record['table_name']}"


def _record_sort_key(record: dict[str, Any]) -> tuple[str, ...]:
    return (
        record.get("relationship_type", ""),
        record.get("schema_name", record.get("source_schema", "")),
        record.get("table_name", record.get("source_table", "")),
        record.get("constraint_name", record.get("index_name", "")),
        ",".join(record.get("column_names", record.get("source_columns", ()))),
        record.get("referenced_schema", record.get("target_schema", "")),
        record.get("referenced_table", record.get("target_table", "")),
        ",".join(
            record.get("referenced_column_names", record.get("target_columns", ()))
        ),
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
