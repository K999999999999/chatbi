"""经营分析评估结果的 JSON / Markdown 报告。"""

from collections.abc import Mapping

from .business_analysis_runner import BusinessAnalysisEvaluationRun
from .reporting import RunMetadata, compare_baseline
from .reporting_markdown import _render_run_info


def create_business_analysis_report(
    run: BusinessAnalysisEvaluationRun,
    metadata: RunMetadata,
    baseline: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """生成不包含查询明细和 Secret 的经营分析评估报告。"""

    report: dict[str, object] = {
        "metadata": metadata.to_dict(),
        "summary": {
            "total_cases": run.summary.total_cases,
            "valid_cases": run.summary.valid_cases,
            "passed": run.summary.passed,
            "failed": run.summary.failed,
            "invalid_cases": run.summary.invalid_cases,
            "plan_accuracy": run.summary.plan_accuracy,
            "task_execution_accuracy": run.summary.task_execution_accuracy,
            "report_grounded_accuracy": run.summary.report_grounded_accuracy,
            "end_to_end_accuracy": run.summary.end_to_end_accuracy,
        },
        "cases": [
            {
                "case_id": case.case_id,
                "status": case.status.value,
                "plan_passed": case.plan_passed,
                "task_passed": case.task_passed,
                "report_passed": case.report_passed,
                "failure_reason": case.failure_reason,
                "reason_code": case.reason_code,
                "query_error_code": case.query_error_code,
                "internal_reason": case.internal_reason,
                "duration_ms": case.duration_ms,
                "task_evaluations": [
                    {
                        "task_key": task.task_key,
                        "status": task.status.value,
                        "actual_task_id": task.actual_task_id,
                        "failure_reason": task.failure_reason,
                    }
                    for task in case.task_evaluations
                ],
            }
            for case in run.cases
        ],
        "baseline_comparison": None,
    }
    if baseline is not None:
        report["baseline_comparison"] = compare_baseline(report, baseline)
    return report


def render_business_analysis_markdown(report: Mapping[str, object]) -> str:
    """把 JSON 报告转换为人工可读的稳定摘要。"""

    summary = _mapping(report.get("summary"))
    metadata = _mapping(report.get("metadata"))
    cases = report.get("cases")
    lines = [
        "# 经营分析 Evaluation（评估）",
        "",
        "## 总体结论",
        "",
        (
            "本次共评测 {total} 条：成功 {passed} 条，失败 {failed} 条，"
            "无效 {invalid} 条。"
        ).format(
            total=summary.get("total_cases", "未说明"),
            passed=summary.get("passed", "未说明"),
            failed=summary.get("failed", "未说明"),
            invalid=summary.get("invalid_cases", "未说明"),
        ),
        "",
        "| 指标 | 结果 |",
        "|---|---:|",
        f"| 计划准确率 | {_accuracy(summary.get('plan_accuracy'))} |",
        f"| Task 执行准确率 | {_accuracy(summary.get('task_execution_accuracy'))} |",
        f"| 报告事实依据率 | {_accuracy(summary.get('report_grounded_accuracy'))} |",
        f"| 端到端案例准确率 | {_accuracy(summary.get('end_to_end_accuracy'))} |",
        "",
        "## 案例结果",
        "",
        "| 案例 | 状态 | 计划 | Task | 报告证据 | 原因 |",
        "|---|---|---|---|---|---|",
    ]
    if isinstance(cases, list):
        for case in cases:
            item = _mapping(case)
            lines.append(
                "| {case} | {status} | {plan} | {task} | {report} | {reason} |".format(
                    case=_cell(item.get("case_id")),
                    status=_cell(item.get("status")),
                    plan=_bool_text(item.get("plan_passed")),
                    task=_bool_text(item.get("task_passed")),
                    report=_bool_text(item.get("report_passed")),
                    reason=_cell(item.get("reason_code") or item.get("failure_reason")),
                )
            )
    lines.extend(_render_run_info(metadata))
    comparison = report.get("baseline_comparison")
    if isinstance(comparison, Mapping):
        lines.extend(
            [
                "",
                "## Baseline（基线）比较",
                "",
                _render_comparison(comparison),
            ]
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
        "Seed 版本与 Baseline 不同；实际数据 Hash 相同，仍可比较。"
        if comparison.get("seed_version_changed") is True
        else ""
    )
    return (
        "状态：COMPARABLE。"
        f"{seed_change}"
        f"能力回退：{_list_text(regressions)}；能力改善：{_list_text(improvements)}。"
    )


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
