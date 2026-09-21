"""Business Analysis 计划解析和确定性校验。"""

from collections.abc import Mapping
from typing import Final

from src.online_query.query_understanding import FilterOperator, TimeGranularity

from .contracts import (
    AnalysisFilter,
    AnalysisPlan,
    AnalysisPlanCandidate,
    AnalysisPlanCannotAnswer,
    AnalysisPlanClarificationRequired,
    AnalysisPlanStructureError,
    AnalysisSemanticCatalog,
    AnalysisTask,
    AnalysisTaskCandidate,
    AnalysisTaskType,
    AnalysisTimeRange,
)


MAX_ANALYSIS_DEPTH = 2
MAX_ANALYSIS_TASKS = 12

_PLAN_FIELDS: Final = frozenset({"tasks"})
_TASK_FIELDS: Final = frozenset(
    {
        "task_id",
        "task_type",
        "description",
        "metrics",
        "dimensions",
        "time_range",
        "filters",
        "depends_on",
        "expected_output",
    }
)
_TIME_FIELDS: Final = frozenset({"text", "granularity"})
_FILTER_FIELDS: Final = frozenset({"field_text", "operator", "values"})


def plan_from_payload(payload: Mapping[str, object]) -> AnalysisPlanCandidate:
    """把 LLM 返回对象转换为严格的 AnalysisPlanCandidate。"""

    if not isinstance(payload, Mapping):
        raise _structure("分析计划必须是 JSON 对象", "PLAN_NOT_OBJECT")
    _require_exact_fields(payload, _PLAN_FIELDS, "分析计划")
    tasks_payload = payload["tasks"]
    if not isinstance(tasks_payload, list) or not tasks_payload:
        raise _structure("tasks 必须是非空数组", "TASKS_INVALID")
    return AnalysisPlanCandidate(
        tasks=tuple(_task_from_payload(item) for item in tasks_payload)
    )


def validate_analysis_plan(
    candidate: AnalysisPlanCandidate,
    catalog: AnalysisSemanticCatalog,
    *,
    max_depth: int = MAX_ANALYSIS_DEPTH,
    max_tasks: int = MAX_ANALYSIS_TASKS,
) -> AnalysisPlan:
    """校验计划边界、业务语义和依赖图，并返回可信计划。"""

    if not isinstance(candidate, AnalysisPlanCandidate):
        raise _cannot_answer("分析计划类型无效", "PLAN_TYPE_INVALID")
    if not isinstance(catalog, AnalysisSemanticCatalog):
        raise _cannot_answer("Semantic Catalog 无效", "CATALOG_INVALID")
    if max_depth < 0 or max_tasks <= 0:
        raise ValueError("分析计划限制必须为正数")
    if len(candidate.tasks) > max_tasks:
        raise _cannot_answer(
            f"分析计划的 Task 数量超过上限 {max_tasks}",
            "TASK_LIMIT_EXCEEDED",
        )

    by_id: dict[str, AnalysisTaskCandidate] = {}
    for task in candidate.tasks:
        if task.task_id in by_id:
            raise _cannot_answer(
                f"Task ID 重复：{task.task_id}",
                "TASK_ID_DUPLICATE",
            )
        by_id[task.task_id] = task

    for task in candidate.tasks:
        if len(set(task.depends_on)) != len(task.depends_on):
            raise _cannot_answer(
                f"Task {task.task_id} 的依赖重复",
                "DEPENDENCY_DUPLICATE",
            )
        for dependency in task.depends_on:
            if dependency not in by_id:
                raise _cannot_answer(
                    f"Task {task.task_id} 依赖不存在：{dependency}",
                    "DEPENDENCY_NOT_FOUND",
                )
            if dependency == task.task_id:
                raise _cannot_answer(
                    f"Task {task.task_id} 不能依赖自身",
                    "DEPENDENCY_SELF_REFERENCE",
                )

    depths: dict[str, int] = {}
    visiting: set[str] = set()

    def depth(task_id: str) -> int:
        if task_id in depths:
            return depths[task_id]
        if task_id in visiting:
            raise _cannot_answer(
                "分析计划存在循环依赖",
                "DEPENDENCY_CYCLE",
            )
        visiting.add(task_id)
        task = by_id[task_id]
        value = max(
            (depth(dependency) + 1 for dependency in task.depends_on),
            default=0,
        )
        visiting.remove(task_id)
        depths[task_id] = value
        return value

    for task_id in by_id:
        task_depth = depth(task_id)
        if task_depth > max_depth:
            raise _cannot_answer(
                f"Task {task_id} 超过最大下钻深度 {max_depth}",
                "DEPTH_LIMIT_EXCEEDED",
            )

    validated_tasks: list[AnalysisTask] = []
    for task in candidate.tasks:
        metrics = tuple(
            _resolve_metric(catalog, metric, task.task_id) for metric in task.metrics
        )
        dimensions = tuple(
            _resolve_dimension(catalog, dimension, task.task_id)
            for dimension in task.dimensions
        )
        validated_tasks.append(
            AnalysisTask(
                task_id=task.task_id,
                task_type=task.task_type,
                description=task.description,
                metrics=metrics,
                dimensions=dimensions,
                time_range=task.time_range,
                filters=task.filters,
                depends_on=task.depends_on,
                expected_output=task.expected_output,
            )
        )
    return AnalysisPlan(tasks=tuple(validated_tasks))


