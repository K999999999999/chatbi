"""单API进程内同owner /run的完整执行互斥。"""

from contextlib import contextmanager
from threading import Condition, Lock


class AnalysisExecutionBusy(RuntimeError):
    """同一分析运行仍在执行，不能并发修改checkpoint。"""


class AnalysisExecutionGuard:
    def __init__(self):
        self._condition = Condition()
        self._running = set()
        self._accepting = True

    @contextmanager
    def executing(self, auth, run_id):
        lease = self.reserve(auth, run_id)
        try:
            yield
        finally:
            lease.release()

    def reserve(self, auth, run_id):
        """允许受理层先占用 run，再将同一互斥租约交给 worker。"""

        key = (auth.identity_provider, auth.subject_id, run_id)
        with self._condition:
            if not self._accepting or key in self._running:
                raise AnalysisExecutionBusy("分析运行正在执行")
            self._running.add(key)
        return _AnalysisExecutionLease(self, key)

    def drain(self):
        with self._condition:
            self._accepting = False
            while self._running:
                self._condition.wait()

    def _release(self, key):
        with self._condition:
            self._running.discard(key)
            self._condition.notify_all()


class _AnalysisExecutionLease:
    def __init__(self, guard, key):
        self._guard = guard
        self._key = key
        self._lock = Lock()
        self._released = False

    def release(self):
        with self._lock:
            if self._released:
                return
            self._released = True
        self._guard._release(self._key)
