"""Business Analysis V1 的确定性 AI Evaluation（AI 评测）辅助。"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from src.business_analysis.contracts import AnalysisTaskType


class BusinessAnalysisEvaluationLoadError(RuntimeError):
    """经营分析标准案例无法加载。"""


@dataclass(frozen=True, slots=True)
class BusinessAnalysisExpectedTask:
    """黄金案例中的一个标准 Task。"""

    key: str
    task_type: AnalysisTaskType
    metrics: tuple[str, ...]
    dimensions: tuple[str, ...]
    depends_on: tuple[str, ...]
    expected_sql: str
    order_sensitive: bool = False
    period: str = ""


@dataclass(frozen=True, slots=True)
class BusinessAnalysisCase:
    case_id: str
    question: str
    expected_outcome: str
    min_tasks: int
    required_task_types: tuple[AnalysisTaskType, ...]
    required_metrics: tuple[str, ...]
    required_dimensions: tuple[str, ...]
    expected_tasks: tuple[BusinessAnalysisExpectedTask, ...] = ()
    required_evidence_tasks: tuple[str, ...] = ()
    expected_incomplete_tasks: tuple[str, ...] = ()
    metric_name: str = ""
    comparison_period: str = ""
    current_period: str = ""
    expected_direction: str = ""
    expected_change: str = ""


def load_business_analysis_cases(path: Path) -> tuple[BusinessAnalysisCase, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BusinessAnalysisEvaluationLoadError("经营分析案例无法加载") from exc
    if not isinstance(payload, list) or not payload:
        raise BusinessAnalysisEvaluationLoadError("经营分析案例必须是非空数组")

    result: list[BusinessAnalysisCase] = []
    seen_ids: set[str] = set()
    for item in payload:
        if not isinstance(item, Mapping):
            raise BusinessAnalysisEvaluationLoadError("经营分析案例结构无效")
        expected = item.get("expected")
        if not isinstance(expected, Mapping):
            raise BusinessAnalysisEvaluationLoadError("经营分析案例缺少 expected")
        case_id = _required_text(item.get("id"), "id")
        if case_id in seen_ids:
            raise BusinessAnalysisEvaluationLoadError("经营分析案例 ID 重复")
        seen_ids.add(case_id)
        outcome = _required_text(expected.get("outcome"), "expected.outcome")
        if outcome not in {"plan", "clarification_required"}:
            raise BusinessAnalysisEvaluationLoadError("经营分析案例 outcome 无效")
        min_tasks = expected.get("min_tasks", 0)
        if not isinstance(min_tasks, int) or min_tasks < 0:
            raise BusinessAnalysisEvaluationLoadError("经营分析案例 min_tasks 无效")
        expected_tasks = _expected_tasks(expected.get("tasks", []))
        required_evidence_tasks = _text_list(
            _report_field(expected, "required_evidence_tasks", []),
            "expected.report.required_evidence_tasks",
        )
        expected_incomplete_tasks = _text_list(
            _report_field(expected, "expected_incomplete_tasks", []),
            "expected.report.expected_incomplete_tasks",
        )
        _validate_report_task_references(
            expected_tasks,
            required_evidence_tasks,
            expected_incomplete_tasks,
        )
        result.append(
            BusinessAnalysisCase(
                case_id=case_id,
                question=_required_text(item.get("question"), "question"),
                expected_outcome=outcome,
                min_tasks=min_tasks,
                required_task_types=_task_types(
                    expected.get("required_task_types", [])
                ),
                required_metrics=_text_list(
                    expected.get("required_metrics", []),
                    "expected.required_metrics",
                ),
                required_dimensions=_text_list(
                    expected.get("required_dimensions", []),
                    "expected.required_dimensions",
                ),
                expected_tasks=expected_tasks,
                required_evidence_tasks=required_evidence_tasks,
                expected_incomplete_tasks=expected_incomplete_tasks,
                metric_name=_optional_text(expected.get("metric_name")),
                comparison_period=_optional_text(expected.get("comparison_period")),
                current_period=_optional_text(expected.get("current_period")),
                expected_direction=_optional_text(expected.get("expected_direction")),
                expected_change=_optional_numeric_text(expected.get("expected_change")),
            )
        )
    return tuple(result)


def _task_types(value: object) -> tuple[AnalysisTaskType, ...]:
    if not isinstance(value, list):
        raise BusinessAnalysisEvaluationLoadError("required_task_types 必须是数组")
    try:
        return tuple(AnalysisTaskType(item) for item in value)
    except (TypeError, ValueError):
        raise BusinessAnalysisEvaluationLoadError("required_task_types 无效") from None


def _expected_tasks(value: object) -> tuple[BusinessAnalysisExpectedTask, ...]:
    if not isinstance(value, list):
        raise BusinessAnalysisEvaluationLoadError("expected.tasks 必须是数组")
    result: list[BusinessAnalysisExpectedTask] = []
    keys: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            raise BusinessAnalysisEvaluationLoadError("expected.tasks 结构无效")
        key = _required_text(item.get("key"), "expected.tasks.key")
        if key in keys:
            raise BusinessAnalysisEvaluationLoadError("expected.tasks.key 重复")
        keys.add(key)
        try:
            task_type = AnalysisTaskType(item.get("task_type"))
        except (TypeError, ValueError):
            raise BusinessAnalysisEvaluationLoadError(
                "expected.tasks.task_type 无效"
            ) from None
        expected_sql = _required_text(
            item.get("expected_sql"),
            "expected.tasks.expected_sql",
        )
        order_sensitive = item.get("order_sensitive", False)
        if not isinstance(order_sensitive, bool):
            raise BusinessAnalysisEvaluationLoadError(
                "expected.tasks.order_sensitive 必须是布尔值"
            )
        result.append(
            BusinessAnalysisExpectedTask(
                key=key,
                task_type=task_type,
                metrics=_text_list(item.get("metrics", []), "expected.tasks.metrics"),
                dimensions=_text_list(
                    item.get("dimensions", []),
                    "expected.tasks.dimensions",
                ),
                depends_on=_text_list(
                    item.get("depends_on", []),
                    "expected.tasks.depends_on",
                ),
                expected_sql=expected_sql,
                order_sensitive=order_sensitive,
                period=_optional_text(item.get("period")),
            )
        )
    key_set = {item.key for item in result}
    if any(
        dependency not in key_set for item in result for dependency in item.depends_on
    ):
        raise BusinessAnalysisEvaluationLoadError(
            "expected.tasks.depends_on 引用了不存在的 Task"
        )
    return tuple(result)


def _report_field(
    expected: Mapping[str, object], field: str, default: object
) -> object:
    report = expected.get("report", {})
    if report is None:
        return default
    if not isinstance(report, Mapping):
        raise BusinessAnalysisEvaluationLoadError("expected.report 必须是对象")
    return report.get(field, default)


def _validate_report_task_references(
    expected_tasks: tuple[BusinessAnalysisExpectedTask, ...],
    required_evidence_tasks: tuple[str, ...],
    expected_incomplete_tasks: tuple[str, ...],
) -> None:
    task_keys = {task.key for task in expected_tasks}
    references = (*required_evidence_tasks, *expected_incomplete_tasks)
    if any(reference not in task_keys for reference in references):
        raise BusinessAnalysisEvaluationLoadError("expected.report 引用了不存在的 Task")


def _text_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise BusinessAnalysisEvaluationLoadError(f"{field} 必须是字符串数组")
    return tuple(item.strip() for item in value)


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BusinessAnalysisEvaluationLoadError(f"{field} 必须是非空字符串")
    return value.strip()


def _optional_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _optional_numeric_text(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return ""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise BusinessAnalysisEvaluationLoadError(
            "expected_change 必须是有效数字"
        ) from None
    if not number.is_finite():
        raise BusinessAnalysisEvaluationLoadError("expected_change 必须是有限数字")
    return str(number)
