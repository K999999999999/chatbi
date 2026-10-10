"""恢复候选与显式切换日志的受限本地状态格式。"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.local_backup import (
    BackupFailed,
    atomic_json,
    secure_directory,
    secure_file,
)

RESTORE_ID = re.compile(r"[0-9a-f]{32}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
RECORD_FIELDS = {
    "format",
    "id",
    "status",
    "backup_id",
    "binding",
    "source_commit",
    "api_image",
    "api_image_id",
    "database_image",
    "database_image_id",
    "compatibility_sha256",
    "created_at",
    "verified_at",
    "fingerprints",
    "normalization",
    "verification",
}
JOURNAL_FIELDS = {
    "format",
    "id",
    "state",
    "phase",
    "choice",
    "previous",
    "candidate",
    "updated_at",
}
JOURNAL_PHASES = {
    "candidate-stopping",
    "candidate-stopped",
    "previous-stopping",
    "previous-stopped",
    "binding-switched",
    "candidate-starting",
    "candidate-verified",
    "complete",
    "recover-stopping",
    "recover-stopped",
    "recover-binding-switched",
    "recover-starting",
}


class RestoreStateInvalid(RuntimeError):
    pass


def _timestamp(value):
    if not isinstance(value, str):
        return False
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def _fingerprints(value):
    if not isinstance(value, dict) or set(value) != {"business", "control"}:
        return False
    for database in value.values():
        if not isinstance(database, dict) or not database:
            return False
        for name, digest in database.items():
            if (
                not isinstance(name, str)
                or not name
                or not isinstance(digest, dict)
                or set(digest) != {"rows", "sha256"}
                or type(digest["rows"]) is not int
                or digest["rows"] < 0
                or not isinstance(digest["sha256"], str)
                or not SHA256.fullmatch(digest["sha256"])
            ):
                return False
    return True


def validate_record(value, *, expected_id=None):
    if (
        not isinstance(value, dict)
        or set(value) != RECORD_FIELDS
        or type(value["format"]) is not int
        or value["format"] != 1
        or not isinstance(value["id"], str)
        or not RESTORE_ID.fullmatch(value["id"])
        or (expected_id is not None and value["id"] != expected_id)
        or not isinstance(value["backup_id"], str)
        or not RESTORE_ID.fullmatch(value["backup_id"])
        or not isinstance(value["status"], str)
        or value["status"] not in {"preparing", "verified", "activating", "activated"}
        or not isinstance(value["source_commit"], str)
        or not COMMIT.fullmatch(value["source_commit"])
        or not isinstance(value["api_image"], str)
        or not re.fullmatch(r"chatbi-local-api:[A-Za-z0-9_.-]+", value["api_image"])
        or not isinstance(value["database_image"], str)
        or not re.fullmatch(r"chatbi-local-postgres:[A-Za-z0-9_.-]+", value["database_image"])
        or not isinstance(value["api_image_id"], str)
        or not IMAGE_ID.fullmatch(value["api_image_id"])
        or not isinstance(value["database_image_id"], str)
        or not IMAGE_ID.fullmatch(value["database_image_id"])
        or not isinstance(value["compatibility_sha256"], str)
        or not SHA256.fullmatch(value["compatibility_sha256"])
        or not _timestamp(value["created_at"])
        or not _fingerprints(value["fingerprints"])
        or not isinstance(value["normalization"], dict)
        or set(value["normalization"]) != {"restored_epoch", "active_epoch"}
        or any(
            epoch is not None
            and (not isinstance(epoch, str) or not _is_uuid(epoch))
            for epoch in value["normalization"].values()
        )
        or not isinstance(value["verification"], dict)
        or set(value["verification"])
        != {"readiness", "login", "history", "index_ready", "duration_seconds"}
        or any(
            type(value["verification"][key]) is not bool
            for key in ("readiness", "login", "history", "index_ready")
        )
        or type(value["verification"]["duration_seconds"]) is not int
        or not 0 <= value["verification"]["duration_seconds"] <= 1800
    ):
        raise RestoreStateInvalid("RESTORE_STATE_INVALID")
    if value["status"] in {"verified", "activating", "activated"}:
        checks = value["verification"]
        if not all(checks[key] for key in ("readiness", "login", "history", "index_ready")):
            raise RestoreStateInvalid("RESTORE_STATE_INVALID")
        if not _timestamp(value["verified_at"]):
            raise RestoreStateInvalid("RESTORE_STATE_INVALID")
        if not all(value["normalization"].values()) or (
            value["normalization"]["restored_epoch"]
            == value["normalization"]["active_epoch"]
        ):
            raise RestoreStateInvalid("RESTORE_STATE_INVALID")
    elif value["verified_at"] is not None:
        raise RestoreStateInvalid("RESTORE_STATE_INVALID")
    from scripts.local_runtime_binding import restore_binding

    if value["binding"] != restore_binding(
        value["id"],
        database_image=value["database_image"],
        database_image_id=value["database_image_id"],
    ):
        raise RestoreStateInvalid("RESTORE_STATE_INVALID")
    return dict(value)


def _is_uuid(value):
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def validate_journal(value):
    if (
        not isinstance(value, dict)
        or set(value) != JOURNAL_FIELDS
        or type(value["format"]) is not int
        or value["format"] != 1
        or not isinstance(value["id"], str)
        or not RESTORE_ID.fullmatch(value["id"])
        or not isinstance(value["state"], str)
        or value["state"] not in {"activating", "interrupted", "complete", "recovering"}
        or not isinstance(value["phase"], str)
        or value["phase"] not in JOURNAL_PHASES
        or value["choice"] not in (None, "previous", "candidate")
        or not isinstance(value["previous"], dict)
        or not isinstance(value["candidate"], dict)
        or not _timestamp(value["updated_at"])
    ):
        raise RestoreStateInvalid("RESTORE_JOURNAL_INVALID")
    if value["phase"] == "complete" and value["state"] != "complete":
        raise RestoreStateInvalid("RESTORE_JOURNAL_INVALID")
    if value["state"] == "recovering" and value["choice"] is None:
        raise RestoreStateInvalid("RESTORE_JOURNAL_INVALID")
    return dict(value)


def _state_root(root, *, create):
    root = Path(root)
    if create and not root.exists():
        root.mkdir(mode=0o700, parents=True)
    return secure_directory(root, create=False)


def _restore_dir(root, restore_id, *, create):
    if not isinstance(restore_id, str) or not RESTORE_ID.fullmatch(restore_id):
        raise RestoreStateInvalid("RESTORE_STATE_INVALID")
    base = _state_root(Path(root) / "restores", create=create)
    path = base / restore_id
    if create and not path.exists():
        path.mkdir(mode=0o700)
    return secure_directory(path, create=False)


def load_record(root, restore_id):
    path = _restore_dir(root, restore_id, create=False) / "record.json"
    try:
        value = json.loads(secure_file(path))
    except (OSError, ValueError, TypeError, BackupFailed):
        raise RestoreStateInvalid("RESTORE_STATE_INVALID") from None
    return validate_record(value, expected_id=restore_id)


def write_record(root, value):
    value = validate_record(value)
    directory = _restore_dir(root, value["id"], create=True)
    atomic_json(directory / "record.json", value)
    return value


def load_registry_record(root, restore_id):
    """供资源绑定解析调用；不允许缺损状态降级为 legacy。"""
    value = load_record(root, restore_id)
    if value["status"] not in {"verified", "activated"}:
        raise RestoreStateInvalid("RESTORE_STATE_INVALID")
    return value


def _journal_path(root):
    root = Path(root)
    operations = secure_directory(root / "operations", create=False)
    return operations / "restore-journal.json"


def _state_root_path(root):
    root = Path(root)
    return secure_directory(root, create=False)


def load_journal(root):
    path = _journal_path(root)
    try:
        value = json.loads(secure_file(path))
    except (OSError, ValueError, TypeError, BackupFailed):
        raise RestoreStateInvalid("RESTORE_JOURNAL_INVALID") from None
    return validate_journal(value)


def write_journal(root, value):
    value = validate_journal(value)
    atomic_json(_journal_path(root), value)
    return value


def update_journal(root, *, phase, state, choice=None, now):
    previous = load_journal(root)
    current = dict(
        previous,
        phase=phase,
        state=state,
        choice=choice,
        updated_at=now,
    )
    return write_journal(root, current)


def load_active_binding(state_root):
    from scripts.local_runtime_binding import load_binding

    state_root = _state_root_path(state_root)
    return load_binding(
        state_root / "runtime-binding.json",
        registry_root=state_root / "operations" / "restores",
    )


def write_active_binding(state_root, binding):
    from scripts.local_runtime_binding import validate_binding

    state_root = _state_root_path(state_root)
    operations = secure_directory(state_root / "operations", create=False)
    registry = {}
    environment = binding.get("environment_id") if isinstance(binding, dict) else None
    if isinstance(environment, str) and RESTORE_ID.fullmatch(environment):
        registry[environment] = load_registry_record(operations, environment)
    value = validate_binding(binding, registry=registry)
    target = state_root / "runtime-binding.json"
    if target.exists() or target.is_symlink():
        try:
            secure_file(target, read=False)
        except (OSError, BackupFailed):
            raise RestoreStateInvalid("BINDING_STORAGE_UNSAFE") from None
    atomic_json(target, value)
    return value


def begin_journal(
    state_root,
    restore_id,
    *,
    now,
    previous_release_file=None,
    previous_database_image=None,
    previous_database_image_id=None,
):
    state_root = _state_root_path(state_root)
    operations = secure_directory(state_root / "operations", create=False)
    record = load_registry_record(operations, restore_id)
    if record["status"] != "verified":
        raise RestoreStateInvalid("RESTORE_NOT_VERIFIED")
    path = _journal_path(state_root)
    if path.exists() or path.is_symlink():
        journal = load_journal(state_root)
        if journal["state"] != "complete":
            raise RestoreStateInvalid("RESTORE_JOURNAL_INCOMPLETE")
        history_dir = operations / "restore-journals"
        if not history_dir.exists():
            history_dir.mkdir(mode=0o700)
        history_dir = secure_directory(history_dir, create=False)
        archived = history_dir / (journal["id"] + ".json")
        if archived.exists() or archived.is_symlink():
            raise RestoreStateInvalid("RESTORE_JOURNAL_INVALID")
        atomic_json(archived, journal)
    previous = load_active_binding(state_root)
    if previous["environment_id"] == "legacy":
        if previous_release_file is not None:
            previous["release_file"] = previous_release_file
        if previous_database_image is not None or previous_database_image_id is not None:
            previous["database_image"] = previous_database_image
            previous["database_image_id"] = previous_database_image_id
        from scripts.local_runtime_binding import validate_binding

        previous = validate_binding(previous)
    if previous["environment_id"] == restore_id:
        raise RestoreStateInvalid("RESTORE_ALREADY_ACTIVE")
    return write_journal(
        state_root,
        {
            "format": 1,
            "id": restore_id,
            "state": "activating",
            "phase": "candidate-stopping",
            "choice": None,
            "previous": previous,
            "candidate": record["binding"],
            "updated_at": now,
        },
    )


def begin_recovery(state_root, restore_id, *, choice, now):
    if choice not in {"previous", "candidate"}:
        raise RestoreStateInvalid("RESTORE_RECOVERY_CHOICE_REQUIRED")
    journal = load_journal(state_root)
    if journal["id"] != restore_id or journal["state"] not in {"activating", "interrupted", "recovering"}:
        raise RestoreStateInvalid("RESTORE_JOURNAL_INVALID")
    return update_journal(
        state_root,
        phase="recover-stopping",
        state="recovering",
        choice=choice,
        now=now,
    )


def select_recovery_binding(state_root, *, choice, now):
    journal = load_journal(state_root)
    if journal["state"] != "recovering" or journal["choice"] != choice:
        raise RestoreStateInvalid("RESTORE_JOURNAL_INVALID")
    binding = journal["previous"] if choice == "previous" else journal["candidate"]
    write_active_binding(state_root, binding)
    return update_journal(
        state_root,
        phase="recover-binding-switched",
        state="recovering",
        choice=choice,
        now=now,
    )


def activate_candidate_binding(state_root, *, now):
    journal = load_journal(state_root)
    if journal["state"] != "activating" or journal["phase"] != "previous-stopped":
        raise RestoreStateInvalid("RESTORE_JOURNAL_INVALID")
    write_active_binding(state_root, journal["candidate"])
    return update_journal(
        state_root,
        phase="binding-switched",
        state="activating",
        choice=None,
        now=now,
    )


def complete_journal(state_root, *, now):
    journal = load_journal(state_root)
    return update_journal(
        state_root,
        phase="complete",
        state="complete",
        choice=journal["choice"],
        now=now,
    )


def activate_record(state_root, restore_id):
    operations = secure_directory(Path(state_root) / "operations", create=False)
    record = load_record(operations, restore_id)
    if record["status"] == "activated":
        return record
    if record["status"] not in {"verified", "activating"}:
        raise RestoreStateInvalid("RESTORE_STATE_INVALID")
    record["status"] = "activated"
    return write_record(operations, record)


def cli(argv=None):
    import argparse
    from datetime import UTC, datetime

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=("journal-begin", "journal-phase", "recover-begin", "recover-select", "activate-select", "journal-complete", "record-activated", "journal-show", "list-records"),
    )
    parser.add_argument("--root", default="/workspace/.local")
    parser.add_argument("--restore-id")
    parser.add_argument("--phase")
    parser.add_argument("--state")
    parser.add_argument("--choice", choices=("previous", "candidate"))
    parser.add_argument("--previous-release-file")
    parser.add_argument("--previous-database-image")
    parser.add_argument("--previous-database-image-id")
    try:
        args = parser.parse_args(argv)
        now = datetime.now(UTC).isoformat()
        if args.action == "journal-begin":
            if not args.restore_id:
                raise RestoreStateInvalid("RESTORE_STATE_INVALID")
            result = begin_journal(
                args.root,
                args.restore_id,
                now=now,
                previous_release_file=args.previous_release_file,
                previous_database_image=args.previous_database_image,
                previous_database_image_id=args.previous_database_image_id,
            )
        elif args.action == "journal-phase":
            if args.phase not in JOURNAL_PHASES or args.state not in {"activating", "interrupted", "recovering", "complete"}:
                raise RestoreStateInvalid("RESTORE_JOURNAL_INVALID")
            result = update_journal(
                args.root, phase=args.phase, state=args.state, choice=args.choice, now=now
            )
        elif args.action == "recover-begin":
            if not args.restore_id:
                raise RestoreStateInvalid("RESTORE_STATE_INVALID")
            result = begin_recovery(
                args.root, args.restore_id, choice=args.choice, now=now
            )
        elif args.action == "recover-select":
            if args.choice not in {"previous", "candidate"}:
                raise RestoreStateInvalid("RESTORE_RECOVERY_CHOICE_REQUIRED")
            result = select_recovery_binding(
                args.root, choice=args.choice, now=now
            )
        elif args.action == "activate-select":
            result = activate_candidate_binding(args.root, now=now)
        elif args.action == "journal-complete":
            result = complete_journal(args.root, now=now)
        elif args.action == "record-activated":
            if not args.restore_id:
                raise RestoreStateInvalid("RESTORE_STATE_INVALID")
            result = activate_record(args.root, args.restore_id)
        elif args.action == "journal-show":
            try:
                journal = load_journal(args.root)
                result = {key: journal[key] for key in ("id", "state", "phase", "choice")}
            except RestoreStateInvalid:
                result = None
        else:
            state_root = _state_root_path(args.root)
            restores = state_root / "operations" / "restores"
            items = []
            if restores.exists():
                for child in sorted(restores.iterdir()):
                    if child.name == "staging" or not RESTORE_ID.fullmatch(child.name):
                        continue
                    try:
                        record = load_record(state_root / "operations", child.name)
                    except RestoreStateInvalid:
                        items.append({"id": child.name, "status": "unverified"})
                    else:
                        items.append({"id": record["id"], "status": record["status"]})
            result = items
        print(json.dumps({"status": "success", "result": result}, sort_keys=True))
        return 0
    except (RestoreStateInvalid, BackupFailed, OSError, ValueError, TypeError) as exc:
        print(
            json.dumps(
                {
                    "status": "failure",
                    "failure_code": str(exc)
                    if isinstance(exc, RestoreStateInvalid)
                    else "RESTORE_STATE_FAILED",
                },
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())


def digest_compatibility(raw):
    return hashlib.sha256(raw).hexdigest()
