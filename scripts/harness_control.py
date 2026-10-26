"""Bind Plugin candidate operations to the selected task's actual checkout."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .check_harness_state import checkout_binding, inspect


def selected_item(arguments: list[str]) -> str | None:
    items = []
    for index, argument in enumerate(arguments):
        if argument == "--work-item":
            if index + 1 == len(arguments):
                raise ValueError("work item missing")
            items.append(arguments[index + 1])
        elif argument.startswith("--work-item="):
            items.append(argument.partition("=")[2])
    if len(items) > 1:
        raise ValueError("duplicate work item")
    return items[0] if items else None


def option(arguments: list[str], name: str) -> str | None:
    for index, value in enumerate(arguments):
        if value == name and index + 1 < len(arguments):
            return arguments[index + 1]
        if value.startswith(name + "="):
            return value.partition("=")[2]
    return None


def requires_candidate(arguments: list[str], adapter: Path) -> bool:
    if arguments[0] == "transition":
        target = option(arguments, "--to")
        config = json.loads(adapter.read_text())
        return any(
            edge.get("candidate_required") and edge["to"] == target
            for edge in config["workflow"]["transitions"]
        )
    return arguments[0] in {
        "diff",
        "capture-baseline",
        "attest-evidence",
        "closeout",
        "maintenance",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--plugin-root", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    arguments = args.arguments
    if not arguments:
        parser.error("Plugin command missing")
    try:
        item = selected_item(arguments)
        binding = checkout_binding(args.project_root, item) if item else None
    except (OSError, UnicodeError, ValueError, subprocess.CalledProcessError):
        print("Harness checkout 归属记录不可核实；未执行 Plugin。", file=sys.stderr)
        return 2
    command = [
        sys.executable,
        str(args.plugin_root / "tools/harness.py"),
        "--project-root",
        str(args.project_root),
        "--adapter",
        str(args.adapter),
    ]
    if arguments[0] != "state":
        overall = (
            arguments[:2] == ["closeout", "finalize"]
            and option(arguments, "--scope") == "overall"
        )
        overall = overall or (
            arguments[0] == "transition" and option(arguments, "--to") == "完成"
        )
        if overall:
            if not item or any(
                f["level"] == "ERROR"
                for f in inspect(args.project_root, closeout=item)["findings"]
            ):
                print("Harness 本机收尾尚未核实；未执行总体完成写入。", file=sys.stderr)
                return 2
        try:
            candidate_required = requires_candidate(arguments, args.adapter)
        except (OSError, ValueError, KeyError, TypeError):
            print("Harness 阶段配置不可核实；未执行 Plugin。", file=sys.stderr)
            return 2
        if candidate_required and item and binding["status"] != "matched":
            print(
                "Harness checkout 与任务未绑定或不匹配；请先恢复该任务的 branch / worktree。",
                file=sys.stderr,
            )
            return 2
        os.execv(sys.executable, [*command, *arguments])
    as_json = "--json" in arguments
    if not as_json:
        arguments = [*arguments, "--json"]
    result = subprocess.run([*command, *arguments], text=True, capture_output=True)
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode:
        print(
            "Plugin 读取失败；请核对包与记录格式兼容性。未回退旧检查。", file=sys.stderr
        )
        return result.returncode
    try:
        state = json.loads(result.stdout)
        if not isinstance(state, dict):
            raise ValueError("invalid state result")
    except (ValueError, json.JSONDecodeError):
        print("Plugin state 未返回有效 JSON；没有输出候选结论。", file=sys.stderr)
        return 2
    record_only = (
        not binding
        or binding["status"] != "matched"
        or state.get("legacy_read_only", False)
    )
    state["checkout_binding"] = binding or {"status": "unbound"}
    state["record_only"] = record_only
    if record_only:
        for key in (
            "candidate",
            "closeout",
            "diff_report_sha256",
            "diff_completeness",
            "maintenance_followups",
        ):
            state[key] = None
        for evidence in state.get("evidence_summary", []):
            evidence["validity"] = "not_checked_for_task_checkout"
    if as_json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    else:
        print(
            f"工作项：{state.get('work_item_id')}；状态：{state.get('lifecycle_status')}；阶段：{state.get('stage')}"
        )
        print(f"下一步：{state.get('next')}")
        if record_only:
            print(
                "仅记录查询：当前记录或 checkout 不能核验该任务候选，不生成 candidate / closeout 结论。"
            )
        else:
            print("checkout 归属匹配；完整候选与收尾依据请使用 --json。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
