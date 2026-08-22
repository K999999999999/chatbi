"""POC Execution Accuracy（执行准确率）辅助函数。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from src.executor import QueryResult


def results_equivalent(
    expected: QueryResult,
    actual: QueryResult,
) -> bool:
    """比较结果值，忽略列别名和无 ORDER BY 时的行顺序。"""

    if len(expected.columns) != len(actual.columns):
        return False
    if len(expected.rows) != len(actual.rows):
        return False
    return _normalize_rows(expected.rows) == _normalize_rows(actual.rows)


def _normalize_rows(rows: Iterable[Iterable[Any]]) -> list[tuple[str, ...]]:
    normalized = [
        tuple(_normalize_value(value) for value in row)
        for row in rows
    ]
    return sorted(normalized)


def _normalize_value(value: Any) -> str:
    if value is None:
        return "<NULL>"
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)
