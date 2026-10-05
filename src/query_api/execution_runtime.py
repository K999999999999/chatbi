"""单 API 进程的后台执行额度和 worker 生命周期。"""

from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from threading import Condition, Lock
from typing import TypeVar

from .execution_events import (
    ExecutionEventChannel,
    ExecutionEventSubscription,
)

T = TypeVar("T")


class ExecutionCapacityExceeded(RuntimeError):
    """账号或 API 进程没有可用的执行额度。"""

    def __init__(self, scope: str) -> None:
        super().__init__(scope)
        self.scope = scope


class ExecutionRuntimeClosed(RuntimeError):
    """API 正在关闭，不能再受理执行。"""


class ExecutionLease:
    """持有一个已预留额度和下游互斥锁的可转交执行租约。"""

    def __init__(
        self,
        runtime: ExecutionRuntime,
        owner_id: int,
        history_lease: object,
        analysis_lease: object | None,
    ) -> None:
        self._runtime = runtime
        self._owner_id = owner_id
        self._history_lease = history_lease
        self._analysis_lease = analysis_lease
        self._lock = Lock()
        self._released = False
        self._submitted = False
        self._execution_id: str | None = None
        self._event_channel: ExecutionEventChannel | None = None

    @property
    def released(self) -> bool:
        with self._lock:
            return self._released

    def release(self) -> None:
        with self._lock:
            if self._released:
                return
            self._released = True
        try:
            if self._analysis_lease is not None:
                self._analysis_lease.release()
        finally:
            try:
                self._history_lease.release()
            finally:
                try:
                    self._runtime._release_owner(self._owner_id)
                finally:
                    if self._execution_id is not None:
                        self._runtime._release_event_channel(
                            self._execution_id, self._event_channel
                        )


