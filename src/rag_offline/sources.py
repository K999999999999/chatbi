"""Load and validate RAG Offline Build（RAG 离线构建）的权威事实源。"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STRUCTURE_DIR = PROJECT_ROOT / "src" / "structure" / "generated"
DEFAULT_METRICS_PATH = PROJECT_ROOT / "src" / "semantic" / "metrics.json"


class SourceLoadError(RuntimeError):
    """事实源整体无法安全用于离线构建。"""


@dataclass(frozen=True, slots=True)
class Facts:
    """已经通过加载和交叉校验的权威事实。"""

    tables: tuple[dict[str, Any], ...]
    columns: tuple[dict[str, Any], ...]
    relationships: tuple[dict[str, Any], ...]
    metrics: tuple[dict[str, Any], ...]


def load_facts(
    structure_dir: Path = DEFAULT_STRUCTURE_DIR,
    metrics_path: Path = DEFAULT_METRICS_PATH,
) -> Facts:
    """读取四个事实源，并按离线构建契约完成加载校验。"""

    tables = _normalize_tables(_read_records(structure_dir / "tables.json", "tables"))
    columns = _normalize_columns(
        _read_records(structure_dir / "columns.json", "columns"),
        tables,
    )
    relationships = _read_records(
        structure_dir / "relationships.json",
        "relationships",
    )
    metrics = _normalize_metrics(
        _read_records(metrics_path, "metrics"),
        tables,
        columns,
    )

    return Facts(
        tables=tables,
        columns=columns,
        relationships=relationships,
        metrics=metrics,
    )


def _read_records(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SourceLoadError(f"{label} 文件不存在") from None
    except (OSError, UnicodeError):
        raise SourceLoadError(f"{label} 文件无法读取") from None

    try:
        records = json.loads(content)
    except json.JSONDecodeError:
        raise SourceLoadError(f"{label} 不是合法 JSON") from None
    if not isinstance(records, list) or not records:
        raise SourceLoadError(f"{label} 必须是非空 JSON 数组")
    if any(not isinstance(record, dict) for record in records):
        raise SourceLoadError(f"{label} 的每条记录必须是 JSON 对象")
    return records


def _normalize_tables(records: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, record in enumerate(records, 1):
        schema = _required_text(record, "schema_name", "tables", index)
        table = _required_text(record, "table_name", "tables", index)
        key = f"{schema}.{table}"
        if key in seen:
            raise SourceLoadError(f"tables 存在重复表：{key}")
        seen.add(key)
        normalized.append(
            {
                "schema_name": schema,
                "table_name": table,
                "table_type": _optional_text(record, "table_type") or "BASE TABLE",
                "description": _optional_text(record, "description"),
            }
        )
    return tuple(normalized)


def _normalize_columns(
    records: list[dict[str, Any]],
    tables: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    table_keys = {_table_key(table) for table in tables}
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, record in enumerate(records, 1):
        schema = _required_text(record, "schema_name", "columns", index)
        table = _required_text(record, "table_name", "columns", index)
        column = _required_text(record, "column_name", "columns", index)
        key = f"{schema}.{table}.{column}"
        if f"{schema}.{table}" not in table_keys:
            raise SourceLoadError(
                f"columns 第 {index} 条引用了不存在的表：{schema}.{table}"
            )
        if key in seen:
            raise SourceLoadError(f"columns 存在重复字段：{key}")
        seen.add(key)
        normalized.append(
            {
                "schema_name": schema,
                "table_name": table,
                "column_name": column,
                "data_type": _required_text(record, "data_type", "columns", index),
                "description": _optional_text(record, "description"),
                "nullable": _optional_bool(record, "nullable"),
                "is_primary_key": _optional_bool(record, "is_primary_key", False),
                "is_foreign_key": _optional_bool(record, "is_foreign_key", False),
                "value_examples": _optional_strings(
                    record, "value_examples", "columns", index
                ),
            }
        )
    return tuple(normalized)


def _normalize_metrics(
    records: list[dict[str, Any]],
    tables: tuple[dict[str, Any], ...],
    columns: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, record in enumerate(records, 1):
        name = _required_text(record, "name", "metrics", index)
        if name in seen:
            raise SourceLoadError(f"metrics 存在重复指标名：{name}")
        seen.add(name)
        metric = {
            "name": name,
            "aliases": _optional_strings(record, "aliases", "metrics", index),
            "level": _optional_text(record, "level"),
            "definition": _optional_text(record, "definition"),
            "formula": _optional_text(record, "formula"),
            "data_source": _optional_text(record, "data_source"),
            "depends_on": _optional_strings(record, "depends_on", "metrics", index),
            "filters": _optional_strings(record, "filters", "metrics", index),
            "notes": _optional_text(record, "notes"),
            "time_field": _optional_text(record, "time_field"),
        }
        _validate_metric_references(metric, tables, columns, index)
        normalized.append(metric)

    metric_names = {metric["name"] for metric in normalized}
    for metric in normalized:
        unknown_dependencies = sorted(set(metric["depends_on"]) - metric_names)
        if unknown_dependencies:
            raise SourceLoadError(
                f"metrics 指标 {metric['name']} 依赖不存在的指标："
                + "、".join(unknown_dependencies)
            )
    return tuple(normalized)


def _validate_metric_references(
    metric: dict[str, Any],
    tables: tuple[dict[str, Any], ...],
    columns: tuple[dict[str, Any], ...],
    index: int,
) -> None:
    data_source = metric["data_source"]
    if data_source:
        source_table = _resolve_table_reference(data_source)
        if not _table_exists(source_table, tables):
            raise SourceLoadError(
                f"metrics 第 {index} 条指标 {metric['name']} "
                f"引用了不存在的表：{data_source}"
            )

    time_field = metric["time_field"]
    if not time_field:
        return
    for raw_ref in time_field.split("->"):
        column_ref = raw_ref.strip()
        if not column_ref:
            continue
        resolved = _resolve_column_reference(column_ref, tables, columns)
        if resolved is None:
            raise SourceLoadError(
                f"metrics 第 {index} 条指标 {metric['name']} "
                f"时间字段引用了不存在的表或字段：{column_ref}"
            )


def _resolve_table_reference(reference: str) -> tuple[str | None, str]:
    parts = reference.strip().split(".")
    if len(parts) == 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return None, parts[0]
    raise SourceLoadError(f"无法解析的表引用：{reference}")


def _resolve_column_reference(
    reference: str,
    tables: tuple[dict[str, Any], ...],
    columns: tuple[dict[str, Any], ...],
) -> tuple[str, str] | None:
    parts = reference.split(".")
    if len(parts) == 2:
        schema: str | None = None
        table_name, column_name = parts
    elif len(parts) == 3:
        schema, table_name, column_name = parts
    else:
        return None

    candidate_tables = [
        table
        for table in tables
        if table["table_name"] == table_name
        and (schema is None or table["schema_name"] == schema)
    ]
    if len(candidate_tables) != 1:
        return None
    table = candidate_tables[0]
    table_key = _table_key(table)
    known_columns = {
        column["column_name"] for column in columns if _table_key(column) == table_key
    }
    if column_name not in known_columns:
        return None
    return table_key, column_name


def _table_exists(
    reference: tuple[str | None, str],
    tables: tuple[dict[str, Any], ...],
) -> bool:
    schema, table_name = reference
    return any(
        table["table_name"] == table_name
        and (schema is None or table["schema_name"] == schema)
        for table in tables
    )


def _table_key(record: dict[str, Any]) -> str:
    return f"{record['schema_name']}.{record['table_name']}"


def _required_text(
    record: dict[str, Any],
    field: str,
    label: str,
    index: int,
) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SourceLoadError(f"{label} 第 {index} 条缺少有效的 {field}")
    return value.strip()


def _optional_text(record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SourceLoadError(f"{field} 必须是字符串")
    return value.strip()


def _optional_bool(
    record: dict[str, Any],
    field: str,
    default: bool | None = None,
) -> bool | None:
    value = record.get(field)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise SourceLoadError(f"{field} 必须是布尔值")
    return value


def _optional_strings(
    record: dict[str, Any],
    field: str,
    label: str,
    index: int,
) -> tuple[str, ...]:
    if field not in record:
        return ()
    values = record[field]
    if not isinstance(values, list):
        raise SourceLoadError(f"{label} 第 {index} 条的 {field} 必须是字符串数组")
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise SourceLoadError(f"{label} 第 {index} 条的 {field} 不能包含空值")
        normalized.append(value.strip())
    if len(set(normalized)) != len(normalized):
        raise SourceLoadError(f"{label} 第 {index} 条的 {field} 不能包含重复值")
    return tuple(normalized)
