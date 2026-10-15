"""运行身份采集与排他报告保存测试。"""

import subprocess
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.verification_report import (
    ReportWriteError,
    finish_run,
    start_run,
    write_report_pair,
)


class VerificationReportTest(unittest.TestCase):
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
