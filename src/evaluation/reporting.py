"""生成可复现的 Evaluation（评测）报告并比较 Baseline（基线）。"""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from src.online_query.contracts import QueryData

from .runner import CaseStatus, EvaluationRun


class ReportingError(RuntimeError):
    """评测报告配置、读取或写入失败。"""


@dataclass(frozen=True, slots=True)
class RunMetadata:
    run_id: str
    created_at: str
    git_commit: str
    git_dirty: bool
    model: str
    temperature: float
    max_tokens: int
    model_endpoint_hash: str
    test_set_hash: str
    context_hash: str
    reference_result_hash: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def collect_run_metadata(
    run: EvaluationRun,
    *,
    git_commit: str,
    git_dirty: bool,
    environ: Mapping[str, str],
    test_set_path: Path,
    context_paths: Mapping[str, Path],
    now: datetime | None = None,
) -> RunMetadata:
    """只收集非敏感配置和内容指纹。"""

    commit = git_commit.strip()
    model = environ.get("LLM_MODEL", "").strip()
    if not commit:
        raise ReportingError("缺少 Git Commit")
    if not model:
        raise ReportingError("缺少 LLM_MODEL")

    try:
        temperature = float(environ.get("LLM_TEMPERATURE", "0.1"))
        max_tokens = int(environ.get("LLM_MAX_TOKENS", "1200"))
    except ValueError:
        raise ReportingError("LLM 数字配置无效") from None
    if max_tokens <= 0:
        raise ReportingError("LLM_MAX_TOKENS 必须大于 0")

    created = datetime.now(UTC) if now is None else now
    if created.tzinfo is None:
        raise ReportingError("运行时间必须包含时区")
    created_utc = created.astimezone(UTC)
    timestamp = created_utc.strftime("%Y%m%dT%H%M%SZ")

    return RunMetadata(
        run_id=f"{timestamp}-{commit[:7]}",
        created_at=created_utc.isoformat().replace("+00:00", "Z"),
        git_commit=commit,
        git_dirty=git_dirty,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        model_endpoint_hash=_hash_text(environ.get("LLM_BASE_URL", "").strip()),
        test_set_hash=_hash_file(test_set_path),
        context_hash=_hash_named_files(context_paths),
        reference_result_hash=_hash_reference_results(run.reference_results),
    )


def create_report(
    run: EvaluationRun,
    metadata: RunMetadata,
    baseline: Mapping[str, object] | None = None,
) -> dict[str, object]:
    report: dict[str, object] = {
        "metadata": metadata.to_dict(),
        "summary": {
            "total_cases": run.summary.total_cases,
            "valid_cases": run.summary.valid_cases,
            "passed": run.summary.passed,
            "failed": run.summary.failed,
            "invalid_cases": run.summary.invalid_cases,
            "execution_accuracy": run.summary.execution_accuracy,
            "category_accuracy": dict(run.summary.category_accuracy),
            "failure_stage_counts": _failure_stage_counts(run),
            "internal_reason_counts": _internal_reason_counts(run),
        },
        "cases": [
            {
                "case_id": result.case_id,
                "category": result.category,
                "status": result.status.value,
                "generated_sql": result.generated_sql,
                "query_error_code": result.query_error_code,
                "failure_reason": result.failure_reason,
                "failure_stage": result.failure_stage,
                "internal_reason": result.internal_reason,
                "duration_ms": result.duration_ms,
                "request_id": result.request_id,
                "trace_id": result.trace_id,
            }
            for result in run.cases
        ],
        "baseline_comparison": None,
    }
    if baseline is not None:
        report["baseline_comparison"] = compare_baseline(report, baseline)
    return report


