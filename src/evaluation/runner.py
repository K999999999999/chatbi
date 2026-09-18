"""顺序运行标准案例并汇总 Execution Accuracy（执行准确率）。"""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
import re
from time import perf_counter
from typing import Protocol
from uuid import uuid4

from src.observability.contracts import QuerySource, TraceRecorder
from src.observability.tracing import create_trace_recorder
from src.online_query.contracts import (
    QueryContext,
    QueryData,
    QueryExecutor,
    QueryFailure,
    QueryRequest,
    QueryResult,
    QuerySuccess,
)
from src.online_query.sql_guard import validate_sql

from .evaluator import EvaluationCase, results_match


class EvaluationQueryService(Protocol):
    """Evaluation 使用的已装配 Query Entry。"""

    def query(self, request: QueryRequest) -> QueryResult:
        """执行一次带有显式测试身份的查询。"""


class CaseStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INVALID_CASE = "INVALID_CASE"


@dataclass(frozen=True, slots=True)
class CaseEvaluation:
    case_id: str
    category: str
    status: CaseStatus
    generated_sql: str | None
    query_error_code: str | None
    failure_reason: str | None
    duration_ms: int
    request_id: str | None = None
    trace_id: str | None = None
    failure_stage: str | None = None
    internal_reason: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    total_cases: int
    valid_cases: int
    passed: int
    failed: int
    invalid_cases: int
    execution_accuracy: float | None
    category_accuracy: Mapping[str, float | None]


@dataclass(frozen=True, slots=True)
class EvaluationRun:
    cases: tuple[CaseEvaluation, ...]
    summary: EvaluationSummary
    reference_results: Mapping[str, QueryData]


def run_evaluation(
    cases: tuple[EvaluationCase, ...],
    service: EvaluationQueryService,
    query_executor: QueryExecutor,
    context: QueryContext,
    trace_recorder: TraceRecorder | None = None,
) -> EvaluationRun:
    """逐条运行评测；单条失败不会中断后续案例。"""

    evaluations: list[CaseEvaluation] = []
    reference_results: dict[str, QueryData] = {}
    recorder = _resolve_trace_recorder(trace_recorder)

    for case in cases:
        if not case.is_valid:
            evaluations.append(_invalid(case, case.validation_error or "案例格式错误"))
            continue

        try:
            expected_sql = validate_sql(case.expected_sql, context)
        except Exception:
            evaluations.append(_invalid(case, "标准 SQL 未通过安全校验"))
            continue

        try:
            expected = query_executor.execute(expected_sql)
        except Exception:
            evaluations.append(_invalid(case, "标准 SQL 无法执行"))
            continue

        if expected.truncated:
            evaluations.append(_invalid(case, "标准结果被截断"))
            continue
        reference_results[case.id] = expected

        request_id = f"evaluation-{case.id}"
        started = perf_counter()
        with _evaluation_trace_scope(
            recorder,
            case_id=case.id,
            request_id=request_id,
        ) as trace_id:
            try:
                result = service.query(
                    QueryRequest(
                        question=case.question,
                        request_id=request_id,
                    )
                )
            except Exception:
                duration_ms = _duration_ms(started)
                evaluations.append(
                    _failed(
                        case,
                        "Online Query 调用失败",
                        duration_ms=duration_ms,
                        request_id=request_id,
                        trace_id=trace_id,
                    )
                )
                continue
            duration_ms = _duration_ms(started)

            if isinstance(result, QueryFailure):
                evaluations.append(
                    _failed(
                        case,
                        result.error_message,
                        query_error_code=result.error_code.value,
                        failure_stage=result.failure_stage,
                        internal_reason=result.internal_reason,
                        duration_ms=duration_ms,
                        request_id=request_id,
                        trace_id=trace_id,
                    )
                )
                continue

            if not isinstance(result, QuerySuccess):
                evaluations.append(
                    _failed(
                        case,
                        "Online Query 返回类型无效",
                        duration_ms=duration_ms,
                        request_id=request_id,
                        trace_id=trace_id,
                    )
                )
                continue

            if result.truncated:
                evaluations.append(
                    _invalid(
                        case,
                        "系统结果被截断",
                        generated_sql=result.sql,
                        duration_ms=duration_ms,
                        request_id=request_id,
                        trace_id=trace_id,
                    )
                )
                continue

            actual = QueryData(
                columns=result.columns,
                rows=result.rows,
                truncated=result.truncated,
            )
            matched = results_match(
                actual,
                expected,
                order_sensitive=case.order_sensitive,
            )
            evaluations.append(
                CaseEvaluation(
                    case_id=case.id,
                    category=case.category,
                    status=CaseStatus.PASS if matched else CaseStatus.FAIL,
                    generated_sql=result.sql,
                    query_error_code=None,
                    failure_reason=None if matched else "结果不一致",
                    duration_ms=duration_ms,
                    request_id=request_id,
                    trace_id=trace_id,
                )
            )

    results = tuple(evaluations)
    return EvaluationRun(
        cases=results,
        summary=_summarize(results),
        reference_results=reference_results,
    )


