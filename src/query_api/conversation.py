"""Query API/Application 的短期会话状态边界。"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Protocol
from uuid import uuid4

CONVERSATION_IDLE_TTL = timedelta(minutes=30)
Clock = Callable[[], datetime]


class ConversationUnavailableError(RuntimeError):
    """会话未知、过期或不属于当前认证用户。"""


class ConversationConflictError(RuntimeError):
    """同一会话已有进行中的轮次。"""


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    """服务端持有的最后一次成功会话快照。"""

    conversation_id: str
    subject_id: str
    last_success_at: datetime
    structured_query_state: object | None = None


@dataclass(frozen=True, slots=True)
class ConversationLease:
    """一个已经获得单会话并发租约的轮次。"""

    record: ConversationRecord
    token: str


class ConversationStore(Protocol):
    """Application 会话状态存储的最小 Port。"""

    def create(self, *, subject_id: str) -> ConversationRecord:
        """创建首个成功轮次对应的会话。"""

    def acquire(
        self,
        conversation_id: str,
        *,
        subject_id: str,
    ) -> ConversationLease:
        """校验归属、TTL 和并发状态，并占用一个会话轮次。"""

    def commit(
        self,
        lease: ConversationLease,
        *,
        structured_query_state: object | None,
    ) -> ConversationRecord:
        """提交成功轮次并释放租约。"""

    def abort(self, lease: ConversationLease) -> None:
        """放弃失败轮次且不改变最后一次成功状态。"""


@dataclass(slots=True)
class _StoredConversation:
    record: ConversationRecord
    in_flight_token: str | None = None


class InMemoryConversationStore:
    """进程内短期会话 Adapter。

    V1 明确要求服务重启后会话失效，因此这里不引入持久化或新的外部基础设施。
    通过 `ConversationStore` Port 隔离后续替换为共享存储的边界。
    """

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        idle_ttl: timedelta = CONVERSATION_IDLE_TTL,
    ) -> None:
        if idle_ttl <= timedelta(0):
            raise ValueError("会话 Idle TTL 必须为正数")
        self._clock = clock or (lambda: datetime.now(UTC))
        self._idle_ttl = idle_ttl
        self._entries: dict[str, _StoredConversation] = {}
        self._lock = Lock()

    def create(self, *, subject_id: str) -> ConversationRecord:
        normalized_subject = _required_text(subject_id, "subject_id")
        now = self._now()
        with self._lock:
            self._purge_expired(now)
            conversation_id = uuid4().hex
            while conversation_id in self._entries:
                conversation_id = uuid4().hex
            record = ConversationRecord(
                conversation_id=conversation_id,
                subject_id=normalized_subject,
                last_success_at=now,
            )
            self._entries[conversation_id] = _StoredConversation(record=record)
            return record

    def acquire(
        self,
        conversation_id: str,
        *,
        subject_id: str,
    ) -> ConversationLease:
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            raise ConversationUnavailableError
        normalized_id = conversation_id.strip()
        normalized_subject = _required_text(subject_id, "subject_id")
        now = self._now()
        with self._lock:
            entry = self._entries.get(normalized_id)
            if entry is None:
                raise ConversationUnavailableError
            if entry.record.subject_id != normalized_subject:
                raise ConversationUnavailableError
            if _is_expired(entry.record, now, self._idle_ttl):
                del self._entries[normalized_id]
                raise ConversationUnavailableError
            if entry.in_flight_token is not None:
                raise ConversationConflictError
            token = uuid4().hex
            entry.in_flight_token = token
            return ConversationLease(record=entry.record, token=token)

    def commit(
        self,
        lease: ConversationLease,
        *,
        structured_query_state: object | None,
    ) -> ConversationRecord:
        now = self._now()
        with self._lock:
            entry = self._entry_for_lease(lease)
            record = replace(
                entry.record,
                last_success_at=now,
                structured_query_state=structured_query_state,
            )
            entry.record = record
            entry.in_flight_token = None
            return record

    def abort(self, lease: ConversationLease) -> None:
        with self._lock:
            entry = self._entries.get(lease.record.conversation_id)
            if entry is None:
                return
            if entry.in_flight_token == lease.token:
                entry.in_flight_token = None

    def _entry_for_lease(self, lease: ConversationLease) -> _StoredConversation:
        entry = self._entries.get(lease.record.conversation_id)
        if entry is None or entry.in_flight_token != lease.token:
            raise ConversationUnavailableError
        if entry.record.subject_id != lease.record.subject_id:
            raise ConversationUnavailableError
        return entry

    def _purge_expired(self, now: datetime) -> None:
        expired_ids = [
            conversation_id
            for conversation_id, entry in self._entries.items()
            if _is_expired(entry.record, now, self._idle_ttl)
        ]
        for conversation_id in expired_ids:
            del self._entries[conversation_id]

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise RuntimeError("会话时钟必须返回带时区的 datetime")
        return value.astimezone(UTC)


def _is_expired(
    record: ConversationRecord,
    now: datetime,
    idle_ttl: timedelta,
) -> bool:
    return now - record.last_success_at >= idle_ttl


def _required_text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} 必须是非空字符串")
    return value.strip()
