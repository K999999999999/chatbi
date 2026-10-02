"""手动 Real E2E 报告验收测试。"""

import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.common.real_e2e_acceptance import (
    main,
    validate_real_e2e_summary,
)


class RealE2EAcceptanceTest(unittest.TestCase):
    def test_accepts_report_matching_the_loaded_case_set_size(self) -> None:
        for case_count in (21, 29):
            with self.subTest(case_count=case_count):
                self.assertEqual(
                    validate_real_e2e_summary(
                        self._summary(case_count),
                        expected_case_count=case_count,
                    ),
                    (),
                )

    def test_rejects_stale_total_case_count(self) -> None:
        errors = validate_real_e2e_summary(
            self._summary(21),
            expected_case_count=29,
        )

        self.assertTrue(any("total_cases" in error for error in errors))
        self.assertTrue(any("passed" in error for error in errors))

    def test_rejects_failures_and_invalid_cases(self) -> None:
        summary = self._summary(29)
        summary.update(
            {
                "valid_cases": 28,
                "passed": 28,
                "failed": 1,
                "invalid_cases": 1,
                "execution_accuracy": 28 / 29,
            }
        )

        errors = validate_real_e2e_summary(summary, expected_case_count=29)

        self.assertTrue(any("valid_cases" in error for error in errors))
        self.assertTrue(any("failed" in error for error in errors))
        self.assertTrue(any("invalid_cases" in error for error in errors))

    def test_cli_rejects_summary_without_report_identity(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path = root / "cases.json"
            report_path = root / "report.json"
            cases_path.write_text(
                json.dumps([{"id": "one"}, {"id": "two"}, {"id": "three"}]),
                encoding="utf-8",
            )
            report_path.write_text(
                json.dumps({"summary": self._summary(3)}),
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = main(
                    [
                        "--cases",
                        str(cases_path),
                        "--report",
                        str(report_path),
                        "--expected-commit",
                        "a" * 40,
                        "--expected-rag-version",
                        "test-rag",
                    ]
                )

        self.assertEqual(result, 1)
        self.assertIn("metadata", stderr.getvalue())

    @staticmethod
    def _summary(case_count: int) -> dict[str, object]:
        return {
            "total_cases": case_count,
            "valid_cases": case_count,
            "passed": case_count,
            "failed": 0,
            "invalid_cases": 0,
            "execution_accuracy": 1.0,
        }
