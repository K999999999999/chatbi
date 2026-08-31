"""标准评测案例加载与确定性结果比较。"""

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from src.online_query.contracts import QueryData

_TOLERANCE = Decimal("0.000001")
_REQUIRED_TEXT_FIELDS = (
    "id",
    "schema_name",
    "category",
    "question",
    "description",
    "expected_sql",
)


class EvaluationLoadError(RuntimeError):
    """标准测试集文件整体无法用于评测。"""


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """一条标准案例；格式错误由 validation_error 保留。"""

    id: str
    schema_name: str
    category: str
    question: str
    description: str
    expected_sql: str
    order_sensitive: bool = False
    validation_error: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.validation_error is None


def load_evaluation_cases(path: Path) -> tuple[EvaluationCase, ...]:
    """加载测试集；文件级错误拒绝，单条错误保留给 Runner 处理。"""

    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise EvaluationLoadError("标准测试集文件不存在") from None
    except (OSError, UnicodeError):
        raise EvaluationLoadError("标准测试集文件无法读取") from None

    try:
        records = json.loads(content)
    except json.JSONDecodeError:
        raise EvaluationLoadError("标准测试集不是合法 JSON") from None

    if not isinstance(records, list) or not records:
        raise EvaluationLoadError("标准测试集必须是非空 JSON 数组")

    cases = tuple(_parse_case(record, index) for index, record in enumerate(records, 1))
    case_ids = [case.id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise EvaluationLoadError("标准测试集存在重复 id")
    return cases


def results_match(
    actual: QueryData,
    expected: QueryData,
    *,
    order_sensitive: bool = False,
) -> bool:
    """按已确认的行列和数值规则比较两个查询结果。"""

    if actual.truncated or expected.truncated:
        return False
    if len(actual.columns) != len(expected.columns):
        return False
    if len(actual.rows) != len(expected.rows):
        return False
    if not _rows_have_expected_width(actual) or not _rows_have_expected_width(expected):
        return False

    if order_sensitive:
        return all(
            _rows_match(actual_row, expected_row)
            for actual_row, expected_row in zip(actual.rows, expected.rows, strict=True)
        )

    unmatched = list(expected.rows)
    for actual_row in actual.rows:
        for index, expected_row in enumerate(unmatched):
            if _rows_match(actual_row, expected_row):
                unmatched.pop(index)
                break
        else:
            return False
    return not unmatched


def _parse_case(record: object, index: int) -> EvaluationCase:
    if not isinstance(record, dict):
        return EvaluationCase(
            id=f"case-{index}",
            schema_name="",
            category="unknown",
            question="",
            description="",
            expected_sql="",
            validation_error="案例必须是 JSON 对象",
        )

    values: dict[str, str] = {}
    errors: list[str] = []
    for field in _REQUIRED_TEXT_FIELDS:
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            values[field] = value.strip()
        else:
            values[field] = ""
            errors.append(f"缺少有效的 {field}")

    order_sensitive = record.get("order_sensitive", False)
    if not isinstance(order_sensitive, bool):
        errors.append("order_sensitive 必须是布尔值")
        order_sensitive = False

    return EvaluationCase(
        id=values["id"] or f"case-{index}",
        schema_name=values["schema_name"],
        category=values["category"] or "unknown",
        question=values["question"],
        description=values["description"],
        expected_sql=values["expected_sql"],
        order_sensitive=order_sensitive,
        validation_error="；".join(errors) or None,
    )


def _rows_have_expected_width(data: QueryData) -> bool:
    width = len(data.columns)
    return all(len(row) == width for row in data.rows)


def _rows_match(actual: tuple[object, ...], expected: tuple[object, ...]) -> bool:
    return len(actual) == len(expected) and all(
        _values_match(actual_value, expected_value)
        for actual_value, expected_value in zip(actual, expected, strict=True)
    )


def _values_match(actual: object, expected: object) -> bool:
    if actual is None or expected is None:
        return actual is None and expected is None

    actual_is_number = _is_number(actual)
    expected_is_number = _is_number(expected)
    if actual_is_number or expected_is_number:
        if not (actual_is_number and expected_is_number):
            return False
        return _numbers_match(actual, expected)
    return actual == expected


def _is_number(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float, Decimal))


def _numbers_match(actual: object, expected: object) -> bool:
    try:
        actual_decimal = Decimal(str(actual))
        expected_decimal = Decimal(str(expected))
    except (InvalidOperation, ValueError):
        return actual == expected

    if not actual_decimal.is_finite() or not expected_decimal.is_finite():
        return actual_decimal == expected_decimal

    difference = abs(actual_decimal - expected_decimal)
    relative_limit = _TOLERANCE * max(
        abs(actual_decimal),
        abs(expected_decimal),
    )
    return difference <= max(_TOLERANCE, relative_limit)
