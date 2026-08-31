"""顺序运行标准案例并汇总 Execution Accuracy（执行准确率）。"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from time import perf_counter

from src.online_query.contracts import (
    QueryContext,
    QueryData,
    QueryExecutor,
    QueryFailure,
    QueryRequest,
    QuerySuccess,
)
from src.online_query.service import OnlineQueryService
from src.online_query.sql_guard import validate_sql

from .evaluator import EvaluationCase, results_match


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
    service: OnlineQueryService,
    query_executor: QueryExecutor,
    context: QueryContext,
) -> EvaluationRun:
    """逐条运行评测；单条失败不会中断后续案例。"""

    evaluations: list[CaseEvaluation] = []
    reference_results: dict[str, QueryData] = {}

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

        started = perf_counter()
        try:
            result = service.query(
                QueryRequest(
                    question=case.question,
                    request_id=f"evaluation-{case.id}",
                )
            )
        except Exception:
            duration_ms = _duration_ms(started)
            evaluations.append(
                _failed(case, "Online Query 调用失败", duration_ms=duration_ms)
            )
            continue
        duration_ms = _duration_ms(started)

        if isinstance(result, QueryFailure):
            evaluations.append(
                _failed(
                    case,
                    result.error_message,
                    query_error_code=result.error_code.value,
                    duration_ms=duration_ms,
                )
            )
            continue

        if not isinstance(result, QuerySuccess):
            evaluations.append(
                _failed(case, "Online Query 返回类型无效", duration_ms=duration_ms)
            )
            continue

        if result.truncated:
            evaluations.append(
                _invalid(
                    case,
                    "系统结果被截断",
                    generated_sql=result.sql,
                    duration_ms=duration_ms,
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
        category_cases = [
            case
            for case in valid
            if case.category == category
        ]
        category_passed = sum(
            case.status == CaseStatus.PASS for case in category_cases
        )
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
) -> CaseEvaluation:
    return CaseEvaluation(
        case_id=case.id,
        category=case.category,
        status=CaseStatus.INVALID_CASE,
        generated_sql=generated_sql,
        query_error_code=None,
        failure_reason=reason,
        duration_ms=duration_ms,
    )


def _failed(
    case: EvaluationCase,
    reason: str,
    *,
    query_error_code: str | None = None,
    duration_ms: int = 0,
) -> CaseEvaluation:
    return CaseEvaluation(
        case_id=case.id,
        category=case.category,
        status=CaseStatus.FAIL,
        generated_sql=None,
        query_error_code=query_error_code,
        failure_reason=reason,
        duration_ms=duration_ms,
    )


def _duration_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))
