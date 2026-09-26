"""把 Evaluation（评测）报告渲染为 Markdown（标记语言）总结。"""

from collections.abc import Mapping

from .reporting_errors import ReportingError


def render_markdown_report(report: Mapping[str, object]) -> str:
    """把机器可读 JSON 报告渲染为简洁的人类可读总结。"""

    metadata, summary, cases = _report_sections(report)
    lines = _render_overview(summary)
    lines.extend(
        _render_count_section(
            summary,
            title="失败阶段分布",
            field="failure_stage_counts",
            header="| 阶段 | 失败案例数 |",
            empty_message="没有记录失败阶段。",
            error_message="报告失败阶段汇总结构无效",
        )
    )
    lines.extend(
        _render_count_section(
            summary,
            title="内部原因分布",
            field="internal_reason_counts",
            header="| 内部原因 | 案例数 |",
            empty_message="没有记录内部原因。",
            error_message="报告内部原因汇总结构无效",
        )
    )
    lines.extend(_render_category_accuracy(summary))
    lines.extend(_render_trace_links(cases))
    lines.extend(_render_non_pass_cases(cases))
    lines.extend(_render_baseline_comparison(report))
    lines.extend(_render_run_info(metadata))
    return "\n".join(lines)


def _report_sections(
    report: Mapping[str, object],
) -> tuple[Mapping[str, object], Mapping[str, object], list[object]]:
    metadata = _object_mapping(report.get("metadata"))
    summary = _object_mapping(report.get("summary"))
    cases = report.get("cases")
    if metadata is None or summary is None or not isinstance(cases, list):
        raise ReportingError("报告结构无效，无法生成总结")
    return metadata, summary, cases


def _render_overview(summary: Mapping[str, object]) -> list[str]:
    total = _summary_count(summary, "total_cases")
    passed = _summary_count(summary, "passed")
    failed = _summary_count(summary, "failed")
    invalid = _summary_count(summary, "invalid_cases")
    accuracy_text = _accuracy_text(summary.get("execution_accuracy"))
    result = "PASS" if failed == 0 and invalid == 0 else "FAIL"
    return [
        "# ChatBI Evaluation（评测）报告",
        "",
        "## 总体结论",
        "",
        f"**{result}**",
        "",
        (
            f"本次共评测 {total} 条：成功 {passed} 条，失败 {failed} 条，"
            f"无效 {invalid} 条；有效案例执行准确率 {accuracy_text}。"
        ),
    ]


def _render_count_section(
    summary: Mapping[str, object],
    *,
    title: str,
    field: str,
    header: str,
    empty_message: str,
    error_message: str,
) -> list[str]:
    counts = _object_mapping(summary.get(field))
    if counts is None:
        raise ReportingError(error_message)
    lines = ["", f"## {title}", ""]
    if not counts:
        lines.append(empty_message)
        return lines
    lines.extend([header, "|---|---:|"])
    for label, count in sorted(counts.items()):
        lines.append(f"| {_markdown_cell(label)} | {_markdown_cell(count)} |")
    return lines


def _render_category_accuracy(summary: Mapping[str, object]) -> list[str]:
    category_accuracy = _object_mapping(summary.get("category_accuracy"))
    if category_accuracy is None:
        raise ReportingError("报告分类汇总结构无效")
    lines = [
        "",
        "## 分类准确率",
        "",
        "| 分类 | 执行准确率 |",
        "|---|---:|",
    ]
    for category, accuracy in sorted(category_accuracy.items()):
        lines.append(f"| {_markdown_cell(category)} | {_accuracy_text(accuracy)} |")
    return lines


def _render_trace_links(cases: list[object]) -> list[str]:
    lines = [
        "",
        "## 链路关联",
        "",
        "| 案例 | Request ID | Trace ID |",
        "|---|---|---|",
    ]
    for item in cases:
        case = _case_mapping(item)
        request_id = case.get("request_id") or "-"
        trace_id = case.get("trace_id") or "-"
        lines.append(
            "| {case_id} | {request_id} | {trace_id} |".format(
                case_id=_markdown_cell(case.get("case_id")),
                request_id=_markdown_cell(request_id),
                trace_id=_markdown_cell(trace_id),
            )
        )
    return lines


def _render_non_pass_cases(cases: list[object]) -> list[str]:
    non_pass_cases: list[Mapping[str, object]] = []
    for item in cases:
        case = _case_mapping(item)
        if case.get("status") != "PASS":
            non_pass_cases.append(case)

    lines = ["", "## 失败与无效案例", ""]
    if not non_pass_cases:
        lines.append("无失败或无效案例。")
        return lines

    lines.extend(
        [
            "| 案例 | 分类 | 状态 | 阶段 | 内部原因 | 原因 |",
            "|---|---|---|---|---|---|",
        ]
    )
    for case in non_pass_cases:
        lines.append(
            (
                "| {case_id} | {category} | {status} | {stage} | "
                "{internal_reason} | {reason} |"
            ).format(
                case_id=_markdown_cell(case.get("case_id")),
                category=_markdown_cell(case.get("category")),
                status=_markdown_cell(case.get("status")),
                stage=_markdown_cell(case.get("failure_stage") or "未说明"),
                internal_reason=_markdown_cell(case.get("internal_reason") or "未说明"),
                reason=_markdown_cell(case.get("failure_reason") or "未说明"),
            )
        )
    return lines


