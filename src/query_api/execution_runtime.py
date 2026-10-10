"""单 API 进程的后台执行额度和 worker 生命周期。"""

from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from threading import Condition, Event, Lock, Thread
from time import monotonic
from typing import TypeVar

from src.online_query.contracts import ExecutionStopped, ExecutionStopReason

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


class OwnerCapacityLease:
    """只持有共享容量，不创建history/analysis持久状态。"""

    def __init__(self, runtime, owner):
        self._runtime = runtime
        self._owner = owner
        self._lock = Lock()
        self._released = False

    def release(self):
        with self._lock:
            if self._released:
                return
            self._released = True
        self._runtime._release_owner(self._owner)


class ExecutionLease:
    """持有一个已预留额度和下游互斥锁的可转交执行租约。"""

    def __init__(
        self,
        runtime: ExecutionRuntime,
        history_lease: object,
        analysis_lease: object | None,
        capacity_lease: OwnerCapacityLease,
    ) -> None:
        self._runtime = runtime
        self._capacity_lease = capacity_lease
        self._history_lease = history_lease
        self._analysis_lease = analysis_lease
        self._lock = Lock()
        self._released = False
        self._submitted = False
        self._execution_id: str | None = None
        self._event_channel: ExecutionEventChannel | None = None
        self._stop_control: _ExecutionStopControl | None = None

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
            if self._execution_id is not None:
                try:
                    self._runtime._release_event_channel(
                        self._execution_id, self._event_channel
                    )
                finally:
                    self._runtime._release_stop_control(
                        self._execution_id, self._stop_control
                    )
        finally:
            try:
                if self._analysis_lease is not None:
                    self._analysis_lease.release()
            finally:
                try:
                    self._history_lease.release()
                finally:
                    self._capacity_lease.release()


