"""Validate the PostgreSQL and renderer evidence required by hosted CI."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from pathlib import Path

from scripts.verification_report import parse_junit_counts

_COUNT_FIELDS = ("total", "passed", "failed", "errors", "skipped")
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_GIT_COMMIT = re.compile(r"[0-9a-f]{40,64}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _valid_counts(value: object) -> bool:
    if not isinstance(value, Mapping) or set(value) != set(_COUNT_FIELDS):
        return False
    counts = {field: value[field] for field in _COUNT_FIELDS}
    return (
        all(type(count) is int and count >= 0 for count in counts.values())
        and counts["total"] > 0
        and counts["total"] == sum(counts[field] for field in _COUNT_FIELDS[1:])
        and counts["passed"] == counts["total"]
        and all(counts[field] == 0 for field in _COUNT_FIELDS[2:])
    )


def _read_ci_identity(path: Path) -> dict[str, str] | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None

    identity = {}
    for line in lines:
        key, separator, value = line.partition("=")
        if not separator or not key or not value or key in identity:
            return None
        identity[key] = value

    commit = identity.get("git_commit", "")
    lock_hash = identity.get("uv_lock_sha256", "")
    postgres_image = identity.get("postgres_image_id", "")
    renderer_image = identity.get("python_dev_image_id", "")
    if (
        _GIT_COMMIT.fullmatch(commit) is None
        or _SHA256.fullmatch(lock_hash) is None
        or re.fullmatch(r"sha256:[0-9a-f]{64}", postgres_image) is None
        or re.fullmatch(r"sha256:[0-9a-f]{64}", renderer_image) is None
    ):
        return None
    return identity


def _validate_junit(path: Path, label: str) -> list[str]:
    counts = parse_junit_counts(path)
    if counts is None:
        return [f"{label}: JUnit 缺失、损坏或没有测试用例 ({path.name})"]
    if not _valid_counts(counts):
        return [f"{label}: 必须至少执行一个测试且全部通过 ({counts})"]
    return []


def _is_trusted_renderer_identity(
    report: Mapping[str, object], ci_identity: Mapping[str, str] | None
) -> bool:
    if ci_identity is None:
        return False
    provenance = report.get("provenance")
    if not isinstance(provenance, Mapping):
        return False
    source_start = provenance.get("source_start")
    source_end = provenance.get("source_end")
    if not isinstance(source_start, Mapping) or not isinstance(source_end, Mapping):
        return False
    commit = source_start.get("git_commit")
    tracked_changes_hash = source_start.get("tracked_changes_hash")
    if (
        provenance.get("consistency") != "stable"
        or dict(source_start) != dict(source_end)
        or source_start.get("verified") is not True
        or source_start.get("git_dirty") is not False
        or not isinstance(commit, str)
        or _GIT_COMMIT.fullmatch(commit) is None
        or commit != ci_identity["git_commit"]
        or not isinstance(tracked_changes_hash, str)
        or _SHA256.fullmatch(tracked_changes_hash) is None
    ):
        return False

    environment = report.get("environment")
    if not isinstance(environment, Mapping):
        return False
    lockfiles = environment.get("lockfiles")
    images = environment.get("container_images")
    return (
        environment.get("runner") == "dev-container"
        and environment.get("runtime") == "python"
        and isinstance(environment.get("python_version"), str)
        and bool(environment.get("python_version"))
        and environment.get("lockfiles_verified") is True
        and isinstance(lockfiles, Mapping)
        and isinstance(lockfiles.get("uv"), str)
        and _SHA256.fullmatch(lockfiles["uv"]) is not None
        and lockfiles["uv"] == ci_identity["uv_lock_sha256"]
        and isinstance(images, Mapping)
        and isinstance(images.get("python"), str)
        and re.fullmatch(r"sha256:[0-9a-f]{64}", images["python"]) is not None
        and images["python"] == ci_identity["python_dev_image_id"]
    )


def _validate_renderer_report(
    test_reports: Path, ci_identity: Mapping[str, str] | None
) -> list[str]:
    summaries = sorted(test_reports.glob("*.json"))
    if len(summaries) != 1:
        return [
            f"renderer: 需要且只允许一个根目录 JSON 摘要 (实际 {len(summaries)} 个)"
        ]

    summary_path = summaries[0]
    try:
        report = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return [f"renderer: JSON 摘要缺失或损坏 ({summary_path.name})"]
    if not isinstance(report, Mapping):
        return [f"renderer: JSON 摘要结构无效 ({summary_path.name})"]

    errors = []
    run_id = report.get("run_id")
    if not isinstance(run_id, str) or _RUN_ID.fullmatch(run_id) is None:
        return ["renderer: Run ID 无效"]
    expected_junit = f"{run_id}/renderer.xml"
    junit_path = test_reports / run_id / "renderer.xml"

    if (
        type(report.get("schema_version")) is not int
        or report.get("schema_version") != 1
        or report.get("kind") != "test"
        or report.get("scope") != "renderer"
        or report.get("status") != "passed"
        or type(report.get("exit_code")) is not int
        or report.get("exit_code") != 0
    ):
        errors.append("renderer: 摘要必须是完整通过的 renderer 测试报告")
    if summary_path.name != f"{run_id}.json":
        errors.append("renderer: 摘要文件名必须与 Run ID 一致")
    if report.get("planned_steps") != ["renderer"] or report.get("counted_steps") != [
        "renderer"
    ]:
        errors.append("renderer: 计划和计数步骤必须仅包含 renderer")
    if report.get("missing_artifacts") != []:
        errors.append("renderer: 摘要记录了缺失产物")
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list) or expected_junit not in artifacts:
        errors.append("renderer: 摘要未关联对应的 JUnit 产物")
    if not _is_trusted_renderer_identity(report, ci_identity):
        errors.append("renderer: 源码或运行环境身份缺失、不可信或与CI记录不一致")

    summary_counts = report.get("counts")
    if not _valid_counts(summary_counts):
        errors.append("renderer: 摘要计数缺失、为零或包含失败 / 跳过")

    steps = report.get("steps")
    renderer_steps = (
        [steps[0]]
        if isinstance(steps, list) and len(steps) == 1 and isinstance(steps[0], Mapping)
        else []
    )
    if (
        len(renderer_steps) != 1
        or renderer_steps[0].get("name") != "renderer"
        or renderer_steps[0].get("status") != "passed"
        or type(renderer_steps[0].get("exit_code")) is not int
        or renderer_steps[0].get("exit_code") != 0
        or not _valid_counts(renderer_steps[0].get("counts"))
    ):
        errors.append("renderer: renderer 步骤证据不完整或未通过")

    junit_counts = parse_junit_counts(junit_path)
    if junit_counts is None:
        errors.append("renderer: JUnit 缺失、损坏或没有测试用例")
    elif not _valid_counts(junit_counts):
        errors.append(f"renderer: JUnit 必须全部通过且计数非零 ({junit_counts})")
    elif _valid_counts(summary_counts) and dict(summary_counts) != junit_counts:
        errors.append(
            "renderer: JSON 摘要计数与 JUnit 不一致 "
            f"(summary={dict(summary_counts)}, junit={junit_counts})"
        )
    elif (
        len(renderer_steps) == 1
        and _valid_counts(renderer_steps[0].get("counts"))
        and dict(renderer_steps[0]["counts"]) != junit_counts
    ):
        errors.append("renderer: renderer 步骤计数与 JUnit 不一致")

    return errors


def validate_ci_test_evidence(ci_reports: Path, test_reports: Path) -> list[str]:
    """Return actionable errors when required reports are missing or incomplete."""

    errors = []
    for filename in ("postgres-ci.xml", "postgres-development.xml"):
        errors.extend(_validate_junit(ci_reports / filename, filename))
    errors.extend(
        _validate_renderer_report(
            test_reports, _read_ci_identity(ci_reports / "environment.txt")
        )
    )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="核验 CI 数据库和 renderer 测试证据")
    parser.add_argument("--ci-reports", type=Path, required=True)
    parser.add_argument("--test-reports", type=Path, required=True)
    args = parser.parse_args(argv)

    errors = validate_ci_test_evidence(args.ci_reports, args.test_reports)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("PostgreSQL CI / development 与 renderer 测试证据完整。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
