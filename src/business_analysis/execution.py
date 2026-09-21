"""Business Analysis Task Semantic Adapter 与 Executor。"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from src.online_query.contracts import (
    QueryFailure,
    QueryRequest,
    QueryResult,
    QuerySuccess,
)
from src.online_query.query_understanding import (
    FilterCandidate,
    QueryType,
    SemanticQueryCandidate,
    SemanticQueryValidationError,
    TimeCandidate,
    ValidatedSemanticQuery,
    validate_candidate,
)

from .contracts import AnalysisPlan, AnalysisTask, AnalysisFilter, AnalysisTimeRange


class TaskSemanticAdapterError(ValueError):
    """Task 不能转换为安全的单次查询。"""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class TaskStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class TaskError:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class TaskResult:
    task_id: str
    status: TaskStatus
    columns: tuple[str, ...] = ()
    rows: tuple[tuple[object, ...], ...] = ()
    row_count: int = 0
    truncated: bool = False
    error: TaskError | None = None


class BoundQueryService(Protocol):
    def query(self, request: QueryRequest) -> QueryResult:
        """使用已经绑定的当前用户身份执行一次查询。"""


class TaskSemanticAdapter:
    def to_query_request(
        self,
        task: AnalysisTask,
        *,
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> QueryRequest:
        if not isinstance(task, AnalysisTask):
            raise TaskSemanticAdapterError(
                "Task 类型无效",
                reason="TASK_TYPE_INVALID",
            )
        question = canonical_task_question(task)
        time = _time_candidate(task.time_range)
        filters = tuple(_filter_candidate(item) for item in task.filters)
        try:
            semantic_query = validate_candidate(
                _candidate(
                    task,
                    time=time,
                    filters=filters,
                ),
                original_question=question,
                now=now,
            )
        except SemanticQueryValidationError as exc:
            raise TaskSemanticAdapterError(
                "Task 语义校验失败",
                reason=exc.reason,
            ) from exc
        if not isinstance(semantic_query, ValidatedSemanticQuery):
            raise TaskSemanticAdapterError(
                "Task 语义校验未返回有效结果",
                reason="SEMANTIC_RESULT_INVALID",
            )
        return QueryRequest(
            question=question,
            request_id=request_id,
            semantic_query=semantic_query,
        )


class TaskExecutor:
    def __init__(
        self,
        query_service: BoundQueryService,
        adapter: TaskSemanticAdapter,
    ) -> None:
        self._query_service = query_service
        self._adapter = adapter

    def execute(
        self,
        plan: AnalysisPlan,
        *,
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> tuple[TaskResult, ...]:
        if not isinstance(plan, AnalysisPlan):
            raise ValueError("分析计划类型无效")

        pending = list(plan.tasks)
        results: dict[str, TaskResult] = {}
        while pending:
            progressed = False
            next_pending: list[AnalysisTask] = []
            for task in pending:
                if any(dependency not in results for dependency in task.depends_on):
                    next_pending.append(task)
                    continue

                progressed = True
                dependency_results = [results[item] for item in task.depends_on]
                if any(
                    result.status is not TaskStatus.COMPLETED
                    for result in dependency_results
                ):
                    result = TaskResult(
                        task_id=task.task_id,
                        status=TaskStatus.SKIPPED,
                        error=TaskError(
                            code="DEPENDENCY_FAILED",
                            message="依赖 Task 未成功完成",
                        ),
                    )
                else:
                    result = self._execute_task(
                        task,
                        request_id=request_id,
                        now=now,
                    )
                results[task.task_id] = result

            if not progressed:
                raise RuntimeError("分析计划依赖图无法推进")
            pending = next_pending

        return tuple(results[task.task_id] for task in plan.tasks)

    def _execute_task(
        self,
        task: AnalysisTask,
        *,
        request_id: str | None,
        now: datetime | None,
    ) -> TaskResult:
        try:
            request = self._adapter.to_query_request(
                task,
                request_id=_task_request_id(request_id, task.task_id),
                now=now,
            )
        except TaskSemanticAdapterError:
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=TaskError(
                    code="TASK_SEMANTIC_INVALID",
                    message="Task 语义无法安全校验",
                ),
            )
        except Exception:
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=TaskError(
                    code="TASK_ADAPTER_ERROR",
                    message="Task 适配失败",
                ),
            )

        try:
            result = self._query_service.query(request)
        except Exception:
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=TaskError(
                    code="TASK_EXECUTION_ERROR",
                    message="Task 查询执行失败",
                ),
            )
        if isinstance(result, QuerySuccess):
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                columns=tuple(result.columns),
                rows=tuple(tuple(row) for row in result.rows),
                row_count=result.row_count,
                truncated=result.truncated,
            )
        if isinstance(result, QueryFailure):
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=TaskError(
                    code=str(result.error_code.value),
                    message=str(result.error_message),
                ),
            )
        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.FAILED,
            error=TaskError(
                code="TASK_RESULT_INVALID",
                message="Task 查询返回无效结果",
            ),
        )


def canonical_task_question(task: AnalysisTask) -> str:
    """把完整 Task 转换为稳定、无物理资源的查询文本。"""

    metrics = "、".join(task.metrics) if task.metrics else "无"
    dimensions = "、".join(task.dimensions) if task.dimensions else "无"
    time_range = _canonical_time_range(task.time_range)
    filters = "、".join(_canonical_filter(item) for item in task.filters) or "无"
    return f"指标={metrics}；维度={dimensions}；时间={time_range}；筛选={filters}"


def _candidate(
    task: AnalysisTask,
    *,
    time: TimeCandidate | None,
    filters: tuple[FilterCandidate, ...],
) -> SemanticQueryCandidate:
    return SemanticQueryCandidate(
        query_type=QueryType.METRIC_ANALYSIS,
        subjects=(),
        metrics=task.metrics,
        dimensions=task.dimensions,
        time=time,
        filters=filters,
    )


def _time_candidate(time_range: AnalysisTimeRange | None) -> TimeCandidate | None:
    if time_range is None:
        return None
    return TimeCandidate(
        text=time_range.text,
        granularity=time_range.granularity,
    )


def _filter_candidate(item: AnalysisFilter) -> FilterCandidate:
    return FilterCandidate(
        field_text=item.field_text,
        operator=item.operator,
        values=item.values,
    )


def _canonical_time_range(time_range: AnalysisTimeRange | None) -> str:
    if time_range is None:
        return "无"
    return f"{time_range.text}({time_range.granularity.value})"


def _canonical_filter(item: AnalysisFilter) -> str:
    values = ",".join(item.values)
    return f"{item.field_text}{item.operator.value}{values}"


def _task_request_id(request_id: str | None, task_id: str) -> str:
    if isinstance(request_id, str) and request_id.strip():
        return f"{request_id.strip()}:{task_id}"
    return task_id
