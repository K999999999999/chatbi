"""就绪与共享额度保护；同步执行持有租约直到真实工作结束。"""

import logging
from contextlib import contextmanager
from threading import Timer
from time import monotonic

from src.online_query.contracts import (
    ExecutionStopped,
    ExecutionStopReason,
    QueryErrorCode,
    QueryFailure,
)
from .execution_runtime import ExecutionCapacityExceeded, ExecutionRuntimeClosed


class AdmissionRejected(RuntimeError):
    def __init__(self, result):
        super().__init__(result.error_code.value)
        self.result = result


def capacity_owner(auth):
    return (
        auth.user_id
        if auth.user_id is not None
        else (auth.identity_provider, auth.subject_id)
    )


class SynchronousExecutionControl:
    def __init__(self, seconds, *, clock=monotonic):
        self._clock = clock
        self._deadline = clock() + seconds

    def checkpoint(self):
        if self._clock() >= self._deadline:
            raise ExecutionStopped(ExecutionStopReason.DEADLINE_EXCEEDED)

    @contextmanager
    def register_database_cancel(self, callback):
        self.checkpoint()

        def cancel_database():
            try:
                callback()
            except Exception:  # noqa: BLE001 - cancellation cannot log database details
                logging.getLogger(__name__).warning("数据库中断通知失败")

        timer = Timer(max(0, self._deadline - self._clock()), cancel_database)
        timer.daemon = True
        timer.start()
        try:
            yield
        finally:
            timer.cancel()
            timer.join(timeout=2)


@contextmanager
def admit(request, auth, request_id, *, seconds):
    state = request.app.state
    operations = getattr(state, "operations", None)
    runtime = getattr(state, "execution_runtime", None)
    if operations is None or not operations.ready or runtime is None:
        raise AdmissionRejected(
            QueryFailure(
                request_id,
                QueryErrorCode.SERVICE_NOT_READY,
                "服务暂时不可用，请稍后重试",
            )
        )
    try:
        lease = runtime.reserve_owner(capacity_owner(auth))
    except ExecutionCapacityExceeded:
        raise AdmissionRejected(
            QueryFailure(
                request_id,
                QueryErrorCode.EXECUTION_LIMIT_REACHED,
                "已有执行仍在运行，请稍后重试",
            )
        ) from None
    except ExecutionRuntimeClosed:
        raise AdmissionRejected(
            QueryFailure(
                request_id, QueryErrorCode.SERVICE_NOT_READY, "执行服务正在关闭"
            )
        ) from None
    try:
        yield SynchronousExecutionControl(seconds)
    finally:
        lease.release()