class ExecutionRuntime:
    """在 worker 真正退出前保留账号、进程、history 和分析 run 的占用。"""

    def __init__(
        self,
        history_runtime,
        analysis_guard,
        *,
        max_per_user: int = 1,
        max_total: int = 4,
        wall_clock: Callable[[], datetime] | None = None,
        monotonic_clock: Callable[[], float] = monotonic,
        monitor_interval: float = 1.0,
    ) -> None:
        if (
            isinstance(max_per_user, bool)
            or isinstance(max_total, bool)
            or not isinstance(max_per_user, int)
            or not isinstance(max_total, int)
            or max_per_user < 1
            or max_total < 1
            or max_per_user > max_total
            or monitor_interval <= 0
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
        self._stop_controls: dict[str, _ExecutionStopControl] = {}
        self._wall_clock = wall_clock or (lambda: datetime.now(UTC))
        self._monotonic_clock = monotonic_clock
        self._monitor_interval = monitor_interval
        self._monitor_stop = Event()
        self._monitor_thread = Thread(
            target=self._monitor_loop,
            name="chatbi-execution-monitor",
            daemon=True,
        )
        self._accepting = True
        self._closed = False
        self._executor = ThreadPoolExecutor(
            max_workers=max_total, thread_name_prefix="chatbi-execution"
        )
        self._monitor_thread.start()

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
            raise ValueError("owner_id必须为正整数")
        capacity_lease = self.reserve_owner(owner_id)

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
            return ExecutionLease(self, history_lease, analysis_lease, capacity_lease)
        except BaseException:
            if analysis_lease is not None:
                analysis_lease.release()
            if history_lease is not None:
                history_lease.release()
            capacity_lease.release()
            raise

    def reserve_owner(self, owner_id) -> OwnerCapacityLease:
        if not (
            (
                isinstance(owner_id, int)
                and not isinstance(owner_id, bool)
                and owner_id > 0
            )
            or (
                isinstance(owner_id, tuple)
                and len(owner_id) == 2
                and all(isinstance(value, str) and value for value in owner_id)
            )
        ):
            raise ValueError("owner必须是有效账号ID或服务端Provider/Subject身份")
        with self._condition:
            if not self._accepting:
                raise ExecutionRuntimeClosed()
            if self._active_by_user.get(owner_id, 0) >= self._max_per_user:
                raise ExecutionCapacityExceeded("user")
            if self._active_total >= self._max_total:
                raise ExecutionCapacityExceeded("process")
            self._active_by_user[owner_id] = self._active_by_user.get(owner_id, 0) + 1
            self._active_total += 1

        return OwnerCapacityLease(self, owner_id)

    def capacity_snapshot(self):
        with self._condition:
            return {
                "active": self._active_total,
                "max_total": self._max_total,
                "max_per_user": self._max_per_user,
                "accepting": self._accepting,
            }

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

    def bind_stop_control(
        self,
        lease: ExecutionLease,
        execution,
        progress,
        *,
        persist_stop: Callable[[str], object],
        authorize: Callable[[], None],
    ) -> _ExecutionStopControl:
        """把持久停止裁决、授权轮询和下游中断绑定到当前 worker 租约。"""

        if lease._runtime is not self:
            raise ValueError("执行租约不属于当前 Runtime")
        with lease._lock:
            if lease._released or lease._submitted or lease._execution_id is None:
                raise ExecutionRuntimeClosed()
            if lease._stop_control is not None:
                raise ValueError("执行租约已绑定停止控制")
            remaining = (execution.deadline_at - self._wall_clock()).total_seconds()
            control = _ExecutionStopControl(
                execution.id,
                progress,
                persist_stop,
                authorize,
                deadline=self._monotonic_clock() + max(0.0, remaining),
                monotonic_clock=self._monotonic_clock,
            )
            if execution.status == "stopping":
                control.signal(
                    execution.stop_reason or ExecutionStopReason.USER_CANCELLED
                )
            with self._condition:
                self._stop_controls[execution.id] = control
                lease._stop_control = control
            return control

    def request_stop(self, execution_id: str, reason: str):
        with self._condition:
            control = self._stop_controls.get(execution_id)
        return None if control is None else control.request_stop(reason)

    def signal_stop(self, execution_id: str, reason: str) -> None:
        with self._condition:
            control = self._stop_controls.get(execution_id)
        if control is not None:
            control.signal(reason)

    def monitor_once(self) -> None:
        """检查 deadline 和原执行身份；向测试 seam 提供无 sleep 的时钟边界。"""

        with self._condition:
            controls = tuple(self._stop_controls.values())
        now = self._monotonic_clock()
        for control in controls:
            if control.stopped:
                continue
            if now >= control.deadline:
                self._request_stop_from_monitor(
                    control, ExecutionStopReason.DEADLINE_EXCEEDED
                )
                continue
            try:
                control.authorize()
            except Exception as exc:
                self._request_stop_from_monitor(
                    control, _authorization_stop_reason(exc)
                )

    def _request_stop_from_monitor(self, control, reason) -> None:
        try:
            control.request_stop(reason)
        except Exception:
            # 认证或持久化依赖失效时停止本地业务链；持久化不确定性由重开协调标识。
            control.signal(reason)

    def _monitor_loop(self) -> None:
        while not self._monitor_stop.wait(self._monitor_interval):
            self.monitor_once()

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
        self._monitor_stop.set()
        self._monitor_thread.join(timeout=max(1.0, self._monitor_interval * 2))
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

    def _release_stop_control(self, execution_id, control) -> None:
        with self._condition:
            if self._stop_controls.get(execution_id) is control:
                del self._stop_controls[execution_id]


class _ExecutionStopControl:
    def __init__(
        self,
        execution_id,
        progress,
        persist_stop,
        authorize,
        *,
        deadline,
        monotonic_clock,
    ):
        self.execution_id = execution_id
        self.progress = progress
        self._persist_stop = persist_stop
        self.authorize = authorize
        self.deadline = deadline
        self._monotonic_clock = monotonic_clock
        self._lock = Lock()
        self._reason: ExecutionStopReason | None = None
        self._database_cancel: Callable[[], None] | None = None

    @property
    def stopped(self) -> bool:
        with self._lock:
            return self._reason is not None

    def checkpoint(self) -> None:
        with self._lock:
            reason = self._reason
        if reason is not None:
            raise ExecutionStopped(reason)
        if self._monotonic_clock() >= self.deadline:
            reason = ExecutionStopReason.DEADLINE_EXCEEDED
            try:
                self.request_stop(reason)
            except Exception:
                self.signal(reason)
            with self._lock:
                reason = self._reason or reason
            raise ExecutionStopped(reason)
        try:
            self.authorize()
        except Exception as exc:
            reason = _authorization_stop_reason(exc)
            try:
                self.request_stop(reason)
            except Exception:
                self.signal(reason)
            with self._lock:
                reason = self._reason or reason
            raise ExecutionStopped(reason) from None
        with self._lock:
            reason = self._reason
        if reason is not None:
            raise ExecutionStopped(reason)

    def request_stop(self, reason: str):
        requested = ExecutionStopReason(reason)
        record = self._persist_stop(requested.value)
        if record.status == "stopping":
            self.signal(record.stop_reason or requested)
        return record

    def signal(self, reason: str) -> None:
        requested = ExecutionStopReason(reason)
        with self._lock:
            if self._reason is not None:
                return
            self._reason = requested
            callback = self._database_cancel
        if self.progress is not None:
            self.progress.set_status("stopping", requested.value)
        if callback is not None:
            try:
                callback()
            except Exception:
                pass

    @contextmanager
    def register_database_cancel(self, callback: Callable[[], None]):
        with self._lock:
            previous = self._database_cancel
            self._database_cancel = callback
            already_stopped = self._reason is not None
        if already_stopped:
            try:
                callback()
            except Exception:
                pass
        try:
            yield
        finally:
            with self._lock:
                if self._database_cancel is callback:
                    self._database_cancel = previous


def _positive_limit(value):
    if not isinstance(value, str) or not value.strip().isdigit():
        raise ValueError("执行额度配置必须为正整数")
    result = int(value.strip())
    if result < 1:
        raise ValueError("执行额度配置必须为正整数")
    return result


def _authorization_stop_reason(error):
    status = getattr(error, "status", None)
    if status in {401, 403}:
        return ExecutionStopReason.AUTHORIZATION_REVOKED
    return ExecutionStopReason.AUTHORIZATION_UNAVAILABLE
