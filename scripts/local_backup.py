"""受限工具容器中的备份入口；不持 Docker socket，不输出敏感异常。"""

import argparse
import fcntl
import json
import os
import re
import signal
import socket
import stat
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from scripts.local_backup_archive import (
    BackupInvalid,
    ID_PATTERN,
    SHA_PATTERN,
    digest_file,
    extract_bundle,
    validate_bundle,
    write_bundle,
)
from scripts.local_backup_postgres import DatabaseBackupFailed, Snapshot, verify_dump


class BackupFailed(RuntimeError):
    pass


def secure_directory(path, *, public=False, create=True):
    path = Path(path)
    if create and not path.exists():
        path.mkdir(mode=0o700)
        if public:
            descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fchmod(descriptor, 0o755)
            finally:
                os.close(descriptor)
    info = path.lstat()
    mode = 0o755 if public else 0o700
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != mode
    ):
        raise BackupFailed("BACKUP_STORAGE_UNSAFE")
    return path


def secure_file(path, *, maximum=1024**2, read=True):
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > maximum
        ):
            raise BackupFailed("BACKUP_STORAGE_UNSAFE")
        return stream.read(maximum + 1) if read else None


def atomic_json(path, value, *, public=False):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            os.fchmod(stream.fileno(), 0o644 if public else 0o600)
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def command(args, *, timeout=120):
    try:
        return subprocess.run(
            args, check=True, capture_output=True, timeout=timeout
        ).stdout
    except subprocess.TimeoutExpired:
        raise BackupFailed("BACKUP_TIMEOUT") from None
    except (OSError, subprocess.CalledProcessError):
        raise BackupFailed("BACKUP_TOOL_FAILED") from None


@contextmanager
def operation_lock(path, *, host_locked=False):
    # host-locked is used only by the privileged local wrapper while its flock lives.
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise BackupFailed("BACKUP_STORAGE_UNSAFE")
        if not host_locked:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise BackupFailed("BACKUP_LOCKED") from None
        yield
    finally:
        os.close(fd)


