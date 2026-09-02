"""加载并缓存 Online Query（在线查询）使用的静态上下文。"""

from collections import defaultdict
from functools import lru_cache
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .contracts import QueryContext


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
