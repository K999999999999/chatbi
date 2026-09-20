"""ChatBI 持久化审计适配器和安全字段 Contract。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.chatbi_control.models import AuditEvent, User

from .contracts import AuthorizationAuditEvent


class AuditUnavailable(RuntimeError):
    """安全审计无法写入，调用方必须按 Contract Fail Closed。"""


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """不携带敏感业务载荷的统一审计记录。"""

    event_type: str
    target_type: str
    target_id: str | None
    outcome: str
    request_id: str | None = None
    reason: str | None = None
    actor_user_id: int | None = None
    details: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("event_type", "target_type", "outcome"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} 必须是非空字符串")
        if self.actor_user_id is not None and self.actor_user_id <= 0:
            raise ValueError("actor_user_id 必须是正整数")
        if any(_contains_sensitive_key(key) for key in self.details):
            raise ValueError(
                "审计 details 不能包含 Secret、Token、Password、SQL 或结果载荷"
            )


class AuditWriter(Protocol):
    """可在现有数据库事务中写入安全审计记录的 Port。"""

    def write(self, session: Session, record: AuditRecord) -> None:
        """把记录加入当前事务。"""


class PersistentAuditSink:
    """把授权和查询审计写入 chatbi_control.audit_events。"""

    def __init__(self, session_factory: object) -> None:
        self._session_factory = session_factory

    def write(self, session: Session, record: AuditRecord) -> None:
        try:
            session.add(
                AuditEvent(
                    actor_user_id=record.actor_user_id,
                    event_type=record.event_type,
                    target_type=record.target_type,
                    target_id=record.target_id,
                    outcome=record.outcome,
                    request_id=record.request_id,
                    reason=record.reason,
                    details=record.details or None,
                )
            )
        except Exception as exc:  # noqa: BLE001 - audit boundary is explicit
            raise AuditUnavailable("ChatBI 审计写入失败") from exc

    def emit(self, event: AuthorizationAuditEvent) -> None:
        with self._session_factory() as session, session.begin():
            actor_user_id = session.scalar(
                select(User.id).where(User.username == event.subject_id)
            )
            self.write(
                session,
                AuditRecord(
                    event_type="query.authorization",
                    target_type="resource",
                    target_id=event.resource,
                    outcome=event.decision.value,
                    request_id=event.request_id,
                    reason=event.reason_code,
                    actor_user_id=actor_user_id,
                    details={
                        "identity_provider": event.identity_provider,
                        "action": event.action,
                        "policy_version": event.policy_version,
                    },
                ),
            )

    def emit_record(self, record: AuditRecord) -> None:
        with self._session_factory() as session, session.begin():
            self.write(session, record)

    def emit_query_outcome(
        self,
        *,
        request_id: str,
        actor_user_id: int | None,
        outcome: str,
        reason: str,
    ) -> None:
        self.emit_record(
            AuditRecord(
                event_type="query.outcome",
                target_type="resource",
                target_id="mart_sales",
                outcome=outcome,
                request_id=request_id,
                reason=reason,
                actor_user_id=actor_user_id,
            )
        )


def _contains_sensitive_key(key: object) -> bool:
    if not isinstance(key, str):
        return True
    normalized = key.casefold()
    return any(
        marker in normalized
        for marker in (
            "password",
            "secret",
            "token",
            "hash",
            "sql",
            "result",
            "question",
        )
    )
