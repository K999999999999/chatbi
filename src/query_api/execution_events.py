"""同一执行的有界实时快照和 SSE 订阅缓冲。"""

from __future__ import annotations

import json
from collections import deque
from threading import Condition

from src.online_query.contracts import ExecutionStage


class ExecutionSubscriberLimit(RuntimeError):
    """一个执行已达到允许的观察连接数。"""


class ExecutionEventChannel:
    VERSION = 1

    def __init__(
        self,
        execution,
        *,
        max_events: int = 64,
        max_bytes: int = 1024 * 1024,
        max_subscribers: int = 8,
    ):
        if min(max_events, max_bytes, max_subscribers) < 1:
            raise ValueError("执行事件缓冲与订阅上限必须为正整数")
        self.execution = execution
        self._max_events = max_events
        self._max_bytes = max_bytes
        self._max_subscribers = max_subscribers
        self._condition = Condition()
        self._sequence = 0
        self._state = {
            "status": execution.status,
            "stage": None,
            "completed_tasks": 0,
            "total_tasks": None,
            "stop_reason": execution.stop_reason,
            "draft_generation": 0,
        }
        self._ring: deque[tuple[dict, int]] = deque()
        self._ring_bytes = 0
        self._subscribers = 0
        self._terminal = execution.status in {
            "succeeded",
            "failed",
            "cancelled",
            "timed_out",
            "unconfirmed",
        }

    @property
    def terminal(self) -> bool:
        with self._condition:
            return self._terminal

    @property
    def ring_bytes(self) -> int:
        with self._condition:
            return self._ring_bytes

    def set_status(self, status: str) -> None:
        if status not in {"accepted", "running"}:
            raise ValueError("执行中状态无效")
        with self._condition:
            if self._terminal:
                return
            if status == "accepted" and self._state["status"] != "accepted":
                raise ValueError("执行状态不能回退")
            self._state["status"] = status
            self._append_locked("progress", {"status": status})

    def set_stage(self, stage: ExecutionStage | str) -> None:
        try:
            value = ExecutionStage(stage).value
        except ValueError as exc:
            raise ValueError("执行阶段不在公开 Contract 中") from exc
        with self._condition:
            if self._terminal:
                return
            self._state["stage"] = value
            self._append_locked("progress", self._progress_payload())

    def set_task_progress(self, completed: int, total: int) -> None:
        if (
            isinstance(completed, bool)
            or isinstance(total, bool)
            or not isinstance(completed, int)
            or not isinstance(total, int)
            or total < 1
            or completed < 0
            or completed > total
        ):
            raise ValueError("分析任务计数无效")
        with self._condition:
            if self._terminal:
                return
            self._state["completed_tasks"] = completed
            self._state["total_tasks"] = total
            self._append_locked("progress", self._progress_payload())

    def finish(self, status: str, public_error: dict | None = None) -> None:
        if status not in {"succeeded", "failed", "cancelled", "timed_out", "unconfirmed"}:
            raise ValueError("执行终态无效")
        with self._condition:
            if self._terminal:
                return
            self._state["status"] = status
            payload = {"status": status}
            if public_error is not None:
                safe_error = {
                    key: public_error[key]
                    for key in ("error_code", "error_message")
                    if isinstance(public_error.get(key), str)
                }
                if safe_error:
                    payload["public_error"] = safe_error
            self._terminal = True
            self._append_locked("terminal", payload)

    def subscribe(self) -> ExecutionEventSubscription:
        with self._condition:
            if self._subscribers >= self._max_subscribers:
                raise ExecutionSubscriberLimit()
            self._subscribers += 1
            return ExecutionEventSubscription(self, self._snapshot_locked())

    def _unsubscribe(self) -> None:
        with self._condition:
            if self._subscribers <= 0:
                raise RuntimeError("执行观察连接重复释放")
            self._subscribers -= 1
            self._condition.notify_all()

    def _read_after(self, sequence: int, timeout: float | None):
        with self._condition:
            if not any(event["sequence"] > sequence for event, _ in self._ring) and not self._terminal:
                self._condition.wait_for(
                    lambda: self._terminal
                    or any(event["sequence"] > sequence for event, _ in self._ring),
                    timeout=timeout,
                )
            if not self._ring:
                return (), sequence
            oldest = self._ring[0][0]["sequence"]
            if sequence < oldest - 1:
                snapshot = self._snapshot_locked()
                return (snapshot,), snapshot["sequence"]
            events = tuple(
                event for event, _ in self._ring if event["sequence"] > sequence
            )
            if events:
                return events, events[-1]["sequence"]
            return (), sequence

    def _snapshot_locked(self) -> dict:
        return {
            "version": self.VERSION,
            "execution_id": self.execution.id,
            "history_id": self.execution.history_id,
            "turn_id": self.execution.turn_id,
            "sequence": self._sequence,
            "draft_generation": self._state["draft_generation"],
            "type": "snapshot",
            "payload": dict(self._state),
        }

    def _progress_payload(self) -> dict:
        return {
            "stage": self._state["stage"],
            "completed_tasks": self._state["completed_tasks"],
            "total_tasks": self._state["total_tasks"],
        }

    def _append_locked(self, event_type: str, payload: dict) -> None:
        self._sequence += 1
        event = {
            "version": self.VERSION,
            "execution_id": self.execution.id,
            "history_id": self.execution.history_id,
            "turn_id": self.execution.turn_id,
            "sequence": self._sequence,
            "draft_generation": self._state["draft_generation"],
            "type": event_type,
            "payload": payload,
        }
        size = len(json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode())
        if size > self._max_bytes:
            self._sequence -= 1
            raise ValueError("执行事件超过共享缓冲上限")
        self._ring.append((event, size))
        self._ring_bytes += size
        while len(self._ring) > self._max_events or self._ring_bytes > self._max_bytes:
            _, removed_size = self._ring.popleft()
            self._ring_bytes -= removed_size
        self._condition.notify_all()


class ExecutionEventSubscription:
    def __init__(self, channel: ExecutionEventChannel, snapshot: dict):
        self._channel = channel
        self.snapshot = snapshot
        self._sequence = snapshot["sequence"]
        self._closed = False

    def read(self, timeout: float | None = None) -> tuple[dict, ...]:
        if self._closed:
            return ()
        events, self._sequence = self._channel._read_after(self._sequence, timeout)
        return events

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._channel._unsubscribe()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


def encode_sse(event: dict) -> bytes:
    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"id: {event['sequence']}\nevent: {event['type']}\ndata: {data}\n\n".encode()
