"""用存储故障seam验证Application不会误执行或推进未提交状态。"""

from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from src.authorization.contracts import AuthContext
from src.online_query.contracts import QuerySuccess
from src.query_api.history import HistoryApplication
from src.query_api.history_contracts import (
    AcceptedAttempt,
    ExecutionToken,
    HistoryError,
    HistoryHeader,
    HistoryTurn,
)
from tests.query_api.history_fixtures import query_state

AUTH = AuthContext("local:1", "local", user_id=1)
NOW = datetime(2026, 10, 4, tzinfo=UTC)
HEADER = HistoryHeader("h", "query", "q", "q", NOW, NOW, 0, 0, None, None, None)
TURN = HistoryTurn("t", "h", 1, "q", "accepted", "r", NOW, None, None)


class Runtime:
    epoch = "epoch"

    def check(self):
        pass

    @contextmanager
    def executing(self, history_id):
        yield


class ScriptedStore:
    """只注入受理 /完成故障；PG事务正确性另由真实Adapter测试验证。"""

    def __init__(self, *, begin_error=None, finish_error=None, base_state=None):
        self.begin_error, self.finish_error = begin_error, finish_error
        self.finish_calls = 0
        self.base_state = base_state
        self.finished_snapshot = None

    def header(self, owner, history_id):
        return HEADER

    def begin_attempt(self, *args):
        if self.begin_error:
            raise self.begin_error
        return AcceptedAttempt(
            ExecutionToken("h", "t", "epoch", 1), TURN, self.base_state
        )

    def finish_attempt(self, *args):
        self.finish_calls += 1
        self.finished_snapshot = args[2]
        if self.finish_error:
            raise self.finish_error
        return TURN


class QueryEntry:
    def __init__(self):
        self.executions = 0

    def authorize(self, request, *, auth_context):
        return None

    def execute_authorized(self, request, *, auth_context):
        self.executions += 1
        return QuerySuccess(
            "r", "SELECT 1", ("n",), ((1,),), 1, False, restoration_state=query_state()
        )


def test_begin_storage_failure_never_executes_business_query():
    entry = QueryEntry()
    store = ScriptedStore(
        begin_error=HistoryError("HISTORY_STORAGE_UNAVAILABLE", "不可用", 503)
    )
    app = HistoryApplication(store, Runtime(), entry)
    with pytest.raises(HistoryError):
        app.submit_query(AUTH, "r", "h", "q", "op", 0, reauthenticate=lambda: AUTH)
    assert entry.executions == 0
    assert store.finish_calls == 0


def test_successful_query_snapshot_keeps_the_exact_turn_question_for_requery():
    entry = QueryEntry()
    store = ScriptedStore()
    app = HistoryApplication(store, Runtime(), entry)

    app.submit_query(
        AUTH, "r", "h", "改看按产品毛利", "op", 0, reauthenticate=lambda: AUTH
    )

    assert store.finished_snapshot["source_question"] == "改看按产品毛利"


def test_finish_commit_unknown_never_reexecutes_or_retries_commit():
    entry = QueryEntry()
    store = ScriptedStore(
        finish_error=HistoryError("HISTORY_SAVE_UNCONFIRMED", "未确认", 503)
    )
    app = HistoryApplication(store, Runtime(), entry)
    with pytest.raises(HistoryError):
        app.submit_query(AUTH, "r", "h", "q", "op", 0, reauthenticate=lambda: AUTH)
    assert entry.executions == 1
    assert store.finish_calls == 1


def test_finish_busy_never_retries_as_a_failed_business_result():
    entry = QueryEntry()
    store = ScriptedStore(finish_error=HistoryError("HISTORY_BUSY", "仍在执行", 409))
    app = HistoryApplication(store, Runtime(), entry)

    with pytest.raises(HistoryError) as failure:
        app.submit_query(AUTH, "r", "h", "q", "op", 0, reauthenticate=lambda: AUTH)

    assert failure.value.code == "HISTORY_SAVE_UNCONFIRMED"
    assert entry.executions == 1
    assert store.finish_calls == 1


def test_changed_business_definition_rejects_before_revision_or_execution():
    state = query_state()
    entry = QueryEntry()
    store = ScriptedStore(base_state=state)
    app = HistoryApplication(
        store,
        Runtime(),
        entry,
        certifier=lambda semantic: {"provenance": {"changed": True}},
    )
    with pytest.raises(HistoryError) as incompatible:
        app.submit_query(
            AUTH, "r", "h", "改成毛利", "op", 1, reauthenticate=lambda: AUTH
        )
    assert incompatible.value.code == "HISTORY_CONTEXT_INCOMPATIBLE"
    assert entry.executions == 0 and store.finish_calls == 1


def test_current_retrieval_failure_is_not_reported_as_definition_change():
    def failed_certifier(semantic):
        raise RuntimeError("provider unavailable")

    entry = QueryEntry()
    app = HistoryApplication(
        ScriptedStore(base_state=query_state()),
        Runtime(),
        entry,
        certifier=failed_certifier,
    )
    with pytest.raises(HistoryError) as failure:
        app.submit_query(
            AUTH, "r", "h", "改成毛利", "op", 1, reauthenticate=lambda: AUTH
        )
    assert failure.value.code == "CONTEXT_ERROR" and entry.executions == 0


def test_completed_analysis_snapshot_reads_after_checkpoint_expiry_without_execution():
    from dataclasses import replace

    class CompletedStore(ScriptedStore):
        def header(self, owner, history_id):
            return replace(
                HEADER,
                kind="analysis",
                last_success_turn_id="t",
                analysis_recovery_available=False,
            )

        def turn(self, owner, history_id, turn_id):
            return TURN

    entry = QueryEntry()
    store = CompletedStore()
    result = HistoryApplication(store, Runtime(), entry).resume_analysis(
        AUTH, "r", "h", "op", 0, reauthenticate=lambda: AUTH
    )
    assert result == TURN and entry.executions == 0 and store.finish_calls == 0
