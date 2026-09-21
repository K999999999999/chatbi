"""Business Analysis V1 的确定性 AI Evaluation（AI 评测）辅助。"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from src.business_analysis.contracts import (
    AnalysisDecompositionContext,
    AnalysisPlanCandidate,
    AnalysisPlanClarificationRequired,
    AnalysisSemanticCatalog,
    AnalysisTaskType,
)
from src.business_analysis.decomposer import AnalysisPlanDecomposer
from src.business_analysis.planning import validate_analysis_plan


class BusinessAnalysisEvaluationLoadError(RuntimeError):
    """经营分析标准案例无法加载。"""


@dataclass(frozen=True, slots=True)
class BusinessAnalysisCase:
    case_id: str
    question: str
    expected_outcome: str
    min_tasks: int
    required_task_types: tuple[AnalysisTaskType, ...]
    required_metrics: tuple[str, ...]
    required_dimensions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BusinessAnalysisEvaluation:
    case_id: str
    passed: bool
    failure_reason: str | None = None
    reason_code: str | None = None


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
            )
        )
    return tuple(result)


def evaluate_business_analysis_plans(
    cases: Sequence[BusinessAnalysisCase],
    decomposer: AnalysisPlanDecomposer,
    context: AnalysisDecompositionContext,
    catalog: AnalysisSemanticCatalog,
) -> tuple[BusinessAnalysisEvaluation, ...]:
    """比较模型拆解结果与业务期望，不暴露模型原始输出。"""

    results: list[BusinessAnalysisEvaluation] = []
    for case in cases:
        try:
            candidate = decomposer.decompose(case.question, context)
            if case.expected_outcome == "clarification_required":
                validate_analysis_plan(candidate, catalog)
                results.append(
                    _failed(case, "歧义指标未触发澄清", "EXPECTED_CLARIFICATION")
                )
                continue
            plan = validate_analysis_plan(candidate, catalog)
        except AnalysisPlanClarificationRequired:
            if case.expected_outcome == "clarification_required":
                results.append(
                    BusinessAnalysisEvaluation(case_id=case.case_id, passed=True)
                )
            else:
                results.append(
                    _failed(case, "可回答案例意外要求澄清", "UNEXPECTED_CLARIFICATION")
                )
            continue
        except Exception as exc:
            results.append(
                _failed(case, "计划未通过确定性校验", _safe_reason(exc))
            )
            continue

        task_types = {task.task_type for task in plan.tasks}
        metrics = {metric for task in plan.tasks for metric in task.metrics}
        dimensions = {dimension for task in plan.tasks for dimension in task.dimensions}
        missing_types = set(case.required_task_types) - task_types
        missing_metrics = set(case.required_metrics) - metrics
        missing_dimensions = set(case.required_dimensions) - dimensions
        if len(plan.tasks) < case.min_tasks:
            results.append(_failed(case, "Task 数量不足", "TASK_COUNT_TOO_LOW"))
        elif missing_types:
            results.append(_failed(case, "缺少期望的 Task 类型", "TASK_TYPE_MISSING"))
        elif missing_metrics:
            results.append(_failed(case, "缺少期望的指标", "METRIC_MISSING"))
        elif missing_dimensions:
            results.append(_failed(case, "缺少期望的维度", "DIMENSION_MISSING"))
        else:
            results.append(BusinessAnalysisEvaluation(case_id=case.case_id, passed=True))
    return tuple(results)


def _task_types(value: object) -> tuple[AnalysisTaskType, ...]:
    if not isinstance(value, list):
        raise BusinessAnalysisEvaluationLoadError("required_task_types 必须是数组")
    try:
        return tuple(AnalysisTaskType(item) for item in value)
    except (TypeError, ValueError):
        raise BusinessAnalysisEvaluationLoadError("required_task_types 无效") from None


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


def _failed(
    case: BusinessAnalysisCase,
    message: str,
    reason: str,
) -> BusinessAnalysisEvaluation:
    return BusinessAnalysisEvaluation(
        case_id=case.case_id,
        passed=False,
        failure_reason=message,
        reason_code=reason,
    )


def _safe_reason(error: Exception) -> str:
    reason = getattr(error, "reason", None)
    return reason if isinstance(reason, str) and reason else type(error).__name__
