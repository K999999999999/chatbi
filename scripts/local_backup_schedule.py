"""备份调度政策与受限工具循环；不负责启动或重启 API。"""

import json
import signal
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

from scripts.local_backup import (
    BackupFailed,
    BackupStore,
    atomic_json,
    operation_lock,
    public_failure,
    secure_file,
)
from scripts.local_backup_archive import BackupInvalid
from scripts.local_backup_postgres import DatabaseBackupFailed

from scripts.local_backup_policy import should_attempt


class BackupScheduler:
    def __init__(self, store, *, clock=lambda: datetime.now(UTC)):
        self.store = store
        self.clock = clock
        self.path = store.operations / "schedule.json"
        self.starting = True

    def _last_attempt(self):
        if not self.path.exists():
            return None
        value = json.loads(secure_file(self.path))
        if (
            not isinstance(value, dict)
            or set(value) != {"format", "last_attempt"}
            or value["format"] != 1
        ):
            raise BackupFailed("BACKUP_STORAGE_UNSAFE")
        timestamp = datetime.fromisoformat(value["last_attempt"])
        if timestamp.tzinfo is None:
            raise BackupFailed("BACKUP_STORAGE_UNSAFE")
        return timestamp

    def tick(self, source):
        now = self.clock()
        entries = self.store.catalog()["backups"]
        last_success = max(
            (datetime.fromisoformat(e["created_at"]) for e in entries), default=None
        )
        should = should_attempt(
            now,
            last_success=last_success,
            last_attempt=self._last_attempt(),
            starting=self.starting,
        )
        self.starting = False
        if not should:
            return False
        # Attempt is durable before taking the lock: failures and contention do not hot loop.
        atomic_json(self.path, {"format": 1, "last_attempt": now.isoformat()})
        try:
            with operation_lock(self.store.root / "operation.lock"):
                self.store.backup(source, require_live=True)

        except Exception as exc:
            code = (
                str(exc)
                if isinstance(exc, (BackupFailed, BackupInvalid, DatabaseBackupFailed))
                else "BACKUP_FAILED"
            )
            self.store.projection(failure_code=public_failure(code))
            print(
                json.dumps({"status": "failure", "failure_code": public_failure(code)}),
                flush=True,
            )
        else:
            print(json.dumps({"status": "success", "backup": "registered"}), flush=True)
        return True


def run_schedule(root=Path("/state"), source=Path("/state/operations/source")):
    import os

    os.umask(0o077)
    stop = Event()
    running = False

    def terminate(*_):
        stop.set()
        if running:
            raise BackupFailed("BACKUP_INTERRUPTED")

    def timeout(*_):
        raise BackupFailed("BACKUP_TIMEOUT")

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    signal.signal(signal.SIGALRM, timeout)
    store = BackupStore(root)
    scheduler = BackupScheduler(store)
    while not stop.is_set():
        running = True
        signal.alarm(1200)
        try:
            scheduler.tick(source)
        except Exception:
            store.projection(failure_code="BACKUP_FAILED")
            print('{"status":"failure","failure_code":"BACKUP_FAILED"}', flush=True)
            return
        finally:
            signal.alarm(0)
            running = False
        stop.wait(30)


if __name__ == "__main__":
    try:
        run_schedule()
    except Exception:
        print('{"status":"failure","failure_code":"BACKUP_FAILED"}')
        raise SystemExit(1) from None
