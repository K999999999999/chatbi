"""加载并缓存 Online Query（在线查询）使用的静态上下文。"""

from collections import defaultdict
from functools import lru_cache
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

from ..rag_offline.relationships import (
    RelationshipGraphError,
    build_relationship_graph,
)
from ..rag_offline.sources import Facts
from .contracts import JoinConstraint, QueryContext


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STRUCTURE_DIR = PROJECT_ROOT / "src" / "structure" / "generated"
DEFAULT_METRICS_PATH = PROJECT_ROOT / "src" / "semantic" / "metrics.json"


class ContextLoadError(RuntimeError):
    """静态上下文无法安全加载。"""


@lru_cache(maxsize=None)
def load_query_context(
    structure_dir: Path = DEFAULT_STRUCTURE_DIR,
    metrics_path: Path = DEFAULT_METRICS_PATH,
) -> QueryContext:
    """读取四个明确文件，并按路径缓存成功结果。"""

    resources = {
        "tables": _load_records(structure_dir / "tables.json", "tables"),
        "columns": _load_records(structure_dir / "columns.json", "columns"),
        "relationships": _load_records(
            structure_dir / "relationships.json",
            "relationships",
        ),
        "metrics": _load_records(metrics_path, "metrics"),
    }

    allowed_tables = frozenset(
        _qualified_table(record, "tables") for record in resources["tables"]
    )
    columns_by_table: defaultdict[str, set[str]] = defaultdict(set)
    for record in resources["columns"]:
        table = _qualified_table(record, "columns")
        column = _required_text(record, "column_name", "columns")
        _validate_value_examples(record)
        columns_by_table[table].add(column)

    unknown_column_tables = set(columns_by_table) - allowed_tables
    if unknown_column_tables:
        raise ContextLoadError("columns 引用了 tables 中不存在的表")

    join_constraints = _build_join_constraints(resources)

    allowed_columns = MappingProxyType(
        {
            table: frozenset(columns_by_table.get(table, set()))
            for table in sorted(allowed_tables)
        }
    )
    prompt_context = json.dumps(resources, ensure_ascii=False, indent=2)

    return QueryContext(
        prompt_context=prompt_context,
        allowed_tables=allowed_tables,
        allowed_columns=allowed_columns,
        join_constraints=join_constraints,
    )


def _build_join_constraints(
    resources: dict[str, list[dict[str, Any]]],
) -> tuple[JoinConstraint, ...]:
    """把静态关系事实转换成 SQL Guard 可验证的直接 Join 约束。

    静态上下文只用于显式装配的离线评测/基础模式；在线 RAG 入口仍只消费
    当前 Asset Snapshot（资源快照）生成的动态上下文。这里复用离线关系图
    校验，避免静态评测绕过和在线路径不同的 FK → PK 约束。
    """

    try:
        graph = build_relationship_graph(
            Facts(
                tables=tuple(resources["tables"]),
                columns=tuple(resources["columns"]),
                relationships=tuple(resources["relationships"]),
                metrics=tuple(resources["metrics"]),
            )
        ).to_dict()
    except RelationshipGraphError as exc:
        raise ContextLoadError(
            f"relationships 无法构建安全关系图：{exc}"
        ) from None

    unique_keys: dict[tuple[str, tuple[str, ...]], str] = {}
    for section, prefix in (
        ("primary_keys", "primary_key"),
        ("unique_constraints", "unique_constraint"),
    ):
        for record in graph[section]:
            table = f"{record['schema_name']}.{record['table_name']}"
            columns = tuple(record["column_names"])
            unique_keys[(table, columns)] = (
                f"{prefix}:{record['constraint_name']}"
            )

    constraints: list[JoinConstraint] = []
    for edge in graph["foreign_keys"]:
        source_table = f"{edge['source_schema']}.{edge['source_table']}"
        target_table = f"{edge['target_schema']}.{edge['target_table']}"
        source_columns = tuple(edge["source_columns"])
        target_columns = tuple(edge["target_columns"])
        uniqueness_basis = unique_keys.get((target_table, target_columns))
        if uniqueness_basis is None:
            raise ContextLoadError(
                "relationships 外键目标缺少 Primary Key / Unique Constraint（主键/唯一约束）证明"
            )
        constraints.append(
            JoinConstraint(
                source_table=source_table,
                source_columns=source_columns,
                target_table=target_table,
                target_columns=target_columns,
                uniqueness_basis=uniqueness_basis,
                direction="forward",
            )
        )
    return tuple(
        sorted(
            constraints,
            key=lambda item: (
                item.source_table,
                item.target_table,
                item.source_columns,
                item.target_columns,
            ),
        )
    )


def _load_records(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ContextLoadError(f"{label} 文件不存在") from None
    except (OSError, UnicodeError):
        raise ContextLoadError(f"{label} 文件无法读取") from None

    try:
        records = json.loads(content)
    except json.JSONDecodeError:
        raise ContextLoadError(f"{label} 不是合法 JSON") from None

    if not isinstance(records, list) or not records:
        raise ContextLoadError(f"{label} 必须是非空 JSON 数组")
    if any(not isinstance(record, dict) for record in records):
        raise ContextLoadError(f"{label} 的每条记录必须是 JSON 对象")
    return records


def _validate_value_examples(record: dict[str, Any]) -> None:
    if "value_examples" not in record:
        return

    values = record["value_examples"]
    if not isinstance(values, list):
        raise ContextLoadError("columns 的 value_examples 必须是字符串数组")

    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ContextLoadError("columns 的 value_examples 不能包含空值")
        normalized.append(value.strip())

    if len(set(normalized)) != len(normalized):
        raise ContextLoadError("columns 的 value_examples 不能包含重复值")


def _qualified_table(record: dict[str, Any], label: str) -> str:
    schema = _required_text(record, "schema_name", label)
    table = _required_text(record, "table_name", label)
    return f"{schema}.{table}"


def _required_text(record: dict[str, Any], field: str, label: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ContextLoadError(f"{label} 缺少有效的 {field}")
    return value.strip()
