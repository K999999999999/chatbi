"""分目录评测产物不得使 clean commit 验收变脏。"""

from pathlib import Path
import subprocess


def test_root_and_nested_evaluation_reports_are_ignored():
    root = Path(__file__).resolve().parents[2]
    paths = [
        "reports/evaluation/report.json",
        "reports/evaluation/report.md",
        "reports/evaluation/baseline/formal/report.json",
        "reports/evaluation/baseline/diagnostic-1/report.md",
        "reports/evaluation/baseline/execution-summary.json",
    ]
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        cwd=root,
        input="\n".join(paths) + "\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == paths