def render_markdown_report(report: Mapping[str, object]) -> str:
    """把机器可读 JSON 报告渲染为简洁的人类可读总结。"""

    metadata = _object_mapping(report.get("metadata"))
    summary = _object_mapping(report.get("summary"))
    cases = report.get("cases")
    if metadata is None or summary is None or not isinstance(cases, list):
        raise ReportingError("报告结构无效，无法生成总结")

    total = _summary_count(summary, "total_cases")
    passed = _summary_count(summary, "passed")
    failed = _summary_count(summary, "failed")
    invalid = _summary_count(summary, "invalid_cases")
    accuracy_text = _accuracy_text(summary.get("execution_accuracy"))
    result = "PASS" if failed == 0 and invalid == 0 else "FAIL"

    lines = [
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
        "",
        "## 失败阶段分布",
        "",
    ]
    stage_counts = _object_mapping(summary.get("failure_stage_counts"))
    if stage_counts is None:
        raise ReportingError("报告失败阶段汇总结构无效")
    if not stage_counts:
        lines.append("没有记录失败阶段。")
    else:
        lines.extend(
            [
                "| 阶段 | 失败案例数 |",
                "|---|---:|",
            ]
        )
        for stage, count in sorted(stage_counts.items()):
            lines.append(f"| {_markdown_cell(stage)} | {_markdown_cell(count)} |")

    lines.extend(["", "## 内部原因分布", ""])
    reason_counts = _object_mapping(summary.get("internal_reason_counts"))
    if reason_counts is None:
        raise ReportingError("报告内部原因汇总结构无效")
    if not reason_counts:
        lines.append("没有记录内部原因。")
    else:
        lines.extend(
            [
                "| 内部原因 | 案例数 |",
                "|---|---:|",
            ]
        )
        for reason, count in sorted(reason_counts.items()):
            lines.append(f"| {_markdown_cell(reason)} | {_markdown_cell(count)} |")

    lines.extend(
        [
            "",
            "## 分类准确率",
            "",
            "| 分类 | 执行准确率 |",
            "|---|---:|",
        ]
    )

    category_accuracy = _object_mapping(summary.get("category_accuracy"))
    if category_accuracy is None:
        raise ReportingError("报告分类汇总结构无效")
    for category, accuracy in sorted(category_accuracy.items()):
        lines.append(
            f"| {_markdown_cell(category)} | {_accuracy_text(accuracy)} |"
        )

    lines.extend(["", "## 链路关联", ""])
    lines.extend(
        [
            "| 案例 | Request ID | Trace ID |",
            "|---|---|---|",
        ]
    )
    for item in cases:
        case = _object_mapping(item)
        if case is None:
            raise ReportingError("报告案例结构无效")
        request_id = case.get("request_id") or "-"
        trace_id = case.get("trace_id") or "-"
        lines.append(
            "| {case_id} | {request_id} | {trace_id} |".format(
                case_id=_markdown_cell(case.get("case_id")),
                request_id=_markdown_cell(request_id),
                trace_id=_markdown_cell(trace_id),
            )
        )

    lines.extend(["", "## 失败与无效案例", ""])
    non_pass_cases: list[Mapping[str, object]] = []
    for item in cases:
        case = _object_mapping(item)
        if case is None:
            raise ReportingError("报告案例结构无效")
        if case.get("status") != "PASS":
            non_pass_cases.append(case)
    if not non_pass_cases:
        lines.append("无失败或无效案例。")
    else:
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
                    internal_reason=_markdown_cell(
                        case.get("internal_reason") or "未说明"
                    ),
                    reason=_markdown_cell(case.get("failure_reason") or "未说明"),
                )
            )

    lines.extend(["", "## 基线对比", ""])
    comparison = report.get("baseline_comparison")
    if comparison is None:
        lines.append("本次未执行自动基线比较；可与历史报告人工对照。")
    else:
        comparison_mapping = _object_mapping(comparison)
        if comparison_mapping is None:
            raise ReportingError("基线对比结构无效")
        if comparison_mapping.get("comparable") is not True:
            reason = _markdown_cell(comparison_mapping.get("reason") or "原因未知")
            lines.append(f"未形成有效基线对比：{reason}。")
        else:
            regressions = _string_list(comparison_mapping, "regressions")
            improvements = _string_list(comparison_mapping, "improvements")
            unchanged = _string_list(comparison_mapping, "unchanged")
            lines.extend(
                [
                    _comparison_line("能力回退", regressions),
                    _comparison_line("能力改善", improvements),
                    f"状态未变化 {len(unchanged)} 条。",
                ]
            )

    lines.extend(
        [
            "",
            "## 运行信息",
            "",
            f"- Run ID：{_markdown_cell(metadata.get('run_id'))}",
            f"- 运行时间：{_markdown_cell(metadata.get('created_at'))}",
            f"- Git Commit：{_markdown_cell(metadata.get('git_commit'))}",
            f"- Git Dirty：{_markdown_cell(metadata.get('git_dirty'))}",
            f"- Model：{_markdown_cell(metadata.get('model'))}",
            "",
        ]
    )
    return "\n".join(lines)


