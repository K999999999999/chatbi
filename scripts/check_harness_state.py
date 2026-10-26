"""Read-only inspection of local Harness work records and Git state."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


FIELDS = {
    "ID",
    "Status",
    "Related work items",
    "Active work item",
    "Follow-up work item",
    "Ticket files",
    "Harness review",
    "Harness evidence",
    "Harness follow-up work item",
    "Branch",
    "Worktree",
    "Worktree disposition",
    "Retention reason",
    "Return worktree",
    "Merge commit",
    "Cleanup evidence",
}
WORK_ITEM_STATUSES = {"open", "in-progress", "blocked", "done", "cancelled"}
TICKET_STATUSES = {"open", "in-progress", "blocked", "done"}
TERMINAL_WORK_ITEM_STATUSES = {"done", "cancelled"}
HARNESS_REVIEW_STATUSES = {"no-gap", "gap-found"}
IDENTITY_FIELDS = {"Branch", "Worktree", "Worktree disposition"}
DISPOSITIONS = {"active", "parked", "removed", "retained"}


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(repo), *args],
        text=True,
        stderr=subprocess.PIPE,
    ).strip()


def fields(path: Path) -> dict[str, str]:
    """Read current unindented fields; exclude fenced examples and history."""
    return text_fields(path.read_text(encoding="utf-8"))


def text_fields(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    fence = ""
    for line in text.splitlines():
        stripped = line.strip()
        if fence:
            if re.fullmatch(
                re.escape(fence[0]) + "{" + str(len(fence)) + ",}", stripped
            ):
                fence = ""
            continue
        marker = re.match(r"^(`{3,}|~{3,})", stripped)
        if marker:
            fence = marker.group(1)
            continue
        if values and re.match(r"^#{1,6}\s+(历史|History\b)", line, re.IGNORECASE):
            break
        key, separator, value = line.partition(":")
        if separator and key in FIELDS:
            if key in values:
                raise ValueError("duplicate current field")
            values[key] = value.strip()
    return values


def references(value: str) -> list[str]:
    return [] if value in {"", "None"} else [part.strip() for part in value.split(",")]


def list_worktrees(repo: Path) -> list[dict]:
    result: list[dict] = []
    current: dict = {}
    for entry in git(repo, "worktree", "list", "--porcelain", "-z").split("\0"):
        key, _, value = entry.partition(" ")
        if key == "worktree":
            if current:
                result.append(current)
            current = {"path": str(Path(value).resolve()), "branch": None}
        elif key == "HEAD":
            current["head"] = value
        elif key == "branch":
            current["branch"] = value.removeprefix("refs/heads/")
    if current:
        result.append(current)
    return result


def checkout_binding(repo: Path, work_item: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", work_item):
        raise ValueError("invalid work item ID")
    root = Path(git(repo, "rev-parse", "--show-toplevel")).resolve()
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    values = fields(common / "harness/work-items" / work_item / "status.md")
    if values.get("ID") != work_item:
        raise ValueError("record ID mismatch")
    actual_branch = git(repo, "branch", "--show-current")
    bound = IDENTITY_FIELDS <= values.keys()
    matched = (
        bound
        and Path(values["Worktree"]).is_absolute()
        and Path(values["Worktree"]).resolve() == root
        and values["Branch"] == actual_branch
        and values["Worktree disposition"] in {"active", "parked", "retained"}
    )
    phase = "candidate"
    if (
        not matched
        and bound
        and actual_branch == "master"
        and values.get("Return worktree") == str(root)
        and values["Worktree disposition"] in {"removed", "retained"}
    ):
        cleanup_report = inspect(repo, closeout=work_item)
        if not any(f["level"] == "ERROR" for f in cleanup_report["findings"]):
            matched = True
            phase = "post-merge"
    return {
        "status": "matched" if matched else "mismatch" if bound else "unbound",
        "phase": phase,
        "work_item": work_item,
        "expected_branch": values.get("Branch"),
        "expected_worktree": values.get("Worktree"),
        "actual_branch": actual_branch,
        "actual_worktree": str(root),
    }


def inspect(
    repo: Path, *, work_item: str | None = None, closeout: str | None = None
) -> dict:
    root = Path(git(repo, "rev-parse", "--show-toplevel")).resolve()
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    work_items = common / "harness/work-items"
    findings: list[dict[str, str]] = []

    def add(level: str, code: str, item: str, message: str) -> None:
        findings.append(
            {"level": level, "code": code, "item": item, "message": message}
        )

    records: dict[str, dict[str, str]] = {}
    for path in sorted(work_items.glob("*/status.md")):
        item = path.parent.name
        try:
            values = fields(path)
        except (OSError, UnicodeError, ValueError):
            add("ERROR", "RECORD_INVALID", item, "当前记录不可读取或含重复字段")
            continue
        if values.get("ID") != item or values.get("Status") not in WORK_ITEM_STATUSES:
            add(
                "ERROR",
                "RECORD_INVALID",
                item,
                "ID / Status 缺失、无效或 ID 与目录不一致",
            )
            continue
        records[item] = values

    worktrees = list_worktrees(repo)
    by_path = {w["path"]: w for w in worktrees}
    branch_refs = set(
        git(repo, "for-each-ref", "--format=%(refname)", "refs/heads").splitlines()
    )
    for worktree in worktrees:
        path = Path(worktree["path"])
        if not path.exists():
            worktree["dirty"] = None
            add(
                "REVIEW",
                "WORKTREE_MISSING",
                str(path),
                "登记目录不存在，需核对生命周期",
            )
            continue
        try:
            worktree["dirty"] = bool(
                git(path, "status", "--porcelain=v1", "--untracked-files=all")
            )
        except subprocess.CalledProcessError:
            worktree["dirty"] = None
            add("ERROR", "WORKTREE_INSPECTION_FAILED", str(path), "无法检查登记工作树")
            continue
        if worktree["dirty"]:
            add(
                "REVIEW",
                "DIRTY_WORKTREE",
                str(path),
                "工作树有修改，需核对归属；未输出文件内容",
            )

    def cleanup(item: str, values: dict[str, str], *, strict: bool = False) -> None:
        disposition = values.get("Worktree disposition")
        if disposition in {"active", "parked"}:
            add(
                "ERROR",
                "CLEANUP_INCOMPLETE",
                item,
                "工作树仍 active / parked，不能宣布整体完成",
            )
        required = IDENTITY_FIELDS | {
            "Return worktree",
            "Merge commit",
            "Cleanup evidence",
        }
        if not required <= values.keys() or any(
            not values.get(k) or values[k] == "None" for k in required
        ):
            add(
                "ERROR",
                "CLEANUP_EVIDENCE_MISSING",
                item,
                "缺少结构化归属、返回目录、合并提交或清理依据",
            )
            return
        if disposition not in DISPOSITIONS:
            add("ERROR", "CLEANUP_INCOMPLETE", item, "工作树去向无效")
        owned = Path(values["Worktree"])
        returned = Path(values["Return worktree"])
        if not owned.is_absolute() or not returned.is_absolute():
            add("ERROR", "CLEANUP_IDENTITY_INVALID", item, "本机目录必须是绝对路径")
            return
        owned_key = str(owned.resolve())
        if disposition == "removed" and (
            owned.exists() or owned.is_symlink() or owned_key in by_path
        ):
            add("ERROR", "WORKTREE_NOT_REMOVED", item, "工作树登记或物理目录仍存在")
        if disposition == "retained" and (
            not values.get("Retention reason") or owned_key not in by_path
        ):
            add(
                "ERROR",
                "WORKTREE_RETENTION_INVALID",
                item,
                "保留工作树必须存在并有明确原因",
            )
        return_tree = by_path.get(str(returned.resolve()))
        if (
            not return_tree
            or return_tree["branch"] != "master"
            or return_tree.get("dirty") is not False
        ):
            reused = return_tree and any(
                other != item
                and v["Status"] not in TERMINAL_WORK_ITEM_STATUSES
                and v.get("Worktree disposition") == "active"
                and v.get("Worktree") == return_tree["path"]
                and v.get("Branch") == return_tree["branch"]
                for other, v in records.items()
            )
            if reused and not strict:
                add(
                    "INFO",
                    "RETURN_WORKTREE_REUSED",
                    item,
                    "返回目录现由另一登记任务使用；不将后续正常实施误判为历史清理失败",
                )
            else:
                add(
                    "ERROR",
                    "RETURN_WORKTREE_NOT_READY",
                    item,
                    "返回工作树未处于干净 master；先交接其他活动任务",
                )
        branch = values["Branch"]
        if branch == "master" or f"refs/heads/{branch}" in branch_refs:
            add(
                "ERROR",
                "FEATURE_BRANCH_NOT_REMOVED",
                item,
                "任务 Feature branch 尚未清理或错误绑定 master",
            )
        try:
            master = git(repo, "rev-parse", "--verify", "refs/heads/master")
            remote = git(repo, "rev-parse", "--verify", "refs/remotes/origin/master")
            if master != remote:
                add(
                    "ERROR",
                    "BASELINE_NOT_SYNCED",
                    item,
                    "本地 master 与已获取的 origin/master 不同",
                )
            merge = values["Merge commit"]
            if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", merge):
                raise ValueError("merge commit must be a full hash")
            git(repo, "merge-base", "--is-ancestor", merge, "refs/heads/master")
        except (subprocess.CalledProcessError, ValueError):
            add(
                "ERROR",
                "MERGE_NOT_VERIFIED",
                item,
                "合并提交不在本地 master 或基线引用不可核实",
            )

    for item, values in records.items():
        if IDENTITY_FIELDS & values.keys():
            if (
                not IDENTITY_FIELDS <= values.keys()
                or values.get("Worktree disposition") not in DISPOSITIONS
            ):
                add(
                    "ERROR",
                    "CHECKOUT_IDENTITY_INVALID",
                    item,
                    "归属字段缺失或 disposition 无效",
                )
                continue
            owned = Path(values["Worktree"])
            if not owned.is_absolute():
                add(
                    "ERROR",
                    "CHECKOUT_IDENTITY_INVALID",
                    item,
                    "Worktree 必须是本机绝对路径",
                )
                continue
            actual = by_path.get(str(owned.resolve()))
            if values["Worktree disposition"] == "retained" and values.get(
                "Retention reason", "None"
            ) in {"", "None"}:
                add(
                    "ERROR",
                    "WORKTREE_RETENTION_INVALID",
                    item,
                    "保留工作树缺少明确原因",
                )
            if (
                values["Worktree disposition"] == "parked"
                and f"refs/heads/{values['Branch']}" not in branch_refs
            ):
                add(
                    "ERROR",
                    "CANDIDATE_BRANCH_MISSING",
                    item,
                    "parked 候选分支已不存在，需恢复事实",
                )
            if values["Worktree disposition"] == "active" and (
                not actual or actual["branch"] != values["Branch"]
            ):
                add(
                    "ERROR",
                    "CHECKOUT_MISMATCH",
                    item,
                    "active 任务的 branch / worktree 与实际 checkout 不同",
                )
            if values["Status"] == "done":
                cleanup(item, values, strict=closeout == item)

    if work_item:
        binding = checkout_binding(repo, work_item)
        if binding["status"] != "matched":
            add(
                "ERROR",
                "CHECKOUT_MISMATCH",
                work_item,
                "当前 checkout 不属于指定任务；候选操作已拒绝",
            )
    if closeout:
        if closeout not in records:
            add("ERROR", "RECORD_INVALID", closeout, "待收尾工作项不存在或无效")
        elif (
            records[closeout]["Status"] != "done"
            or not IDENTITY_FIELDS & records[closeout].keys()
        ):
            cleanup(closeout, records[closeout], strict=True)

    for worktree in worktrees[1:]:
        owners = [
            item
            for item, values in records.items()
            if values.get("Worktree")
            and Path(values["Worktree"]).resolve() == Path(worktree["path"])
            and values.get("Worktree disposition") in {"active", "retained"}
        ]
        if not owners:
            add(
                "REVIEW",
                "UNOWNED_WORKTREE",
                worktree["path"],
                "额外工作树没有结构化活动归属或保留依据",
            )

    for item, values in records.items():
        status = values["Status"]
        if status not in TERMINAL_WORK_ITEM_STATUSES:
            add(
                "REVIEW", "OPEN_WORK_ITEM", item, f"状态为 {status}；需核对下一步及授权"
            )
        for key in ("Related work items", "Active work item", "Follow-up work item"):
            targets = references(values.get(key, ""))
            if key != "Related work items" and len(targets) > 1:
                add("ERROR", "REFERENCE_INVALID", item, f"{key} 只能引用一个工作项")
            for target in targets:
                if target not in records:
                    add(
                        "ERROR",
                        "REFERENCE_MISSING",
                        item,
                        f"{key} 引用的当前记录不存在或无效",
                    )
                elif (
                    key == "Active work item"
                    and records[target]["Status"] in TERMINAL_WORK_ITEM_STATUSES
                ):
                    if records[target]["Status"] == "done":
                        add(
                            "ERROR",
                            "ACTIVE_COMPLETED",
                            item,
                            "Active work item 已完成，汇总需同步",
                        )
                    else:
                        add(
                            "ERROR",
                            "ACTIVE_CANCELLED",
                            item,
                            "Active work item 已取消，汇总需同步",
                        )
                elif key == "Follow-up work item":
                    add(
                        "INFO",
                        "FOLLOW_UP",
                        item,
                        f"后续由工作项 {target} 接手；不继承授权",
                    )

        review_fields = (
            "Harness review",
            "Harness evidence",
            "Harness follow-up work item",
        )
        review_fields_present = [key in values for key in review_fields]
        if any(review_fields_present):
            if not all(review_fields_present):
                add(
                    "ERROR",
                    "HARNESS_REVIEW_INVALID",
                    item,
                    "Harness 复盘字段必须全部填写",
                )
            else:
                review = values["Harness review"]
                evidence = values["Harness evidence"]
                follow_up = values["Harness follow-up work item"]
                if review not in HARNESS_REVIEW_STATUSES:
                    add(
                        "ERROR",
                        "HARNESS_REVIEW_INVALID",
                        item,
                        "Harness review 只能是 no-gap 或 gap-found",
                    )
                if not evidence:
                    add(
                        "ERROR",
                        "HARNESS_REVIEW_INVALID",
                        item,
                        "Harness evidence 不能为空",
                    )
                follow_up_targets = references(follow_up)
                if len(follow_up_targets) > 1:
                    add(
                        "ERROR",
                        "HARNESS_REVIEW_INVALID",
                        item,
                        "Harness follow-up work item 只能引用一个工作项",
                    )
                elif review == "no-gap" and follow_up != "None":
                    add(
                        "ERROR",
                        "HARNESS_REVIEW_INVALID",
                        item,
                        "no-gap 复盘必须将 Harness follow-up work item 设为 None",
                    )
                elif review == "gap-found" and not follow_up_targets:
                    add(
                        "ERROR",
                        "HARNESS_REVIEW_INVALID",
                        item,
                        "gap-found 复盘必须引用一个 Harness follow-up work item",
                    )
                elif follow_up_targets:
                    target = follow_up_targets[0]
                    if target == item:
                        add(
                            "ERROR",
                            "HARNESS_REVIEW_INVALID",
                            item,
                            "Harness follow-up work item 不能引用当前工作项",
                        )
                    elif target not in records:
                        add(
                            "ERROR",
                            "REFERENCE_MISSING",
                            item,
                            "Harness follow-up work item 引用的当前记录不存在或无效",
                        )

        for relative in references(values.get("Ticket files", "")):
            declared = Path(relative)
            ref = None
            if values.get("Worktree disposition") == "parked":
                ref = "refs/heads/" + values["Branch"]
            elif values["Status"] == "done" and values.get("Merge commit"):
                ref = values["Merge commit"]
            ticket_root = root
            if (
                values.get("Worktree disposition") == "active"
                and values.get("Worktree") in by_path
            ):
                ticket_root = Path(values["Worktree"])
            ticket = (ticket_root / declared).resolve()
            if (
                declared.is_absolute()
                or ".." in declared.parts
                or (ref is None and not ticket.is_relative_to(ticket_root))
            ):
                add(
                    "ERROR",
                    "TICKET_OUTSIDE_REPO",
                    item,
                    "Ticket files 必须指向仓库内相对路径",
                )
                continue
            try:
                if ref:
                    tree_entry = git(repo, "ls-tree", ref, "--", relative)
                    if not tree_entry.startswith(
                        "100644 "
                    ) and not tree_entry.startswith("100755 "):
                        raise ValueError("ticket must be a regular Git blob")
                    ticket_status = text_fields(
                        git(repo, "show", f"{ref}:{relative}")
                    ).get("Status")
                else:
                    ticket_status = fields(ticket).get("Status")
            except (OSError, UnicodeError, ValueError, subprocess.CalledProcessError):
                ticket_status = None
            if ticket_status not in TICKET_STATUSES:
                add(
                    "ERROR",
                    "TICKET_INVALID",
                    item,
                    "声明的 Ticket 不可读取或 Status 无效",
                )
            elif status == "done" and ticket_status != "done":
                add(
                    "ERROR",
                    "TICKET_NOT_DONE",
                    item,
                    "工作项已完成，但声明的 Ticket 尚未完成",
                )

    if not work_items.exists():
        add(
            "REVIEW",
            "LOCAL_RECORDS_ABSENT",
            "repository",
            "没有本机工作记录；需依据长期记录恢复，不能证明收尾完整",
        )
    elif not records and not findings:
        add("REVIEW", "LOCAL_RECORDS_ABSENT", "repository", "没有可用的当前工作记录")
    current = git(repo, "branch", "--show-current")
    branches = git(
        repo, "for-each-ref", "--format=%(refname:short)", "refs/heads"
    ).splitlines()
    if "master" not in branches:
        add(
            "REVIEW",
            "BASELINE_ABSENT",
            "repository",
            "缺少本地 master，无法核对分支相对基线",
        )
    else:
        for branch in branches:
            if branch in {"master", current}:
                continue
            count = int(
                git(
                    repo,
                    "rev-list",
                    "--count",
                    f"refs/heads/master..refs/heads/{branch}",
                )
            )
            if count:
                add(
                    "REVIEW",
                    "RETAINED_BRANCH",
                    branch,
                    f"有 {count} 个 master 不可达提交；需核对 PR / Squash / 保留原因，不自动判定未合并",
                )
    return {"records": len(records), "findings": findings, "worktrees": worktrees}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--work-item", help="核验指定任务与当前 checkout 的归属")
    selection.add_argument("--closeout", help="严格核验指定任务的本机收尾证据")
    args = parser.parse_args()
    try:
        report = inspect(args.repo, work_item=args.work_item, closeout=args.closeout)
    except (OSError, UnicodeError, ValueError, subprocess.CalledProcessError):
        report = {
            "records": 0,
            "findings": [
                {
                    "level": "ERROR",
                    "code": "INSPECTION_FAILED",
                    "item": "repository",
                    "message": "无法完成本机 Git / 文件检查；未输出记录原文或 Git 错误内容",
                }
            ],
        }
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            f"已检查 {report['records']} 份当前记录（仅本机；不代表远端 / 产品验收通过）"
        )
        for finding in report["findings"]:
            print(
                f"{finding['level']} {finding['code']} [{finding['item']}]: {finding['message']}"
            )
    return int(any(finding["level"] == "ERROR" for finding in report["findings"]))


if __name__ == "__main__":
    raise SystemExit(main())
