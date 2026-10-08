"""运行证据与安全投影；不以存活、历史结果或模型探测冒称就绪。"""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from threading import Lock
from time import monotonic

DEPENDENCIES = ("control_database", "business_database", "qdrant", "assets")
STATES = frozenset({"ready", "not_ready", "unknown"})


class OperationsState:
    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        backup_provider: Callable[[], dict] | None = None,
    ):
        self._clock = clock
        self._wall_clock = wall_clock
        self._lock = Lock()
        self._checks = dict.fromkeys(DEPENDENCIES, "unknown")
        self._checked_at = None
        self._checked_tick = None
        self._model = None
        self._backup_provider = backup_provider

    def record_checks(self, checks: Mapping[str, str]) -> None:
        if set(checks) != set(DEPENDENCIES) or any(
            v not in STATES for v in checks.values()
        ):
            raise ValueError("运行依赖结果必须完整且使用安全状态")
        with self._lock:
            self._checks = dict(checks)
            self._checked_at = self._wall_clock().isoformat()
            self._checked_tick = self._clock()

    def record_model(self, success: bool) -> None:
        with self._lock:
            self._model = (self._clock(), self._wall_clock().isoformat(), success)

    def snapshot(self, *, detailed: bool = False) -> dict:
        backup = (
            (
                self._backup_provider()
                if self._backup_provider is not None
                else {"status": "unknown", "last_success": None, "overdue": True}
            )
            if detailed
            else None
        )
        with self._lock:
            now = self._clock()
            stale = self._checked_tick is None or now - self._checked_tick >= 30
            checks = (
                dict.fromkeys(DEPENDENCIES, "unknown") if stale else dict(self._checks)
            )
            status = (
                "not_ready"
                if "not_ready" in checks.values()
                else "unknown"
                if "unknown" in checks.values()
                else "ready"
            )
            result = {"status": status, "checked_at": self._checked_at}
            if detailed:
                model = {"status": "unknown", "checked_at": None}
                if self._model is not None:
                    tick, timestamp, success = self._model
                    model = {
                        "status": ("success" if success else "failure")
                        if now - tick < 900
                        else "unknown",
                        "checked_at": timestamp,
                    }
                    if not success and now - tick < 900:
                        model["failure_code"] = "MODEL_CALL_FAILED"
                result["details"] = {
                    "dependencies": checks,
                    "model": model,
                    "backup": backup,
                }
            return result

    @property
    def ready(self) -> bool:
        return self.snapshot()["status"] == "ready"