class ExecutionRuntime:
    """在 worker 真正退出前保留账号、进程、history 和分析 run 的占用。"""

    def __init__(
        self,
        history_runtime,
        analysis_guard,
        *,
        max_per_user: int = 1,
        max_total: int = 4,
    ) -> None:
        if (
            isinstance(max_per_user, bool)
            or isinstance(max_total, bool)
            or not isinstance(max_per_user, int)
            or not isinstance(max_total, int)
            or max_per_user < 1
            or max_total < 1
            or max_per_user > max_total
        ):
            raise ValueError("执行额度必须为正整数，且账号额度不能大于进程额度")
        self._history_runtime = history_runtime
        self._analysis_guard = analysis_guard
        self._max_per_user = max_per_user
        self._max_total = max_total
        self._condition = Condition()
        self._active_by_user: dict[int, int] = {}
        self._active_total = 0
        self._operation_locks: dict[tuple[int, str], tuple[Lock, int]] = {}
        self._event_channels: dict[str, ExecutionEventChannel] = {}
        self._accepting = True
        self._closed = False
        self._executor = ThreadPoolExecutor(
            max_workers=max_total, thread_name_prefix="chatbi-execution"
        )

    @classmethod
    def from_environment(cls, history_runtime, analysis_guard, environ=None):
        values = os.environ if environ is None else environ
        per_user = _positive_limit(values.get("CHATBI_EXECUTION_MAX_PER_USER", "1"))
        total = _positive_limit(values.get("CHATBI_EXECUTION_MAX_TOTAL", "4"))
        return cls(
            history_runtime,
            analysis_guard,
            max_per_user=per_user,
            max_total=total,
        )

    @property
    def accepting(self) -> bool:
        with self._condition:
            return self._accepting

    @property
    def active_total(self) -> int:
        with self._condition:
            return self._active_total

    def reserve(
        self,
        owner_id: int,
        history_id: str,
        *,
        auth=None,
        analysis_run_id: str | None = None,
    ) -> ExecutionLease:
        """先同步预留额度，再取得 history / analysis 的互斥租约。"""

        if isinstance(owner_id, bool) or not isinstance(owner_id, int) or owner_id < 1:
            raise ValueError("owner_id 必须为正整数")
        with self._condition:
            if not self._accepting:
                raise ExecutionRuntimeClosed()
            if self._active_by_user.get(owner_id, 0) >= self._max_per_user:
                raise ExecutionCapacityExceeded("user")
            if self._active_total >= self._max_total:
                raise ExecutionCapacityExceeded("process")
            self._active_by_user[owner_id] = self._active_by_user.get(owner_id, 0) + 1
            self._active_total += 1

        history_lease = None
        analysis_lease = None
        try:
            history_lease = self._history_runtime.reserve(history_id)
            if analysis_run_id is not None:
                if self._analysis_guard is None or auth is None:
                    raise ExecutionRuntimeClosed()
                analysis_lease = self._analysis_guard.reserve(auth, analysis_run_id)
            with self._condition:
                if not self._accepting:
                    raise ExecutionRuntimeClosed()
            return ExecutionLease(self, owner_id, history_lease, analysis_lease)
        except BaseException:
            if analysis_lease is not None:
                analysis_lease.release()
            if history_lease is not None:
                history_lease.release()
            self._release_owner(owner_id)
            raise

    def attach_progress(self, lease: ExecutionLease, execution):
        """为已持久受理的 execution 安装仅存活于当前 worker 的进度通道。"""

        if lease._runtime is not self:
            raise ValueError("执行租约不属于当前 Runtime")
        with lease._lock:
            if lease._released or lease._submitted:
                raise ExecutionRuntimeClosed()
            if lease._execution_id is not None:
                raise ValueError("执行租约已绑定进度通道")
            channel = ExecutionEventChannel(execution)
            with self._condition:
                if execution.id in self._event_channels:
                    raise ValueError("执行进度通道已存在")
                self._event_channels[execution.id] = channel
                lease._execution_id = execution.id
                lease._event_channel = channel
            return channel

    def subscribe(self, execution_id: str) -> ExecutionEventSubscription | None:
        with self._condition:
            channel = self._event_channels.get(execution_id)
        return None if channel is None else channel.subscribe()

    @contextmanager
    def serialize_operation(self, owner_id: int, operation_id: str):
        """让同一账号的并发重放先看到第一次持久受理结果。"""

        key = (owner_id, str(operation_id))
        with self._condition:
            lock, references = self._operation_locks.get(key, (Lock(), 0))
            self._operation_locks[key] = (lock, references + 1)
        acquired = False
        try:
            lock.acquire()
            acquired = True
            yield
        finally:
            if acquired:
                lock.release()
            with self._condition:
                current_lock, references = self._operation_locks[key]
                if references == 1:
                    del self._operation_locks[key]
                else:
                    self._operation_locks[key] = (current_lock, references - 1)

    def submit(self, lease: ExecutionLease, work: Callable[[], T]) -> Future[T]:
        """把工作交给固定线程池；future 完成后才释放租约和执行额度。"""

        with lease._lock:
            if lease._released:
                raise ExecutionRuntimeClosed()
            if lease._submitted:
                raise ValueError("执行租约已提交")
            lease._submitted = True

        def run() -> T:
            try:
                return work()
            finally:
                lease.release()

        try:
            return self._executor.submit(run)
        except BaseException:
            with lease._lock:
                lease._submitted = False
            raise

    def close_admission(self) -> None:
        with self._condition:
            self._accepting = False
            self._condition.notify_all()

    def drain(self) -> None:
        self.close_admission()
        with self._condition:
            while self._active_total:
                self._condition.wait()

    def close(self) -> None:
        self.close_admission()
        with self._condition:
            if self._closed:
                return
        self.drain()
        self._executor.shutdown(wait=True, cancel_futures=False)
        with self._condition:
            self._closed = True

    def _release_owner(self, owner_id: int) -> None:
        with self._condition:
            active = self._active_by_user.get(owner_id, 0)
            if active <= 0 or self._active_total <= 0:
                raise RuntimeError("执行额度租约重复释放")
            if active == 1:
                del self._active_by_user[owner_id]
            else:
                self._active_by_user[owner_id] = active - 1
            self._active_total -= 1
            self._condition.notify_all()

    def _release_event_channel(self, execution_id, channel) -> None:
        if channel is not None and not channel.terminal:
            channel.finish("unconfirmed")
        with self._condition:
            if self._event_channels.get(execution_id) is channel:
                del self._event_channels[execution_id]


def _positive_limit(value):
    if not isinstance(value, str) or not value.strip().isdigit():
        raise ValueError("执行额度配置必须为正整数")
    result = int(value.strip())
    if result < 1:
        raise ValueError("执行额度配置必须为正整数")
    return result
