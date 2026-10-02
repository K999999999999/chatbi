"""正式基线必须绑定当前身份和三套完整结果。"""

import copy
import hashlib
import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from evaluation.common.real_e2e_acceptance import main


ROOT = Path(__file__).resolve().parents[3]
COMMIT = "a" * 40
RAG_VERSION = "test-rag"
SUITES = {
    "single_turn_query": "single_turn",
    "multi_turn_conversation": "multi_turn",
    "business_analysis": "business_analysis",
}


def passing_report(suite):
    path = ROOT / "evaluation" / "suites" / SUITES[suite] / "cases.json"
    payload = json.loads(path.read_bytes())
    cases = payload["cases"] if isinstance(payload, dict) else payload
    summary = {
        "total_cases": len(cases),
        "valid_cases": len(cases),
        "passed": len(cases),
        "failed": 0,
        "invalid_cases": 0,
        "execution_accuracy": 1.0,
        "case_accuracy": 1.0,
        "conversation_accuracy": 1.0,
        "end_to_end_accuracy": 1.0,
        "outcome_accuracy": 1.0,
        "plan_accuracy": 1.0,
        "summary_accuracy": 1.0,
    }
    results = [{"case_id": case["id"], "status": "PASS"} for case in cases]
    if suite == "multi_turn_conversation":
        total = sum(len(case["turns"]) for case in cases)
        summary.update(
            total_turns=total,
            valid_turns=total,
            passed_turns=total,
            failed_turns=0,
            invalid_turns=0,
        )
        for result, case in zip(results, cases, strict=True):
            result["turns"] = [
                {"turn_id": turn["id"], "status": "PASS"} for turn in case["turns"]
            ]
    return {
        "metadata": {
            "git_commit": COMMIT,
            "git_dirty": False,
            "evaluation_suite": suite,
            "test_set_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
            "rag_asset_version": RAG_VERSION,
            "model": "test-model",
            "temperature": 0.1,
            "max_tokens": 4096,
            "model_endpoint_hash": "b" * 64,
            "context_hash": "c" * 64,
            "reference_result_hash": "d" * 64,
            "sales_mart_seed_version": "test-seed",
            "sales_mart_data_hash": "e" * 64,
            "sales_mart_data_hash_algorithm": "sha256-sales-mart-row-snapshot-v1",
            "sales_mart_data_summary": {"table_counts": {"test": 1}, "total_rows": 1},
        },
        "summary": summary,
        "cases": results,
    }


class BaselineAcceptanceTest(unittest.TestCase):
    def setUp(self):
        self.reports = {suite: passing_report(suite) for suite in SUITES}

    def run_acceptance(self, reports=None):
        with TemporaryDirectory() as directory:
            for name, report in (self.reports if reports is None else reports).items():
                (Path(directory) / f"{name}.json").write_text(json.dumps(report))
            output, errors = StringIO(), StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                result = main(
                    [
                        "--report-dir",
                        directory,
                        "--expected-commit",
                        COMMIT,
                        "--expected-rag-version",
                        RAG_VERSION,
                    ]
                )
            return result, output.getvalue(), errors.getvalue()

    def test_accepts_complete_baseline(self):
        result, output, errors = self.run_acceptance()
        self.assertEqual(result, 0, errors)
        self.assertIn("3", output)

    def test_rejects_old_dirty_missing_and_wrong_identity(self):
        for field, value in (
            ("git_commit", "f" * 40),
            ("git_dirty", True),
            ("git_dirty", 0),
            ("test_set_hash", "f" * 64),
            ("rag_asset_version", "old-rag"),
            ("model", ""),
            ("sales_mart_data_hash", None),
        ):
            with self.subTest(field=field, value=value):
                reports = copy.deepcopy(self.reports)
                reports["single_turn_query"]["metadata"][field] = value
                self.assertEqual(self.run_acceptance(reports)[0], 1)

    def test_rejects_missing_or_duplicate_suite(self):
        reports = copy.deepcopy(self.reports)
        del reports["business_analysis"]
        self.assertEqual(self.run_acceptance(reports)[0], 1)
        reports["duplicate"] = reports["single_turn_query"]
        self.assertEqual(self.run_acceptance(reports)[0], 1)

    def test_rejects_inconsistent_resources_or_model(self):
        for field, value in (
            ("sales_mart_data_hash", "f" * 64),
            ("model", "another-model"),
            ("max_tokens", 1200),
            ("temperature", 0.0),
            ("sales_mart_seed_version", "other"),
        ):
            with self.subTest(field=field):
                reports = copy.deepcopy(self.reports)
                reports["business_analysis"]["metadata"][field] = value
                self.assertEqual(self.run_acceptance(reports)[0], 1)

    def test_rejects_wrong_cases_even_with_passing_summary(self):
        for suite in SUITES:
            with self.subTest(suite=suite):
                reports = copy.deepcopy(self.reports)
                reports[suite]["cases"][0]["case_id"] = "unknown-case"
                self.assertEqual(self.run_acceptance(reports)[0], 1)

    def test_rejects_duplicate_and_failed_case_results(self):
        reports = copy.deepcopy(self.reports)
        results = reports["single_turn_query"]["cases"]
        results[1]["case_id"] = results[0]["case_id"]
        self.assertEqual(self.run_acceptance(reports)[0], 1)
        reports = copy.deepcopy(self.reports)
        reports["business_analysis"]["cases"][0]["status"] = "FAIL"
        self.assertEqual(self.run_acceptance(reports)[0], 1)

    def test_rejects_missing_metadata_and_invalid_json(self):
        reports = copy.deepcopy(self.reports)
        del reports["single_turn_query"]["metadata"]
        self.assertEqual(self.run_acceptance(reports)[0], 1)
        with TemporaryDirectory() as directory:
            (Path(directory) / "broken.json").write_text("{")
            with redirect_stderr(StringIO()):
                result = main(
                    [
                        "--report-dir",
                        directory,
                        "--expected-commit",
                        COMMIT,
                        "--expected-rag-version",
                        RAG_VERSION,
                    ]
                )
            self.assertEqual(result, 2)

    def test_accepts_single_report_and_rejects_wrong_suite(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text(json.dumps(self.reports["single_turn_query"]))
            arguments = [
                "--report",
                str(path),
                "--expected-commit",
                COMMIT,
                "--expected-rag-version",
                RAG_VERSION,
            ]
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(main(arguments), 0)
                self.assertEqual(main(arguments + ["--suite", "business_analysis"]), 1)

    def test_rejects_failed_or_invalid_cases(self):
        for suite in SUITES:
            with self.subTest(suite=suite):
                reports = copy.deepcopy(self.reports)
                reports[suite]["summary"]["failed"] = 1
                self.assertEqual(self.run_acceptance(reports)[0], 1)

    def test_rejects_missing_turn_and_boolean_counts(self):
        reports = copy.deepcopy(self.reports)
        reports["multi_turn_conversation"]["cases"][0]["turns"].pop()
        self.assertEqual(self.run_acceptance(reports)[0], 1)
        reports = copy.deepcopy(self.reports)
        reports["single_turn_query"]["summary"]["failed"] = False
        self.assertEqual(self.run_acceptance(reports)[0], 1)

    def test_suite_specific_context_and_reference_hashes_may_differ(self):
        self.reports["business_analysis"]["metadata"]["context_hash"] = "f" * 64
        self.reports["business_analysis"]["metadata"]["reference_result_hash"] = (
            "0" * 64
        )
        self.assertEqual(self.run_acceptance()[0], 0)
