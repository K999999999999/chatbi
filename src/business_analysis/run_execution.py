"""单API进程内同owner /run的完整执行互斥。"""

from contextlib import contextmanager
from threading import Condition


class AnalysisExecutionBusy(RuntimeError):
    """同一分析运行仍在执行，不能并发修改checkpoint。"""


class AnalysisExecutionGuard:
    def __init__(self):
        self._condition = Condition()
        self._running = set()
        self._accepting = True

    @contextmanager
    def executing(self, auth, run_id):
        key = (auth.identity_provider, auth.subject_id, run_id)
        with self._condition:
            if not self._accepting or key in self._running:
                raise AnalysisExecutionBusy("分析运行正在执行")
            self._running.add(key)
        try:
            yield
        finally:
            with self._condition:
                self._running.remove(key)
                self._condition.notify_all()

    def drain(self):
        with self._condition:
            self._accepting = False
            while self._running:
                self._condition.wait()
