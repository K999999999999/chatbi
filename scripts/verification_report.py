"""Safe run identity and exclusive report-pair helpers (standard library only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")


class ReportWriteError(RuntimeError):
    """A report pair could not be saved without overwriting existing evidence."""


@dataclass(frozen=True, slots=True)
class RunStart:
    run_id: str
    started_at: str
    source_start: Mapping[str, object]
    inputs_start: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class VerificationStart:
    """Immutable identity captured before a local verification command."""

    run_id: str
    kind: str
    scope: str
    started_at: str
    source_start: Mapping[str, object]
    parameters: Mapping[str, object]
    environment: Mapping[str, object]
    planned_steps: tuple[str, ...]
    counted_steps: tuple[str, ...]


def start_run(
    repository_root: Path,
    inputs: Mapping[str, Path],
    *,
    suite: str,
    now: datetime | None = None,
    git_state_reader: Callable[[Path], tuple[str, bool]] | None = None,
) -> RunStart:
    """Capture safe source/input identities before loading or executing a run."""

    if _SAFE_NAME.fullmatch(suite) is None:
        raise ValueError("suite name is not safe for a report ID")
    started = _utc_timestamp(now)
    timestamp = datetime.fromisoformat(started)
    source = capture_source_identity(repository_root, git_state_reader)
    return RunStart(
        run_id=create_run_id(
            str(source.get("git_commit") or ""), suite=suite, now=timestamp
        ),
        started_at=started,
        source_start=source,
        inputs_start=capture_inputs_identity(inputs),
    )


def finish_run(
    start: RunStart,
    repository_root: Path,
    inputs: Mapping[str, Path],
    *,
    now: datetime | None = None,
    git_state_reader: Callable[[Path], tuple[str, bool]] | None = None,
) -> dict[str, object]:
    """Capture end identities and classify the evidence as stable/changed/unverified."""

    finished_at = _utc_timestamp(now)
    source_end = capture_source_identity(repository_root, git_state_reader)
    inputs_end = capture_inputs_identity(inputs)
    verified = all(
        identity.get("verified") is True
        for identity in (
            start.source_start,
            source_end,
            start.inputs_start,
            inputs_end,
        )
    )
    if not verified:
        consistency = "unverified"
    elif (
        dict(start.source_start) != source_end or dict(start.inputs_start) != inputs_end
    ):
        consistency = "changed"
    else:
        consistency = "stable"

    return {
        "version": 1,
        "started_at": start.started_at,
        "finished_at": finished_at,
        "source_start": dict(start.source_start),
        "source_end": source_end,
        "inputs_start": dict(start.inputs_start),
        "inputs_end": inputs_end,
        "consistency": consistency,
    }


def capture_source_identity(
    repository_root: Path,
    git_state_reader: Callable[[Path], tuple[str, bool]] | None = None,
) -> dict[str, object]:
    """Read Git identity and hash tracked changes without retaining their contents."""

    try:
        if git_state_reader is None:
            commit = (
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repository_root),
                        "rev-parse",
                        "--verify",
                        "HEAD",
                    ],
                    check=True,
                    capture_output=True,
                )
                .stdout.decode("ascii")
                .strip()
            )
            dirty = False
        else:
            commit, dirty = git_state_reader(repository_root)
            if type(dirty) is not bool:
                raise ValueError("Git dirty state is not boolean")
        status = subprocess.run(
            ["git", "-C", str(repository_root), "status", "--porcelain=v1", "-z"],
            check=True,
            capture_output=True,
        ).stdout
        if git_state_reader is None:
            dirty = bool(status)
        diff = subprocess.run(
            [
                "git",
                "-C",
                str(repository_root),
                "diff",
                "--binary",
                "--no-ext-diff",
                "HEAD",
                "--",
            ],
            check=True,
            capture_output=True,
        ).stdout
        if not isinstance(commit, str) or not commit.strip():
            raise ValueError("Git returned an empty commit")
    except (
        OSError,
        RuntimeError,
        TypeError,
        UnicodeError,
        ValueError,
        subprocess.SubprocessError,
    ):
        return {
            "verified": False,
            "git_commit": None,
            "git_dirty": None,
            "tracked_changes_hash": None,
        }
    return {
        "verified": re.fullmatch(r"[0-9a-f]{40,64}", commit) is not None,
        "git_commit": commit,
        "git_dirty": bool(dirty),
        "tracked_changes_hash": hashlib.sha256(diff).hexdigest(),
    }


def capture_inputs_identity(inputs: Mapping[str, Path]) -> dict[str, object]:
    """Hash named input files while excluding their paths and contents from reports."""

    fingerprints: dict[str, str] = {}
    context_digest = hashlib.sha256()
    context_found = False
    try:
        for name, path in sorted(inputs.items()):
            if _SAFE_NAME.fullmatch(name) is None:
                raise ValueError("input name is not safe")
            content = path.read_bytes()
            fingerprints[name] = hashlib.sha256(content).hexdigest()
            if name.startswith("context."):
                context_found = True
                context_name = name.removeprefix("context.")
                context_digest.update(context_name.encode("utf-8"))
                context_digest.update(b"\0")
                context_digest.update(content)
                context_digest.update(b"\0")
    except (OSError, TypeError, ValueError):
        return {"verified": False, "fingerprints": {}}
    identity: dict[str, object] = {
        "verified": bool(fingerprints),
        "fingerprints": fingerprints,
    }
    if context_found:
        identity["context_hash"] = context_digest.hexdigest()
    return identity


def create_run_id(
    git_commit: str,
    *,
    suite: str,
    now: datetime | None = None,
) -> str:
    """Create a path-safe ID that remains unique at a fixed time and commit."""

    if _SAFE_NAME.fullmatch(suite) is None:
        raise ValueError("suite name is not safe for a report ID")
    timestamp = datetime.fromisoformat(_utc_timestamp(now))
    stamp = timestamp.strftime("%Y%m%dT%H%M%SZ")
    short_commit = git_commit[:7] if git_commit else "unverified"
    if re.fullmatch(r"[0-9a-fA-F]{1,64}", short_commit) is None:
        short_commit = "unverified"
    return f"{stamp}-{short_commit}-{suite}-{uuid4().hex[:12]}"


def write_report_pair(
    output_directory: Path,
    run_id: str,
    json_content: str,
    markdown_content: str,
) -> tuple[Path, Path]:
    """Create a JSON/Markdown pair exclusively; never replace prior evidence."""

    if _SAFE_NAME.fullmatch(run_id) is None:
        raise ReportWriteError("评测 Run ID 无效")
    json_path = output_directory / f"{run_id}.json"
    markdown_path = output_directory / f"{run_id}.md"
    json_fd: int | None = None
    markdown_fd: int | None = None
    try:
        output_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        json_fd = os.open(json_path, flags, 0o600)
        markdown_fd = os.open(markdown_path, flags, 0o600)
        with os.fdopen(json_fd, "wb") as json_file:
            json_fd = None
            json_file.write(json_content.encode("utf-8"))
        with os.fdopen(markdown_fd, "wb") as markdown_file:
            markdown_fd = None
            markdown_file.write(markdown_content.encode("utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise ReportWriteError("评测 JSON / Markdown 报告未能完整保存") from None
    finally:
        if json_fd is not None:
            os.close(json_fd)
        if markdown_fd is not None:
            os.close(markdown_fd)
    return json_path, markdown_path


def start_verification(
    repository_root: Path,
    *,
    kind: str,
    scope: str,
    parameters: Mapping[str, object],
    environment: Mapping[str, object],
    planned_steps: tuple[str, ...],
    counted_steps: tuple[str, ...] | None = None,
    now: datetime | None = None,
) -> VerificationStart:
    """Capture a safe command identity before local verification begins."""

    if kind not in {"test", "check", "business-acceptance"}:
        raise ValueError("verification kind is not allowed")
    if _SAFE_NAME.fullmatch(scope) is None or len(scope) > 32:
        raise ValueError("verification scope is not safe")
    if len(set(planned_steps)) != len(planned_steps):
        raise ValueError("verification step names must be unique")
    for name in planned_steps:
        if _SAFE_NAME.fullmatch(name) is None or len(name) > 48:
            raise ValueError("verification step name is not safe")
    counted = (
        planned_steps
        if counted_steps is None and kind == "test"
        else (counted_steps or ())
    )
    if len(set(counted)) != len(counted) or any(
        name not in planned_steps for name in counted
    ):
        raise ValueError("counted verification steps must be planned")

    safe_parameters = _safe_parameters(parameters)
    environment_values = dict(environment)
    if (
        kind in {"test", "check"}
        and environment_values.get("runner") == "dev-container"
    ):
        required_lockfiles = _required_lockfiles(planned_steps)
        lockfile_paths = {
            "uv": repository_root / "uv.lock",
            "npm": repository_root / "frontend" / "package-lock.json",
        }
        lockfiles = {}
        for name in required_lockfiles:
            try:
                lockfiles[name] = hashlib.sha256(
                    lockfile_paths[name].read_bytes()
                ).hexdigest()
            except OSError:
                continue
        environment_values["lockfiles"] = lockfiles
        environment_values["lockfiles_verified"] = set(lockfiles) == required_lockfiles
    safe_environment = _safe_environment(environment_values)
    started_at = _utc_timestamp(now)
    source_start = capture_source_identity(repository_root)
    return VerificationStart(
        run_id=create_run_id(
            str(source_start.get("git_commit") or ""),
            suite=f"{kind}-{scope}",
            now=datetime.fromisoformat(started_at),
        ),
        kind=kind,
        scope=scope,
        started_at=started_at,
        source_start=source_start,
        parameters=safe_parameters,
        environment=safe_environment,
        planned_steps=planned_steps,
        counted_steps=counted,
    )


def finish_verification(
    start: VerificationStart,
    repository_root: Path,
    *,
    exit_code: int | None,
    counts: Mapping[str, int] | None,
    steps: tuple[Mapping[str, object], ...],
    cleanup_status: str,
    artifacts: tuple[str, ...] = (),
    missing_artifacts: tuple[str, ...] = (),
    interrupted: bool = False,
    now: datetime | None = None,
) -> dict[str, object]:
    """Build a command summary without turning missing evidence into success."""

    if exit_code is not None and (type(exit_code) is not int or exit_code < 0):
        raise ValueError("verification exit code is invalid")
    if cleanup_status not in {"passed", "failed", "not_applicable", "not_run"}:
        raise ValueError("verification cleanup status is invalid")
    safe_counts = _safe_counts(counts)
    safe_artifacts = _safe_artifacts(artifacts)
    safe_missing_artifacts = _safe_artifacts(missing_artifacts)
    safe_steps = _complete_steps(
        start.planned_steps,
        steps,
        counted_steps=start.counted_steps,
    )
    if safe_counts is None and start.counted_steps:
        safe_counts = _aggregate_counts(safe_steps, start.counted_steps)
    source_end = capture_source_identity(repository_root)
    source_verified = (
        start.source_start.get("verified") is True
        and source_end.get("verified") is True
    )
    consistency = (
        "unverified"
        if not source_verified
        else "stable"
        if dict(start.source_start) == source_end
        else "changed"
    )
    finished_at = _utc_timestamp(now)
    status = _verification_status(
        start.kind,
        exit_code=exit_code,
        counts=safe_counts,
        steps=safe_steps,
        cleanup_status=cleanup_status,
        interrupted=interrupted,
    )
    if status == "passed" and consistency != "stable":
        status = "incomplete"
    if status == "passed" and start.environment.get("lockfiles_verified") is False:
        status = "incomplete"
    if status == "passed" and start.kind in {"test", "check"}:
        images = start.environment.get("container_images", {})
        image_names = set(images) if isinstance(images, Mapping) else set()
        if not _required_container_images(start).issubset(image_names):
            status = "incomplete"
    if status == "passed" and safe_missing_artifacts:
        status = "incomplete"
    counts_reason = None
    if safe_counts is None:
        counts_reason = "unavailable" if start.kind == "test" else "not_applicable"
    return {
        "schema_version": 1,
        "run_id": start.run_id,
        "kind": start.kind,
        "scope": start.scope,
        "parameters": dict(start.parameters),
        "started_at": start.started_at,
        "finished_at": finished_at,
        "provenance": {
            "version": 1,
            "source_start": dict(start.source_start),
            "source_end": source_end,
            "consistency": consistency,
        },
        "environment": dict(start.environment),
        "planned_steps": list(start.planned_steps),
        "counted_steps": list(start.counted_steps),
        "status": status,
        "exit_code": exit_code,
        "cleanup_status": cleanup_status,
        "counts": safe_counts,
        "counts_reason": counts_reason,
        "steps": safe_steps,
        "artifacts": list(safe_artifacts),
        "missing_artifacts": list(safe_missing_artifacts),
        "business_acceptance_status": (
            "not_run" if start.kind != "business-acceptance" else status
        ),
    }


def parse_junit_counts(path: Path) -> dict[str, int] | None:
    """Read real pytest/JUnit case outcomes; never infer counts from console text."""

    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError):
        return None
    cases = list(root.iter("testcase"))
    if not cases:
        return None
    counts = {"total": len(cases), "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for case in cases:
        if case.find("error") is not None:
            counts["errors"] += 1
        elif case.find("failure") is not None:
            counts["failed"] += 1
        elif case.find("skipped") is not None:
            counts["skipped"] += 1
        else:
            counts["passed"] += 1
    return counts


def parse_playwright_counts(path: Path) -> dict[str, int] | None:
    """Read Playwright JSON reporter totals without retaining failure text."""

    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    stats = report.get("stats") if isinstance(report, Mapping) else None
    if not isinstance(stats, Mapping):
        return None
    required_fields = ("expected", "unexpected", "flaky", "skipped")
    values = {field: stats.get(field) for field in required_fields}
    interrupted = stats.get("interrupted", 0)
    if any(type(value) is not int or value < 0 for value in values.values()) or (
        type(interrupted) is not int or interrupted < 0
    ):
        return None
    counts = {
        "total": sum(values.values()) + interrupted,
        "passed": values["expected"],
        "failed": values["unexpected"] + values["flaky"],
        "errors": interrupted,
        "skipped": values["skipped"],
    }
    return counts if counts["total"] > 0 else None


def write_verification_summary(
    output_directory: Path,
    run_id: str,
    report: Mapping[str, object],
) -> Path:
    """Publish one JSON summary exclusively with restrictive file permissions."""

    if _SAFE_NAME.fullmatch(run_id) is None or report.get("run_id") != run_id:
        raise ReportWriteError("验证报告 Run ID 无效或不一致")
    path = output_directory / f"{run_id}.json"
    descriptor: int | None = None
    try:
        output_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
        with os.fdopen(descriptor, "wb") as report_file:
            descriptor = None
            payload = json.dumps(
                dict(report), ensure_ascii=False, indent=2, allow_nan=False
            )
            report_file.write((payload + "\n").encode("utf-8"))
    except (OSError, TypeError, UnicodeError, ValueError):
        raise ReportWriteError("本地验证报告无法安全保存") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return path


def _safe_parameters(parameters: Mapping[str, object]) -> dict[str, object]:
    allowed = {"filtered", "mode"}
    result = {}
    for name, value in parameters.items():
        if name not in allowed:
            raise ValueError("verification parameter is not allowlisted")
        if name == "filtered":
            if type(value) is not bool:
                raise ValueError("filtered parameter must be boolean")
            result[name] = value
        elif name == "mode":
            if not isinstance(value, str) or value not in {"isolated", "real"}:
                raise ValueError("verification mode is not allowed")
            result[name] = value
    return result


def _safe_environment(environment: Mapping[str, object]) -> dict[str, object]:
    allowed = {
        "runner",
        "runtime",
        "python_version",
        "node_version",
        "lockfiles",
        "lockfiles_verified",
        "container_images",
    }
    result = {}
    for name, value in environment.items():
        if name not in allowed:
            raise ValueError("verification environment field is not safe")
        if name in {"lockfiles", "container_images"}:
            if not isinstance(value, Mapping):
                raise ValueError("verification environment map is invalid")
            field_names = (
                {"uv", "npm"}
                if name == "lockfiles"
                else {"python", "node", "browser", "postgres"}
            )
            checked = {}
            for field, fingerprint in value.items():
                if field not in field_names or not isinstance(fingerprint, str):
                    raise ValueError("verification environment map is not allowlisted")
                pattern = (
                    r"[0-9a-f]{64}" if name == "lockfiles" else r"sha256:[0-9a-f]{64}"
                )
                if re.fullmatch(pattern, fingerprint) is None:
                    raise ValueError("verification environment fingerprint is invalid")
                checked[field] = fingerprint
            result[name] = checked
        elif name == "lockfiles_verified":
            if type(value) is not bool:
                raise ValueError("verification lockfile status is invalid")
            result[name] = value
        else:
            if not isinstance(value, str) or len(value) > 64:
                raise ValueError("verification environment value is not safe")
            if re.fullmatch(r"[A-Za-z0-9_.+ -]+", value) is None:
                raise ValueError("verification environment value is not safe")
            result[name] = value
    return result


def _required_lockfiles(planned_steps: tuple[str, ...]) -> set[str]:
    required = {"uv"}
    node_steps = {
        "browser-image-build",
        "web-build",
        "web-packaged",
        "web-dev",
        "export-build",
    }
    if set(planned_steps) & node_steps:
        required.add("npm")
    return required


def _required_container_images(start: VerificationStart) -> set[str]:
    if (
        start.kind not in {"test", "check"}
        or start.environment.get("runner") != "dev-container"
    ):
        return set()
    required = {"python"}
    planned = set(start.planned_steps)
    if planned & {"database-ci", "database-development"}:
        required.add("postgres")
    if planned & {"browser-image-build", "web-packaged", "web-dev"}:
        required.add("browser")
    if planned & {"web-build", "export-build"}:
        required.add("node")
    return required


def _safe_counts(counts: Mapping[str, int] | None) -> dict[str, int] | None:
    if counts is None:
        return None
    fields = ("total", "passed", "failed", "errors", "skipped")
    if set(counts) != set(fields) or any(
        type(counts[field]) is not int or counts[field] < 0 for field in fields
    ):
        raise ValueError("verification counts are invalid")
    if counts["total"] != sum(counts[field] for field in fields[1:]):
        raise ValueError("verification counts do not add up")
    return {field: counts[field] for field in fields}


def _safe_artifacts(artifacts: tuple[str, ...]) -> tuple[str, ...]:
    for artifact in artifacts:
        parts = artifact.split("/")
        if (
            not artifact
            or artifact.startswith("/")
            or ".." in parts
            or any(_SAFE_NAME.fullmatch(part) is None for part in parts)
        ):
            raise ValueError("verification artifact path is unsafe")
    return artifacts


def _complete_steps(
    planned: tuple[str, ...],
    steps: tuple[Mapping[str, object], ...],
    *,
    counted_steps: tuple[str, ...],
) -> list[dict[str, object]]:
    allowed_statuses = {"passed", "failed", "running", "not_run", "interrupted"}
    indexed = {}
    for step in steps:
        name = step.get("name")
        if (
            name not in planned
            or name in indexed
            or step.get("status") not in allowed_statuses
        ):
            raise ValueError("verification step does not match the plan")
        exit_code = step.get("exit_code")
        if exit_code is not None and (type(exit_code) is not int or exit_code < 0):
            raise ValueError("verification step exit code is invalid")
        counts = _safe_counts(step.get("counts"))
        artifacts = _safe_artifacts(tuple(step.get("artifacts", ())))
        counts_applicable = step.get("counts_applicable", name in counted_steps)
        if type(counts_applicable) is not bool:
            raise ValueError("verification count applicability is invalid")
        indexed[name] = {
            "name": name,
            "status": step["status"],
            "exit_code": exit_code,
            "counts": counts,
            "counts_applicable": counts_applicable,
            "artifacts": list(artifacts),
        }
    return [
        indexed.get(
            name,
            {
                "name": name,
                "status": "not_run",
                "exit_code": None,
                "counts": None,
                "counts_applicable": name in counted_steps,
                "artifacts": [],
            },
        )
        for name in planned
    ]


def _aggregate_counts(
    steps: list[dict[str, object]], counted_steps: tuple[str, ...]
) -> dict[str, int] | None:
    by_name = {step["name"]: step for step in steps}
    values = [by_name[name].get("counts") for name in counted_steps]
    if not values or any(not isinstance(value, Mapping) for value in values):
        return None
    fields = ("total", "passed", "failed", "errors", "skipped")
    return {field: sum(value[field] for value in values) for field in fields}


def _verification_status(
    kind: str,
    *,
    exit_code: int | None,
    counts: Mapping[str, int] | None,
    steps: list[dict[str, object]],
    cleanup_status: str,
    interrupted: bool,
) -> str:
    statuses = {step["status"] for step in steps}
    if interrupted or "interrupted" in statuses:
        return "interrupted"
    if exit_code not in (0, None) or cleanup_status == "failed" or "failed" in statuses:
        return "failed"
    if counts is not None and (counts["failed"] > 0 or counts["errors"] > 0):
        return "failed"
    if (
        exit_code is None
        or cleanup_status == "not_run"
        or statuses - {"passed"}
        or (kind in {"test", "business-acceptance"} and counts is None)
        or (counts is not None and counts["skipped"] > 0)
    ):
        return "incomplete"
    return "passed"


def _state_file(reports_directory: Path, run_id: str) -> Path:
    if _SAFE_NAME.fullmatch(run_id) is None:
        raise ValueError("verification Run ID is invalid")
    root = reports_directory.resolve()
    run_directory = (root / run_id).resolve()
    if run_directory.parent != root:
        raise ValueError("verification state directory is unsafe")
    return run_directory / ".state.json"


def _write_state(
    path: Path, state: Mapping[str, object], *, exclusive: bool = False
) -> None:
    payload = (
        json.dumps(dict(state), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    if exclusive:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
        with os.fdopen(descriptor, "wb") as state_file:
            state_file.write(payload)
        return

    descriptor, temporary_name = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as state_file:
            descriptor = -1
            state_file.write(payload)
        os.replace(temporary_path, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary_path.unlink(missing_ok=True)


def _read_state(path: Path) -> dict[str, object]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError("verification run state is unavailable") from None
    if not isinstance(state, dict):
        raise ValueError("verification run state is invalid")
    return state


def _start_from_state(payload: object) -> VerificationStart:
    if not isinstance(payload, Mapping):
        raise ValueError("verification start state is invalid")
    try:
        return VerificationStart(
            run_id=payload["run_id"],
            kind=payload["kind"],
            scope=payload["scope"],
            started_at=payload["started_at"],
            source_start=payload["source_start"],
            parameters=payload["parameters"],
            environment=payload["environment"],
            planned_steps=tuple(payload["planned_steps"]),
            counted_steps=tuple(payload["counted_steps"]),
        )
    except (KeyError, TypeError):
        raise ValueError("verification start state is invalid") from None


def _relative_artifact(path: Path, reports_directory: Path) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(reports_directory.resolve()).as_posix()
    except ValueError:
        raise ValueError(
            "verification artifact is outside its report directory"
        ) from None
    return _safe_artifacts((relative,))[0]


def _begin_session(args: argparse.Namespace) -> int:
    parameters: dict[str, object] = {}
    if args.filtered:
        parameters["filtered"] = True
    if args.mode is not None:
        parameters["mode"] = args.mode
    environment: dict[str, object] = {
        "runner": args.runner,
        "runtime": args.runtime,
    }
    if args.runtime == "python":
        environment["python_version"] = platform.python_version()
    start = start_verification(
        args.repository_root,
        kind=args.kind,
        scope=args.scope,
        parameters=parameters,
        environment=environment,
        planned_steps=tuple(args.step),
        counted_steps=(
            tuple(args.counted_step) if args.counted_step is not None else None
        ),
    )
    args.reports_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_directory = args.reports_directory / start.run_id
    run_directory.mkdir(mode=0o700)
    state = {
        "start": {
            "run_id": start.run_id,
            "kind": start.kind,
            "scope": start.scope,
            "started_at": start.started_at,
            "source_start": dict(start.source_start),
            "parameters": dict(start.parameters),
            "environment": dict(start.environment),
            "planned_steps": list(start.planned_steps),
            "counted_steps": list(start.counted_steps),
        },
        "steps": [
            {
                "name": name,
                "status": "not_run",
                "exit_code": None,
                "counts": None,
                "counts_applicable": name in start.counted_steps,
                "artifacts": [],
            }
            for name in start.planned_steps
        ],
    }
    _write_state(
        _state_file(args.reports_directory, start.run_id), state, exclusive=True
    )
    print(start.run_id)
    return 0


def _update_step(args: argparse.Namespace, *, complete: bool) -> int:
    state_path = _state_file(args.reports_directory, args.run_id)
    state = _read_state(state_path)
    start = _start_from_state(state.get("start"))
    steps = state.get("steps")
    if not isinstance(steps, list):
        raise ValueError("verification step state is invalid")
    step = next(
        (
            item
            for item in steps
            if isinstance(item, dict) and item.get("name") == args.name
        ),
        None,
    )
    if step is None:
        raise ValueError("verification step is not planned")
    if not complete:
        if step.get("status") != "not_run":
            raise ValueError("verification step has already started")
        step["status"] = "running"
    else:
        if step.get("status") != "running":
            raise ValueError("verification step was not started")
        status = args.status or ("passed" if args.exit_code == 0 else "failed")
        counts = None
        artifacts: list[str] = []
        if args.junit is not None:
            counts = parse_junit_counts(args.junit)
            if args.junit.is_file() and not args.counts_only:
                artifacts.append(_relative_artifact(args.junit, args.reports_directory))
        if args.playwright is not None:
            counts = parse_playwright_counts(args.playwright)
            if args.playwright.is_file() and not args.counts_only:
                artifacts.append(
                    _relative_artifact(args.playwright, args.reports_directory)
                )
        for artifact in args.artifact:
            artifact_path = Path(artifact)
            if not artifact_path.is_absolute():
                artifact_path = args.reports_directory / artifact_path
            if artifact_path.exists():
                artifacts.append(
                    _relative_artifact(artifact_path, args.reports_directory)
                )
        step.update(
            {
                "status": status,
                "exit_code": args.exit_code,
                "counts": counts,
                "counts_applicable": not args.counts_not_applicable,
                "artifacts": list(dict.fromkeys(artifacts)),
            }
        )
    _write_state(state_path, state)
    return 0


def _finish_session(args: argparse.Namespace) -> int:
    state_path = _state_file(args.reports_directory, args.run_id)
    state = _read_state(state_path)
    start = _start_from_state(state.get("start"))
    raw_steps = state.get("steps")
    if not isinstance(raw_steps, list) or any(
        not isinstance(item, dict) for item in raw_steps
    ):
        raise ValueError("verification step state is invalid")
    environment = dict(start.environment)
    container_images = dict(environment.get("container_images", {}))
    for item in args.container_image:
        name, separator, image_id = item.partition("=")
        if not separator or name in container_images:
            raise ValueError("verification container image identity is invalid")
        container_images[name] = image_id
    if container_images:
        environment["container_images"] = container_images
    start = replace(start, environment=_safe_environment(environment))
    steps = tuple(raw_steps)
    if args.interrupted:
        steps = tuple(
            {**step, "status": "interrupted"}
            if step.get("status") == "running"
            else step
            for step in steps
        )
    step_artifacts = tuple(
        artifact
        for step in steps
        for artifact in step.get("artifacts", [])
        if isinstance(artifact, str)
    )
    extra_artifacts = _safe_artifacts(tuple(args.artifact))
    artifact_root = (args.artifact_root or args.reports_directory).resolve()
    existing_extra_artifacts = []
    missing_extra_artifacts = []
    for artifact in extra_artifacts:
        artifact_path = (artifact_root / artifact).resolve()
        if not artifact_path.is_relative_to(artifact_root):
            raise ValueError("verification artifact is outside its report directory")
        if artifact_path.exists():
            existing_extra_artifacts.append(artifact)
        else:
            missing_extra_artifacts.append(artifact)
    report = finish_verification(
        start,
        args.repository_root,
        exit_code=args.exit_code,
        counts=None,
        steps=steps,
        cleanup_status=args.cleanup_status,
        artifacts=tuple(dict.fromkeys((*step_artifacts, *existing_extra_artifacts))),
        missing_artifacts=tuple(missing_extra_artifacts),
        interrupted=args.interrupted,
    )
    path = write_verification_summary(
        args.output_directory or args.reports_directory, args.run_id, report
    )
    print(path.name)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="本地开发验证报告工具")
    commands = parser.add_subparsers(dest="command", required=True)
    begin = commands.add_parser("begin")
    begin.add_argument("--repository-root", type=Path, required=True)
    begin.add_argument("--reports-directory", type=Path, required=True)
    begin.add_argument(
        "--kind", choices=("test", "check", "business-acceptance"), required=True
    )
    begin.add_argument("--scope", required=True)
    begin.add_argument("--step", action="append", required=True)
    begin.add_argument("--counted-step", action="append")
    begin.add_argument(
        "--runner", choices=("dev-container", "host-browser"), default="dev-container"
    )
    begin.add_argument(
        "--runtime", choices=("python", "node", "browser"), default="python"
    )
    begin.add_argument("--mode", choices=("isolated", "real"))
    begin.add_argument("--filtered", action="store_true")
    step_start = commands.add_parser("step-start")
    _add_session_arguments(step_start)
    step_start.add_argument("--name", required=True)
    step_finish = commands.add_parser("step-finish")
    _add_session_arguments(step_finish)
    step_finish.add_argument("--name", required=True)
    step_finish.add_argument("--exit-code", type=int, required=True)
    step_finish.add_argument(
        "--status", choices=("passed", "failed", "interrupted", "not_run")
    )
    step_finish.add_argument("--junit", type=Path)
    step_finish.add_argument("--playwright", type=Path)
    step_finish.add_argument("--artifact", action="append", default=[])
    step_finish.add_argument("--counts-not-applicable", action="store_true")
    step_finish.add_argument("--counts-only", action="store_true")
    finish = commands.add_parser("finish")
    finish.add_argument("--repository-root", type=Path, required=True)
    finish.add_argument("--reports-directory", type=Path, required=True)
    finish.add_argument("--run-id", required=True)
    finish.add_argument("--output-directory", type=Path)
    finish.add_argument("--artifact-root", type=Path)
    finish.add_argument("--container-image", action="append", default=[])
    finish.add_argument("--exit-code", type=int)
    finish.add_argument("--artifact", action="append", default=[])
    finish.add_argument(
        "--cleanup-status",
        choices=("passed", "failed", "not_applicable", "not_run"),
        default="not_applicable",
    )
    finish.add_argument("--interrupted", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "begin":
            return _begin_session(args)
        if args.command == "step-start":
            return _update_step(args, complete=False)
        if args.command == "step-finish":
            return _update_step(args, complete=True)
        return _finish_session(args)
    except (OSError, ReportWriteError, TypeError, ValueError):
        print("本地验证报告未能安全生成；命令按失败 / 未确认处理。", file=sys.stderr)
        return 2


def _add_session_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--reports-directory", type=Path, required=True)
    parser.add_argument("--run-id", required=True)


def _utc_timestamp(now: datetime | None) -> str:
    value = datetime.now(UTC) if now is None else now
    if value.tzinfo is None:
        raise ValueError("run timestamp must include a timezone")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
