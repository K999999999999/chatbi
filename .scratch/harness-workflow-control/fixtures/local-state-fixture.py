#!/usr/bin/env python3
"""Disposable Git/worktree fixtures for S03-S06, S19, and S20."""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "--initial-branch=master", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    git(path, "config", "user.name", "Harness Fixture")
    git(path, "config", "user.email", "fixture@example.invalid")
    (path / "README.md").write_text("# Isolated fixture\n")
    git(path, "add", "README.md")
    git(path, "commit", "-m", "fixture: 初始化")
    return path


def common_dir(path: Path) -> Path:
    return Path(git(path, "rev-parse", "--path-format=absolute", "--git-common-dir"))


def status_path(path: Path, item_id: str) -> Path:
    return common_dir(path) / "harness" / "work-items" / item_id / "status.md"


def atomic_write(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text)
    os.replace(temporary, path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print("PASS:", message)


with tempfile.TemporaryDirectory(prefix="harness-local-state-") as temporary_root:
    root = Path(temporary_root)
    main = init_repo(root / "main")
    feature = root / "feature"
    reader = root / "reader"
    git(main, "worktree", "add", "-b", "feature/fixture", str(feature))
    git(main, "worktree", "add", "--detach", str(reader))

    common = common_dir(main)
    state_path = common / "harness" / "work-items" / "fixture-01" / "status.md"
    state_path.parent.mkdir(parents=True)
    initial_head = git(main, "rev-parse", "HEAD")
    initial_status = {path: git(path, "status", "--porcelain") for path in (main, feature, reader)}

    require(
        all(common_dir(path) == common for path in (main, feature, reader)),
        "S04 multiple worktrees resolve one Git common directory",
    )

    atomic_write(
        state_path,
        "ID: fixture-01\nStatus: in-progress\nStage: implementation\n"
        "Primary record: Self\nPublication authorization: unknown\n",
    )
    read_hash = hashlib.sha256(state_path.read_bytes()).hexdigest()
    require(
        all(status_path(path, "fixture-01").read_text() == state_path.read_text() for path in (main, feature, reader)),
        "S04 each worktree can read the same live status record",
    )

    atomic_write(
        state_path,
        "ID: fixture-01\nStatus: in-progress\nStage: validation\n"
        "Primary record: Self\nPublication authorization: unknown\n",
    )
    latest_bytes = state_path.read_bytes()
    stale_writer_detected = hashlib.sha256(latest_bytes).hexdigest() != read_hash
    require(stale_writer_detected, "S19 stale writer detects another update and does not overwrite it")
    require(state_path.read_bytes() == latest_bytes, "S19 latest writer content remains intact")

    feature_path_record = f"\nLast feature worktree: {feature}\n"
    with state_path.open("a") as state_file:
        state_file.write(feature_path_record)
    with (feature / "README.md").open("a") as readme:
        readme.write("Merged feature fixture.\n")
    git(feature, "add", "README.md")
    git(feature, "commit", "-m", "fixture: 合并 feature")
    git(main, "merge", "--no-ff", "feature/fixture", "-m", "fixture: 模拟 PR 合并")
    merged_head = git(main, "rev-parse", "HEAD")
    git(main, "worktree", "remove", str(feature))
    git(main, "branch", "-D", "feature/fixture")
    require(state_path.exists(), "S03 status survives feature worktree and branch removal")
    require("fixture-01" in state_path.read_text(), "S03 work item is recoverable from master")

    before_post_merge_update = git(main, "rev-parse", "HEAD")
    atomic_write(
        state_path,
        "ID: fixture-01\nStatus: in-progress\nStage: post-merge-cleanup\n"
        "Primary record: Self\nPublication authorization: unknown\n",
    )
    require(
        before_post_merge_update == merged_head != initial_head
        and git(main, "rev-parse", "HEAD") == before_post_merge_update,
        "S05 post-merge state update creates no Git commit",
    )
    require(
        all(git(path, "status", "--porcelain") == status for path, status in initial_status.items() if path != feature),
        "S04/S05 status updates do not dirty surviving worktrees",
    )

    dirty_work = root / "dirty-work"
    git(main, "worktree", "add", "-b", "feature/user-modification", str(dirty_work))
    user_file = dirty_work / "user-notes.txt"
    user_file.write_text("user-owned change\n")
    dirty = bool(git(dirty_work, "status", "--porcelain"))
    worktree_list = git(main, "worktree", "list", "--porcelain")
    branch_list = git(main, "branch", "--list", "--format=%(refname:short)")
    cleanup_allowed = not dirty
    require(dirty and not cleanup_allowed, "S06 user modification blocks cleanup")
    require(
        str(dirty_work) in worktree_list
        and "feature/user-modification" in branch_list
        and user_file.read_text() == "user-owned change\n",
        "S06 branch/worktree and user file are preserved",
    )

    corrupt_path = state_path.parent / "corrupt-status.md"
    corrupt_bytes = b"ID: fixture-bad\nStatus: in-progress\nPublication authorization: unknown\n"
    corrupt_path.write_bytes(corrupt_bytes)
    fields = {line.split(":", 1)[0] for line in corrupt_path.read_text().splitlines() if ":" in line}
    required_fields = {"ID", "Status", "Stage", "Owner", "Publication authorization"}
    unknown_authorization = "Implementation authorization" not in fields or "Publication authorization" not in fields
    preserve_corrupt_record = not required_fields.issubset(fields)
    require(unknown_authorization and preserve_corrupt_record, "S19 incomplete status leaves authorization unknown")
    require(corrupt_path.read_bytes() == corrupt_bytes, "S19 malformed record is retained byte-for-byte")

    linked = init_repo(root / "linked")
    main_record = state_path.parent / "cross-repo-main.md"
    linked_record = common_dir(linked) / "harness" / "work-items" / "fixture-cross-repo" / "status.md"
    linked_record.parent.mkdir(parents=True)
    atomic_write(
        main_record,
        "ID: fixture-cross-repo\nPrimary record: Self\n"
        "Spec: K999999999999/chatbi:.scratch/fixture/spec.md@abc123\n"
        "Implementation authorization: user-confirmed scope\n"
        "Publication authorization: none\n",
    )
    atomic_write(
        linked_record,
        "ID: fixture-cross-repo\nPrimary record: K999999999999/chatbi status for fixture-cross-repo\n"
        "Target repository: K999999999999/agent-plugins\n"
        "Spec: K999999999999/chatbi:.scratch/fixture/spec.md@abc123\n"
        "Publication authorization: see primary record\n",
    )
    require(
        "ID: fixture-cross-repo" in main_record.read_text()
        and "ID: fixture-cross-repo" in linked_record.read_text(),
        "S20 main and linked records share a stable work item ID",
    )
    require(
        "Implementation authorization: user-confirmed scope" not in linked_record.read_text(),
        "S20 linked record points to the sole authorization source",
    )
    require(".scratch/fixture/spec.md@abc123" in linked_record.read_text(), "S20 stable repository-relative Spec reference survives worktree cleanup")

    git(main, "worktree", "remove", "--force", str(dirty_work))
    git(main, "branch", "-D", "feature/user-modification")