def _task_from_payload(payload: object) -> AnalysisTaskCandidate:
    if not isinstance(payload, Mapping):
        raise _structure("Task 必须是 JSON 对象", "TASK_NOT_OBJECT")
    _require_exact_fields(payload, _TASK_FIELDS, "Task")
    task_type_value = payload["task_type"]
    if not isinstance(task_type_value, str):
        raise _structure("task_type 必须是字符串", "TASK_TYPE_INVALID")
    try:
        task_type = AnalysisTaskType(task_type_value)
    except (TypeError, ValueError):
        raise _structure(
            "task_type 不在 V1 允许范围内",
            "TASK_TYPE_UNSUPPORTED",
        ) from None

    return AnalysisTaskCandidate(
        task_id=_required_text(payload["task_id"], "task_id"),
        task_type=task_type,
        description=_required_text(payload["description"], "description"),
        metrics=_string_list(payload["metrics"], "metrics", allow_empty=False),
        dimensions=_string_list(payload["dimensions"], "dimensions"),
        time_range=_time_range(payload["time_range"]),
        filters=_filters(payload["filters"]),
        depends_on=_string_list(payload["depends_on"], "depends_on"),
        expected_output=_required_text(
            payload["expected_output"],
            "expected_output",
        ),
    )


def _time_range(value: object) -> AnalysisTimeRange | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise _structure("time_range 必须是对象或 null", "TIME_RANGE_INVALID")
    _require_exact_fields(value, _TIME_FIELDS, "time_range")
    try:
        granularity = TimeGranularity(value["granularity"])
    except (KeyError, TypeError, ValueError):
        raise _structure(
            "time_range.granularity 无效",
            "TIME_GRANULARITY_INVALID",
        ) from None
    return AnalysisTimeRange(
        text=_required_text(value["text"], "time_range.text"),
        granularity=granularity,
    )


def _filters(value: object) -> tuple[AnalysisFilter, ...]:
    if not isinstance(value, list):
        raise _structure("filters 必须是数组", "FILTERS_INVALID")
    result: list[AnalysisFilter] = []
    for index, item in enumerate(value, 1):
        if not isinstance(item, Mapping):
            raise _structure(
                f"第 {index} 个 filter 必须是对象",
                "FILTER_INVALID",
            )
        _require_exact_fields(item, _FILTER_FIELDS, f"第 {index} 个 filter")
        try:
            operator = FilterOperator(item["operator"])
        except (KeyError, TypeError, ValueError):
            raise _structure(
                f"第 {index} 个 filter 的 operator 无效",
                "FILTER_OPERATOR_INVALID",
            ) from None
        values = _string_list(item["values"], f"第 {index} 个 filter.values")
        if not values:
            raise _structure(
                f"第 {index} 个 filter 的 values 不能为空",
                "FILTER_VALUES_EMPTY",
            )
        if operator is not FilterOperator.IN and len(values) != 1:
            raise _structure(
                f"第 {index} 个 filter 的 values 数量无效",
                "FILTER_VALUE_CARDINALITY_INVALID",
            )
        result.append(
            AnalysisFilter(
                field_text=_required_text(
                    item["field_text"],
                    f"第 {index} 个 filter.field_text",
                ),
                operator=operator,
                values=values,
            )
        )
    return tuple(result)


def _resolve_metric(
    catalog: AnalysisSemanticCatalog,
    value: str,
    task_id: str,
) -> str:
    matches = catalog.metric_matches.get(_lookup_key(value), frozenset())
    if len(matches) != 1:
        raise AnalysisPlanClarificationRequired(
            f"Task {task_id} 的指标无法唯一确定：{value}",
            reason="METRIC_NOT_UNIQUE",
        )
    return next(iter(matches))


def _resolve_dimension(
    catalog: AnalysisSemanticCatalog,
    value: str,
    task_id: str,
) -> str:
    matches = catalog.dimension_matches.get(_lookup_key(value), frozenset())
    if len(matches) != 1:
        raise AnalysisPlanCannotAnswer(
            f"Task {task_id} 的维度未登记：{value}",
            reason="DIMENSION_NOT_FOUND",
        )
    return next(iter(matches))


def _lookup_key(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _structure(f"{field} 必须是非空字符串", "TEXT_REQUIRED")
    return value.strip()


def _string_list(
    value: object,
    field: str,
    *,
    allow_empty: bool = True,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise _structure(f"{field} 必须是字符串数组", "STRING_LIST_INVALID")
    result = tuple(_required_text(item, field) for item in value)
    if not allow_empty and not result:
        raise _structure(f"{field} 不能为空", "STRING_LIST_EMPTY")
    if len(set(result)) != len(result):
        raise _structure(f"{field} 不能包含重复值", "STRING_LIST_DUPLICATE")
    return result


def _require_exact_fields(
    payload: Mapping[str, object],
    expected: frozenset[str],
    label: str,
) -> None:
    fields = set(payload)
    missing = expected - fields
    extra = fields - expected
    if missing:
        raise _structure(
            f"{label} 缺少字段：{'、'.join(sorted(missing))}",
            "FIELD_MISSING",
        )
    if extra:
        raise _structure(
            f"{label} 包含未允许字段：{'、'.join(sorted(extra))}",
            "FIELD_EXTRA",
        )


def _structure(message: str, reason: str) -> AnalysisPlanStructureError:
    return AnalysisPlanStructureError(message, reason=reason)


def _cannot_answer(message: str, reason: str) -> AnalysisPlanCannotAnswer:
    return AnalysisPlanCannotAnswer(message, reason=reason)
