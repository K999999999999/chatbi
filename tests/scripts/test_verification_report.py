"""运行身份采集与排他报告保存测试。"""

import json
import hashlib
import subprocess
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.verification_report import (
    ReportWriteError,
    finish_verification,
    finish_run,
    parse_junit_counts,
    parse_playwright_counts,
    start_run,
    start_verification,
    write_verification_summary,
    write_report_pair,
)

ROOT = Path(__file__).resolve().parents[2]


class VerificationReportTest(unittest.TestCase):
    def test_junit_counts_report_pass_fail_error_and_skipped_separately(self) -> None:
        with TemporaryDirectory() as directory:
            report = Path(directory) / "pytest.xml"
            report.write_text(
                """<testsuites><testsuite>
                <testcase classname="suite" name="passed" />
                <testcase classname="suite" name="failed"><failure /></testcase>
                <testcase classname="suite" name="errored"><error /></testcase>
                <testcase classname="suite" name="skipped"><skipped /></testcase>
                </testsuite></testsuites>""",
                encoding="utf-8",
            )

            counts = parse_junit_counts(report)

        self.assertEqual(
            counts,
            {"total": 4, "passed": 1, "failed": 1, "errors": 1, "skipped": 1},
        )

    def test_playwright_counts_use_reporter_json_not_console_output(self) -> None:
        with TemporaryDirectory() as directory:
            report = Path(directory) / "playwright.json"
            report.write_text(
                json.dumps(
                    {
                        "stats": {
                            "expected": 5,
                            "unexpected": 1,
                            "flaky": 0,
                            "skipped": 2,
                            "interrupted": 0,
                        }
                    }
                ),
                encoding="utf-8",
            )

            counts = parse_playwright_counts(report)

        self.assertEqual(
            counts,
            {"total": 8, "passed": 5, "failed": 1, "errors": 0, "skipped": 2},
        )

    def test_playwright_standard_json_without_interrupted_field_is_supported(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            report = Path(directory) / "playwright.json"
            report.write_text(
                json.dumps(
                    {
                        "stats": {
                            "expected": 3,
                            "unexpected": 0,
                            "flaky": 1,
                            "skipped": 0,
                        }
                    }
                ),
                encoding="utf-8",
            )

            counts = parse_playwright_counts(report)

        self.assertEqual(
            counts,
            {"total": 4, "passed": 3, "failed": 1, "errors": 0, "skipped": 0},
        )

    def test_report_cli_publishes_machine_counts_and_source_provenance(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repository"
            repository.mkdir()
            source = repository / "app.py"
            source.write_text("value = 1\n", encoding="utf-8")
            self._initialize_repository(repository, source)
            reports = root / "reports"
            command = [
                sys.executable,
                "-m",
                "scripts.verification_report",
                "begin",
                "--repository-root",
                str(repository),
                "--reports-directory",
                str(reports),
                "--kind",
                "test",
                "--scope",
                "python",
                "--step",
                "pytest",
                "--runner",
                "dev-container",
                "--runtime",
                "python",
            ]
            started = subprocess.run(
                command,
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(started.returncode, 0, started.stderr)
            run_id = started.stdout.strip()
            junit = reports / run_id / "pytest.xml"
            junit.write_text(
                "<testsuite><testcase name='one'/><testcase name='two'>"
                "<skipped/></testcase></testsuite>",
                encoding="utf-8",
            )

            for arguments in (
                [
                    "step-start",
                    "--reports-directory",
                    str(reports),
                    "--run-id",
                    run_id,
                    "--name",
                    "pytest",
                ],
                [
                    "step-finish",
                    "--reports-directory",
                    str(reports),
                    "--run-id",
                    run_id,
                    "--name",
                    "pytest",
                    "--exit-code",
                    "0",
                    "--junit",
                    str(junit),
                ],
                [
                    "finish",
                    "--repository-root",
                    str(repository),
                    "--reports-directory",
                    str(reports),
                    "--run-id",
                    run_id,
                    "--exit-code",
                    "0",
                    "--cleanup-status",
                    "not_applicable",
                ],
            ):
                result = subprocess.run(
                    [sys.executable, "-m", "scripts.verification_report", *arguments],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((reports / f"{run_id}.json").read_text())

        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(
            report["counts"],
            {"total": 2, "passed": 1, "failed": 0, "errors": 0, "skipped": 1},
        )
        self.assertEqual(report["provenance"]["consistency"], "stable")
        self.assertEqual(report["artifacts"], [f"{run_id}/pytest.xml"])

    def test_dev_container_summary_records_lockfiles_and_image_content_ids(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repository"
            frontend = repository / "frontend"
            frontend.mkdir(parents=True)
            source = repository / "app.py"
            uv_lock = repository / "uv.lock"
            npm_lock = frontend / "package-lock.json"
            source.write_text("value = 1\n", encoding="utf-8")
            uv_lock.write_text("python-lock-v1\n", encoding="utf-8")
            npm_lock.write_text("node-lock-v1\n", encoding="utf-8")
            self._initialize_repository(repository, source, uv_lock, npm_lock)
            reports = root / "reports"
            started = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.verification_report",
                    "begin",
                    "--repository-root",
                    str(repository),
                    "--reports-directory",
                    str(reports),
                    "--kind",
                    "check",
                    "--scope",
                    "all",
                    "--step",
                    "python",
                    "--step",
                    "web-build",
                    "--runner",
                    "dev-container",
                    "--runtime",
                    "python",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(started.returncode, 0, started.stderr)
            run_id = started.stdout.strip()
            for name in ("python", "web-build"):
                for command in ("step-start", "step-finish"):
                    arguments = [
                        sys.executable,
                        "-m",
                        "scripts.verification_report",
                        command,
                        "--reports-directory",
                        str(reports),
                        "--run-id",
                        run_id,
                        "--name",
                        name,
                    ]
                    if command == "step-finish":
                        arguments.extend(
                            ["--exit-code", "0", "--counts-not-applicable"]
                        )
                    result = subprocess.run(
                        arguments,
                        cwd=ROOT,
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)

            python_image = "sha256:" + "1" * 64
            node_image = "sha256:" + "2" * 64
            finished = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.verification_report",
                    "finish",
                    "--repository-root",
                    str(repository),
                    "--reports-directory",
                    str(reports),
                    "--run-id",
                    run_id,
                    "--exit-code",
                    "0",
                    "--cleanup-status",
                    "not_applicable",
                    "--container-image",
                    f"python={python_image}",
                    "--container-image",
                    f"node={node_image}",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(finished.returncode, 0, finished.stderr)
            report = json.loads((reports / f"{run_id}.json").read_text())

        self.assertEqual(report["status"], "passed")
        self.assertEqual(
            report["environment"]["lockfiles"],
            {
                "uv": hashlib.sha256(b"python-lock-v1\n").hexdigest(),
                "npm": hashlib.sha256(b"node-lock-v1\n").hexdigest(),
            },
        )
        self.assertTrue(report["environment"]["lockfiles_verified"])
        self.assertEqual(
            report["environment"]["container_images"],
            {"python": python_image, "node": node_image},
        )

    def test_missing_required_container_image_prevents_a_passed_summary(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repository"
            repository.mkdir()
            source = repository / "app.py"
            lock = repository / "uv.lock"
            source.write_text("value = 1\n", encoding="utf-8")
            lock.write_text("python-lock-v1\n", encoding="utf-8")
            self._initialize_repository(repository, source, lock)
            reports = root / "reports"
            started = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.verification_report",
                    "begin",
                    "--repository-root",
                    str(repository),
                    "--reports-directory",
                    str(reports),
                    "--kind",
                    "check",
                    "--scope",
                    "all",
                    "--step",
                    "python",
                    "--step",
                    "web-build",
                    "--runner",
                    "dev-container",
                    "--runtime",
                    "python",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(started.returncode, 0, started.stderr)
            run_id = started.stdout.strip()
            for name in ("python", "web-build"):
                for command in ("step-start", "step-finish"):
                    arguments = [
                        sys.executable,
                        "-m",
                        "scripts.verification_report",
                        command,
                        "--reports-directory",
                        str(reports),
                        "--run-id",
                        run_id,
                        "--name",
                        name,
                    ]
                    if command == "step-finish":
                        arguments.extend(
                            ["--exit-code", "0", "--counts-not-applicable"]
                        )
                    result = subprocess.run(
                        arguments,
                        cwd=ROOT,
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
            finished = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.verification_report",
                    "finish",
                    "--repository-root",
                    str(repository),
                    "--reports-directory",
                    str(reports),
                    "--run-id",
                    run_id,
                    "--exit-code",
                    "0",
                    "--cleanup-status",
                    "not_applicable",
                    "--container-image",
                    "python=sha256:" + "1" * 64,
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(finished.returncode, 0, finished.stderr)
            report = json.loads((reports / f"{run_id}.json").read_text())

        self.assertEqual(report["status"], "incomplete")

    def test_report_cli_can_parse_private_machine_output_and_publish_elsewhere(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repository"
            repository.mkdir()
            source = repository / "app.py"
            source.write_text("value = 1\n", encoding="utf-8")
            self._initialize_repository(repository, source)
            state_directory = root / "private-staging"
            published_directory = root / "published" / "browser-real"
            artifacts_directory = root / "published" / "browser-real-artifacts"
            artifacts_directory.mkdir(parents=True)
            (artifacts_directory / "run-artifacts").mkdir()
            (artifacts_directory / "run-artifacts" / "runtime.json").write_text(
                '{"model_config_sha256":"safe-hash"}', encoding="utf-8"
            )
            playwright = root / "private-staging" / "playwright.json"
            playwright.parent.mkdir()
            playwright.write_text(
                json.dumps(
                    {
                        "stats": {
                            "expected": 2,
                            "unexpected": 0,
                            "flaky": 0,
                            "skipped": 1,
                            "interrupted": 0,
                        }
                    }
                ),
                encoding="utf-8",
            )
            started = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.verification_report",
                    "begin",
                    "--repository-root",
                    str(repository),
                    "--reports-directory",
                    str(state_directory),
                    "--kind",
                    "business-acceptance",
                    "--scope",
                    "container-dev",
                    "--step",
                    "browser",
                    "--counted-step",
                    "browser",
                    "--runner",
                    "dev-container",
                    "--runtime",
                    "browser",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(started.returncode, 0, started.stderr)
            run_id = started.stdout.strip()
            for arguments in (
                [
                    "step-start",
                    "--reports-directory",
                    str(state_directory),
                    "--run-id",
                    run_id,
                    "--name",
                    "browser",
                ],
                [
                    "step-finish",
                    "--reports-directory",
                    str(state_directory),
                    "--run-id",
                    run_id,
                    "--name",
                    "browser",
                    "--exit-code",
                    "0",
                    "--playwright",
                    str(playwright),
                    "--counts-only",
                ],
                [
                    "finish",
                    "--repository-root",
                    str(repository),
                    "--reports-directory",
                    str(state_directory),
                    "--run-id",
                    run_id,
                    "--exit-code",
                    "0",
                    "--cleanup-status",
                    "passed",
                    "--output-directory",
                    str(published_directory),
                    "--artifact-root",
                    str(root / "published"),
                    "--artifact",
                    "browser-real-artifacts/run-artifacts/runtime.json",
                ],
            ):
                result = subprocess.run(
                    [sys.executable, "-m", "scripts.verification_report", *arguments],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            report = json.loads((published_directory / f"{run_id}.json").read_text())

        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["business_acceptance_status"], "incomplete")
        self.assertEqual(
            report["counts"],
            {"total": 3, "passed": 2, "failed": 0, "errors": 0, "skipped": 1},
        )
        self.assertEqual(
            report["artifacts"], ["browser-real-artifacts/run-artifacts/runtime.json"]
        )

    def test_verification_summary_keeps_source_change_and_step_failures_visible(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "app.py"
            source.write_text("value = 1\n", encoding="utf-8")
            self._initialize_repository(root, source)
            now = datetime(2026, 10, 15, 12, tzinfo=UTC)
            start = start_verification(
                root,
                kind="test",
                scope="all",
                parameters={"filtered": False},
                environment={"runner": "dev-container"},
                planned_steps=("python", "database"),
                now=now,
            )
            source.write_text("value = 2\n", encoding="utf-8")

            report = finish_verification(
                start,
                root,
                exit_code=1,
                counts={
                    "total": 3,
                    "passed": 2,
                    "failed": 1,
                    "errors": 0,
                    "skipped": 0,
                },
                steps=(
                    {"name": "python", "status": "failed", "exit_code": 1},
                    {"name": "database", "status": "not_run", "exit_code": None},
                ),
                cleanup_status="passed",
                now=now.replace(minute=1),
            )

        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["provenance"]["consistency"], "changed")
        self.assertEqual(report["counts"]["failed"], 1)
        self.assertEqual(
            [step["status"] for step in report["steps"]], ["failed", "not_run"]
        )

    def test_missing_test_counts_prevent_a_complete_pass(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "app.py"
            source.write_text("value = 1\n", encoding="utf-8")
            self._initialize_repository(root, source)
            now = datetime(2026, 10, 15, 12, tzinfo=UTC)
            start = start_verification(
                root,
                kind="test",
                scope="python",
                parameters={},
                environment={"runner": "dev-container"},
                planned_steps=("pytest",),
                now=now,
            )

            report = finish_verification(
                start,
                root,
                exit_code=0,
                counts=None,
                steps=({"name": "pytest", "status": "passed", "exit_code": 0},),
                cleanup_status="passed",
                now=now.replace(minute=1),
            )

        self.assertEqual(report["status"], "incomplete")
        self.assertIsNone(report["counts"])
        self.assertEqual(report["counts_reason"], "unavailable")

    def test_skipped_test_cases_cannot_produce_a_passed_summary(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "app.py"
            source.write_text("value = 1\n", encoding="utf-8")
            self._initialize_repository(root, source)
            start = start_verification(
                root,
                kind="test",
                scope="python",
                parameters={},
                environment={"runner": "dev-container"},
                planned_steps=("pytest",),
            )

            report = finish_verification(
                start,
                root,
                exit_code=0,
                counts={
                    "total": 2,
                    "passed": 1,
                    "failed": 0,
                    "errors": 0,
                    "skipped": 1,
                },
                steps=({"name": "pytest", "status": "passed", "exit_code": 0},),
                cleanup_status="passed",
            )

        self.assertEqual(report["status"], "incomplete")

    def test_unverified_source_identity_prevents_a_passed_summary(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            start = start_verification(
                root,
                kind="test",
                scope="python",
                parameters={},
                environment={"runner": "dev-container"},
                planned_steps=("pytest",),
            )

            report = finish_verification(
                start,
                root,
                exit_code=0,
                counts={
                    "total": 1,
                    "passed": 1,
                    "failed": 0,
                    "errors": 0,
                    "skipped": 0,
                },
                steps=({"name": "pytest", "status": "passed", "exit_code": 0},),
                cleanup_status="passed",
            )

        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["provenance"]["consistency"], "unverified")

    def test_verification_summary_is_exclusive_and_preserves_previous_bytes(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)
            run_id = "20261015T120000Z-abcdef1-test-python-deadbeef"
            report_path = output / f"{run_id}.json"
            old_bytes = b"existing final evidence"
            report_path.write_bytes(old_bytes)

            with self.assertRaises(ReportWriteError):
                write_verification_summary(output, run_id, {"run_id": run_id})

            self.assertEqual(report_path.read_bytes(), old_bytes)

    def test_fixed_time_and_commit_still_produce_unique_run_ids(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            cases = root / "cases.json"
            cases.write_text("[]", encoding="utf-8")
            self._initialize_repository(root, cases)
            now = datetime(2026, 10, 15, 12, tzinfo=UTC)

            first = start_run(root, {"cases": cases}, suite="semantic", now=now)
            second = start_run(root, {"cases": cases}, suite="semantic", now=now)

        self.assertNotEqual(first.run_id, second.run_id)
        self.assertIn("semantic", first.run_id)

    def test_provenance_is_stable_when_source_and_inputs_do_not_change(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            cases = root / "cases.json"
            cases.write_text('[{"id":"A"}]', encoding="utf-8")
            self._initialize_repository(root, cases)
            started_at = datetime(2026, 10, 15, 12, tzinfo=UTC)
            start = start_run(root, {"test_set": cases}, suite="single", now=started_at)

            provenance = finish_run(
                start,
                root,
                {"test_set": cases},
                now=started_at + timedelta(seconds=1),
            )

        self.assertEqual(provenance["version"], 1)
        self.assertEqual(provenance["consistency"], "stable")
        self.assertEqual(provenance["source_start"], provenance["source_end"])
        self.assertEqual(provenance["inputs_start"], provenance["inputs_end"])
        self.assertEqual(provenance["source_start"]["git_dirty"], False)

    def test_provenance_detects_source_and_input_changes(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            cases = root / "cases.json"
            cases.write_text('[{"id":"A"}]', encoding="utf-8")
            tracked = root / "source.py"
            tracked.write_text("value = 1\n", encoding="utf-8")
            self._initialize_repository(root, cases, tracked)
            now = datetime(2026, 10, 15, 12, tzinfo=UTC)
            inputs = {"test_set": cases}
            start = start_run(root, inputs, suite="single", now=now)

            cases.write_text('[{"id":"B"}]', encoding="utf-8")
            tracked.write_text("value = 2\n", encoding="utf-8")
            provenance = finish_run(
                start,
                root,
                inputs,
                now=now + timedelta(seconds=1),
            )

        self.assertEqual(provenance["consistency"], "changed")
        self.assertNotEqual(provenance["source_start"], provenance["source_end"])
        self.assertNotEqual(provenance["inputs_start"], provenance["inputs_end"])

    def test_unreadable_git_or_input_is_unverified(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            missing_input = root / "missing.json"
            start = start_run(
                root,
                {"test_set": missing_input},
                suite="semantic",
                now=datetime(2026, 10, 15, 12, tzinfo=UTC),
            )

            provenance = finish_run(
                start,
                root,
                {"test_set": missing_input},
                now=datetime(2026, 10, 15, 12, 0, 1, tzinfo=UTC),
            )

        self.assertEqual(provenance["consistency"], "unverified")
        self.assertFalse(provenance["source_start"]["verified"])
        self.assertFalse(provenance["inputs_start"]["verified"])

    def test_report_pair_is_exclusive_and_does_not_overwrite_existing_bytes(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)
            run_id = "20261015T120000Z-abcdef1-single-deadbeef"
            json_path = output / f"{run_id}.json"
            markdown_path = output / f"{run_id}.md"
            old_bytes = b"prior report must remain byte-for-byte"
            json_path.write_bytes(old_bytes)

            with self.assertRaises(ReportWriteError):
                write_report_pair(output, run_id, "new json", "new markdown")

            self.assertEqual(json_path.read_bytes(), old_bytes)
            self.assertFalse(markdown_path.exists())

    def test_partial_report_pair_failure_is_not_reported_as_success(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)
            run_id = "20261015T120000Z-abcdef1-single-deadbeef"
            markdown_path = output / f"{run_id}.md"
            old_markdown = b"existing markdown"
            markdown_path.write_bytes(old_markdown)

            with self.assertRaises(ReportWriteError):
                write_report_pair(output, run_id, "new json", "new markdown")

            self.assertEqual(markdown_path.read_bytes(), old_markdown)
            self.assertTrue((output / f"{run_id}.json").exists())

    @staticmethod
    def _initialize_repository(root: Path, *tracked_paths: Path) -> None:
        commands = (
            ("git", "init", "--quiet", str(root)),
            ("git", "-C", str(root), "config", "user.name", "Test User"),
            (
                "git",
                "-C",
                str(root),
                "config",
                "user.email",
                "test@example.invalid",
            ),
            (
                "git",
                "-C",
                str(root),
                "add",
                *(str(path) for path in tracked_paths),
            ),
            (
                "git",
                "-C",
                str(root),
                "-c",
                "commit.gpgsign=false",
                "commit",
                "--quiet",
                "-m",
                "test baseline",
            ),
        )
        for command in commands:
            subprocess.run(command, check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
