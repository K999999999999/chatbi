"""执行真实工作流 shell，确认失败保留与正式 / 诊断隔离。"""

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap


ROOT = Path(__file__).resolve().parents[2]


def workflow_script(step_id):
    lines = (ROOT / ".github/workflows/real-e2e.yml").read_text().splitlines()
    start = lines.index(f"        id: {step_id}")
    run = lines.index("        run: |", start) + 1
    end = run
    while end < len(lines) and (not lines[end] or lines[end].startswith("          ")):
        end += 1
    return textwrap.dedent("\n".join(lines[run:end]))


def run_workflow_script(tmp_path, step_id, failed_suite=""):
    shim = tmp_path / "uv"
    shim.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['COMMAND_LOG'], 'a') as log:\n"
        "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "sys.exit(1 if os.environ['FAILED_SUITE'] in sys.argv[1:] else 0)\n"
    )
    shim.chmod(0o700)
    env = {
        "PATH": str(tmp_path) + os.pathsep + os.defpath,
        "COMMAND_LOG": str(tmp_path / "commands.jsonl"),
        "FAILED_SUITE": failed_suite,
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_SHA": "a" * 40,
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
    }
    result = subprocess.run(
        ["bash", "-c", workflow_script(step_id)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    calls = [
        json.loads(line)
        for line in (tmp_path / "commands.jsonl").read_text().splitlines()
    ]
    return result, calls


def test_formal_failure_still_runs_all_suites_and_identity_acceptance(tmp_path):
    result, calls = run_workflow_script(tmp_path, "baseline", "--single-turn")
    assert result.returncode == 1, result.stderr
    assert len(calls) == 4
    assert "--single-turn" in calls[0]
    assert "--multi-turn" in calls[1]
    assert "--business-analysis" in calls[2]
    assert "evaluation.common.real_e2e_acceptance" in calls[3]
    assert "a" * 40 in calls[3]


def test_formal_pass_returns_success(tmp_path):
    result, calls = run_workflow_script(tmp_path, "baseline")
    assert result.returncode == 0, result.stderr
    assert len(calls) == 4


def test_identity_acceptance_failure_rejects_formal_baseline(tmp_path):
    result, calls = run_workflow_script(
        tmp_path, "baseline", "evaluation.common.real_e2e_acceptance"
    )
    assert result.returncode == 1, result.stderr
    assert len(calls) == 4


def test_diagnostic_failures_are_all_retained_and_do_not_change_formal_gate(tmp_path):
    result, calls = run_workflow_script(tmp_path, "diagnostics", "--multi-turn")
    assert result.returncode == 0, result.stderr
    assert len(calls) == 3
    assert len({call[-1] for call in calls}) == 3
    assert all("diagnostic-" in call[-1] for call in calls)
    assert (tmp_path / "summary.md").read_text().count("FAIL or unavailable") == 3