def compare_baseline(
    current: Mapping[str, object],
    baseline: Mapping[str, object],
) -> dict[str, object]:
    """仅在测试集和标准结果一致时声明回退或改善。"""

    current_metadata = _object_mapping(current.get("metadata"))
    baseline_metadata = _object_mapping(baseline.get("metadata"))
    if current_metadata is None or baseline_metadata is None:
        return _incomparable("报告缺少 metadata")

    for field, reason in (
        ("test_set_hash", "标准测试集不同"),
        ("reference_result_hash", "标准数据库结果不同"),
    ):
        if current_metadata.get(field) != baseline_metadata.get(field):
            return _incomparable(reason)

    current_cases = _case_statuses(current.get("cases"))
    baseline_cases = _case_statuses(baseline.get("cases"))
    if current_cases is None or baseline_cases is None:
        return _incomparable("报告案例结构无效")
    if set(current_cases) != set(baseline_cases):
        return _incomparable("报告案例集合不同")

    regressions: list[str] = []
    improvements: list[str] = []
    unchanged: list[str] = []
    for case_id in sorted(current_cases):
        before = baseline_cases[case_id]
        after = current_cases[case_id]
        if before == "PASS" and after == "FAIL":
            regressions.append(case_id)
        elif before == "FAIL" and after == "PASS":
            improvements.append(case_id)
        else:
            unchanged.append(case_id)

    return {
        "comparable": True,
        "reason": None,
        "regressions": regressions,
        "improvements": improvements,
        "unchanged": unchanged,
    }


def _failure_stage_counts(run: EvaluationRun) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in run.cases:
        if case.status == CaseStatus.PASS or not case.failure_stage:
            continue
        counts[case.failure_stage] = counts.get(case.failure_stage, 0) + 1
    return dict(sorted(counts.items()))


def _internal_reason_counts(run: EvaluationRun) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in run.cases:
        if case.status == CaseStatus.PASS or not case.internal_reason:
            continue
        counts[case.internal_reason] = counts.get(case.internal_reason, 0) + 1
    return dict(sorted(counts.items()))


def write_report(report: Mapping[str, object], path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError):
        raise ReportingError("评测报告无法写入") from None


def write_markdown_report(report: Mapping[str, object], path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown_report(report), encoding="utf-8")
    except OSError:
        raise ReportingError("评测总结报告无法写入") from None


def load_report(path: Path) -> dict[str, object]:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise ReportingError("评测报告无法读取") from None
    try:
        report = json.loads(content)
    except json.JSONDecodeError:
        raise ReportingError("评测报告不是合法 JSON") from None
    if not isinstance(report, dict):
        raise ReportingError("评测报告必须是 JSON 对象")
    return report


def _hash_file(path: Path) -> str:
    try:
        content = path.read_bytes()
    except OSError:
        raise ReportingError("指纹文件无法读取") from None
    return hashlib.sha256(content).hexdigest()


def _hash_named_files(paths: Mapping[str, Path]) -> str:
    digest = hashlib.sha256()
    for name, path in sorted(paths.items()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError:
            raise ReportingError("上下文文件无法读取") from None
        digest.update(b"\0")
    return digest.hexdigest()


def _hash_reference_results(results: Mapping[str, QueryData]) -> str:
    payload = [
        {
            "case_id": case_id,
            "column_count": len(data.columns),
            "rows": [
                [_canonical_value(value) for value in row]
                for row in data.rows
            ],
            "truncated": data.truncated,
        }
        for case_id, data in sorted(results.items())
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_value(value: object) -> object:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, (int, float, Decimal)):
        try:
            number = Decimal(str(value))
        except InvalidOperation:
            return {"type": type(value).__name__, "value": str(value)}
        if number.is_finite():
            normalized = Decimal(0) if number == 0 else number.normalize()
            return {"number": format(normalized, "f")}
        return {"number": str(number)}
    if isinstance(value, (datetime, date, time)):
        return {"type": type(value).__name__, "value": value.isoformat()}
    if isinstance(value, bytes):
        return {"type": "bytes", "value": value.hex()}
    return {"type": type(value).__name__, "value": str(value)}


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


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


def _object_mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, dict) else None


def _case_statuses(value: object) -> dict[str, str] | None:
    if not isinstance(value, list):
        return None
    statuses: dict[str, str] = {}
    for item in value:
        if not isinstance(item, dict):
            return None
        case_id = item.get("case_id")
        status = item.get("status")
        if not isinstance(case_id, str) or not isinstance(status, str):
            return None
        if case_id in statuses:
            return None
        statuses[case_id] = status
    return statuses


def _incomparable(reason: str) -> dict[str, object]:
    return {
        "comparable": False,
        "reason": reason,
        "regressions": [],
        "improvements": [],
        "unchanged": [],
    }
