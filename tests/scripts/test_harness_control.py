import json
import subprocess
import sys
from pathlib import Path

import pytest


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def binding(repo: Path, branch: str, disposition: str = "active") -> str:
    return f"Branch: {branch}\nWorktree: {repo}\nWorktree disposition: {disposition}\n"


def record(repo: Path, item: str, status: str, extra: str = "") -> Path:
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    p = common / "harness/work-items" / item / "status.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"ID: {item}\nStatus: {status}\n{extra}")
    return p


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    root = tmp_path / "checkout"
    root.mkdir()
    git(root, "init", "-b", "master")
    git(
        root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "baseline",
    )
    return root


@pytest.fixture
def plugin(tmp_path: Path) -> Path:
    root = tmp_path / "plugin"
    (root / "tools").mkdir(parents=True)
    (root / "tools/harness.py").write_text(
        "import json,sys\n"
        "from pathlib import Path\n"
        "if 'diff' in sys.argv or 'finalize' in sys.argv or 'cancel' in sys.argv:\n"
        "    Path(__file__).with_name('called').touch()\n"
        "print(json.dumps({'work_item_id':'item','lifecycle_status':'in-progress',"
        "'stage':'实施中','next':'keep working','candidate':{'branch':'current'},"
        "'closeout':{'overall_ready':True},'evidence_summary':[]}))\n"
    )
    return root


def run(root: Path, plugin: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.harness_control",
            "--project-root",
            str(root),
            "--plugin-root",
            str(plugin),
            "--adapter",
            str(root / "adapter.json"),
            *args,
        ],
        capture_output=True,
        text=True,
    )


def test_unbound_legacy_state_does_not_claim_a_task_candidate(
    checkout: Path, plugin: Path
):
    record(checkout, "item", "in-progress")
    result = run(checkout, plugin, "state", "--work-item", "item", "--json")
    assert result.returncode == 0, result.stderr
    state = json.loads(result.stdout)
    assert state["record_only"] is True
    assert state["candidate"] is None
    assert state["closeout"] is None
    assert state["checkout_binding"]["status"] == "unbound"


def test_wrong_checkout_state_retains_progress_without_candidate(
    checkout: Path, plugin: Path
):
    record(
        checkout, "item", "in-progress", binding(checkout, "docs/elsewhere", "parked")
    )
    result = run(checkout, plugin, "state", "--work-item", "item", "--json")
    state = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert state["next"] == "keep working"
    assert state["candidate"] is None


def test_wrong_checkout_diff_is_refused_before_plugin_execution(
    checkout: Path, plugin: Path
):
    p = record(
        checkout, "item", "in-progress", binding(checkout, "docs/elsewhere", "parked")
    )
    before = p.read_bytes()
    result = run(checkout, plugin, "diff", "--work-item", "item", "--json")
    assert result.returncode == 2
    assert "checkout" in result.stderr.lower()
    assert not (plugin / "tools/called").exists()
    assert p.read_bytes() == before


def test_matched_state_preserves_actual_plugin_candidate(checkout: Path, plugin: Path):
    record(checkout, "item", "in-progress", binding(checkout, "master"))
    result = run(checkout, plugin, "state", "--work-item", "item", "--json")
    state = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert state["candidate"] == {"branch": "current"}
    assert state["checkout_binding"]["status"] == "matched"
    assert state["record_only"] is False


def test_overall_completion_requires_actual_cleanup(checkout: Path, plugin: Path):
    record(checkout, "item", "in-progress", binding(checkout, "master"))
    result = run(
        checkout,
        plugin,
        "closeout",
        "finalize",
        "--scope",
        "overall",
        "--work-item",
        "item",
    )
    assert result.returncode == 2
    assert not (plugin / "tools/called").exists()


def test_completed_task_is_bound_to_verified_return_checkout(
    checkout: Path, plugin: Path
):
    sha = git(checkout, "rev-parse", "master")
    git(checkout, "update-ref", "refs/remotes/origin/master", sha)
    record(
        checkout,
        "item",
        "done",
        binding(checkout.parent / "removed", "fix/completed", "removed")
        + f"Return worktree: {checkout}\nMerge commit: {sha}\nCleanup evidence: verified\n",
    )
    result = run(checkout, plugin, "state", "--work-item", "item", "--json")
    state = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert state["record_only"] is False
    assert state["checkout_binding"]["phase"] == "post-merge"


def test_cancel_remains_a_record_operation_without_a_candidate_checkout(
    checkout: Path, plugin: Path
):
    p = record(checkout, "item", "in-progress")
    before = p.read_bytes()
    result = run(
        checkout, plugin, "cancel", "--work-item", "item", "--expected-sha", "0" * 64
    )
    assert result.returncode == 0, result.stderr
    assert (plugin / "tools/called").exists()
    assert p.read_bytes() == before


def test_plugin_failure_does_not_become_a_successful_state_query(
    checkout: Path, plugin: Path
):
    record(checkout, "item", "in-progress")
    (plugin / "tools/harness.py").write_text("raise SystemExit(7)\n")
    result = run(checkout, plugin, "state", "--work-item", "item", "--json")
    assert result.returncode == 7
    assert not result.stdout


def test_legacy_record_does_not_claim_plugin_closeout_even_when_checkout_matches(
    checkout: Path, plugin: Path
):
    record(checkout, "item", "in-progress", binding(checkout, "master"))
    payload = {
        "work_item_id": "item",
        "legacy_read_only": True,
        "candidate": {"branch": "master"},
        "closeout": {"overall_ready": False},
    }
    (plugin / "tools/harness.py").write_text(
        "print(" + repr(json.dumps(payload)) + ")\n"
    )
    result = run(checkout, plugin, "state", "--work-item", "item", "--json")
    state = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert state["checkout_binding"]["status"] == "matched"
    assert state["record_only"] is True
    assert state["candidate"] is None and state["closeout"] is None