def _summarize(cases: tuple[CaseEvaluation, ...]) -> EvaluationSummary:
    valid = [case for case in cases if case.status != CaseStatus.INVALID_CASE]
    passed = sum(case.status == CaseStatus.PASS for case in valid)
    failed = sum(case.status == CaseStatus.FAIL for case in valid)
    categories = sorted({case.category for case in cases})
    category_accuracy: dict[str, float | None] = {}
    for category in categories:
        category_cases = [case for case in valid if case.category == category]
        category_passed = sum(case.status == CaseStatus.PASS for case in category_cases)
        category_accuracy[category] = (
            category_passed / len(category_cases) if category_cases else None
        )

    return EvaluationSummary(
        total_cases=len(cases),
        valid_cases=len(valid),
        passed=passed,
        failed=failed,
        invalid_cases=len(cases) - len(valid),
        execution_accuracy=passed / len(valid) if valid else None,
        category_accuracy=category_accuracy,
    )


def _invalid(
    case: EvaluationCase,
    reason: str,
    *,
    generated_sql: str | None = None,
    duration_ms: int = 0,
    request_id: str | None = None,
    trace_id: str | None = None,
) -> CaseEvaluation:
    return CaseEvaluation(
        case_id=case.id,
        category=case.category,
        status=CaseStatus.INVALID_CASE,
        generated_sql=generated_sql,
        query_error_code=None,
        failure_reason=reason,
        duration_ms=duration_ms,
        request_id=request_id,
        trace_id=trace_id,
    )


def _failed(
    case: EvaluationCase,
    reason: str,
    *,
    query_error_code: str | None = None,
    failure_stage: str | None = None,
    internal_reason: str | None = None,
    duration_ms: int = 0,
    request_id: str | None = None,
    trace_id: str | None = None,
) -> CaseEvaluation:
    return CaseEvaluation(
        case_id=case.id,
        category=case.category,
        status=CaseStatus.FAIL,
        generated_sql=None,
        query_error_code=query_error_code,
        failure_reason=reason,
        duration_ms=duration_ms,
        request_id=request_id,
        trace_id=trace_id,
        failure_stage=failure_stage,
        internal_reason=internal_reason,
    )


def _duration_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


_TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _resolve_trace_recorder(
    trace_recorder: TraceRecorder | None,
) -> TraceRecorder | None:
    if trace_recorder is not None:
        return trace_recorder
    try:
        return create_trace_recorder()
    except Exception:
        # Trace 是旁路能力；即使初始化异常，也必须继续跑完评测。
        return None


@contextmanager
def _evaluation_trace_scope(
    recorder: TraceRecorder | None,
    *,
    case_id: str,
    request_id: str,
) -> Iterator[str]:
    """创建 Evaluation 拥有的 Root；Recorder 失败时退化为合法本地 Trace ID。"""

    fallback_trace_id = _new_trace_id()
    scope: object | None = None
    if recorder is not None:
        try:
            scope = recorder.query_trace(
                QuerySource.EVALUATION,
                attributes={
                    "evaluation.case_id": case_id,
                    "chatbi.request.id": request_id,
                },
            )
        except Exception:
            scope = None

    if scope is None:
        scope = _EvaluationNoopScope(fallback_trace_id)

    entered = False
    try:
        try:
            entered_scope = scope.__enter__()  # type: ignore[attr-defined]
            entered = True
        except Exception:
            scope = _EvaluationNoopScope(fallback_trace_id)
            scope.__enter__()
            entered = True
            entered_scope = scope

        trace_id = _trace_id_from_scope(entered_scope, fallback_trace_id)
        yield trace_id
    finally:
        if entered:
            try:
                scope.__exit__(None, None, None)  # type: ignore[attr-defined]
            except Exception:
                pass


class _EvaluationNoopScope:
    def __init__(self, trace_id: str) -> None:
        self.trace_id = trace_id

    @property
    def owns_root(self) -> bool:
        return True

    def __enter__(self) -> "_EvaluationNoopScope":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        return False


def _trace_id_from_scope(scope: object, fallback: str) -> str:
    try:
        trace_id = getattr(scope, "trace_id")
    except Exception:
        return fallback
    if (
        isinstance(trace_id, str)
        and _TRACE_ID_RE.fullmatch(trace_id)
        and int(trace_id, 16) != 0
    ):
        return trace_id
    return fallback


def _new_trace_id() -> str:
    trace_id = uuid4().hex
    return trace_id if int(trace_id, 16) != 0 else "0" * 31 + "1"
