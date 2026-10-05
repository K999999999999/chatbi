"""单API进程的持久执行归属；断连不能提前释放仍执行的请求。"""

from contextlib import contextmanager
from threading import Condition, Lock
from uuid import uuid4

import psycopg
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .history_contracts import busy, storage_unavailable

HISTORY_ADVISORY_KEY = 731247919801


class HistoryRuntime:
    def __init__(self, engine, connect_kwargs):
        self.engine = engine
        self.epoch = str(uuid4())
        self._condition = Condition()
        self._guard_lock = Lock()
        self._running = set()
        self._valid = False
        self._accepting = True
        self._guard = psycopg.connect(**connect_kwargs, autocommit=True)
        try:
            if not self._guard.execute(
                "SELECT pg_try_advisory_lock(%s)", (HISTORY_ADVISORY_KEY,)
            ).fetchone()[0]:
                raise RuntimeError("历史服务只支持单API进程；已有运行进程")
            with engine.begin() as connection:
                connection.execute(
                    text("""INSERT INTO history_runtime(singleton,runtime_epoch)
                    VALUES (TRUE,:epoch) ON CONFLICT (singleton) DO UPDATE SET runtime_epoch=:epoch"""),
                    {"epoch": self.epoch},
                )
                connection.execute(
                    text("""UPDATE history_turns SET status='unconfirmed',
                    completed_at=CURRENT_TIMESTAMP WHERE status='accepted'""")
                )
                connection.execute(
                    text("""UPDATE history_executions SET status='unconfirmed',
                    finished_at=CURRENT_TIMESTAMP
                    WHERE status IN ('accepted','running','stopping')""")
                )
                connection.execute(
                    text("""UPDATE history_records SET active_turn_id=NULL,
                    execution_generation=execution_generation+1,record_revision=record_revision+1,
                    updated_at=CURRENT_TIMESTAMP WHERE active_turn_id IS NOT NULL""")
                )
            self._valid = True
        except Exception:
            self._guard.close()
            raise

    def check(self):
        with self._guard_lock:
            if not self._valid:
                raise storage_unavailable()
            try:
                self._guard.execute("SELECT 1").fetchone()
            except psycopg.Error:
                self._valid = False
                raise storage_unavailable() from None

    @contextmanager
    def executing(self, history_id):
        lease = self.reserve(history_id)
        try:
            yield
        finally:
            lease.release()

    def reserve(self, history_id):
        """把 history 的运行占用从 HTTP 受理交接给后台 worker。"""

        self.check()
        with self._condition:
            if not self._valid or not self._accepting:
                raise storage_unavailable()
            if history_id in self._running:
                raise busy()
            self._running.add(history_id)
        return _HistoryLease(self, history_id)

    def _release(self, history_id):
        with self._condition:
            if history_id not in self._running:
                return
            self._running.remove(history_id)
            self._condition.notify_all()

    def reconcile(self, history_id):
        try:
            self._reconcile(history_id)
        except SQLAlchemyError as exc:
            if getattr(getattr(exc, "orig", None), "sqlstate", None) == "55P03":
                raise busy() from None
            raise storage_unavailable() from None

    def _reconcile(self, history_id):
        """仅无本进程执行者时回收本epoch未确认记录，绝不按超时推定停止。"""
        self.check()
        with self._condition:
            if history_id in self._running:
                return
            with self.engine.begin() as connection:
                row = connection.execute(
                    text(
                        "SELECT active_turn_id FROM history_records WHERE id=:id FOR UPDATE NOWAIT"
                    ),
                    {"id": history_id},
                ).first()
                if row is None or row[0] is None:
                    return
                changed = connection.execute(
                    text("""UPDATE history_turns SET status='unconfirmed',completed_at=CURRENT_TIMESTAMP
                    WHERE id=:turn AND status='accepted' AND runtime_epoch=:epoch"""),
                    {"turn": row[0], "epoch": self.epoch},
                )
                if changed.rowcount != 1:
                    raise storage_unavailable()
                connection.execute(
                    text("""UPDATE history_executions SET status='unconfirmed',
                    finished_at=CURRENT_TIMESTAMP
                    WHERE history_id=:id AND turn_id=:turn AND runtime_epoch=:epoch
                      AND status IN ('accepted','running','stopping')"""),
                    {"id": history_id, "turn": row[0], "epoch": self.epoch},
                )
                connection.execute(
                    text("""UPDATE history_records SET active_turn_id=NULL,
                    execution_generation=execution_generation+1,record_revision=record_revision+1,
                    updated_at=CURRENT_TIMESTAMP WHERE id=:id"""),
                    {"id": history_id},
                )

    def drain(self):
        with self._condition:
            self._accepting = False
            while self._running:
                self._condition.wait()

    def close(self):
        self.drain()
        self._valid = False
        with self._guard_lock:
            try:
                if not self._guard.closed:
                    self._guard.execute(
                        "SELECT pg_advisory_unlock(%s)", (HISTORY_ADVISORY_KEY,)
                    )
            finally:
                self._guard.close()


class _HistoryLease:
    def __init__(self, runtime, history_id):
        self._runtime = runtime
        self._history_id = history_id
        self._lock = Lock()
        self._released = False

    def release(self):
        with self._lock:
            if self._released:
                return
            self._released = True
        self._runtime._release(self._history_id)
