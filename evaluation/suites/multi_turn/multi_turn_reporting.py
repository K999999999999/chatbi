"""多轮 Conversation（对话场景）评测报告。"""

from collections.abc import Mapping
from pathlib import Path

from .multi_turn_evaluation import MultiTurnEvaluationRun
from ...common.reporting import RunMetadata, compare_baseline
from ...common.reporting_errors import ReportingError


def create_multi_turn_report(
    run: MultiTurnEvaluationRun,
    metadata: RunMetadata,
    baseline: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """生成按完整 Conversation 计分并保留轮次诊断的报告。"""

    report: dict[str, object] = {
        "metadata": {
            **metadata.to_dict(),
            "evaluation_suite": "multi_turn_conversation",
        },
        "summary": {
            "total_cases": run.summary.total_conversations,
            "valid_cases": run.summary.valid_conversations,
            "passed": run.summary.passed_conversations,
            "failed": run.summary.failed_conversations,
            "invalid_cases": run.summary.invalid_conversations,
            "conversation_accuracy": run.summary.conversation_accuracy,
            "total_turns": run.summary.total_turns,
            "valid_turns": run.summary.valid_turns,
            "passed_turns": run.summary.passed_turns,
            "failed_turns": run.summary.failed_turns,
            "invalid_turns": run.summary.invalid_turns,
            "execution_turns": run.summary.execution_turns,
            "execution_passed": run.summary.execution_passed,
            "execution_accuracy": run.summary.execution_accuracy,
            "outcome_turns": run.summary.outcome_turns,
            "outcome_passed": run.summary.outcome_passed,
            "outcome_accuracy": run.summary.outcome_accuracy,
            "coverage_accuracy": dict(run.summary.coverage_accuracy),
        },
        "cases": [
            {
                "case_id": case.case_id,
                "coverage": list(case.coverage),
                "status": case.status.value,
                "failure_reason": case.failure_reason,
                "turns": [
                    {
                        "turn_id": turn.turn_id,
                        "question": turn.question,
                        "expected_outcome": turn.expected_outcome,
                        "expected_error_code": turn.expected_error_code,
                        "status": turn.status.value,
                        "query_error_code": turn.query_error_code,
                        "failure_reason": turn.failure_reason,
                        "duration_ms": turn.duration_ms,
                        "generated_sql": turn.generated_sql,
                    }
                    for turn in case.turns
                ],
            }
            for case in run.cases
        ],
        "baseline_comparison": None,
    }
    if baseline is not None:
        report["baseline_comparison"] = compare_baseline(report, baseline)
    return report


def write_multi_turn_markdown_report(
    report: Mapping[str, object],
    path: Path,
) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_multi_turn_markdown(report), encoding="utf-8")
    except OSError:
        raise ReportingError("多轮评测总结报告无法写入") from None


def render_multi_turn_markdown(report: Mapping[str, object]) -> str:
    summary = _mapping(report.get("summary"))
    metadata = _mapping(report.get("metadata"))
    cases = report.get("cases")
    if not summary or not metadata or not isinstance(cases, list):
        raise ReportingError("多轮评测报告结构无效")

    lines = [
        "# 多轮对话 Evaluation（评测）",
        "",
        "## 总体结论",
        "",
        (
            "Conversation 准确率：{conversation}；成功场景 {passed}/{valid}，"
            "失败 {failed}，无效 {invalid}。"
        ).format(
            conversation=_accuracy(summary.get("conversation_accuracy")),
            passed=summary.get("passed", 0),
            valid=summary.get("valid_cases", 0),
            failed=summary.get("failed", 0),
            invalid=summary.get("invalid_cases", 0),
        ),
        "",
        "| 指标 | 结果 |",
        "|---|---:|",
        f"| Conversation 准确率 | {_accuracy(summary.get('conversation_accuracy'))} |",
        f"| 查询执行准确率 | {_accuracy(summary.get('execution_accuracy'))} |",
        f"| 失败 outcome 命中率 | {_accuracy(summary.get('outcome_accuracy'))} |",
        ("| 成功 / 失败 / 无效轮次 | {passed} / {failed} / {invalid} |").format(
            passed=summary.get("passed_turns", 0),
            failed=summary.get("failed_turns", 0),
            invalid=summary.get("invalid_turns", 0),
        ),
        "",
        "## 场景及轮次结果",
        "",
    ]
    if not cases:
        lines.append("没有可报告的 Conversation 案例。")
    for raw_case in cases:
        case = _mapping(raw_case)
        lines.extend(
            [
                "### {case_id}：{status}".format(
                    case_id=_cell(case.get("case_id")),
                    status=_cell(case.get("status")),
                ),
                "",
                f"覆盖：{_cell(', '.join(_string_list(case.get('coverage'))))}",
                "",
                "| 轮次 | 期望 outcome / 错误码 | 状态 | 实际错误码 | 原因 |",
                "|---|---|---|---|---|",
            ]
        )
        turns = case.get("turns")
        if isinstance(turns, list):
            for raw_turn in turns:
                turn = _mapping(raw_turn)
                expected = turn.get("expected_outcome")
                error_code = turn.get("expected_error_code")
                if error_code:
                    expected = f"{expected} / {error_code}"
                lines.append(
                    "| {turn_id} | {expected} | {status} | {actual} | {reason} |".format(
                        turn_id=_cell(turn.get("turn_id")),
                        expected=_cell(expected),
                        status=_cell(turn.get("status")),
                        actual=_cell(turn.get("query_error_code") or "-"),
                        reason=_cell(turn.get("failure_reason") or "-"),
                    )
                )
        lines.append("")

    comparison = report.get("baseline_comparison")
    if comparison is None:
        lines.append("本次未执行同一多轮测试集的 Baseline（基线）比较。")
    else:
        comparison_mapping = _mapping(comparison)
        if comparison_mapping.get("comparable") is True:
            lines.append(
                "Baseline 状态：COMPARABLE；回退 {regressions} 个场景，改善 {improvements} 个场景。".format(
                    regressions=len(
                        _string_list(comparison_mapping.get("regressions"))
                    ),
                    improvements=len(
                        _string_list(comparison_mapping.get("improvements"))
                    ),
                )
            )
        else:
            lines.append(
                "Baseline 状态：NOT_COMPARABLE；原因：{reason}。".format(
                    reason=_cell(comparison_mapping.get("reason")),
                )
            )
    lines.extend(
        [
            "",
            "## 运行信息",
            "",
            f"- Run ID：{_cell(metadata.get('run_id'))}",
            f"- Git Commit：{_cell(metadata.get('git_commit'))}",
            f"- Git Dirty：{_cell(metadata.get('git_dirty'))}",
            f"- Model：{_cell(metadata.get('model'))}",
            f"- RAG 资产：{_cell(metadata.get('rag_asset_version'))}",
            "",
        ]
    )
    return "\n".join(lines)


def _accuracy(value: object) -> str:
    return "N/A" if value is None else f"{float(value):.2%}"


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _cell(value: object) -> str:
    if value is None:
        return "未说明"
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


__all__ = [
    "create_multi_turn_report",
    "render_multi_turn_markdown",
    "write_multi_turn_markdown_report",
]
