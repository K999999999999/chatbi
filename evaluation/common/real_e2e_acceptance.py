"""验收绑定 clean commit、案例集及资源身份的正式 Evaluation。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

SUITES = {
    "single_turn_query": "single_turn",
    "multi_turn_conversation": "multi_turn",
    "business_analysis": "business_analysis",
}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_HASH = re.compile(r"[0-9a-f]{64}")
_SHARED_METADATA = (
    "rag_asset_version",
    "sales_mart_seed_version",
    "sales_mart_data_hash",
    "sales_mart_data_hash_algorithm",
    "sales_mart_data_summary",
    "model",
    "temperature",
    "max_tokens",
    "model_endpoint_hash",
)


def validate_real_e2e_summary(
    summary: Mapping[str, object],
    *,
    expected_case_count: int,
) -> tuple[str, ...]:
    """保留单轮成绩检查入口；完整验收还必须校验报告身份。"""
    return _check_counts(summary, expected_case_count) + _check_accuracy(
        summary, ("execution_accuracy",)
    )


def _check_counts(summary: Mapping[str, object], count: int) -> tuple[str, ...]:
    expected = {
        "total_cases": count,
        "valid_cases": count,
        "passed": count,
        "failed": 0,
        "invalid_cases": 0,
    }
    return tuple(
        field
        for field, value in expected.items()
        if type(summary.get(field)) is not int or summary[field] != value
    )


def _check_accuracy(summary: Mapping[str, object], fields) -> tuple[str, ...]:
    return tuple(
        field
        for field in fields
        if type(summary.get(field)) not in (int, float) or summary[field] != 1.0
    )


def _case_results_errors(results, expected, *, id_field: str) -> list[str]:
    if not isinstance(results, list) or len(results) != len(expected):
        return [f"{id_field}: missing or extra results"]
    ids = [item.get(id_field) if isinstance(item, dict) else None for item in results]
    expected_ids = [item["id"] for item in expected]
    if any(not isinstance(value, str) for value in ids) or sorted(ids) != sorted(
        expected_ids
    ):
        return [f"{id_field}: unexpected or duplicate IDs"]
    return [
        f"{id_field}: non-PASS result"
        for item in results
        if item.get("status") != "PASS"
    ]


def validate_report(
    report: Mapping[str, object],
    cases_payload: bytes,
    *,
    suite: str,
    expected_commit: str,
    expected_rag_version: str,
) -> tuple[str, ...]:
    """校验实际文件指纹、全量案例 / 轮次及非敏感运行身份。"""
    payload = json.loads(cases_payload)
    cases = payload.get("cases") if isinstance(payload, dict) else payload
    if (
        not isinstance(cases, list)
        or not cases
        or any(
            not isinstance(case, dict) or not isinstance(case.get("id"), str)
            for case in cases
        )
    ):
        raise ValueError("invalid Golden Set case IDs")
    metadata = report.get("metadata")
    summary = report.get("summary")
    if not isinstance(metadata, dict):
        return ("metadata: missing or invalid",)
    if not isinstance(summary, dict):
        return ("summary: missing or invalid",)
    errors = []
    expected_identity = {
        "git_commit": expected_commit,
        "evaluation_suite": suite,
        "test_set_hash": hashlib.sha256(cases_payload).hexdigest(),
        "rag_asset_version": expected_rag_version,
    }
    errors.extend(
        f"metadata.{field}: identity mismatch"
        for field, value in expected_identity.items()
        if metadata.get(field) != value
    )
    if metadata.get("git_dirty") is not False:
        errors.append("metadata.git_dirty: must be false")
    for field in (
        "test_set_hash",
        "model_endpoint_hash",
        "context_hash",
        "reference_result_hash",
        "sales_mart_data_hash",
    ):
        value = metadata.get(field)
        if not isinstance(value, str) or _HASH.fullmatch(value) is None:
            errors.append(f"metadata.{field}: missing or invalid fingerprint")
    for field in ("model", "sales_mart_seed_version"):
        value = metadata.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"metadata.{field}: missing")
    if (
        metadata.get("sales_mart_data_hash_algorithm")
        != "sha256-sales-mart-row-snapshot-v1"
    ):
        errors.append("metadata.sales_mart_data_hash_algorithm: unsupported")
    data_summary = metadata.get("sales_mart_data_summary")
    if not isinstance(data_summary, dict) or not data_summary:
        errors.append("metadata.sales_mart_data_summary: missing")
    temperature = metadata.get("temperature")
    if type(temperature) not in (int, float) or not math.isfinite(temperature):
        errors.append("metadata.temperature: invalid")
    tokens = metadata.get("max_tokens")
    if type(tokens) is not int or tokens <= 0:
        errors.append("metadata.max_tokens: invalid")
    errors.extend(_check_counts(summary, len(cases)))
    accuracy_fields = {
        "single_turn_query": ("execution_accuracy", "case_accuracy"),
        "multi_turn_conversation": ("conversation_accuracy", "execution_accuracy"),
        "business_analysis": (
            "outcome_accuracy",
            "plan_accuracy",
            "summary_accuracy",
            "end_to_end_accuracy",
        ),
    }
    errors.extend(_check_accuracy(summary, accuracy_fields[suite]))
    results = report.get("cases")
    result_errors = _case_results_errors(results, cases, id_field="case_id")
    errors.extend(result_errors)
    if suite == "multi_turn_conversation":
        count = sum(len(case["turns"]) for case in cases)
        for field, value in {
            "total_turns": count,
            "valid_turns": count,
            "passed_turns": count,
            "failed_turns": 0,
            "invalid_turns": 0,
        }.items():
            if type(summary.get(field)) is not int or summary[field] != value:
                errors.append(field)
        if not result_errors:
            by_id = {case["id"]: case for case in cases}
            for result in results:
                errors.extend(
                    _case_results_errors(
                        result.get("turns"),
                        by_id[result["case_id"]]["turns"],
                        id_field="turn_id",
                    )
                )
    return tuple(errors)


def _read_report(path: Path) -> dict:
    report = json.loads(path.read_bytes())
    if not isinstance(report, dict):
        raise ValueError("report must be an object")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="验收正式三套基线或指定套件报告")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--report", type=Path, help="指定套件的 JSON 报告")
    inputs.add_argument(
        "--report-dir", type=Path, help="仅包含正式三套 JSON 报告的目录"
    )
    parser.add_argument("--cases", type=Path, help="指定套件的案例文件")
    parser.add_argument("--suite", choices=tuple(SUITES), default="single_turn_query")
    parser.add_argument(
        "--expected-commit", required=True, help="待验收的完整 clean commit SHA"
    )
    parser.add_argument(
        "--expected-rag-version", required=True, help="本次运行的发布 RAG 版本"
    )
    args = parser.parse_args(argv)
    if (
        re.fullmatch(r"[0-9a-f]{40}", args.expected_commit) is None
        or not args.expected_rag_version.strip()
    ):
        parser.error("expected commit / RAG version is invalid")
    if args.report_dir is not None and args.cases is not None:
        parser.error("--cases only applies to --report")
    try:
        errors = []
        if args.report is not None:
            path = (
                args.cases
                or PROJECT_ROOT
                / "evaluation/suites"
                / SUITES[args.suite]
                / "cases.json"
            )
            report = _read_report(args.report)
            errors.extend(
                validate_report(
                    report,
                    path.read_bytes(),
                    suite=args.suite,
                    expected_commit=args.expected_commit,
                    expected_rag_version=args.expected_rag_version,
                )
            )
            reports = {args.suite: report}
        else:
            paths = sorted(args.report_dir.glob("*.json"))
            reports = {}
            for path in paths:
                report = _read_report(path)
                metadata = report.get("metadata")
                suite = (
                    metadata.get("evaluation_suite")
                    if isinstance(metadata, dict)
                    else None
                )
                if (
                    not isinstance(suite, str)
                    or suite not in SUITES
                    or suite in reports
                ):
                    errors.append("missing, unsupported or duplicate evaluation_suite")
                    continue
                reports[suite] = report
                cases_path = (
                    PROJECT_ROOT / "evaluation/suites" / SUITES[suite] / "cases.json"
                )
                errors.extend(
                    f"{suite}: {error}"
                    for error in validate_report(
                        report,
                        cases_path.read_bytes(),
                        suite=suite,
                        expected_commit=args.expected_commit,
                        expected_rag_version=args.expected_rag_version,
                    )
                )
            if set(reports) != set(SUITES) or len(paths) != len(SUITES):
                errors.append("baseline requires exactly 3 complete suite reports")
            if set(reports) == set(SUITES):
                first = reports["single_turn_query"]["metadata"]
                for suite, report in reports.items():
                    for field in _SHARED_METADATA:
                        if report["metadata"].get(field) != first.get(field):
                            errors.append(f"{suite}: inconsistent metadata.{field}")
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        print("Real E2E acceptance input is unreadable or invalid.", file=sys.stderr)
        return 2
    if errors:
        print("Real E2E acceptance failed: " + "; ".join(errors), file=sys.stderr)
        return 1
    print(
        f"Real E2E acceptance: {len(reports)} complete suite(s), clean commit and resource identity verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
