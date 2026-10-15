"""Safe run identity and exclusive report-pair helpers (standard library only)."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")


class ReportWriteError(RuntimeError):
    """A report pair could not be saved without overwriting existing evidence."""


@dataclass(frozen=True, slots=True)
class RunStart:
    run_id: str
    started_at: str
    source_start: Mapping[str, object]
    inputs_start: Mapping[str, object]


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


def _utc_timestamp(now: datetime | None) -> str:
    value = datetime.now(UTC) if now is None else now
    if value.tzinfo is None:
        raise ValueError("run timestamp must include a timezone")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
