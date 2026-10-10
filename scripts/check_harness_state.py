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
}
STATUSES = {"open", "in-progress", "blocked", "done"}
HARNESS_REVIEW_STATUSES = {"no-gap", "gap-found"}


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(repo), *args],
        text=True,
        stderr=subprocess.PIPE,
    ).strip()


def fields(path: Path) -> dict[str, str]:
    """Read current unindented fields; exclude fenced examples and history."""
    values: dict[str, str] = {}
    fence = ""
    for line in path.read_text(encoding="utf-8").splitlines():
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
        if re.match(r"^#{1,6}\s+(历史|History\b)", line, re.IGNORECASE):
            break
        key, separator, value = line.partition(":")
        if separator and key in FIELDS:
            if key in values:
                raise ValueError("duplicate current field")
            values[key] = value.strip()
    return values


def references(value: str) -> list[str]:
    return [] if value in {"", "None"} else [part.strip() for part in value.split(",")]


def inspect(repo: Path) -> dict:
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
        if values.get("ID") != item or values.get("Status") not in STATUSES:
            add(
                "ERROR",
                "RECORD_INVALID",
                item,
                "ID / Status 缺失、无效或 ID 与目录不一致",
            )
            continue
        records[item] = values

    for item, values in records.items():
        status = values["Status"]
        if status != "done":
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
                elif key == "Active work item" and records[target]["Status"] == "done":
                    add(
                        "ERROR",
                        "ACTIVE_COMPLETED",
                        item,
                        "Active work item 已完成，汇总需同步",
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
            ticket = (root / declared).resolve()
            if declared.is_absolute() or not ticket.is_relative_to(root):
                add(
                    "ERROR",
                    "TICKET_OUTSIDE_REPO",
                    item,
                    "Ticket files 必须指向仓库内相对路径",
                )
                continue
            try:
                ticket_status = fields(ticket).get("Status")
            except (OSError, UnicodeError, ValueError):
                ticket_status = None
            if ticket_status not in STATUSES:
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
    if git(repo, "status", "--porcelain=v1", "--untracked-files=all"):
        add(
            "REVIEW",
            "DIRTY_WORKTREE",
            "repository",
            "当前工作区有修改；需判断归属与阶段",
        )
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
    return {"records": len(records), "findings": findings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = inspect(args.repo)
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