def _render_baseline_comparison(report: Mapping[str, object]) -> list[str]:
    lines = ["", "## 基线对比", ""]
    comparison = report.get("baseline_comparison")
    if comparison is None:
        lines.append("本次未执行自动基线比较；可与历史报告人工对照。")
        return lines

    comparison_mapping = _object_mapping(comparison)
    if comparison_mapping is None:
        raise ReportingError("基线对比结构无效")
    if comparison_mapping.get("comparable") is not True:
        reason = _markdown_cell(comparison_mapping.get("reason") or "原因未知")
        lines.append(f"状态：NOT_COMPARABLE。未形成有效基线对比：{reason}。")
        return lines

    regressions = _string_list(comparison_mapping, "regressions")
    improvements = _string_list(comparison_mapping, "improvements")
    unchanged = _string_list(comparison_mapping, "unchanged")
    if comparison_mapping.get("seed_version_changed") is True:
        lines.append("Seed 版本与 Baseline 不同；实际数据 Hash 相同，本次仍可比较。")
    lines.extend(
        [
            "状态：COMPARABLE。",
            _comparison_line("能力回退", regressions),
            _comparison_line("能力改善", improvements),
            f"状态未变化 {len(unchanged)} 条。",
        ]
    )
    return lines


def _render_run_info(metadata: Mapping[str, object]) -> list[str]:
    lines = [
        "",
        "## 运行信息",
        "",
        f"- Run ID：{_markdown_cell(metadata.get('run_id'))}",
        f"- 运行时间：{_markdown_cell(metadata.get('created_at'))}",
        f"- Git Commit：{_markdown_cell(metadata.get('git_commit'))}",
        f"- Git Dirty：{_markdown_cell(metadata.get('git_dirty'))}",
        f"- Model：{_markdown_cell(metadata.get('model'))}",
    ]
    seed_version = metadata.get("sales_mart_seed_version")
    data_hash = metadata.get("sales_mart_data_hash")
    hash_algorithm = metadata.get("sales_mart_data_hash_algorithm")
    summary = _object_mapping(metadata.get("sales_mart_data_summary"))
    counts = _object_mapping(summary.get("table_counts")) if summary else None
    date_range = _object_mapping(summary.get("date_range")) if summary else None
    if summary is None or counts is None or date_range is None:
        lines.extend(
            [
                "- Sales Mart Seed：未记录",
                "- Sales Mart 数据 Hash：未记录",
            ]
        )
    else:
        count_summary = ", ".join(
            f"{_markdown_cell(table)}={_markdown_cell(count)}"
            for table, count in sorted(counts.items())
        )
        date_summary = (
            f"{_markdown_cell(date_range.get('start'))} 至 "
            f"{_markdown_cell(date_range.get('end'))}"
        )
        lines.extend(
            [
                f"- Sales Mart Seed：{_markdown_cell(seed_version)}",
                (
                    f"- Sales Mart 数据 Hash：{_markdown_cell(hash_algorithm)} "
                    f"`{_markdown_cell(data_hash)}`"
                ),
                (
                    f"- Sales Mart 摘要：{_markdown_cell(summary.get('total_rows'))} 行；"
                    f"日期 {date_summary}；表行数 {count_summary}"
                ),
            ]
        )
    lines.append("")
    return lines


def _summary_count(summary: Mapping[str, object], field: str) -> int:
    value = summary.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReportingError(f"报告汇总字段无效：{field}")
    return value


def _accuracy_text(value: object) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReportingError("报告准确率字段无效")
    return f"{float(value):.2%}"


def _markdown_cell(value: object) -> str:
    return (
        str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")
    )


def _string_list(mapping: Mapping[str, object], field: str) -> list[str]:
    value = mapping.get(field)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ReportingError(f"基线对比字段无效：{field}")
    return value


def _comparison_line(label: str, case_ids: list[str]) -> str:
    if not case_ids:
        return f"{label} 0 条。"
    rendered = "、".join(_markdown_cell(case_id) for case_id in case_ids)
    return f"{label} {len(case_ids)} 条：{rendered}。"


def _case_mapping(value: object) -> Mapping[str, object]:
    mapping = _object_mapping(value)
    if mapping is None:
        raise ReportingError("报告案例结构无效")
    return mapping


def _object_mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, dict) else None
