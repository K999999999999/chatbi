"""后台执行 Application / Infrastructure 共享的最小持久化 DTO。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .history_contracts import AcceptedAttempt


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    id: str
    history_id: str
    turn_id: str
    operation_id: str
    mode: str
    operation_kind: str
    status: str
    stop_reason: str | None
    created_at: datetime
    started_at: datetime | None
    deadline_at: datetime
    finished_at: datetime | None
    public_error: dict | None


@dataclass(frozen=True, slots=True)
class ExecutionAcceptance:
    execution: ExecutionRecord
    attempt: AcceptedAttempt | None
    created: bool


class ExecutionStore(Protocol):
    def execution(self, owner: int, execution_id: str) -> ExecutionRecord: ...

    def execution_by_operation(
        self, owner: int, operation_id: str
    ) -> ExecutionRecord | None: ...
