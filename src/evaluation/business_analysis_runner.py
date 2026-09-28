"""经营分析标准案例的双维度 AI Evaluation Runner。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from time import perf_counter
from typing import Protocol
from uuid import uuid4

from src.authorization.contracts import AuthContext
from src.business_analysis.application import (
    BusinessAnalysisApplication,
    BusinessAnalysisSuccess,
)
from src.online_query.contracts import QueryData, QueryFailure

from .business_analysis_evaluation import BusinessAnalysisCase


class BusinessAnalysisCaseStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INVALID_CASE = "INVALID_CASE"


@dataclass(frozen=True, slots=True)
class JudgeResult:
    passed: bool
    reason: str


class BusinessAnalysisJudge(Protocol):
    def evaluate_plan(
        self, case: BusinessAnalysisCase, result: BusinessAnalysisSuccess
    ) -> JudgeResult: ...

    def evaluate_summary(
        self, case: BusinessAnalysisCase, result: BusinessAnalysisSuccess
    ) -> JudgeResult: ...


@dataclass(frozen=True, slots=True)
class BusinessAnalysisCaseEvaluation:
    case_id: str
    status: BusinessAnalysisCaseStatus
    outcome_passed: bool | None
    plan_passed: bool | None
    summary_passed: bool | None
    failure_reason: str | None = None
    reason_code: str | None = None
    query_error_code: str | None = None
    plan_reason: str | None = None
    summary_reason: str | None = None
    duration_ms: int = 0


@dataclass(frozen=True, slots=True)
class BusinessAnalysisEvaluationSummary:
    total_cases: int
    valid_cases: int
    passed: int
    failed: int
    invalid_cases: int
    outcome_accuracy: float | None
    plan_accuracy: float | None
    summary_accuracy: float | None
    end_to_end_accuracy: float | None


@dataclass(frozen=True, slots=True)
class BusinessAnalysisEvaluationRun:
    cases: tuple[BusinessAnalysisCaseEvaluation, ...]
    summary: BusinessAnalysisEvaluationSummary
    reference_results: dict[str, QueryData]


def run_business_analysis_evaluation(
    cases: Sequence[BusinessAnalysisCase],
    application: BusinessAnalysisApplication,
    auth_context: AuthContext,
    judge: BusinessAnalysisJudge | None = None,
) -> BusinessAnalysisEvaluationRun:
    """运行案例；成功案例的任务计划与总结分别判定，不互相短路。"""

    evaluations: list[BusinessAnalysisCaseEvaluation] = []
    for case in cases:
        started = perf_counter()
        try:
            result = application.analyze(
                case.question,
                request_id=f"analysis-evaluation-{case.case_id}",
                auth_context=auth_context,
                analysis_run_id=str(uuid4()),
            )
        except Exception:  # noqa: BLE001 - isolate a failed app call to this case
            evaluations.append(
                _failure(case, "经营分析调用失败", "APPLICATION_CALL_FAILED", started)
            )
            continue

        if case.expected_outcome != "success":
            evaluations.append(
                _evaluate_rejection_or_clarification(case, result, started)
            )
            continue
        if not isinstance(result, BusinessAnalysisSuccess):
            evaluations.append(
                BusinessAnalysisCaseEvaluation(
                    case_id=case.case_id,
                    status=BusinessAnalysisCaseStatus.FAIL,
                    outcome_passed=False,
                    plan_passed=False,
                    summary_passed=False,
                    failure_reason="案例应成功分析但系统返回失败",
                    reason_code="EXPECTED_SUCCESS_MISSING",
                    query_error_code=_error_code(result),
                    duration_ms=_duration_ms(started),
                )
            )
            continue
        if judge is None:
            evaluations.append(
                _failure(
                    case,
                    "成功案例未配置 LLM Judge",
                    "JUDGE_NOT_CONFIGURED",
                    started,
                    outcome_passed=True,
                )
            )
            continue

        plan_result, plan_error = _run_judge(partial(judge.evaluate_plan, case, result))
        summary_result, summary_error = _run_judge(
            partial(judge.evaluate_summary, case, result)
        )
        plan_passed = plan_result.passed if plan_result else False
        summary_passed = summary_result.passed if summary_result else False
        failed_axes = []
        if not plan_passed:
            failed_axes.append("任务拆解")
        if not summary_passed:
            failed_axes.append("总结")
        evaluations.append(
            BusinessAnalysisCaseEvaluation(
                case_id=case.case_id,
                status=(
                    BusinessAnalysisCaseStatus.PASS
                    if not failed_axes
                    else BusinessAnalysisCaseStatus.FAIL
                ),
                outcome_passed=True,
                plan_passed=plan_passed,
                summary_passed=summary_passed,
                failure_reason=("、".join(failed_axes) + "判定未通过")
                if failed_axes
                else None,
                reason_code=(
                    "JUDGE_RESULT_INVALID"
                    if plan_error or summary_error
                    else "JUDGE_REJECTED"
                    if failed_axes
                    else None
                ),
                plan_reason=plan_result.reason if plan_result else plan_error,
                summary_reason=summary_result.reason
                if summary_result
                else summary_error,
                duration_ms=_duration_ms(started),
            )
        )

    result_cases = tuple(evaluations)
    return BusinessAnalysisEvaluationRun(result_cases, _summarize(result_cases), {})


def _evaluate_rejection_or_clarification(
    case: BusinessAnalysisCase, result: object, started: float
) -> BusinessAnalysisCaseEvaluation:
    expected = case.error_code
    actual = _error_code(result)
    passed = isinstance(result, QueryFailure) and actual == expected
    return BusinessAnalysisCaseEvaluation(
        case_id=case.case_id,
        status=BusinessAnalysisCaseStatus.PASS
        if passed
        else BusinessAnalysisCaseStatus.FAIL,
        outcome_passed=passed,
        plan_passed=None,
        summary_passed=None,
        failure_reason=None if passed else "拒绝或澄清结果与案例预期不一致",
        reason_code=None if passed else "OUTCOME_MISMATCH",
        query_error_code=actual,
        duration_ms=_duration_ms(started),
    )


def _run_judge(call) -> tuple[JudgeResult | None, str | None]:
    try:
        value = call()
    except Exception:  # noqa: BLE001 - provider errors must fail this judge axis closed
        return None, "LLM Judge 调用失败"
    if (
        not isinstance(value, JudgeResult)
        or not isinstance(value.passed, bool)
        or not isinstance(value.reason, str)
        or not value.reason.strip()
    ):
        return None, "LLM Judge 返回结构无效"
    return value, None


def _failure(
    case: BusinessAnalysisCase,
    message: str,
    code: str,
    started: float,
    *,
    outcome_passed: bool = False,
) -> BusinessAnalysisCaseEvaluation:
    return BusinessAnalysisCaseEvaluation(
        case_id=case.case_id,
        status=BusinessAnalysisCaseStatus.FAIL,
        outcome_passed=outcome_passed,
        plan_passed=False if case.expected_outcome == "success" else None,
        summary_passed=False if case.expected_outcome == "success" else None,
        failure_reason=message,
        reason_code=code,
        duration_ms=_duration_ms(started),
    )


def _error_code(result: object) -> str | None:
    if isinstance(result, QueryFailure):
        return result.error_code.value
    return None


def _duration_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def _accuracy(values: list[bool]) -> float | None:
    return sum(values) / len(values) if values else None


def _summarize(
    cases: tuple[BusinessAnalysisCaseEvaluation, ...],
) -> BusinessAnalysisEvaluationSummary:
    valid = [
        item
        for item in cases
        if item.status is not BusinessAnalysisCaseStatus.INVALID_CASE
    ]
    plan = [item.plan_passed for item in valid if item.plan_passed is not None]
    summary = [item.summary_passed for item in valid if item.summary_passed is not None]
    outcome = [item.outcome_passed for item in valid if item.outcome_passed is not None]
    return BusinessAnalysisEvaluationSummary(
        total_cases=len(cases),
        valid_cases=len(valid),
        passed=sum(item.status is BusinessAnalysisCaseStatus.PASS for item in cases),
        failed=sum(item.status is BusinessAnalysisCaseStatus.FAIL for item in cases),
        invalid_cases=sum(
            item.status is BusinessAnalysisCaseStatus.INVALID_CASE for item in cases
        ),
        outcome_accuracy=_accuracy(outcome),
        plan_accuracy=_accuracy(plan),
        summary_accuracy=_accuracy(summary),
        end_to_end_accuracy=_accuracy(
            [item.status is BusinessAnalysisCaseStatus.PASS for item in valid]
        ),
    )
