"""同一执行的有界实时快照和 SSE 订阅缓冲。"""

from __future__ import annotations

import json
from collections import deque
from io import StringIO
from threading import Condition

from src.online_query.contracts import ExecutionStage

_TEXT_DRAFT_FIELDS = frozenset({"title", "executive_summary", "trend_judgment"})
_LIST_DRAFT_FIELDS = frozenset({"key_findings", "root_causes", "action_suggestions"})
_DRAFT_FIELDS = _TEXT_DRAFT_FIELDS | _LIST_DRAFT_FIELDS
_MAX_DRAFT_BYTES = 5 * 1024 * 1024
_MAX_DELTA_BYTES = 16 * 1024


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
            "draft": None,
        }
        self._draft_parts: dict[tuple[str, int | None], StringIO] = {}
        self._draft_lengths: dict[tuple[str, int | None], int] = {}
        self._draft_list_lengths: dict[str, int] = {}
        self._draft_fields: set[str] = set()
        self._draft_bytes = 0
        self._draft_snapshot_bytes = 2
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

    def set_status(self, status: str, stop_reason: str | None = None) -> None:
        if status not in {"accepted", "running", "stopping"}:
            raise ValueError("执行中状态无效")
        with self._condition:
            if self._terminal:
                return
            order = {"accepted": 0, "running": 1, "stopping": 2}
            if order[status] < order[self._state["status"]]:
                raise ValueError("执行状态不能回退")
            self._state["status"] = status
            payload = {"status": status}
            if status == "stopping":
                if stop_reason is None:
                    raise ValueError("停止状态必须包含原因")
                self._state["stop_reason"] = stop_reason
                payload["stop_reason"] = stop_reason
            self._append_locked("progress", payload)

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

    def text_delta(self, field: str, index: int | None, offset: int, text: str) -> None:
        if field not in _DRAFT_FIELDS:
            raise ValueError("报告草稿字段不在公开白名单中")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("报告草稿偏移无效")
        if field in _TEXT_DRAFT_FIELDS:
            if index is not None:
                raise ValueError("报告文字字段不能包含列表索引")
        elif isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise ValueError("报告列表草稿索引无效")
        if not isinstance(text, str) or not text:
            raise ValueError("报告草稿增量必须是非空文本")
        try:
            encoded_size = len(text.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise ValueError("报告草稿包含无效 Unicode") from exc
        with self._condition:
            if self._terminal:
                return
            if field in _TEXT_DRAFT_FIELDS:
                target_index = None
            else:
                assert index is not None
                if index > self._draft_list_lengths.get(field, 0):
                    raise ValueError("报告草稿列表索引不连续")
                target_index = index
            key = (field, target_index)
            if self._draft_lengths.get(key, 0) != offset:
                raise ValueError("报告草稿偏移与当前文本不一致")
            if self._draft_bytes + encoded_size > _MAX_DRAFT_BYTES:
                raise ValueError("报告草稿超过公开上限")

            snapshot_increment = _draft_snapshot_increment(
                field,
                target_index,
                field_exists=field in self._draft_fields,
                has_any_field=bool(self._draft_fields),
                existing_list_length=self._draft_list_lengths.get(field, 0),
                text=text,
            )
            if self._draft_snapshot_bytes + snapshot_increment > _MAX_DRAFT_BYTES:
                raise ValueError("报告草稿快照超过公开上限")

            chunk_limit = min(_MAX_DELTA_BYTES, self._max_bytes)
            chunks = _split_utf8(text, chunk_limit)
            while not self._delta_events_fit(field, target_index, offset, chunks):
                if chunk_limit == 1:
                    raise ValueError("报告草稿事件超过共享缓冲上限")
                chunk_limit = max(1, chunk_limit // 2)
                chunks = _split_utf8(text, chunk_limit)

            writer = self._draft_parts.get(key)
            if writer is None:
                writer = StringIO()
                self._draft_parts[key] = writer
            writer.write(text)
            self._draft_lengths[key] = offset + len(text)
            if field not in self._draft_fields:
                self._draft_fields.add(field)
            if (
                target_index is not None
                and target_index == self._draft_list_lengths.get(field, 0)
            ):
                self._draft_list_lengths[field] = target_index + 1
            self._draft_bytes += encoded_size
            self._draft_snapshot_bytes += snapshot_increment
            next_offset = offset
            for chunk in chunks:
                self._append_locked(
                    "text_delta",
                    {
                        "field": field,
                        "index": target_index,
                        "offset": next_offset,
                        "text": chunk,
                    },
                )
                next_offset += len(chunk)

    def _delta_events_fit(
        self,
        field: str,
        index: int | None,
        offset: int,
        chunks: tuple[str, ...],
    ) -> bool:
        next_offset = offset
        for ordinal, chunk in enumerate(chunks, start=1):
            event = {
                "version": self.VERSION,
                "execution_id": self.execution.id,
                "history_id": self.execution.history_id,
                "turn_id": self.execution.turn_id,
                "sequence": self._sequence + ordinal,
                "draft_generation": self._state["draft_generation"],
                "type": "text_delta",
                "payload": {
                    "field": field,
                    "index": index,
                    "offset": next_offset,
                    "text": chunk,
                },
            }
            size = len(
                json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode(
                    "utf-8"
                )
            )
            if size > self._max_bytes:
                return False
            next_offset += len(chunk)
        return True

    def reset(self, reason: str) -> None:
        if reason != "model_retry":
            raise ValueError("报告草稿重置原因无效")
        with self._condition:
            if self._terminal:
                return
            self._state["draft_generation"] += 1
            self._clear_draft_locked()
            self._append_locked("draft_reset", {"reason": reason})

    def finish(self, status: str, public_error: dict | None = None) -> None:
        if status not in {
            "succeeded",
            "failed",
            "cancelled",
            "timed_out",
            "unconfirmed",
        }:
            raise ValueError("执行终态无效")
        with self._condition:
            if self._terminal:
                return
            self._state["status"] = status
            self._clear_draft_locked()
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
            if (
                not any(event["sequence"] > sequence for event, _ in self._ring)
                and not self._terminal
            ):
                self._condition.wait_for(
                    lambda: (
                        self._terminal
                        or any(event["sequence"] > sequence for event, _ in self._ring)
                    ),
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
            "payload": {
                **self._state,
                "draft": self._current_draft_locked(),
            },
        }

    def _current_draft_locked(self) -> dict | None:
        if not self._draft_parts:
            return None
        draft: dict = {}
        for (field, index), writer in self._draft_parts.items():
            value = writer.getvalue()
            if index is None:
                draft[field] = value
            else:
                values = draft.setdefault(field, [])
                if len(values) != index:
                    raise RuntimeError("报告草稿列表状态不连续")
                values.append(value)
        return draft

    def _clear_draft_locked(self) -> None:
        self._draft_parts.clear()
        self._draft_lengths.clear()
        self._draft_list_lengths.clear()
        self._draft_fields.clear()
        self._draft_bytes = 0
        self._draft_snapshot_bytes = 2

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
        size = len(
            json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode()
        )
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


def _split_utf8(text: str, max_bytes: int) -> tuple[str, ...]:
    parts: list[str] = []
    current: list[str] = []
    current_bytes = 0
    for char in text:
        char_bytes = len(char.encode("utf-8"))
        if current and current_bytes + char_bytes > max_bytes:
            parts.append("".join(current))
            current = []
            current_bytes = 0
        if char_bytes > max_bytes:
            raise ValueError("报告草稿字符超过单事件上限")
        current.append(char)
        current_bytes += char_bytes
    if current:
        parts.append("".join(current))
    return tuple(parts)


def _draft_snapshot_increment(
    field: str,
    index: int | None,
    *,
    field_exists: bool,
    has_any_field: bool,
    existing_list_length: int,
    text: str,
) -> int:
    content_bytes = 0
    short_escapes = {'"', "\\", "\b", "\t", "\n", "\f", "\r"}
    for char in text:
        if char in short_escapes:
            content_bytes += 2
        elif ord(char) < 0x20:
            content_bytes += 6
        else:
            content_bytes += len(char.encode("utf-8"))

    if field_exists:
        if index is not None and index == existing_list_length:
            return content_bytes + (1 if existing_list_length else 0) + 2
        return content_bytes

    key_bytes = len(field.encode("ascii")) + 2
    value_bytes = 2 if index is None else 4
    return content_bytes + key_bytes + 1 + value_bytes + (1 if has_any_field else 0)
