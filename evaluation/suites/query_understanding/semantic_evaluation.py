"""Query Understanding（查询理解）语义评测。"""

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from evaluation.common.reporting import model_configuration_fingerprint
from scripts.verification_report import (
    ReportWriteError,
    create_run_id,
    write_report_pair,
)
from src.online_query.query_understanding import (
    QueryUnderstandingClarificationRequired,
    SemanticQueryCandidate,
    SemanticQueryValidationError,
    candidate_from_payload,
    validate_candidate,
)
from src.online_query.query_understanding_llm import QueryUnderstandingAdapter

_REQUIRED_CASE_FIELDS = frozenset({"id", "question", "expected"})
_EXPECTED_FIELDS = frozenset({"query_type", "metrics", "dimensions", "time"})
_WHITESPACE_RE = re.compile(r"\s+")


class SemanticEvaluationLoadError(RuntimeError):
    """语义评测集无法加载。"""


@dataclass(frozen=True, slots=True)
class QueryUnderstandingCase:
    id: str
    question: str
    expected: SemanticQueryCandidate | None
    expected_outcome: str | None = None


@dataclass(frozen=True, slots=True)
class QueryUnderstandingEvaluation:
    case_id: str
    passed: bool
    failure_reason: str | None = None
    reason_code: str | None = None


def create_query_understanding_report(
    results: Sequence[QueryUnderstandingEvaluation],
    *,
    git_commit: str | None,
    git_dirty: bool | None,
    model: str,
    cases_path: Path,
    run_id: str | None = None,
    test_set_hash: str | None = None,
    model_configuration: Mapping[str, object] | None = None,
    provenance: Mapping[str, object] | None = None,
    created_at: datetime | None = None,
) -> dict[str, object]:
    """创建不包含 Prompt 或模型原始输出的语义评测报告。"""

    commit = git_commit.strip() if isinstance(git_commit, str) else None
    if not isinstance(model, str) or not model.strip():
        raise SemanticEvaluationLoadError("语义评测报告缺少 LLM_MODEL")
    created = datetime.now(UTC) if created_at is None else created_at
    if created.tzinfo is None:
        raise SemanticEvaluationLoadError("语义评测报告时间必须包含时区")
    created_utc = created.astimezone(UTC)
    effective_model = dict(model_configuration) if model_configuration else None
    passed = sum(item.passed for item in results)
    failed = len(results) - passed
    return {
        "metadata": {
            "run_id": (
                run_id
                if run_id is not None
                else create_run_id(
                    commit or "", suite="query-understanding", now=created_utc
                )
            ),
            "created_at": created_utc.isoformat().replace("+00:00", "Z"),
            "git_commit": commit,
            "git_dirty": git_dirty,
            "model": model.strip(),
            "cases_file": cases_path.name,
            "evaluation_suite": "query_understanding",
            "test_set_hash": test_set_hash,
            "temperature": (
                effective_model.get("temperature")
                if effective_model is not None
                else None
            ),
            "max_tokens": (
                effective_model.get("max_tokens")
                if effective_model is not None
                else None
            ),
            "timeout_seconds": (
                effective_model.get("timeout_seconds")
                if effective_model is not None
                else None
            ),
            "model_endpoint_hash": (
                effective_model.get("model_endpoint_hash")
                if effective_model is not None
                else None
            ),
            "model_configuration": effective_model,
            "model_configuration_hash": (
                model_configuration_fingerprint(effective_model)
                if effective_model is not None
                else None
            ),
            "provenance": dict(provenance) if provenance is not None else None,
        },
        "summary": {
            "total_cases": len(results),
            "passed": passed,
            "failed": failed,
            "accuracy": passed / len(results) if results else None,
            "reason_code_counts": _reason_code_counts(results),
        },
        "cases": [
            {
                "case_id": item.case_id,
                "status": "PASS" if item.passed else "FAIL",
                "failure_reason": item.failure_reason,
                "reason_code": item.reason_code,
            }
            for item in results
        ],
    }


