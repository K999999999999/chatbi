"""按当前单轮 Golden Set 验收手动 Real E2E 报告。"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path


def validate_real_e2e_summary(
    summary: Mapping[str, object],
    *,
    expected_case_count: int,
) -> tuple[str, ...]:
    """返回与完整单轮套件 100% 通过门槛不符的字段。"""

    expected_values: dict[str, object] = {
        "total_cases": expected_case_count,
        "valid_cases": expected_case_count,
        "passed": expected_case_count,
        "failed": 0,
        "invalid_cases": 0,
        "execution_accuracy": 1.0,
    }
    return tuple(
        f"{field}: expected {expected!r}, got {summary.get(field)!r}"
        for field, expected in expected_values.items()
        if summary.get(field) != expected
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="按单轮 Golden Set 验收 Real E2E JSON 报告"
    )
    parser.add_argument("--cases", type=Path, required=True, help="本次运行的案例集")
    parser.add_argument(
        "--report", type=Path, required=True, help="Evaluation JSON 报告"
    )
    args = parser.parse_args(argv)

    try:
        cases = json.loads(args.cases.read_text(encoding="utf-8"))
        report = json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"Real E2E acceptance input could not be read: {error}", file=sys.stderr)
        return 2

    if not isinstance(cases, list) or not cases:
        print("Real E2E acceptance requires a non-empty cases array.", file=sys.stderr)
        return 2
    if not isinstance(report, dict) or not isinstance(report.get("summary"), dict):
        print("Real E2E report does not contain a summary object.", file=sys.stderr)
        return 2

    expected_case_count = len(cases)
    errors = validate_real_e2e_summary(
        report["summary"],
        expected_case_count=expected_case_count,
    )
    if errors:
        details = "; ".join(errors)
        print(f"Real E2E acceptance failed: {details}", file=sys.stderr)
        return 1

    print(
        "Real E2E acceptance: "
        f"{expected_case_count}/{expected_case_count} passed, "
        "Execution Accuracy=100%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