class BackupStore:
    def __init__(self, root, *, clock=lambda: datetime.now(UTC), create=True):
        self.root = Path(root)
        self.clock = clock
        self.operations = secure_directory(self.root / "operations", create=create)
        self.public = secure_directory(
            self.operations / "public", public=True, create=create
        )
        self.keys = secure_directory(self.root / "backup-keys", create=create)
        self.backups = secure_directory(self.root / "backups", create=create)
        self.staging = self.operations / "staging"
        if create:
            secure_directory(self.staging)
        self.catalog_path = self.operations / "catalog.json"

    def catalog(self):
        if not self.catalog_path.exists():
            return {"format": 1, "backups": []}
        value = json.loads(secure_file(self.catalog_path))
        if (
            not isinstance(value, dict)
            or set(value) != {"format", "backups"}
            or value["format"] != 1
            or not isinstance(value["backups"], list)
        ):
            raise BackupFailed("BACKUP_STORAGE_UNSAFE")
        seen = set()
        for entry in value["backups"]:
            if (
                not isinstance(entry, dict)
                or set(entry) != {"id", "created_at", "size", "sha256", "source_commit"}
                or not isinstance(entry["id"], str)
                or not ID_PATTERN.fullmatch(entry["id"])
                or entry["id"] in seen
                or type(entry["size"]) is not int
                or entry["size"] <= 0
                or not isinstance(entry.get("sha256"), str)
                or not SHA_PATTERN.fullmatch(entry["sha256"])
                or not isinstance(entry.get("source_commit"), str)
                or not re.fullmatch("[0-9a-f]{40}", entry["source_commit"])
            ):
                raise BackupFailed("BACKUP_STORAGE_UNSAFE")
            try:
                timestamp = datetime.fromisoformat(entry["created_at"])
                if timestamp.tzinfo is None:
                    raise ValueError()
            except (TypeError, ValueError):
                raise BackupFailed("BACKUP_STORAGE_UNSAFE") from None
            seen.add(entry["id"])
        return value

    def projection(self, *, failure_code=None, success=None):
        path = self.public / "backup.json"
        previous = None
        try:
            previous = json.loads(path.read_bytes()).get("last_success")
        except (OSError, ValueError, AttributeError):
            pass
        atomic_json(
            path,
            {
                "version": 1,
                "last_success": success or previous,
                "failure_code": failure_code,
            },
            public=True,
        )

    def initialize_key(self):
        private, public = self.keys / "identity.txt", self.keys / "recipient.txt"
        if private.exists():
            secure_file(private)
        else:
            # age-keygen refuses an existing destination; never truncate an identity.
            temporary = self.keys / (".identity-" + uuid.uuid4().hex)
            try:
                command(["age-keygen", "-o", str(temporary)])
                os.chmod(temporary, 0o600)
                os.link(temporary, private)
            finally:
                temporary.unlink(missing_ok=True)
        recipient = command(["age-keygen", "-y", str(private)]).strip()
        if not recipient.startswith(b"age1") or b"\n" in recipient:
            raise BackupFailed("BACKUP_KEY_INVALID")
        if public.exists():
            if secure_file(public).strip() != recipient:
                raise BackupFailed("BACKUP_KEY_INVALID")
        else:
            fd = os.open(
                public, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            with os.fdopen(fd, "wb") as stream:
                stream.write(recipient + b"\n")
        return "initialized"

    def require_key(self):
        try:
            private = self.keys / "identity.txt"
            secure_file(private)
            recipient = secure_file(self.keys / "recipient.txt").strip()
            if command(["age-keygen", "-y", str(private)]).strip() != recipient:
                raise BackupFailed("BACKUP_KEY_INVALID")
        except FileNotFoundError:
            raise BackupFailed("BACKUP_NOT_INITIALIZED") from None
        return private, self.keys / "recipient.txt"

    def known_artifact(self, backup_id):
        if not isinstance(backup_id, str) or not ID_PATTERN.fullmatch(backup_id):
            raise BackupFailed("BACKUP_INVALID")
        entries = [e for e in self.catalog()["backups"] if e["id"] == backup_id]
        if len(entries) != 1:
            raise BackupFailed("BACKUP_INVALID")
        entry = entries[0]
        path = self.backups / (backup_id + ".age")
        secure_file(path, maximum=5 * 1024**3, read=False)
        if path.stat().st_size != entry["size"] or digest_file(path) != entry["sha256"]:
            raise BackupFailed("BACKUP_INVALID")
        return path, entry

    def decrypt(self, backup_id, destination):
        path, _ = self.known_artifact(backup_id)
        private, _ = self.require_key()
        with tempfile.TemporaryDirectory(
            dir=self.staging, prefix="verify-"
        ) as temporary:
            plain = Path(temporary) / "bundle.zip"
            command(["age", "-d", "-i", str(private), "-o", str(plain), str(path)])
            return extract_bundle(plain, destination, expected_id=backup_id)

    def backup(self, source, *, require_live=True):
        private, recipient = self.require_key()
        source = Path(source)
        identity = json.loads(secure_file(source / "identity.json"))
        require_live = require_live or identity.get("live_required", False)
        verify_source(identity, self.clock(), require_live=require_live)
        protected = [
            "config.env",
            "secrets.env",
            "release.env",
            "rag-current.json",
            "rag-manifest.json",
            "compatibility.json",
            "identity.json",
        ]
        before = {name: secure_file(source / name) for name in protected}
        backup_id = uuid.uuid4().hex
        pending = self.backups / (".pending-" + backup_id + ".age")
        final = self.backups / (backup_id + ".age")
        registered = False
        try:
            with tempfile.TemporaryDirectory(
                dir=self.staging, prefix="capture-"
            ) as temporary:
                directory = Path(temporary)
                for name in protected[:-1]:
                    (directory / name).write_bytes(before[name])
                business_db = os.environ.get("POSTGRES_DB", "chatbi_mvp")
                control_db = os.environ.get("POSTGRES_CONTROL_DB", "chatbi_control")
                with Snapshot(business_db) as business:
                    business_fingerprint = business.fingerprints()
                    roles = business.approved_roles()
                    business.dump(directory / "business.dump")
                with Snapshot(control_db) as control:
                    control_fingerprint = control.fingerprints()
                    control.dump(directory / "control.dump")
                with Snapshot(business_db) as business:
                    if business.fingerprints() != business_fingerprint:
                        raise BackupFailed("BACKUP_SOURCE_CHANGED")
                verify_source(identity, self.clock(), require_live=require_live)
                if any(
                    secure_file(source / name) != before[name] for name in protected
                ):
                    raise BackupFailed("BACKUP_SOURCE_CHANGED")
                metadata = {
                    "id": backup_id,
                    "created_at": self.clock().isoformat(),
                    "source": identity,
                    "roles": roles,
                    "databases": {
                        "business": {
                            "name": business_db,
                            "tables": business_fingerprint,
                        },
                        "control": {"name": control_db, "tables": control_fingerprint},
                    },
                }
                plain = directory / "bundle.zip"
                write_bundle(directory, plain, metadata)
                command(["age", "-R", str(recipient), "-o", str(pending), str(plain)])
                os.chmod(pending, 0o600)
                decrypted = directory / "verified.zip"
                command(
                    [
                        "age",
                        "-d",
                        "-i",
                        str(private),
                        "-o",
                        str(decrypted),
                        str(pending),
                    ]
                )
                validate_bundle(decrypted, expected_id=backup_id)
                verified = directory / "verified"
                verified.mkdir(mode=0o700)
                extract_bundle(decrypted, verified, expected_id=backup_id)
                verify_dump(verified / "control.dump")
                verify_dump(verified / "business.dump")
                entry = {
                    "id": backup_id,
                    "created_at": metadata["created_at"],
                    "size": pending.stat().st_size,
                    "sha256": digest_file(pending),
                    "source_commit": identity["source_commit"],
                }
                with pending.open("rb") as stream:
                    os.fsync(stream.fileno())
                # link is exclusive; unrelated artifacts are never replaced.
                os.link(pending, final)
                catalog = self.catalog()
                catalog["backups"].append(entry)
                atomic_json(self.catalog_path, catalog)
                registered = True
                self.projection(success=metadata["created_at"])
                return entry
        finally:
            pending.unlink(missing_ok=True)
            if not registered:
                final.unlink(missing_ok=True)


def verify_source(identity, now, *, require_live):
    if (
        not isinstance(identity, dict)
        or identity.get("format") != 1
        or not isinstance(identity.get("source_commit"), str)
        or not re.fullmatch("[0-9a-f]{40}", identity["source_commit"])
        or any(
            not isinstance(identity.get(key), str)
            or not re.fullmatch("sha256:[0-9a-f]{64}", identity[key])
            for key in ("api_image_id", "database_image_id")
        )
    ):
        raise BackupFailed("BACKUP_SOURCE_CHANGED")
    if require_live:
        path = os.environ.get("CHATBI_OPERATIONS_SOCKET_PATH", "/runtime/status.sock")
        try:
            with socket.socket(socket.AF_UNIX) as connection:
                connection.settimeout(3)
                connection.connect(path)
                with connection.makefile("rb") as stream:
                    data = stream.readline(16385)
                if len(data) > 16384:
                    raise ValueError()
                snapshot = json.loads(data)
            if (
                snapshot.get("source_commit") != identity["source_commit"]
                or not identity.get("asset_sha256")
                or snapshot.get("asset_sha256") != identity["asset_sha256"]
            ):
                raise ValueError()
            checked = datetime.fromisoformat(snapshot["checked_at"])
            if checked.tzinfo is None or not 0 <= (now - checked).total_seconds() < 30:
                raise ValueError()
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            raise BackupFailed("BACKUP_SOURCE_CHANGED") from None
    else:
        try:
            captured = datetime.fromisoformat(identity["captured_at"])
            if (
                captured.tzinfo is None
                or not 0 <= (now - captured).total_seconds() <= 1200
            ):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise BackupFailed("BACKUP_SOURCE_CHANGED") from None


def public_failure(code):
    if code in {"BACKUP_KEY_INVALID", "BACKUP_NOT_INITIALIZED"}:
        return "BACKUP_KEY_UNAVAILABLE"
    if code == "BACKUP_STORAGE_UNSAFE":
        return "BACKUP_STORAGE_UNAVAILABLE"
    if code in {"BACKUP_LOCKED", "BACKUP_TIMEOUT", "BACKUP_INVALID"}:
        return code
    return "BACKUP_FAILED"


def _interrupt(*_):
    raise BackupFailed("BACKUP_INTERRUPTED")


def _timeout(*_):
    raise BackupFailed("BACKUP_TIMEOUT")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["init", "backup", "list"])
    parser.add_argument("--root", default="/state")
    parser.add_argument("--source", default="/state/operations/source")
    parser.add_argument("--host-locked", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    store = None
    signal.signal(signal.SIGTERM, _interrupt)
    signal.signal(signal.SIGINT, _interrupt)
    signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(1200)
    try:
        store = BackupStore(args.root, create=args.action != "list")
        if args.action == "list":
            result = store.catalog()["backups"]
        else:
            with operation_lock(
                Path(args.root) / "operation.lock", host_locked=args.host_locked
            ):
                result = (
                    store.initialize_key()
                    if args.action == "init"
                    else store.backup(args.source, require_live=not args.host_locked)
                )
        print(json.dumps({"status": "success", "result": result}, sort_keys=True))
    except Exception as exc:
        code = (
            str(exc)
            if isinstance(exc, (BackupFailed, BackupInvalid, DatabaseBackupFailed))
            else "BACKUP_FAILED"
        )
        if store is not None and args.action != "list":
            try:
                store.projection(failure_code=public_failure(code))
            except (OSError, BackupFailed):
                pass
        print(json.dumps({"status": "failure", "failure_code": code}))
        raise SystemExit(1) from None
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    main()