def render_query_understanding_report(report: Mapping[str, object]) -> str:
    """渲染语义评测的可读摘要。"""

    metadata = report.get("metadata")
    summary = report.get("summary")
    cases = report.get("cases")
    if not isinstance(metadata, Mapping) or not isinstance(summary, Mapping):
        raise SemanticEvaluationLoadError("语义评测报告结构无效")
    if not isinstance(cases, list):
        raise SemanticEvaluationLoadError("语义评测报告案例结构无效")

    total = summary.get("total_cases", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    accuracy = summary.get("accuracy")
    accuracy_text = "N/A" if accuracy is None else f"{float(accuracy):.2%}"
    lines = [
        "# Query Understanding Evaluation（查询理解评测）",
        "",
        f"结果：{'PASS' if failed == 0 else 'FAIL'}",
        f"案例：{total}，通过：{passed}，失败：{failed}，准确率：{accuracy_text}",
        "",
        "## 失败案例",
        "",
    ]
    failures = [
        item
        for item in cases
        if isinstance(item, Mapping) and item.get("status") != "PASS"
    ]
    if not failures:
        lines.append("无失败案例。")
    else:
        lines.extend(
            [
                "| 案例 | 内部原因 | 原因 |",
                "|---|---|---|",
            ]
        )
        for item in failures:
            lines.append(
                "| {case_id} | {reason_code} | {reason} |".format(
                    case_id=item.get("case_id", ""),
                    reason_code=item.get("reason_code") or "未说明",
                    reason=item.get("failure_reason") or "未说明",
                )
            )
    lines.extend(
        [
            "",
            "## 运行信息",
            "",
            f"- Run ID：{metadata.get('run_id', '')}",
            f"- 运行时间：{metadata.get('created_at', '')}",
            f"- Git Commit：{metadata.get('git_commit', '')}",
            f"- Git Dirty：{metadata.get('git_dirty', '')}",
            f"- Model：{metadata.get('model', '')}",
            f"- Temperature：{metadata.get('temperature', '')}",
            f"- Max Tokens：{metadata.get('max_tokens', '')}",
            f"- Timeout：{metadata.get('timeout_seconds', '')}",
            f"- Endpoint Hash：{metadata.get('model_endpoint_hash', '')}",
            f"- Test Set Hash：{metadata.get('test_set_hash', '')}",
            f"- Run Consistency：{_provenance_consistency(metadata)}",
            "",
        ]
    )
    return "\n".join(lines)


def write_query_understanding_report(
    report: Mapping[str, object],
    json_path: Path,
    markdown_path: Path,
) -> None:
    """写入语义评测 JSON 与 Markdown 报告。"""

    metadata = report.get("metadata")
    run_id = metadata.get("run_id") if isinstance(metadata, Mapping) else None
    if (
        not isinstance(run_id, str)
        or json_path.parent != markdown_path.parent
        or json_path.stem != run_id
        or markdown_path.stem != run_id
    ):
        raise SemanticEvaluationLoadError("语义评测 JSON / Markdown Run ID 不一致")
    try:
        write_report_pair(
            json_path.parent,
            run_id,
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            render_query_understanding_report(report),
        )
    except (OSError, ReportWriteError, TypeError, ValueError):
        raise SemanticEvaluationLoadError("语义评测报告无法写入") from None


def _provenance_consistency(metadata: Mapping[str, object]) -> str:
    provenance = metadata.get("provenance")
    if not isinstance(provenance, Mapping):
        return "未确认"
    consistency = provenance.get("consistency")
    return consistency if isinstance(consistency, str) else "未确认"


def load_query_understanding_cases(
    path: Path,
) -> tuple[QueryUnderstandingCase, ...]:
    """加载只描述业务语义的评测案例。"""

    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError):
        raise SemanticEvaluationLoadError(
            "Query Understanding 评测集无法读取"
        ) from None
    except json.JSONDecodeError:
        raise SemanticEvaluationLoadError(
            "Query Understanding 评测集不是合法 JSON"
        ) from None

    if not isinstance(records, list) or not records:
        raise SemanticEvaluationLoadError("Query Understanding 评测集必须是非空数组")

    cases: list[QueryUnderstandingCase] = []
    ids: set[str] = set()
    for index, record in enumerate(records, 1):
        if not isinstance(record, Mapping):
            raise SemanticEvaluationLoadError(f"第 {index} 条语义案例必须是对象")
        missing = _REQUIRED_CASE_FIELDS - set(record)
        extra = set(record) - _REQUIRED_CASE_FIELDS
        if missing or extra:
            raise SemanticEvaluationLoadError(f"第 {index} 条语义案例字段无效")
        case_id = _required_text(record["id"], f"第 {index} 条案例 id")
        question = _required_text(record["question"], f"第 {index} 条案例 question")
        if case_id in ids:
            raise SemanticEvaluationLoadError("Query Understanding 评测集存在重复 id")
        ids.add(case_id)
        expected = _expected_candidate(record["expected"], index)
        cases.append(
            QueryUnderstandingCase(
                id=case_id,
                question=question,
                expected=expected[0],
                expected_outcome=expected[1],
            )
        )
    return tuple(cases)


