"""可终止的轻量依赖探测进程与真实模型调用观察装配。"""

import json
import subprocess
import sys
from threading import Event, Thread

from src.query_api.operations import DEPENDENCIES


class ProcessReadinessProbe:
    def __init__(self, *, command=None, timeout=10):
        self._command = command or [sys.executable, "-m", "src.bootstrap.readiness"]
        self._timeout = timeout

    def __call__(self):
        unknown = dict.fromkeys(DEPENDENCIES, "unknown")
        try:
            result = subprocess.run(
                self._command, capture_output=True, timeout=self._timeout, check=False
            )
            if result.returncode or len(result.stdout) > 4096:
                return unknown
            checks = json.loads(result.stdout)
            if (
                not isinstance(checks, dict)
                or set(checks) != set(DEPENDENCIES)
                or any(
                    value not in {"ready", "not_ready", "unknown"}
                    for value in checks.values()
                )
            ):
                return unknown
            return checks
        except (OSError, subprocess.TimeoutExpired, ValueError):
            return unknown


class OperationsMonitor:
    def __init__(self, state, *, probe=None, interval=15):
        self._state = state
        self._probe = probe or ProcessReadinessProbe()
        self._interval = interval
        self._stop = Event()
        self._thread = Thread(target=self._run, name="chatbi-readiness", daemon=True)

    def start(self):
        self._thread.start()

    def close(self):
        self._stop.set()
        self._thread.join(timeout=11)

    def _run(self):
        while not self._stop.is_set():
            checks = self._probe()
            if self._stop.is_set():
                return
            self._state.record_checks(checks)
            if self._stop.wait(self._interval):
                return


class ObservedModel:
    """仅观察真实invoke结束；不接收/保存问题、结果或异常文本。"""

    def __init__(self, model, observer):
        self._model = model
        self._observer = observer

    def invoke(self, prompt):
        try:
            response = self._model.invoke(prompt)
        except Exception:
            self._observer(False)
            raise
        self._observer(True)
        return response
