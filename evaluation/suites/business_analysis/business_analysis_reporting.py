"""经营分析评测结果的 JSON / Markdown 报告。"""

from collections.abc import Mapping

from .business_analysis_runner import BusinessAnalysisEvaluationRun
from ...common.reporting import RunMetadata, compare_baseline
from ...common.reporting_markdown import _render_run_info


def create_business_analysis_report(
    run: BusinessAnalysisEvaluationRun,
    metadata: RunMetadata,
    baseline: Mapping[str, object] | None = None,
) -> dict[str, object]:
    report: dict[str, object] = {
        "metadata": {**metadata.to_dict(), "evaluation_suite": "business_analysis"},
        "summary": {
            "total_cases": run.summary.total_cases,
            "valid_cases": run.summary.valid_cases,
            "passed": run.summary.passed,
            "failed": run.summary.failed,
            "invalid_cases": run.summary.invalid_cases,
            "outcome_accuracy": run.summary.outcome_accuracy,
            "plan_accuracy": run.summary.plan_accuracy,
            "summary_accuracy": run.summary.summary_accuracy,
            "end_to_end_accuracy": run.summary.end_to_end_accuracy,
        },
        "cases": [
            {
                "case_id": case.case_id,
                "status": case.status.value,
                "outcome_passed": case.outcome_passed,
                "plan_passed": case.plan_passed,
                "summary_passed": case.summary_passed,
                "plan_reason": case.plan_reason,
                "summary_reason": case.summary_reason,
                "failure_reason": case.failure_reason,
                "reason_code": case.reason_code,
                "query_error_code": case.query_error_code,
                "duration_ms": case.duration_ms,
            }
            for case in run.cases
        ],
        "baseline_comparison": None,
    }
    if baseline is not None:
        report["baseline_comparison"] = compare_baseline(report, baseline)
    return report


def render_business_analysis_markdown(report: Mapping[str, object]) -> str:
    summary = _mapping(report.get("summary"))
    metadata = _mapping(report.get("metadata"))
    cases = report.get("cases")
    lines = [
        "# 经营分析 Evaluation（评测）",
        "",
        "## 总体结论",
        "",
        "本次共评测 {total} 条：通过 {passed} 条，失败 {failed} 条，无效 {invalid} 条。".format(
            total=summary.get("total_cases", "未说明"),
            passed=summary.get("passed", "未说明"),
            failed=summary.get("failed", "未说明"),
            invalid=summary.get("invalid_cases", "未说明"),
        ),
        "",
        "| 评测维度 | 准确率 |",
        "|---|---:|",
        f"| 结果类型 | {_accuracy(summary.get('outcome_accuracy'))} |",
        f"| 任务拆解 | {_accuracy(summary.get('plan_accuracy'))} |",
        f"| 总结质量 | {_accuracy(summary.get('summary_accuracy'))} |",
        f"| 端到端 | {_accuracy(summary.get('end_to_end_accuracy'))} |",
        "",
        "## 案例结果",
        "",
        "| 案例 | 状态 | 结果类型 | 任务拆解 | 总结 | 原因 |",
        "|---|---|---|---|---|---|",
    ]
    if isinstance(cases, list):
        for case in cases:
            item = _mapping(case)
            reason = (
                item.get("failure_reason")
                or item.get("plan_reason")
                or item.get("summary_reason")
            )
            lines.append(
                "| {case} | {status} | {outcome} | {plan} | {summary} | {reason} |".format(
                    case=_cell(item.get("case_id")),
                    status=_cell(item.get("status")),
                    outcome=_bool_text(item.get("outcome_passed")),
                    plan=_bool_text(item.get("plan_passed")),
                    summary=_bool_text(item.get("summary_passed")),
                    reason=_cell(reason),
                )
            )
    lines.extend(_render_run_info(metadata))
    comparison = report.get("baseline_comparison")
    if isinstance(comparison, Mapping):
        lines.extend(
            ["", "## Baseline（基线）比较", "", _render_comparison(comparison)]
        )
    else:
        lines.extend(["", "本次未执行自动 Baseline（基线）比较。"])
    return "\n".join(lines) + "\n"


def _render_comparison(comparison: Mapping[str, object]) -> str:
    if comparison.get("comparable") is not True:
        return f"状态：NOT_COMPARABLE。无法比较：{_cell(comparison.get('reason'))}。"
    regressions = comparison.get("regressions", [])
    improvements = comparison.get("improvements", [])
    seed_change = (
        "Seed 版本与 Baseline 不同；Sales Mart 数据 Hash 相同，仍可比较。"
        if comparison.get("seed_version_changed") is True
        else ""
    )
    return f"状态：COMPARABLE。{seed_change}能力回退：{_list_text(regressions)}；能力改善：{_list_text(improvements)}。"


def _accuracy(value: object) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value:.2%}"
    return _cell(value)


def _bool_text(value: object) -> str:
    if value is True:
        return "PASS"
    if value is False:
        return "FAIL"
    return "N/A"


def _list_text(value: object) -> str:
    if isinstance(value, list):
        return "、".join(_cell(item) for item in value) or "无"
    return "未说明"


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _cell(value: object) -> str:
    text = "未说明" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()
