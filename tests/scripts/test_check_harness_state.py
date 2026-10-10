import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/check_harness_state.py"


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-b", "master")
    git(
        tmp_path,
        "-c",
        "user.name=Harness test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "baseline",
    )
    return tmp_path


def record(repo: Path, item: str, status: str, extra: str = "") -> Path:
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    path = common / "harness/work-items" / item / "status.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# 状态\nID: {item}\nStatus: {status}\n{extra}", encoding="utf-8")
    return path


def check(repo: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode, json.loads(result.stdout)


def codes(report: dict) -> set[str]:
    return {finding["code"] for finding in report["findings"]}


def test_completed_child_cannot_remain_active_in_product_summary(repo: Path) -> None:
    record(repo, "export", "done")
    record(repo, "product", "in-progress", "Active work item: export\n")
    exit_code, report = check(repo)
    assert exit_code == 1
    assert "ACTIVE_COMPLETED" in codes(report)


def test_completed_item_requires_declared_ticket_completion(repo: Path) -> None:
    ticket = repo / "ticket.md"
    ticket.write_text("# Ticket\nStatus: in-progress\n", encoding="utf-8")
    record(repo, "history", "done", "Ticket files: ticket.md\n")
    exit_code, report = check(repo)
    assert exit_code == 1
    assert "TICKET_NOT_DONE" in codes(report)


def test_valid_summary_and_history_do_not_raise_errors(repo: Path) -> None:
    record(repo, "export", "done")
    record(repo, "repair", "in-progress")
    summary = record(
        repo,
        "product",
        "in-progress",
        "Related work items: export, repair\nActive work item: repair\n",
    )
    summary.write_text(
        summary.read_text() + "## 历史快照\nStatus: open\n", encoding="utf-8"
    )
    summary.with_name("status-before-closeout.md").write_text(
        "Status: invalid\n", encoding="utf-8"
    )
    exit_code, report = check(repo)
    assert exit_code == 0
    assert report["records"] == 3
    assert not any(f["level"] == "ERROR" for f in report["findings"])


def test_deferred_candidate_is_visible_and_check_is_read_only(repo: Path) -> None:
    git(repo, "switch", "-c", "docs/old-closeout")
    git(
        repo,
        "-c",
        "user.name=Harness test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "old document candidate",
    )
    git(repo, "switch", "master")
    pending = record(repo, "closeout", "in-progress", "Follow-up work item: repair\n")
    record(repo, "repair", "in-progress")
    before = (
        pending.read_bytes(),
        git(repo, "show-ref"),
        git(repo, "status", "--porcelain"),
    )
    exit_code, report = check(repo)
    assert exit_code == 0
    assert {"RETAINED_BRANCH", "OPEN_WORK_ITEM", "FOLLOW_UP"} <= codes(report)
    assert before == (
        pending.read_bytes(),
        git(repo, "show-ref"),
        git(repo, "status", "--porcelain"),
    )


def test_linked_worktree_reads_shared_common_directory(repo: Path) -> None:
    record(repo, "export", "done")
    record(repo, "product", "in-progress", "Active work item: export\n")
    linked = repo.parent / "linked"
    git(repo, "worktree", "add", "-b", "docs/linked", str(linked))
    exit_code, report = check(linked)
    assert exit_code == 1
    assert report["records"] == 2
    assert "ACTIVE_COMPLETED" in codes(report)


def test_new_clone_reports_missing_local_evidence_without_error(repo: Path) -> None:
    exit_code, report = check(repo)
    assert exit_code == 0
    assert report["records"] == 0
    assert "LOCAL_RECORDS_ABSENT" in codes(report)


@pytest.mark.parametrize(
    "content",
    [
        "Status: done\n",
        "ID: wrong-id\nStatus: done\n",
        "ID: item\nStatus: complete\n",
        "ID: item\nStatus: done\nStatus: in-progress\n",
    ],
)
def test_invalid_current_fields_fail(repo: Path, content: str) -> None:
    path = record(repo, "item", "done")
    path.write_text(content, encoding="utf-8")
    exit_code, report = check(repo)
    assert exit_code == 1
    assert "RECORD_INVALID" in codes(report)


def test_missing_reference_fails_without_dumping_record(repo: Path) -> None:
    record(
        repo,
        "item",
        "in-progress",
        "Related work items: missing\nSecret: do-not-output-this\n",
    )
    exit_code, report = check(repo)
    assert exit_code == 1
    assert "REFERENCE_MISSING" in codes(report)
    assert "do-not-output-this" not in json.dumps(report)


@pytest.mark.parametrize("reference", ["../outside.md", "/tmp/outside.md"])
def test_ticket_cannot_escape_repository(repo: Path, reference: str) -> None:
    record(repo, "item", "done", f"Ticket files: {reference}\n")
    exit_code, report = check(repo)
    assert exit_code == 1
    assert "TICKET_OUTSIDE_REPO" in codes(report)


def test_ticket_symlink_cannot_escape_repository(repo: Path) -> None:
    outside = repo.parent / "outside.md"
    outside.write_text("Status: done\n", encoding="utf-8")
    (repo / "ticket.md").symlink_to(outside)
    record(repo, "item", "done", "Ticket files: ticket.md\n")
    exit_code, report = check(repo)
    assert exit_code == 1
    assert "TICKET_OUTSIDE_REPO" in codes(report)


def test_finished_ticket_and_fenced_examples_pass(repo: Path) -> None:
    (repo / "ticket.md").write_text(
        "# Ticket\n```md\nStatus: open\n```\nStatus: done\n", encoding="utf-8"
    )
    record(repo, "item", "done", "Ticket files: ticket.md\n")
    exit_code, report = check(repo)
    assert exit_code == 0
    assert "TICKET_NOT_DONE" not in codes(report)


def test_missing_ticket_fails(repo: Path) -> None:
    record(repo, "item", "done", "Ticket files: missing.md\n")
    exit_code, report = check(repo)
    assert exit_code == 1
    assert "TICKET_INVALID" in codes(report)


def test_git_failure_is_error_in_json(tmp_path: Path) -> None:
    exit_code, report = check(tmp_path)
    assert exit_code == 1
    assert "INSPECTION_FAILED" in codes(report)


def test_text_output_identifies_scope_and_review(repo: Path) -> None:
    record(repo, "item", "in-progress")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "仅本机" in result.stdout
    assert "REVIEW OPEN_WORK_ITEM [item]" in result.stdout


def test_squash_merged_branch_requires_review_without_error(repo: Path) -> None:
    git(repo, "switch", "-c", "docs/squashed")
    (repo / "note.md").write_text("published note\n", encoding="utf-8")
    git(repo, "add", "note.md")
    git(
        repo,
        "-c",
        "user.name=Harness test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "candidate",
    )
    git(repo, "switch", "master")
    git(repo, "merge", "--squash", "docs/squashed")
    git(
        repo,
        "-c",
        "user.name=Harness test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "published squash",
    )
    record(repo, "published", "done")
    exit_code, report = check(repo)
    assert exit_code == 0
    assert "RETAINED_BRANCH" in codes(report)
    assert not any(f["level"] == "ERROR" for f in report["findings"])


def test_single_active_reference_cannot_contain_multiple_items(repo: Path) -> None:
    record(repo, "one", "in-progress")
    record(repo, "two", "in-progress")
    record(repo, "product", "in-progress", "Active work item: one, two\n")
    exit_code, report = check(repo)
    assert exit_code == 1
    assert "REFERENCE_INVALID" in codes(report)


@pytest.mark.parametrize(
    ("review", "follow_up"),
    [("no-gap", "None"), ("gap-found", "repair")],
)
def test_valid_harness_review_dispositions_pass(
    repo: Path, review: str, follow_up: str
) -> None:
    if follow_up != "None":
        record(repo, follow_up, "in-progress")
    record(
        repo,
        "delivery",
        "done",
        f"Harness review: {review}\n"
        "Harness evidence: PR #52; acceptance.md\n"
        f"Harness follow-up work item: {follow_up}\n",
    )
    exit_code, report = check(repo)
    assert exit_code == 0
    assert not any(f["level"] == "ERROR" for f in report["findings"])


@pytest.mark.parametrize(
    ("fields", "expected_code"),
    [
        ("Harness review: no-gap\n", "HARNESS_REVIEW_INVALID"),
        (
            "Harness review: maybe\nHarness evidence: PR #52\nHarness follow-up work item: None\n",
            "HARNESS_REVIEW_INVALID",
        ),
        (
            "Harness review: no-gap\nHarness evidence: \nHarness follow-up work item: None\n",
            "HARNESS_REVIEW_INVALID",
        ),
        (
            "Harness review: no-gap\nHarness evidence: PR #52\nHarness follow-up work item: repair\n",
            "HARNESS_REVIEW_INVALID",
        ),
        (
            "Harness review: gap-found\nHarness evidence: PR #52\nHarness follow-up work item: None\n",
            "HARNESS_REVIEW_INVALID",
        ),
        (
            "Harness review: gap-found\nHarness evidence: PR #52\nHarness follow-up work item: repair, other\n",
            "HARNESS_REVIEW_INVALID",
        ),
        (
            "Harness review: gap-found\nHarness evidence: PR #52\nHarness follow-up work item: delivery\n",
            "HARNESS_REVIEW_INVALID",
        ),
        (
            "Harness review: gap-found\nHarness evidence: PR #52\nHarness follow-up work item: missing\n",
            "REFERENCE_MISSING",
        ),
    ],
)
def test_invalid_harness_review_disposition_fails(
    repo: Path, fields: str, expected_code: str
) -> None:
    record(repo, "repair", "in-progress")
    record(repo, "other", "in-progress")
    record(repo, "delivery", "done", fields)
    exit_code, report = check(repo)
    assert exit_code == 1
    assert expected_code in codes(report)


def test_harness_review_fields_are_ignored_in_history(repo: Path) -> None:
    path = record(repo, "delivery", "done")
    path.write_text(
        path.read_text(encoding="utf-8")
        + "## 历史复盘\n"
        + "Harness review: gap-found\n"
        + "Harness evidence: old\n"
        + "Harness follow-up work item: missing\n",
        encoding="utf-8",
    )
    exit_code, report = check(repo)
    assert exit_code == 0
    assert "HARNESS_REVIEW_INVALID" not in codes(report)
