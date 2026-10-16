"""用存储故障seam验证Application不会误执行或推进未提交状态。"""

from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from src.authorization.contracts import AuthContext
from src.online_query.contracts import (
    ExecutionStopReason,
    ExecutionStopped,
    QueryErrorCode,
    QueryFailure,
    QuerySuccess,
)
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


def test_history_error_contract_has_no_http_status():
    error = HistoryError("HISTORY_BUSY", "正在执行")

    assert error.code == "HISTORY_BUSY"
    assert error.failure_kind is None
    assert not hasattr(error, "status")


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
        self.finished_error = None

    def header(self, owner, history_id):
        return HEADER

    def begin_attempt(self, *args, before_accept=None):
        if self.begin_error:
            raise self.begin_error
        if before_accept is not None:
            before_accept()
        return AcceptedAttempt(
            ExecutionToken("h", "t", "epoch", 1), TURN, self.base_state
        )

    def finish_attempt(self, *args):
        self.finish_calls += 1
        self.finished_snapshot = args[2]
        self.finished_error = args[3]
        if self.finish_error:
            raise self.finish_error
        if self.finished_error is not None:
            return replace(TURN, status="failed", public_error=self.finished_error)
        return TURN


class QueryEntry:
    def __init__(self):
        self.executions = 0
        self.execution_controls = []

    def authorize(self, request, *, auth_context):
        return None

    def execute_authorized(self, request, *, auth_context):
        self.executions += 1
        self.execution_controls.append(request.execution_control)
        return QuerySuccess(
            "r", "SELECT 1", ("n",), ((1,),), 1, False, restoration_state=query_state()
        )


def test_begin_storage_failure_never_executes_business_query():
    entry = QueryEntry()
    store = ScriptedStore(
        begin_error=HistoryError("HISTORY_STORAGE_UNAVAILABLE", "不可用")
    )
    app = HistoryApplication(store, Runtime(), entry)
    with pytest.raises(HistoryError):
        app.submit_query(AUTH, "r", "h", "q", "op", 0, reauthenticate=lambda: AUTH)
    assert entry.executions == 0
    assert store.finish_calls == 0


def test_new_compat_attempt_holds_shared_admission_until_execution_finishes():
    events = []
    control = SimpleNamespace(checkpoint=lambda: None)

    @contextmanager
    def admission(auth, request_id, *, seconds):
        assert auth == AUTH and request_id == "r"
        events.append(("admit", seconds))
        try:
            yield control
        finally:
            events.append(("release", seconds))

    class Entry(QueryEntry):
        def execute_authorized(self, request, *, auth_context):
            events.append(("execute", request.question))
            return super().execute_authorized(request, auth_context=auth_context)

    entry = Entry()
    app = HistoryApplication(ScriptedStore(), Runtime(), entry, admission=admission)
    app.submit_query(AUTH, "r", "h", "q", "op", 0, reauthenticate=lambda: AUTH)

    assert events == [("admit", 180), ("execute", "q"), ("release", 180)]
    assert entry.execution_controls == [control]


def test_idempotent_compat_replay_does_not_admit_or_execute_again():
    class ReplayStore(ScriptedStore):
        def begin_attempt(self, *args, before_accept=None):
            return AcceptedAttempt(None, replace(TURN, status="succeeded"), None)

    admissions = []

    @contextmanager
    def admission(*_args, seconds):
        admissions.append(seconds)
        yield SimpleNamespace(checkpoint=lambda: None)

    entry = QueryEntry()
    result = HistoryApplication(
        ReplayStore(), Runtime(), entry, admission=admission
    ).submit_query(AUTH, "r", "h", "q", "op", 0, reauthenticate=lambda: AUTH)

    assert result.status == "succeeded"
    assert admissions == []
    assert entry.executions == 0


def test_store_failure_after_admission_releases_shared_capacity():
    events = []

    @contextmanager
    def admission(*_args, seconds):
        events.append(("admit", seconds))
        try:
            yield SimpleNamespace(checkpoint=lambda: None)
        finally:
            events.append(("release", seconds))

    class FailingStore(ScriptedStore):
        def begin_attempt(self, *args, before_accept=None):
            before_accept()
            raise HistoryError("HISTORY_STORAGE_UNAVAILABLE", "存储失败")

    entry = QueryEntry()
    app = HistoryApplication(FailingStore(), Runtime(), entry, admission=admission)
    with pytest.raises(HistoryError):
        app.submit_query(AUTH, "r", "h", "q", "op", 0, reauthenticate=lambda: AUTH)

    assert events == [("admit", 180), ("release", 180)]
    assert entry.executions == 0


