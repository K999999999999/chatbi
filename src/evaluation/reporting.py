"""生成可复现的 Evaluation（评测）报告并比较 Baseline（基线）。"""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol

from src.online_query.contracts import QueryData

from .reporting_errors import ReportingError
from .reporting_markdown import render_markdown_report
from .runner import CaseStatus, EvaluationRun


class EvaluationReferenceRun(Protocol):
    reference_results: Mapping[str, QueryData]


SALES_MART_DATA_HASH_ALGORITHM = "sha256-sales-mart-row-snapshot-v1"


@dataclass(frozen=True, slots=True)
class SalesMartDataFingerprint:
    """非敏感的开发数据版本、摘要和实际记录 Hash。"""

    seed_version: str
    data_summary: Mapping[str, object]
    data_hash: str
    hash_algorithm: str


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
    sales_mart_seed_version: str | None = None
    sales_mart_data_summary: Mapping[str, object] | None = None
    sales_mart_data_hash: str | None = None
    sales_mart_data_hash_algorithm: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def collect_run_metadata(
    run: EvaluationReferenceRun,
    *,
    git_commit: str,
    git_dirty: bool,
    environ: Mapping[str, str],
    test_set_path: Path,
    context_paths: Mapping[str, Path],
    sales_mart_fingerprint: SalesMartDataFingerprint | None = None,
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
        sales_mart_seed_version=(
            sales_mart_fingerprint.seed_version
            if sales_mart_fingerprint is not None
            else None
        ),
        sales_mart_data_summary=(
            dict(sales_mart_fingerprint.data_summary)
            if sales_mart_fingerprint is not None
            else None
        ),
        sales_mart_data_hash=(
            sales_mart_fingerprint.data_hash
            if sales_mart_fingerprint is not None
            else None
        ),
        sales_mart_data_hash_algorithm=(
            sales_mart_fingerprint.hash_algorithm
            if sales_mart_fingerprint is not None
            else None
        ),
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


def compare_baseline(
    current: Mapping[str, object],
    baseline: Mapping[str, object],
) -> dict[str, object]:
    """仅在测试集和标准结果一致时声明回退或改善。"""

    current_metadata = _object_mapping(current.get("metadata"))
    baseline_metadata = _object_mapping(baseline.get("metadata"))
    if current_metadata is None or baseline_metadata is None:
        return _incomparable("报告缺少 metadata")

    current_test_hash = current_metadata.get("test_set_hash")
    baseline_test_hash = baseline_metadata.get("test_set_hash")
    if not _nonempty_string(current_test_hash) or not _nonempty_string(
        baseline_test_hash
    ):
        return _incomparable("报告缺少标准测试集 Hash")
    if current_test_hash != baseline_test_hash:
        return _incomparable("标准测试集不同")

    current_data_hash = current_metadata.get("sales_mart_data_hash")
    baseline_data_hash = baseline_metadata.get("sales_mart_data_hash")
    if not _is_sha256(current_data_hash):
        return _incomparable("当前报告缺少 Sales Mart 数据 Hash")
    if not _is_sha256(baseline_data_hash):
        return _incomparable("基线报告缺少 Sales Mart 数据 Hash")
    if current_data_hash != baseline_data_hash:
        return _incomparable("Sales Mart 数据 Hash 不同")

    current_seed = current_metadata.get("sales_mart_seed_version")
    baseline_seed = baseline_metadata.get("sales_mart_seed_version")
    if not _nonempty_string(current_seed):
        return _incomparable("当前报告缺少 Sales Mart Seed 版本")
    if not _nonempty_string(baseline_seed):
        return _incomparable("基线报告缺少 Sales Mart Seed 版本")

    current_hash_algorithm = current_metadata.get("sales_mart_data_hash_algorithm")
    baseline_hash_algorithm = baseline_metadata.get("sales_mart_data_hash_algorithm")
    if not _nonempty_string(current_hash_algorithm) or not _nonempty_string(
        baseline_hash_algorithm
    ):
        return _incomparable("报告缺少 Sales Mart 数据 Hash 算法")
    if (
        current_hash_algorithm != SALES_MART_DATA_HASH_ALGORITHM
        or current_hash_algorithm != baseline_hash_algorithm
    ):
        return _incomparable("Sales Mart 数据 Hash 算法不同")

    current_summary = current_metadata.get("sales_mart_data_summary")
    baseline_summary = baseline_metadata.get("sales_mart_data_summary")
    if not _valid_sales_mart_summary(current_summary) or not _valid_sales_mart_summary(
        baseline_summary
    ):
        return _incomparable("报告缺少 Sales Mart 数据摘要")
    if current_summary != baseline_summary:
        return _incomparable("Sales Mart 数据摘要不同")

    current_reference_hash = current_metadata.get("reference_result_hash")
    baseline_reference_hash = baseline_metadata.get("reference_result_hash")
    if not _nonempty_string(current_reference_hash) or not _nonempty_string(
        baseline_reference_hash
    ):
        return _incomparable("报告缺少标准数据库结果 Hash")
    if current_reference_hash != baseline_reference_hash:
        return _incomparable("标准数据库结果不同")

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
        "status": "COMPARABLE",
        "comparable": True,
        "reason": None,
        "seed_version_changed": (current_seed != baseline_seed),
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
            "rows": [[_canonical_value(value) for value in row] for row in data.rows],
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


def _object_mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, dict) else None


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def _valid_sales_mart_summary(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    counts = value.get("table_counts")
    total_rows = value.get("total_rows")
    date_range = value.get("date_range")
    if not isinstance(counts, Mapping) or not counts:
        return False
    if any(
        not _nonempty_string(table)
        or isinstance(count, bool)
        or not isinstance(count, int)
        or count < 0
        for table, count in counts.items()
    ):
        return False
    if (
        isinstance(total_rows, bool)
        or not isinstance(total_rows, int)
        or total_rows <= 0
    ):
        return False
    if sum(counts.values()) != total_rows:
        return False
    if not isinstance(date_range, Mapping):
        return False
    return _nonempty_string(date_range.get("start")) and _nonempty_string(
        date_range.get("end")
    )


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
        "status": "NOT_COMPARABLE",
        "comparable": False,
        "reason": reason,
        "seed_version_changed": None,
        "regressions": [],
        "improvements": [],
        "unchanged": [],
    }
