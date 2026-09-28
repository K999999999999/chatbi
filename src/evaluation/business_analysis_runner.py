"""经营分析黄金测试集的确定性 Runner。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from time import perf_counter
from typing import Protocol
from uuid import uuid4

from src.authorization.contracts import AuthContext
from src.business_analysis.application import (
    BusinessAnalysisApplication,
    BusinessAnalysisSuccess,
)
from src.business_analysis.attribution import BusinessAnalysisAttribution
from src.business_analysis.contracts import AnalysisPlan
from src.online_query.contracts import (
    QueryContext,
    QueryData,
    QueryExecutor,
    QueryFailure,
)
from src.online_query.sql_guard import validate_sql

from .business_analysis_evaluation import (
    BusinessAnalysisCase,
    BusinessAnalysisExpectedTask,
)
from .evaluator import results_match


class BusinessAnalysisCaseStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INVALID_CASE = "INVALID_CASE"


class BusinessAnalysisJudge(Protocol):
    def evaluate(
        self,
        question: str,
        result: BusinessAnalysisSuccess,
    ) -> object:
        """检查总结文本是否忠实于程序归因和查询证据。"""


@dataclass(frozen=True, slots=True)
class BusinessAnalysisTaskEvaluation:
    task_key: str
    status: BusinessAnalysisCaseStatus
    actual_task_id: str | None = None
    failure_reason: str | None = None


@dataclass(frozen=True, slots=True)
class BusinessAnalysisCaseEvaluation:
    case_id: str
    status: BusinessAnalysisCaseStatus
    plan_passed: bool | None
    task_passed: bool | None
    report_passed: bool | None
    failure_reason: str | None = None
    reason_code: str | None = None
    query_error_code: str | None = None
    internal_reason: str | None = None
    duration_ms: int = 0
    task_evaluations: tuple[BusinessAnalysisTaskEvaluation, ...] = ()
    attribution_passed: bool | None = None
    direction: str | None = None
    change: str | None = None
    judge_passed: bool | None = None
    judge_reason: str | None = None


@dataclass(frozen=True, slots=True)
class BusinessAnalysisEvaluationSummary:
    total_cases: int
    valid_cases: int
    passed: int
    failed: int
    invalid_cases: int
    plan_accuracy: float | None
    task_execution_accuracy: float | None
    report_grounded_accuracy: float | None
    attribution_accuracy: float | None
    summary_judge_accuracy: float | None
    end_to_end_accuracy: float | None


@dataclass(frozen=True, slots=True)
class BusinessAnalysisEvaluationRun:
    cases: tuple[BusinessAnalysisCaseEvaluation, ...]
    summary: BusinessAnalysisEvaluationSummary
    reference_results: Mapping[str, QueryData]


def run_business_analysis_evaluation(
    cases: Sequence[BusinessAnalysisCase],
    application: BusinessAnalysisApplication,
    query_executor: QueryExecutor,
    context: QueryContext,
    auth_context: AuthContext,
    judge: BusinessAnalysisJudge | None = None,
) -> BusinessAnalysisEvaluationRun:
    """运行经营分析黄金案例；每条案例独立计分。"""

    evaluations: list[BusinessAnalysisCaseEvaluation] = []
    reference_results: dict[str, QueryData] = {}
    for case in cases:
        started = perf_counter()
        try:
            references = _load_reference_results(case, query_executor, context)
        except _InvalidCase as exc:
            evaluations.append(
                BusinessAnalysisCaseEvaluation(
                    case_id=case.case_id,
                    status=BusinessAnalysisCaseStatus.INVALID_CASE,
                    plan_passed=None,
                    task_passed=None,
                    report_passed=None,
                    failure_reason=str(exc),
                    reason_code=exc.reason_code,
                    duration_ms=_duration_ms(started),
                )
            )
            continue
        reference_results.update(references)

        try:
            result = application.analyze(
                case.question,
                request_id=f"analysis-evaluation-{case.case_id}",
                auth_context=auth_context,
                analysis_run_id=str(uuid4()),
            )
        except Exception:
            evaluations.append(
                BusinessAnalysisCaseEvaluation(
                    case_id=case.case_id,
                    status=BusinessAnalysisCaseStatus.FAIL,
                    plan_passed=False,
                    task_passed=None,
                    report_passed=None,
                    failure_reason="经营分析调用失败",
                    reason_code="APPLICATION_CALL_FAILED",
                    duration_ms=_duration_ms(started),
                )
            )
            continue

        if case.expected_outcome == "clarification_required":
            evaluations.append(
                _evaluate_clarification_case(case, result, _duration_ms(started))
            )
            continue

        evaluations.append(
            _evaluate_plan_case(
                case,
                result,
                references,
                duration_ms=_duration_ms(started),
                judge=judge,
            )
        )

    result_cases = tuple(evaluations)
    return BusinessAnalysisEvaluationRun(
        cases=result_cases,
        summary=_summarize(result_cases),
        reference_results=reference_results,
    )


def _load_reference_results(
    case: BusinessAnalysisCase,
    query_executor: QueryExecutor,
    context: QueryContext,
) -> dict[str, QueryData]:
    references: dict[str, QueryData] = {}
    for task in case.expected_tasks:
        try:
            validated_sql = validate_sql(task.expected_sql, context)
            result = query_executor.execute(validated_sql)
        except Exception as exc:
            raise _InvalidCase(
                "标准 Task SQL 无法执行",
                reason_code="REFERENCE_SQL_INVALID",
            ) from exc
        if result.truncated:
            raise _InvalidCase(
                "标准 Task 结果被截断",
                reason_code="REFERENCE_RESULT_TRUNCATED",
            )
        references[_reference_key(case.case_id, task.key)] = result
    return references


def _evaluate_clarification_case(
    case: BusinessAnalysisCase,
    result: object,
    duration_ms: int,
) -> BusinessAnalysisCaseEvaluation:
    if not isinstance(result, QueryFailure):
        return BusinessAnalysisCaseEvaluation(
            case_id=case.case_id,
            status=BusinessAnalysisCaseStatus.FAIL,
            plan_passed=False,
            task_passed=None,
            report_passed=None,
            failure_reason="案例应要求澄清但未返回失败",
            reason_code="EXPECTED_CLARIFICATION_MISSING",
            duration_ms=duration_ms,
        )
    error_code = _error_code(result)
    if error_code != "CLARIFICATION_REQUIRED":
        return BusinessAnalysisCaseEvaluation(
            case_id=case.case_id,
            status=BusinessAnalysisCaseStatus.FAIL,
            plan_passed=False,
            task_passed=None,
            report_passed=None,
            failure_reason="案例返回了错误的失败类型",
            reason_code="CLARIFICATION_ERROR_CODE_MISMATCH",
            query_error_code=error_code,
            internal_reason=_internal_reason(result),
            duration_ms=duration_ms,
        )
    return BusinessAnalysisCaseEvaluation(
        case_id=case.case_id,
        status=BusinessAnalysisCaseStatus.PASS,
        plan_passed=True,
        task_passed=None,
        report_passed=None,
        duration_ms=duration_ms,
    )


def _evaluate_plan_case(
    case: BusinessAnalysisCase,
    result: object,
    references: Mapping[str, QueryData],
    *,
    duration_ms: int,
    judge: BusinessAnalysisJudge | None,
) -> BusinessAnalysisCaseEvaluation:
    if not isinstance(result, BusinessAnalysisSuccess):
        return BusinessAnalysisCaseEvaluation(
            case_id=case.case_id,
            status=BusinessAnalysisCaseStatus.FAIL,
            plan_passed=False,
            task_passed=None,
            report_passed=None,
            failure_reason="经营分析未生成成功结果",
            reason_code="ANALYSIS_RESULT_FAILED",
            query_error_code=_error_code(result),
            internal_reason=_internal_reason(result),
            duration_ms=duration_ms,
        )
    if not isinstance(result.plan, AnalysisPlan):
        return BusinessAnalysisCaseEvaluation(
            case_id=case.case_id,
            status=BusinessAnalysisCaseStatus.FAIL,
            plan_passed=False,
            task_passed=None,
            report_passed=None,
            failure_reason="经营分析成功结果缺少已校验计划",
            reason_code="PLAN_NOT_EXPOSED_FOR_EVALUATION",
            duration_ms=duration_ms,
        )

    plan_failure = _compare_plan(case.expected_tasks, result.plan)
    if plan_failure is not None:
        return BusinessAnalysisCaseEvaluation(
            case_id=case.case_id,
            status=BusinessAnalysisCaseStatus.FAIL,
            plan_passed=False,
            task_passed=None,
            report_passed=None,
            failure_reason=plan_failure[1],
            reason_code=plan_failure[0],
            duration_ms=duration_ms,
        )

    task_evaluations = _compare_task_results(case, result, references)
    tasks_passed = all(
        item.status is BusinessAnalysisCaseStatus.PASS for item in task_evaluations
    )
    if not tasks_passed:
        failed = next(
            item
            for item in task_evaluations
            if item.status is not BusinessAnalysisCaseStatus.PASS
        )
        return BusinessAnalysisCaseEvaluation(
            case_id=case.case_id,
            status=BusinessAnalysisCaseStatus.FAIL,
            plan_passed=True,
            task_passed=False,
            report_passed=None,
            failure_reason=failed.failure_reason,
            reason_code=failed.failure_reason,
            duration_ms=duration_ms,
            task_evaluations=task_evaluations,
        )

    report_failure = _compare_report(case, result)
    if report_failure is not None:
        return BusinessAnalysisCaseEvaluation(
            case_id=case.case_id,
            status=BusinessAnalysisCaseStatus.FAIL,
            plan_passed=True,
            task_passed=True,
            report_passed=False,
            failure_reason=report_failure[1],
            reason_code=report_failure[0],
            duration_ms=duration_ms,
            task_evaluations=task_evaluations,
        )
    attribution = result.attribution
    attribution_failure = _compare_attribution(case, result, references)
    if attribution_failure is not None:
        return BusinessAnalysisCaseEvaluation(
            case_id=case.case_id,
            status=BusinessAnalysisCaseStatus.FAIL,
            plan_passed=True,
            task_passed=True,
            report_passed=True,
            attribution_passed=False,
            failure_reason=attribution_failure[1],
            reason_code=attribution_failure[0],
            duration_ms=duration_ms,
            task_evaluations=task_evaluations,
        )

    judge_passed: bool | None = None
    judge_reason: str | None = None
    if judge is not None:
        try:
            judgement = judge.evaluate(case.question, result)
            judge_passed = getattr(judgement, "passed", None)
            judge_reason = getattr(judgement, "reason", None)
            if not isinstance(judge_passed, bool) or not isinstance(judge_reason, str):
                raise ValueError("Judge 结果结构无效")
        except Exception:
            return BusinessAnalysisCaseEvaluation(
                case_id=case.case_id,
                status=BusinessAnalysisCaseStatus.FAIL,
                plan_passed=True,
                task_passed=True,
                report_passed=True,
                attribution_passed=True,
                failure_reason="LLM Judge 未能形成有效判定",
                reason_code="JUDGE_RESULT_INVALID",
                duration_ms=duration_ms,
                task_evaluations=task_evaluations,
            )
        if not judge_passed:
            return BusinessAnalysisCaseEvaluation(
                case_id=case.case_id,
                status=BusinessAnalysisCaseStatus.FAIL,
                plan_passed=True,
                task_passed=True,
                report_passed=True,
                attribution_passed=True,
                direction=attribution.direction,
                change=str(attribution.total_change),
                judge_passed=False,
                judge_reason=judge_reason,
                failure_reason=judge_reason,
                reason_code="SUMMARY_JUDGE_REJECTED",
                duration_ms=duration_ms,
                task_evaluations=task_evaluations,
            )
    return BusinessAnalysisCaseEvaluation(
        case_id=case.case_id,
        status=BusinessAnalysisCaseStatus.PASS,
        plan_passed=True,
        task_passed=True,
        report_passed=True,
        attribution_passed=True if attribution is not None else None,
        direction=attribution.direction if attribution is not None else None,
        change=str(attribution.total_change) if attribution is not None else None,
        judge_passed=judge_passed,
        judge_reason=judge_reason,
        duration_ms=duration_ms,
        task_evaluations=task_evaluations,
    )


def _compare_plan(
    expected_tasks: tuple[BusinessAnalysisExpectedTask, ...],
    plan: AnalysisPlan,
) -> tuple[str, str] | None:
    if len(plan.tasks) != len(expected_tasks):
        return "PLAN_TASK_COUNT_MISMATCH", "Task 数量与黄金案例不一致"
    actual_ids = {
        expected.key: task.task_id
        for expected, task in zip(expected_tasks, plan.tasks, strict=True)
    }
    for expected, actual in zip(expected_tasks, plan.tasks, strict=True):
        if actual.task_type is not expected.task_type:
            return "PLAN_TASK_TYPE_MISMATCH", f"Task {expected.key} 类型不一致"
        if set(actual.metrics) != set(expected.metrics):
            return "PLAN_METRICS_MISMATCH", f"Task {expected.key} 指标不一致"
        if set(actual.dimensions) != set(expected.dimensions):
            return "PLAN_DIMENSIONS_MISMATCH", f"Task {expected.key} 维度不一致"
        if actual.filters:
            return "PLAN_FILTER_MISMATCH", f"Task {expected.key} 不应添加筛选条件"
        if expected.period and (
            actual.time_range is None or actual.time_range.text != expected.period
        ):
            return "PLAN_PERIOD_MISMATCH", f"Task {expected.key} 时期不一致"
        expected_dependencies = {actual_ids[key] for key in expected.depends_on}
        if set(actual.depends_on) != expected_dependencies:
            return "PLAN_DEPENDENCY_MISMATCH", f"Task {expected.key} 依赖不一致"
    return None


def _compare_attribution(
    case: BusinessAnalysisCase,
    result: BusinessAnalysisSuccess,
    references: Mapping[str, QueryData],
) -> tuple[str, str] | None:
    attribution = result.attribution
    if not isinstance(attribution, BusinessAnalysisAttribution):
        return "ATTRIBUTION_MISSING", "成功结果缺少确定性归因"
    if case.metric_name and attribution.metric_name != case.metric_name:
        return "ATTRIBUTION_METRIC_MISMATCH", "归因目标指标与案例不一致"
    if (
        case.comparison_period
        and attribution.comparison_period != case.comparison_period
    ):
        return "ATTRIBUTION_COMPARISON_PERIOD_MISMATCH", "归因比较时期与案例不一致"
    if case.current_period and attribution.current_period != case.current_period:
        return "ATTRIBUTION_CURRENT_PERIOD_MISMATCH", "归因当前时期与案例不一致"
    if case.metric_name and result.report.attribution != attribution:
        return "REPORT_ATTRIBUTION_MISMATCH", "报告没有保留程序计算的归因事实"
    if case.expected_direction and attribution.direction != case.expected_direction:
        return "ATTRIBUTION_DIRECTION_MISMATCH", "归因变化方向与案例事实不一致"
    if case.expected_change:
        expected_change = _decimal(case.expected_change)
        if expected_change is None or abs(
            attribution.total_change - expected_change
        ) > Decimal("0.02"):
            return "ATTRIBUTION_CHANGE_MISMATCH", "归因变化金额与案例事实不一致"
    old_value = _reference_scalar(references, case.case_id, "comparison-overall")
    new_value = _reference_scalar(references, case.case_id, "current-overall")
    if case.metric_name and (old_value is None or new_value is None):
        return "ATTRIBUTION_REFERENCE_MISSING", "独立 SQL 缺少整体指标参考值"
    if old_value is not None and attribution.comparison_value != old_value:
        return "ATTRIBUTION_BASELINE_MISMATCH", "归因比较期总值与独立 SQL 不一致"
    if new_value is not None and attribution.current_value != new_value:
        return "ATTRIBUTION_CURRENT_MISMATCH", "归因当前期总值与独立 SQL 不一致"
    if (
        old_value is not None
        and new_value is not None
        and attribution.total_change != new_value - old_value
    ):
        return "ATTRIBUTION_REFERENCE_CHANGE_MISMATCH", "归因变化与独立 SQL 差值不一致"
    return None


def _reference_scalar(
    references: Mapping[str, QueryData],
    case_id: str,
    task_key: str,
) -> Decimal | None:
    result = references.get(_reference_key(case_id, task_key))
    if result is None or len(result.rows) != 1 or len(result.rows[0]) != 1:
        return None
    return _decimal(result.rows[0][0])


def _decimal(value: object) -> Decimal | None:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _compare_task_results(
    case: BusinessAnalysisCase,
    result: BusinessAnalysisSuccess,
    references: Mapping[str, QueryData],
) -> tuple[BusinessAnalysisTaskEvaluation, ...]:
    evaluations: list[BusinessAnalysisTaskEvaluation] = []
    for index, expected in enumerate(case.expected_tasks):
        actual = (
            result.task_results[index] if index < len(result.task_results) else None
        )
        if actual is None:
            evaluations.append(
                BusinessAnalysisTaskEvaluation(
                    task_key=expected.key,
                    status=BusinessAnalysisCaseStatus.FAIL,
                    failure_reason="TASK_RESULT_MISSING",
                )
            )
            continue
        if actual.status.value != "completed":
            evaluations.append(
                BusinessAnalysisTaskEvaluation(
                    task_key=expected.key,
                    status=BusinessAnalysisCaseStatus.FAIL,
                    actual_task_id=actual.task_id,
                    failure_reason="TASK_RESULT_NOT_COMPLETED",
                )
            )
            continue
        if actual.truncated:
            evaluations.append(
                BusinessAnalysisTaskEvaluation(
                    task_key=expected.key,
                    status=BusinessAnalysisCaseStatus.FAIL,
                    actual_task_id=actual.task_id,
                    failure_reason="TASK_RESULT_TRUNCATED",
                )
            )
            continue
        expected_result = references[_reference_key(case.case_id, expected.key)]
        matched = results_match(
            QueryData(
                columns=actual.columns,
                rows=actual.rows,
                truncated=actual.truncated,
            ),
            expected_result,
            order_sensitive=expected.order_sensitive,
        )
        evaluations.append(
            BusinessAnalysisTaskEvaluation(
                task_key=expected.key,
                status=(
                    BusinessAnalysisCaseStatus.PASS
                    if matched
                    else BusinessAnalysisCaseStatus.FAIL
                ),
                actual_task_id=actual.task_id,
                failure_reason=None if matched else "TASK_RESULT_MISMATCH",
            )
        )
    return tuple(evaluations)


def _compare_report(
    case: BusinessAnalysisCase,
    result: BusinessAnalysisSuccess,
) -> tuple[str, str] | None:
    actual_ids = {
        expected.key: result.task_results[index].task_id
        for index, expected in enumerate(case.expected_tasks)
        if index < len(result.task_results)
    }
    evidence = set(result.report.evidence_task_ids)
    required_evidence = {
        actual_ids[key] for key in case.required_evidence_tasks if key in actual_ids
    }
    if not required_evidence.issubset(evidence):
        return "REPORT_EVIDENCE_MISSING", "报告缺少黄金案例要求的证据 Task"
    expected_incomplete = {
        actual_ids[key] for key in case.expected_incomplete_tasks if key in actual_ids
    }
    actual_incomplete = {item.task_id for item in result.report.incomplete_tasks}
    if actual_incomplete != expected_incomplete:
        return "REPORT_INCOMPLETE_MISMATCH", "报告不完整 Task 标记与黄金案例不一致"
    return None


def _summarize(
    cases: tuple[BusinessAnalysisCaseEvaluation, ...],
) -> BusinessAnalysisEvaluationSummary:
    valid = [
        item
        for item in cases
        if item.status is not BusinessAnalysisCaseStatus.INVALID_CASE
    ]
    plan_values = [item.plan_passed for item in valid if item.plan_passed is not None]
    report_values = [
        item.report_passed for item in valid if item.report_passed is not None
    ]
    task_results = [task for item in valid for task in item.task_evaluations]
    passed = sum(item.status is BusinessAnalysisCaseStatus.PASS for item in valid)
    return BusinessAnalysisEvaluationSummary(
        total_cases=len(cases),
        valid_cases=len(valid),
        passed=passed,
        failed=len(valid) - passed,
        invalid_cases=len(cases) - len(valid),
        plan_accuracy=_accuracy(plan_values),
        task_execution_accuracy=_accuracy(
            [item.status is BusinessAnalysisCaseStatus.PASS for item in task_results]
        ),
        report_grounded_accuracy=_accuracy(report_values),
        attribution_accuracy=_accuracy(
            [
                item.attribution_passed
                for item in valid
                if item.attribution_passed is not None
            ]
        ),
        summary_judge_accuracy=_accuracy(
            [item.judge_passed for item in valid if item.judge_passed is not None]
        ),
        end_to_end_accuracy=passed / len(valid) if valid else None,
    )


def _accuracy(values: Sequence[bool]) -> float | None:
    return sum(values) / len(values) if values else None


def _reference_key(case_id: str, task_key: str) -> str:
    return f"{case_id}:{task_key}"


def _error_code(result: object) -> str | None:
    error_code = getattr(result, "error_code", None)
    value = getattr(error_code, "value", error_code)
    return value if isinstance(value, str) else None


def _internal_reason(result: object) -> str | None:
    value = getattr(result, "internal_reason", None)
    return value if isinstance(value, str) and value else None


def _duration_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


class _InvalidCase(ValueError):
    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code