def evaluate_query_understanding(
    cases: Sequence[QueryUnderstandingCase],
    adapter: QueryUnderstandingAdapter,
) -> tuple[QueryUnderstandingEvaluation, ...]:
    """调用 Adapter 并比较结构化语义，不执行 Retrieval 或 SQL。"""

    results: list[QueryUnderstandingEvaluation] = []
    for case in cases:
        try:
            actual = adapter.understand(case.question)
            if case.expected_outcome is not None:
                if (
                    not isinstance(actual, QueryUnderstandingClarificationRequired)
                    or actual.outcome != case.expected_outcome
                ):
                    results.append(
                        QueryUnderstandingEvaluation(
                            case_id=case.id,
                            passed=False,
                            failure_reason="受控结果与期望不一致",
                            reason_code="OUTCOME_MISMATCH",
                        )
                    )
                else:
                    results.append(
                        QueryUnderstandingEvaluation(case_id=case.id, passed=True)
                    )
                continue
            if not isinstance(actual, SemanticQueryCandidate):
                raise SemanticQueryValidationError(
                    "期望结构化候选",
                    reason="CANDIDATE_TYPE_INVALID",
                )
            validate_candidate(actual, original_question=case.question)
        except SemanticQueryValidationError as exc:
            results.append(
                QueryUnderstandingEvaluation(
                    case_id=case.id,
                    passed=False,
                    failure_reason="结构化查询未通过确定性校验",
                    reason_code=exc.reason,
                )
            )
            continue
        except Exception as exc:  # noqa: BLE001 - 单案例失败不能中断整套评测
            results.append(
                QueryUnderstandingEvaluation(
                    case_id=case.id,
                    passed=False,
                    failure_reason="Query Understanding 调用失败",
                    reason_code=_reason_code(exc, "ADAPTER_ERROR"),
                )
            )
            continue

        assert case.expected is not None
        mismatch = _semantic_mismatch(actual, case.expected)
        if mismatch is None:
            results.append(QueryUnderstandingEvaluation(case_id=case.id, passed=True))
        else:
            reason_code, reason = mismatch
            results.append(
                QueryUnderstandingEvaluation(
                    case_id=case.id,
                    passed=False,
                    failure_reason=reason,
                    reason_code=reason_code,
                )
            )
    return tuple(results)


def _expected_candidate(
    value: object, index: int
) -> tuple[SemanticQueryCandidate | None, str | None]:
    if not isinstance(value, Mapping):
        raise SemanticEvaluationLoadError(f"第 {index} 条案例 expected 必须是对象")
    if set(value) == {"outcome"}:
        if value["outcome"] != "clarification_required":
            raise SemanticEvaluationLoadError(f"第 {index} 条案例 outcome 不受支持")
        return None, "clarification_required"
    missing = _EXPECTED_FIELDS - set(value)
    extra = set(value) - _EXPECTED_FIELDS
    if missing or extra:
        raise SemanticEvaluationLoadError(f"第 {index} 条案例 expected 字段无效")
    try:
        return (
            candidate_from_payload(
                {
                    "query_type": value["query_type"],
                    "subjects": [],
                    "metrics": value["metrics"],
                    "dimensions": value["dimensions"],
                    "time": value["time"],
                    "filters": [],
                }
            ),
            None,
        )
    except SemanticQueryValidationError as exc:
        raise SemanticEvaluationLoadError(
            f"第 {index} 条案例 expected 无效：{exc.reason}"
        ) from None


def _semantic_mismatch(
    actual: SemanticQueryCandidate,
    expected: SemanticQueryCandidate,
) -> tuple[str, str] | None:
    if actual.query_type is not expected.query_type:
        return "QUERY_TYPE_MISMATCH", "query_type 与期望不一致"
    if actual.metrics != expected.metrics:
        return "METRICS_MISMATCH", "metrics 与期望不一致"
    if actual.dimensions != expected.dimensions:
        return "DIMENSIONS_MISMATCH", "dimensions 与期望不一致"
    if _time_signature(actual) != _time_signature(expected):
        return "TIME_MISMATCH", "time 与期望不一致"
    return None


def _time_signature(candidate: SemanticQueryCandidate) -> tuple[str, str] | None:
    if candidate.time is None:
        return None
    return (
        _WHITESPACE_RE.sub("", candidate.time.text),
        candidate.time.granularity.value,
    )


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SemanticEvaluationLoadError(f"{label} 必须是非空字符串")
    return value.strip()


def _reason_code(exc: Exception, fallback: str) -> str:
    reason = getattr(exc, "reason", None)
    return reason.strip() if isinstance(reason, str) and reason.strip() else fallback


def _reason_code_counts(
    results: Sequence[QueryUnderstandingEvaluation],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in results:
        if item.passed or not item.reason_code:
            continue
        counts[item.reason_code] = counts.get(item.reason_code, 0) + 1
    return dict(sorted(counts.items()))
