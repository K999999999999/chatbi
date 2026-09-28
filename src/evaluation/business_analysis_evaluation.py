"""经营分析 Evaluation（评测）案例加载与结构校验。"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class BusinessAnalysisEvaluationLoadError(RuntimeError):
    """经营分析标准案例无法加载。"""


@dataclass(frozen=True, slots=True)
class BusinessAnalysisExpectedTask:
    key: str
    purpose: str
    period: str
    metrics: tuple[str, ...]
    dimension: str


@dataclass(frozen=True, slots=True)
class BusinessAnalysisCase:
    case_id: str
    question: str
    expected_outcome: str
    expected_task_count: int
    expected_tasks: tuple[BusinessAnalysisExpectedTask, ...]
    evaluation_rules: Mapping[str, object]
    error_code: str | None = None


def load_business_analysis_cases(
    path: Path,
) -> tuple[BusinessAnalysisCase, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BusinessAnalysisEvaluationLoadError("经营分析案例无法加载") from exc
    if not isinstance(payload, Mapping):
        raise BusinessAnalysisEvaluationLoadError("经营分析案例必须是对象")
    cases = payload.get("cases")
    rules = payload.get("evaluation_rules")
    if not isinstance(cases, list) or not cases:
        raise BusinessAnalysisEvaluationLoadError("经营分析 cases 必须是非空数组")
    if not isinstance(rules, Mapping):
        raise BusinessAnalysisEvaluationLoadError("经营分析案例缺少 evaluation_rules")
    _validate_rules(rules)

    result: list[BusinessAnalysisCase] = []
    seen_ids: set[str] = set()
    for item in cases:
        if not isinstance(item, Mapping):
            raise BusinessAnalysisEvaluationLoadError("经营分析案例结构无效")
        case_id = _required_text(item.get("id"), "id")
        if case_id in seen_ids:
            raise BusinessAnalysisEvaluationLoadError("经营分析案例 ID 重复")
        seen_ids.add(case_id)
        outcome = _required_text(item.get("expected_outcome"), "expected_outcome")
        if outcome not in {"success", "clarification_required", "cannot_answer"}:
            raise BusinessAnalysisEvaluationLoadError("经营分析案例 outcome 无效")
        task_count = item.get("expected_task_count")
        if (
            not isinstance(task_count, int)
            or isinstance(task_count, bool)
            or task_count < 0
        ):
            raise BusinessAnalysisEvaluationLoadError("expected_task_count 无效")
        tasks = _expected_tasks(item.get("expected_tasks"))
        if task_count != len(tasks):
            raise BusinessAnalysisEvaluationLoadError(
                "expected_task_count 与 expected_tasks 数量不一致"
            )
        error_code = item.get("error_code")
        if outcome == "success" and error_code is not None:
            raise BusinessAnalysisEvaluationLoadError("success 案例不能设置 error_code")
        if outcome != "success" and not isinstance(error_code, str):
            raise BusinessAnalysisEvaluationLoadError(
                "拒绝或澄清案例必须设置 error_code"
            )
        expected_error = {
            "clarification_required": "CLARIFICATION_REQUIRED",
            "cannot_answer": "CANNOT_ANSWER",
        }.get(outcome)
        if expected_error is not None and error_code != expected_error:
            raise BusinessAnalysisEvaluationLoadError(
                "案例 error_code 与 outcome 不一致"
            )
        if outcome != "success" and task_count != 0:
            raise BusinessAnalysisEvaluationLoadError("拒绝或澄清案例的任务数必须为 0")
        if outcome == "success" and task_count == 0:
            raise BusinessAnalysisEvaluationLoadError(
                "success 案例必须至少有一个预期 Task"
            )
        result.append(
            BusinessAnalysisCase(
                case_id=case_id,
                question=_required_text(item.get("question"), "question"),
                expected_outcome=outcome,
                expected_task_count=task_count,
                expected_tasks=tasks,
                evaluation_rules=rules,
                error_code=error_code,
            )
        )
    return tuple(result)


def _expected_tasks(value: object) -> tuple[BusinessAnalysisExpectedTask, ...]:
    if not isinstance(value, list):
        raise BusinessAnalysisEvaluationLoadError("expected_tasks 必须是数组")
    result: list[BusinessAnalysisExpectedTask] = []
    keys: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            raise BusinessAnalysisEvaluationLoadError("expected_tasks 结构无效")
        key = _required_text(item.get("key"), "expected_tasks.key")
        if key in keys:
            raise BusinessAnalysisEvaluationLoadError("expected_tasks.key 重复")
        keys.add(key)
        metrics = item.get("metrics")
        if not isinstance(metrics, list) or not metrics:
            raise BusinessAnalysisEvaluationLoadError("expected_tasks.metrics 无效")
        result.append(
            BusinessAnalysisExpectedTask(
                key=key,
                purpose=_required_text(item.get("purpose"), "expected_tasks.purpose"),
                period=_required_text(item.get("period"), "expected_tasks.period"),
                metrics=tuple(
                    _required_text(metric, "expected_tasks.metrics")
                    for metric in metrics
                ),
                dimension=_required_text(
                    item.get("dimension"), "expected_tasks.dimension"
                ),
            )
        )
    return tuple(result)


def _validate_rules(rules: Mapping[str, object]) -> None:
    for outcome, dimensions in (
        ("success", ("plan", "summary")),
        ("clarification_required", ("plan",)),
        ("cannot_answer", ("plan",)),
    ):
        outcome_rules = rules.get(outcome)
        for dimension in dimensions:
            section = (
                outcome_rules.get(dimension)
                if isinstance(outcome_rules, Mapping)
                else None
            )
            if not isinstance(section, Mapping):
                raise BusinessAnalysisEvaluationLoadError(
                    f"evaluation_rules.{outcome}.{dimension} 必须是对象"
                )
            for field in ("judge", "pass"):
                value = section.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise BusinessAnalysisEvaluationLoadError(
                        f"evaluation_rules.{outcome}.{dimension}.{field} 必须是非空字符串"
                    )


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BusinessAnalysisEvaluationLoadError(f"{field} 必须是非空字符串")
    return value.strip()
