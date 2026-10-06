"""历史Application与存储Port的稳定DTO，不依赖HTTP或ORM。"""

import json
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Protocol


class HistoryError(RuntimeError):
    """可公开的历史操作错误。"""

    def __init__(
        self,
        code: str,
        message: str,
        status: int,
        *,
        history_id=None,
        turn_id=None,
        execution_id=None,
    ):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.history_id, self.turn_id = history_id, turn_id
        self.execution_id = execution_id


def unavailable() -> HistoryError:
    return HistoryError("HISTORY_UNAVAILABLE", "记录不可用", 404)


def busy() -> HistoryError:
    return HistoryError("HISTORY_BUSY", "当前记录正在执行，请稍后刷新", 409)


def stale() -> HistoryError:
    return HistoryError("HISTORY_STALE", "记录已更新，请刷新后再操作", 409)


def storage_unavailable() -> HistoryError:
    return HistoryError("HISTORY_STORAGE_UNAVAILABLE", "历史存储暂时不可用", 503)


def operation_hash(value) -> str:
    """按稳定 JSON 结构生成操作请求摘要，不依赖具体存储 Adapter。"""

    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class HistoryHeader:
    id: str
    kind: str
    title: str
    first_question: str
    created_at: datetime
    updated_at: datetime
    context_revision: int
    record_revision: int
    last_success_turn_id: str | None
    active_turn_id: str | None
    analysis_run_id: str | None
    analysis_recovery_available: bool = True


@dataclass(frozen=True, slots=True)
class SavedResultHeader:
    id: str
    kind: str
    title: str
    record_revision: int
    created_at: datetime
    updated_at: datetime
    source_history_id: str
    source_turn_id: str


@dataclass(frozen=True, slots=True)
class HistoryTurn:
    id: str
    history_id: str
    ordinal: int
    question: str
    status: str
    request_id: str
    created_at: datetime
    public_error: dict | None
    snapshot: dict | None
    execution_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionToken:
    history_id: str
    turn_id: str
    epoch: str
    generation: int


@dataclass(frozen=True, slots=True)
class AcceptedAttempt:
    token: ExecutionToken | None
    turn: HistoryTurn
    base_state: dict | None
    source_snapshot: dict | None = None


class HistoryStore(Protocol):
    def create(
        self, owner: int, kind: str, question: str, operation_id: str
    ) -> HistoryHeader: ...
    def header(self, owner: int, history_id: str) -> HistoryHeader: ...
    def begin_attempt(
        self,
        owner: int,
        history_id: str,
        question: str,
        operation_id: str,
        revision: int,
        request_id: str,
        epoch: str,
    ) -> AcceptedAttempt: ...
    def begin_execution_attempt(self, **kwargs): ...
    def begin_execution_requery(self, **kwargs): ...
    def execution(self, owner: int, execution_id: str): ...
    def execution_by_operation(self, owner: int, operation_id: str): ...
    def mark_execution_running(self, owner: int, execution_id: str) -> None: ...
    def finish_execution_attempt(
        self, owner: int, token: ExecutionToken, snapshot, error, execution_id: str
    ) -> HistoryTurn: ...
    def finish_attempt(
        self,
        owner: int,
        token: ExecutionToken,
        snapshot: dict | None,
        error: dict | None,
    ) -> HistoryTurn: ...
    def turn(self, owner: int, history_id: str, turn_id: str) -> HistoryTurn: ...
    def list_histories(
        self, owner: int, kind: str | None, limit: int, cursor: str | None, q: str = ""
    ) -> tuple[list[HistoryHeader], str | None]: ...
    def turns(
        self, owner: int, history_id: str, limit: int, cursor: int
    ) -> tuple[list[HistoryTurn], int | None]: ...

    def begin_analysis_attempt(
        self,
        owner: int,
        history_id: str,
        operation_id: str,
        revision: int,
        request_id: str,
        epoch: str,
    ) -> AcceptedAttempt: ...
    def begin_requery(
        self,
        owner: int,
        source_kind: str,
        source_id: str,
        source_turn_id: str | None,
        operation_id: str,
        request_id: str,
        epoch: str,
        new_id: str,
    ) -> tuple[HistoryHeader, AcceptedAttempt]: ...
    def rename_history(
        self, owner: int, history_id: str, title: str, revision: int
    ) -> HistoryHeader: ...
    def delete_history(
        self, owner: int, history_id: str, revision: int, owner_subject: str
    ) -> None: ...
    def copy_result(
        self, owner: int, history_id: str, turn_id: str, title: str
    ) -> SavedResultHeader: ...
    def saved_result(
        self, owner: int, result_id: str
    ) -> tuple[SavedResultHeader, dict]: ...
    def export_snapshot(
        self, owner: int, source_kind: str, source_id: str, turn_id: str | None
    ) -> dict: ...
    def list_saved_results(
        self, owner: int, kind: str | None, limit: int, cursor: str | None, q: str = ""
    ) -> tuple[list[SavedResultHeader], str | None]: ...
    def rename_saved_result(
        self, owner: int, result_id: str, title: str, revision: int
    ) -> SavedResultHeader: ...
    def delete_saved_result(
        self, owner: int, result_id: str, revision: int
    ) -> None: ...