def test_compat_deadline_persists_a_query_timeout_instead_of_leaving_active_turn():
    class ExpiredControl:
        def checkpoint(self):
            raise ExecutionStopped(ExecutionStopReason.DEADLINE_EXCEEDED)

    @contextmanager
    def admission(*_args, seconds):
        assert seconds == 180
        yield ExpiredControl()

    store = ScriptedStore()
    app = HistoryApplication(store, Runtime(), QueryEntry(), admission=admission)
    result = app.submit_query(AUTH, "r", "h", "q", "op", 0, reauthenticate=lambda: AUTH)

    assert result.status == "failed"
    assert result.public_error["error_code"] == "QUERY_TIMEOUT"
    assert store.finish_calls == 1
    assert store.finished_error["error_code"] == "QUERY_TIMEOUT"


@pytest.mark.parametrize(
    ("source_kind", "resolved_kind", "expected_seconds"),
    [
        ("history", "query", 180),
        ("saved", "query", 180),
        ("saved", "analysis", 1200),
    ],
)
def test_requery_uses_the_resolved_kind_deadline_and_releases_after_store_failure(
    source_kind, resolved_kind, expected_seconds
):
    events = []

    @contextmanager
    def admission(_auth, _request_id, *, seconds):
        events.append(("admit", seconds))
        try:
            yield SimpleNamespace(checkpoint=lambda: None)
        finally:
            events.append(("release", seconds))

    class FailingRequeryStore(ScriptedStore):
        def begin_requery(self, *args, before_accept=None):
            before_accept(resolved_kind)
            raise HistoryError("HISTORY_STORAGE_UNAVAILABLE", "存储失败")

    with pytest.raises(HistoryError):
        HistoryApplication(
            FailingRequeryStore(), Runtime(), QueryEntry(), admission=admission
        ).requery(
            AUTH,
            "r",
            source_kind,
            "source",
            None,
            "op",
            reauthenticate=lambda: AUTH,
        )

    assert events == [
        ("admit", expected_seconds),
        ("release", expected_seconds),
    ]


def test_analysis_resume_uses_twelve_hundred_second_admission():
    events = []

    @contextmanager
    def admission(_auth, _request_id, *, seconds):
        events.append(("admit", seconds))
        try:
            yield SimpleNamespace(checkpoint=lambda: None)
        finally:
            events.append(("release", seconds))

    class FailingResumeStore(ScriptedStore):
        def header(self, owner, history_id):
            return replace(
                HEADER,
                kind="analysis",
                last_success_turn_id=None,
                analysis_recovery_available=True,
            )

        def begin_analysis_attempt(self, *args, before_accept=None):
            before_accept("analysis")
            raise HistoryError("HISTORY_STORAGE_UNAVAILABLE", "存储失败")

    with pytest.raises(HistoryError):
        HistoryApplication(
            FailingResumeStore(), Runtime(), QueryEntry(), admission=admission
        ).resume_analysis(AUTH, "r", "h", "op", 0, reauthenticate=lambda: AUTH)

    assert events == [("admit", 1200), ("release", 1200)]


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
        finish_error=HistoryError("HISTORY_SAVE_UNCONFIRMED", "未确认")
    )
    app = HistoryApplication(store, Runtime(), entry)
    with pytest.raises(HistoryError):
        app.submit_query(AUTH, "r", "h", "q", "op", 0, reauthenticate=lambda: AUTH)
    assert entry.executions == 1
    assert store.finish_calls == 1


def test_finish_busy_never_retries_as_a_failed_business_result():
    entry = QueryEntry()
    store = ScriptedStore(finish_error=HistoryError("HISTORY_BUSY", "仍在执行"))
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


def test_history_passes_report_stream_port_only_for_a_capable_r4_observer():
    class AnalysisService:
        def __init__(self):
            self.options = None

        def analyze(self, question, **options):
            self.options = options
            return QueryFailure("r", QueryErrorCode.CANNOT_ANSWER, "no result")

    class ProgressAndDraftObserver:
        def set_stage(self, stage):
            pass

        def set_task_progress(self, completed, total):
            pass

        def text_delta(self, field, index, offset, text):
            pass

        def reset(self, reason):
            pass

    service = AnalysisService()
    store = ScriptedStore()
    app = HistoryApplication(store, Runtime(), QueryEntry(), analysis_service=service)
    observer = ProgressAndDraftObserver()

    app._execute_attempt(
        AUTH,
        "r",
        "h",
        "分析毛利",
        store.begin_attempt(),
        reauthenticate=lambda: AUTH,
        kind="analysis",
        analysis_run_id="analysis-run",
        progress_observer=observer,
    )

    assert service.options["progress_observer"] is observer
    assert service.options["report_observer"] is observer
