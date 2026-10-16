"""真实PG验证短事务、隔离、幂等与停止后重启的迟到提交拒绝。"""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from time import monotonic
from typing import TypedDict
from uuid import UUID, uuid4

import psycopg
import pytest
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from sqlalchemy import event, text

from src.business_analysis.application import BusinessAnalysisSuccess
from src.business_analysis.execution import TaskResult, TaskStatus
from src.business_analysis.reporting import BusinessAnalysisReport
from src.business_analysis.run_store import (
    AnalysisRunConflict,
    PostgresAnalysisRunStore,
)
from src.chatbi_control.database import ControlDatabaseConfig, create_control_engine
from src.chatbi_control.history import PostgresHistoryStore
from src.online_query.contracts import QuerySuccess
from src.query_api.history_codec import encode_snapshot
from src.query_api.history_contracts import HistoryError
from src.query_api.history_runtime import HistoryRuntime
from src.query_api.query_response import analysis_payload, query_payload
from tests.query_api.history_fixtures import query_state


class _CheckpointState(TypedDict):
    value: int


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DEVELOPMENT_DATABASE_TESTS") != "1",
    reason="需要隔离的development PostgreSQL",
)


@pytest.fixture
def history_env():
    config = ControlDatabaseConfig.from_environment()
    engine = create_control_engine(config)
    with engine.begin() as connection:
        owner = connection.execute(
            text(
                "INSERT INTO users(username,password_hash) VALUES (:name,'disabled-test-account') RETURNING id"
            ),
            {"name": "history-test-" + str(uuid4())},
        ).scalar_one()
    runtime = HistoryRuntime(engine, config.app_connection_kwargs())
    try:
        yield engine, PostgresHistoryStore(engine), runtime, owner, config
    finally:
        runtime.close()
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE history_records SET active_turn_id=NULL,last_success_turn_id=NULL WHERE owner_user_id=:owner"
                ),
                {"owner": owner},
            )
            connection.execute(
                text(
                    "DELETE FROM history_turns WHERE history_id IN (SELECT id FROM history_records WHERE owner_user_id=:owner)"
                ),
                {"owner": owner},
            )
            connection.execute(
                text("DELETE FROM saved_results WHERE owner_user_id=:owner"),
                {"owner": owner},
            )
            connection.execute(
                text("DELETE FROM history_records WHERE owner_user_id=:owner"),
                {"owner": owner},
            )
        with psycopg.connect(**config.migrator_connection_kwargs()) as connection:
            connection.execute("DELETE FROM users WHERE id=%s", (owner,))
        engine.dispose()


def begin(
    store,
    runtime,
    owner,
    history_id,
    revision=0,
    operation=None,
    question="人民币净销售额",
    before_accept=None,
):
    return store.begin_attempt(
        owner,
        history_id,
        question,
        operation or str(uuid4()),
        revision,
        "history-test",
        runtime.epoch,
        before_accept=before_accept,
    )


def test_success_failure_and_duplicate_are_durable(history_env):
    _engine, store, runtime, owner, _ = history_env
    creation = str(uuid4())
    header = store.create(owner, "query", "人民币净销售额", creation)
    assert store.create(owner, "query", "人民币净销售额", creation).id == header.id
    operation = str(uuid4())
    admitted = []
    accepted = begin(
        store,
        runtime,
        owner,
        header.id,
        operation=operation,
        before_accept=lambda kind: admitted.append(kind),
    )
    assert admitted == ["query"]
    with pytest.raises(HistoryError, match="正在执行"):
        begin(store, runtime, owner, header.id)
    snapshot = encode_snapshot(
        "query",
        query_payload(QuerySuccess("r", "SELECT 12", ("n",), (("12.50",),), 1, False)),
        query_state=query_state(),
        source_question="人民币净销售额",
    )
    success = store.finish_attempt(owner, accepted.token, snapshot, None)
    assert success.status == "succeeded"
    assert store.header(owner, header.id).context_revision == 1
    duplicate = begin(
        store,
        runtime,
        owner,
        header.id,
        operation=operation,
        before_accept=lambda _kind: pytest.fail("幂等重放不能重新准入"),
    )
    assert duplicate.token is None and duplicate.turn.id == success.id
    with pytest.raises(HistoryError, match="请刷新"):
        begin(store, runtime, owner, header.id)
    second_operation = str(uuid4())
    second = begin(
        store,
        runtime,
        owner,
        header.id,
        revision=1,
        operation=second_operation,
    )
    assert second.base_state == snapshot["query_state"]
    store.finish_attempt(owner, second.token, None, {"error_code": "LLM_ERROR"})
    current = store.header(owner, header.id)
    assert current.context_revision == 1 and current.last_success_turn_id == success.id
    assert store.turn(owner, header.id, success.id).snapshot == snapshot
    failed_replay = begin(
        store,
        runtime,
        owner,
        header.id,
        revision=1,
        operation=second_operation,
        before_accept=lambda _kind: pytest.fail("失败重放不能重新准入"),
    )
    assert failed_replay.token is None
    with pytest.raises(HistoryError) as cross_owner:
        store.header(owner + 100000, header.id)
    assert cross_owner.value.code == "HISTORY_UNAVAILABLE"


def test_rejected_admission_rolls_back_before_creating_history_attempt(history_env):
    engine, store, runtime, owner, _ = history_env
    header = store.create(owner, "query", "销售额", str(uuid4()))
    operation = str(uuid4())

    def reject(_kind):
        raise HistoryError("SERVICE_NOT_READY", "服务未就绪")

    with pytest.raises(HistoryError) as rejected:
        begin(
            store,
            runtime,
            owner,
            header.id,
            operation=operation,
            before_accept=reject,
        )

    assert rejected.value.code == "SERVICE_NOT_READY"
    assert store.header(owner, header.id).active_turn_id is None
    with engine.connect() as connection:
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM history_turns WHERE history_id=:history AND operation_id=:operation"
                ),
                {"history": header.id, "operation": operation},
            ).scalar_one()
            == 0
        )


def test_restart_fences_old_token_and_retains_success(history_env):
    engine, store, runtime, owner, config = history_env
    header = store.create(owner, "query", "人民币净销售额", str(uuid4()))
    old = begin(store, runtime, owner, header.id)
    runtime.close()
    restarted = HistoryRuntime(engine, config.app_connection_kwargs())
    try:
        assert store.turn(owner, header.id, old.turn.id).status == "unconfirmed"
        assert store.header(owner, header.id).active_turn_id is None
        new = begin(store, restarted, owner, header.id)
        with pytest.raises(HistoryError) as late:
            store.finish_attempt(owner, old.token, {"version": 1}, None)
        assert late.value.code == "HISTORY_SAVE_UNCONFIRMED"
        assert store.header(owner, header.id).active_turn_id == new.turn.id
        store.finish_attempt(owner, new.token, None, {"error_code": "LLM_ERROR"})
    finally:
        restarted.close()


def test_finish_waits_behind_short_history_management_lock(history_env):
    engine, store, runtime, owner, config = history_env
    header = store.create(owner, "query", "人民币净销售额", str(uuid4()))
    accepted = begin(store, runtime, owner, header.id)
    snapshot = encode_snapshot(
        "query",
        query_payload(QuerySuccess("r", "SELECT 12", ("n",), ((12,),), 1, False)),
        query_state=query_state(),
        source_question="人民币净销售额",
    )

    worker_engine = create_control_engine(config)
    worker_application_name = "chatbi-history-lock-" + uuid4().hex[:16]
    worker_pid = {}
    worker_connection_ready = Event()

    def configure_worker_connection(dbapi_connection, _record):
        with dbapi_connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('application_name', %s, false)",
                (worker_application_name,),
            )
            cursor.execute(
                "SELECT set_config('statement_timeout', %s, false)", ("15000ms",)
            )
        dbapi_connection.commit()

    def capture_worker_backend(dbapi_connection, _record, _proxy):
        worker_pid["pid"] = dbapi_connection.info.backend_pid
        worker_connection_ready.set()

    event.listen(worker_engine, "connect", configure_worker_connection)
    event.listen(worker_engine, "checkout", capture_worker_backend)
    worker_store = PostgresHistoryStore(worker_engine)

    def finish():
        if os.environ.get("CHATBI_HISTORY_LOCK_TEST_INJECT_WORKER_ERROR") == "1":
            raise RuntimeError("injected history worker failure")
        if os.environ.get("CHATBI_HISTORY_LOCK_TEST_INJECT_WORKER_TIMEOUT") == "1":
            with worker_engine.begin() as connection:
                connection.execute(text("SELECT pg_sleep(30)"))
        return worker_store.finish_attempt(owner, accepted.token, snapshot, None)

    def cancel_worker_backend():
        pid = worker_pid.get("pid")
        if pid is None:
            return
        with engine.begin() as canceller:
            canceller.execute(text("SET LOCAL statement_timeout = '1s'"))
            canceller.execute(
                text("""SELECT pg_cancel_backend(pid)
                    FROM pg_stat_activity
                    WHERE pid=:pid AND datname=current_database()
                      AND application_name=:application_name"""),
                {"pid": pid, "application_name": worker_application_name},
            ).scalar_one_or_none()

    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="history-lock-test")
    lock_connection = None
    lock_transaction = None
    future = None
    failure = None
    cleanup_errors = []
    try:
        lock_connection = engine.connect()
        lock_transaction = lock_connection.begin()
        lock_connection.execute(
            text("SELECT id FROM history_records WHERE id=:id FOR UPDATE"),
            {"id": header.id},
        )
        future = pool.submit(finish)
        ready_deadline = monotonic() + 5
        while not worker_connection_ready.is_set():
            if future.done():
                future.result()
                raise AssertionError(
                    "finish worker exited before acquiring its connection"
                )
            remaining = ready_deadline - monotonic()
            if remaining <= 0:
                raise AssertionError(
                    "finish worker connection was not observed within 5s"
                )
            worker_connection_ready.wait(min(remaining, 0.01))

        deadline = monotonic() + 5
        blocked = False
        with engine.begin() as observer:
            observer.execute(text("SET LOCAL statement_timeout = '1s'"))
            if os.environ.get("CHATBI_HISTORY_LOCK_TEST_FORCE_PROBE_FAILURE") != "1":
                while monotonic() < deadline:
                    if future.done():
                        future.result()
                        break
                    blocked = observer.execute(
                        text("""SELECT EXISTS (
                            SELECT 1 FROM pg_stat_activity
                            WHERE pid=:pid AND datname=current_database()
                              AND application_name=:application_name
                              AND wait_event_type='Lock'
                              AND query ILIKE '%history_records%'
                        )"""),
                        {
                            "pid": worker_pid["pid"],
                            "application_name": worker_application_name,
                        },
                    ).scalar_one()
                    if blocked:
                        break
                    Event().wait(0.01)
        assert blocked, "finish should wait on the short management transaction"
        lock_transaction.commit()
        assert future.result(timeout=5).status == "succeeded"
    except Exception as error:  # noqa: BLE001 - preserve assertion/worker error through cleanup
        failure = error
    finally:
        # Always release our lock before asking the worker thread to join.
        try:
            if lock_transaction is not None and lock_transaction.is_active:
                lock_transaction.rollback()
        except Exception as error:  # noqa: BLE001 - try every owned-resource cleanup
            cleanup_errors.append(f"释放测试锁失败：{error!r}")
        if lock_connection is not None:
            try:
                lock_connection.close()
            except Exception as error:  # noqa: BLE001 - try every owned-resource cleanup
                cleanup_errors.append(f"关闭锁连接失败：{error!r}")

        if future is not None:
            if not future.done():
                try:
                    future.result(timeout=5)
                except FutureTimeoutError as error:
                    if future.done():
                        if failure is None:
                            failure = error
                        elif failure is not error:
                            cleanup_errors.append(f"worker 退出异常：{error!r}")
                    else:
                        if failure is None:
                            failure = error
                        else:
                            cleanup_errors.append(f"worker 清理等待超过 5s：{error!r}")
                        try:
                            cancel_worker_backend()
                        except Exception as cancel_error:  # noqa: BLE001 - retain primary error
                            cleanup_errors.append(
                                f"取消本测试 worker 失败：{cancel_error!r}"
                            )
                        try:
                            future.result(timeout=5)
                        except FutureTimeoutError as wait_error:
                            if future.done():
                                if failure is None:
                                    failure = wait_error
                                elif failure is not wait_error:
                                    cleanup_errors.append(
                                        f"worker 退出异常：{wait_error!r}"
                                    )
                            else:
                                cleanup_errors.append(
                                    f"取消后 worker 仍未在 5s 内退出：{wait_error!r}"
                                )
                        except Exception as worker_error:  # noqa: BLE001 - retain primary error
                            if failure is None:
                                failure = worker_error
                            elif failure is not worker_error:
                                cleanup_errors.append(
                                    f"worker 退出异常：{worker_error!r}"
                                )
                except Exception as worker_error:  # noqa: BLE001 - retain primary error
                    if failure is None:
                        failure = worker_error
                    elif failure is not worker_error:
                        cleanup_errors.append(f"worker 退出异常：{worker_error!r}")
            else:
                try:
                    future.result()
                except Exception as worker_error:  # noqa: BLE001 - retain primary error
                    if failure is None:
                        failure = worker_error
                    elif failure is not worker_error:
                        cleanup_errors.append(f"worker 退出异常：{worker_error!r}")

        try:
            pool.shutdown(wait=True, cancel_futures=True)
        except Exception as error:  # noqa: BLE001 - retain primary error
            cleanup_errors.append(f"线程池关闭失败：{error!r}")
        try:
            worker_engine.dispose()
        except Exception as error:  # noqa: BLE001 - retain primary error
            cleanup_errors.append(f"worker engine 清理失败：{error!r}")

    if failure is not None:
        for cleanup_error in cleanup_errors:
            failure.add_note(cleanup_error)
        raise failure
    assert not cleanup_errors, "; ".join(cleanup_errors)


@pytest.mark.parametrize(
    "injection,expected_diagnostic",
    [
        (
            "CHATBI_HISTORY_LOCK_TEST_FORCE_PROBE_FAILURE",
            "finish should wait on the short management transaction",
        ),
        (
            "CHATBI_HISTORY_LOCK_TEST_INJECT_WORKER_ERROR",
            "injected history worker failure",
        ),
        (
            "CHATBI_HISTORY_LOCK_TEST_INJECT_WORKER_TIMEOUT",
            "finish should wait on the short management transaction",
        ),
    ],
)
def test_lock_wait_failures_exit_bounded_and_release_owned_sessions(
    injection, expected_diagnostic
):
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        f"{Path(__file__).resolve()}::test_finish_waits_behind_short_history_management_lock",
    ]
    environment = os.environ.copy()
    environment.pop("CHATBI_HISTORY_LOCK_TEST_FORCE_PROBE_FAILURE", None)
    environment.pop("CHATBI_HISTORY_LOCK_TEST_INJECT_WORKER_ERROR", None)
    environment.pop("CHATBI_HISTORY_LOCK_TEST_INJECT_WORKER_TIMEOUT", None)
    environment[injection] = "1"
    try:
        result = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[2],
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        pytest.fail(f"锁等待失败路径未能在20秒内退出：{error}")
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert expected_diagnostic in output

    config = ControlDatabaseConfig.from_environment()
    engine = create_control_engine(config)
    try:
        with engine.connect() as connection:
            leaked = connection.execute(
                text("""SELECT EXISTS (
                    SELECT 1 FROM pg_stat_activity
                    WHERE datname=current_database()
                      AND application_name LIKE 'chatbi-history-lock-%'
                )""")
            ).scalar_one()
        assert not leaked, "失败子测试遗留了自己的 worker 数据库连接"
    finally:
        engine.dispose()


def test_single_process_guard_refuses_second_owner(history_env):
    engine, _, _, _, config = history_env
    with pytest.raises(RuntimeError, match="单API进程"):
        HistoryRuntime(engine, config.app_connection_kwargs())


def test_requery_copies_source_in_acceptance_transaction_and_is_idempotent(history_env):
    engine, store, runtime, owner, _ = history_env
    source = store.create(owner, "query", "销售额总额", str(uuid4()))
    accepted = begin(store, runtime, owner, source.id, question="改看按产品毛利")
    snapshot = encode_snapshot(
        "query",
        query_payload(QuerySuccess("r", "SELECT 12", ("n",), (("12.50",),), 1, False)),
        query_state=query_state(),
        source_question=accepted.turn.question,
    )
    source_turn = store.finish_attempt(owner, accepted.token, snapshot, None)
    operation = str(uuid4())
    admitted = []
    header, requery = store.begin_requery(
        owner,
        "history",
        source.id,
        source_turn.id,
        operation,
        "r",
        runtime.epoch,
        str(uuid4()),
        before_accept=lambda kind: admitted.append(kind),
    )
    assert admitted == ["query"]
    assert header.first_question == "改看按产品毛利"
    assert requery.turn.question == "改看按产品毛利"
    assert (
        header.id != source.id
        and header.context_revision == 0
        and header.last_success_turn_id is None
    )
    assert requery.base_state == snapshot["query_state"]
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT attempt_input FROM history_turns WHERE id=:id"),
                {"id": requery.turn.id},
            ).scalar_one()
            == snapshot
        )
    finished = store.finish_attempt(owner, requery.token, snapshot, None)
    same_header, duplicate = store.begin_requery(
        owner,
        "history",
        source.id,
        source_turn.id,
        operation,
        "r2",
        runtime.epoch,
        str(uuid4()),
        before_accept=lambda _kind: pytest.fail("幂等重放不能重新准入"),
    )
    assert (
        same_header.id == header.id
        and duplicate.token is None
        and duplicate.turn.id == finished.id
    )
    assert store.turn(owner, source.id, source_turn.id).snapshot == snapshot


def test_rejected_requery_admission_rolls_back_new_history(history_env):
    engine, store, runtime, owner, _ = history_env
    source = store.create(owner, "analysis", "经营分析", str(uuid4()))
    operation = str(uuid4())
    new_id = str(uuid4())

    def reject(kind):
        assert kind == "analysis"
        raise HistoryError("EXECUTION_LIMIT_REACHED", "额度已满")

    with pytest.raises(HistoryError) as rejected:
        store.begin_requery(
            owner,
            "history",
            source.id,
            None,
            operation,
            "request",
            runtime.epoch,
            new_id,
            before_accept=reject,
        )

    assert rejected.value.code == "EXECUTION_LIMIT_REACHED"
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM history_records WHERE id=:id"),
                {"id": new_id},
            ).scalar_one()
            == 0
        )


def committed_query(store, runtime, owner, title="销售额"):
    header = store.create(owner, "query", title, str(uuid4()))
    accepted = begin(store, runtime, owner, header.id, question=title)
    snapshot = encode_snapshot(
        "query",
        query_payload(QuerySuccess("r", "SELECT 12", ("n",), (("12.50",),), 1, False)),
        query_state=query_state(),
        source_question=title,
    )
    turn = store.finish_attempt(owner, accepted.token, snapshot, None)
    return store.header(owner, header.id), turn, snapshot


def test_invalid_nested_analysis_snapshot_is_rejected_by_copy_and_export(history_env):
    engine, store, runtime, owner, _ = history_env
    question = "毛利分析"
    header = store.create(owner, "analysis", question, str(uuid4()))
    accepted = store.begin_analysis_attempt(
        owner, header.id, str(uuid4()), 0, "analysis-request", runtime.epoch
    )
    report = BusinessAnalysisReport(
        title="毛利变化",
        executive_summary="毛利增加。",
        key_findings=("毛利增加。",),
        trend_judgment="毛利增加。",
        root_causes=(),
        action_suggestions=(),
        evidence_task_ids=("trend",),
        incomplete_tasks=(),
    )
    result = BusinessAnalysisSuccess(
        request_id="analysis-request",
        report=report,
        task_results=(
            TaskResult(
                "trend",
                TaskStatus.COMPLETED,
                columns=("product",),
                rows=(("A",),),
                row_count=1,
            ),
        ),
        analysis_run_id=header.analysis_run_id,
    )
    snapshot = encode_snapshot(
        "analysis",
        analysis_payload(result, header.analysis_run_id),
        original_question=question,
    )
    turn = store.finish_attempt(owner, accepted.token, snapshot, None)
    canary = "POSTGRES_NESTED_SQL_CANARY"
    snapshot["result"]["task_results"][0]["sql"] = canary
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE history_turns SET snapshot=CAST(:snapshot AS jsonb) "
                "WHERE history_id=:history_id AND id=:turn_id"
            ),
            {
                "snapshot": json.dumps(snapshot, ensure_ascii=False),
                "history_id": header.id,
                "turn_id": turn.id,
            },
        )

    with pytest.raises(HistoryError) as copy_failure:
        store.copy_result(owner, header.id, turn.id, "非法旧快照")
    with pytest.raises(HistoryError) as export_failure:
        store.export_snapshot(owner, "history_turn", header.id, turn.id)

    assert copy_failure.value.code == "HISTORY_SNAPSHOT_UNAVAILABLE"
    assert export_failure.value.code == "HISTORY_SNAPSHOT_UNAVAILABLE"
    assert canary not in str(copy_failure.value)
    assert canary not in str(export_failure.value)
    with engine.connect() as connection:
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM saved_results "
                    "WHERE owner_user_id=:owner AND source_turn_id=:turn_id"
                ),
                {"owner": owner, "turn_id": turn.id},
            ).scalar_one()
            == 0
        )


def test_saved_copy_survives_source_deletion_and_stale_delete_is_rejected(history_env):
    _engine, store, runtime, owner, _ = history_env
    header, turn, snapshot = committed_query(store, runtime, owner)
    active = begin(store, runtime, owner, header.id, revision=1)
    saved = store.copy_result(owner, header.id, turn.id, "独立成果")
    with pytest.raises(HistoryError) as blocked:
        store.delete_history(owner, header.id, header.record_revision, "local:test")
    assert blocked.value.code == "HISTORY_BUSY"
    store.finish_attempt(owner, active.token, None, {"error_code": "LLM_ERROR"})
    current = store.header(owner, header.id)
    with pytest.raises(HistoryError) as stale:
        store.delete_history(owner, header.id, header.record_revision, "local:test")
    assert stale.value.code == "HISTORY_STALE"
    store.delete_history(owner, header.id, current.record_revision, "local:test")
    with pytest.raises(HistoryError) as missing:
        store.turn(owner, header.id, turn.id)
    assert missing.value.code == "HISTORY_UNAVAILABLE"
    assert store.saved_result(owner, saved.id)[1] == snapshot
    renamed = store.rename_saved_result(
        owner, saved.id, "新名称", saved.record_revision
    )
    assert store.saved_result(owner, saved.id)[1] == snapshot
    copy_query, accepted = store.begin_requery(
        owner,
        "saved",
        saved.id,
        None,
        str(uuid4()),
        "requery-saved",
        runtime.epoch,
        str(uuid4()),
    )
    assert copy_query.id != header.id
    assert copy_query.title == "新名称"
    assert copy_query.first_question == snapshot["source_question"]
    assert accepted.turn.question == snapshot["source_question"]
    assert accepted.base_state == snapshot["query_state"]
    store.finish_attempt(
        owner, accepted.token, None, {"error_code": "HISTORY_CONTEXT_INCOMPATIBLE"}
    )
    store.delete_saved_result(owner, saved.id, renamed.record_revision)
    with pytest.raises(HistoryError):
        store.saved_result(owner, saved.id)


def test_legacy_saved_query_without_source_question_uses_neutral_requery_text(
    history_env,
):
    engine, store, runtime, owner, _ = history_env
    header, turn, snapshot = committed_query(store, runtime, owner, "原始完整问题")
    legacy = dict(snapshot)
    legacy.pop("source_question")
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE history_turns SET snapshot=CAST(:snapshot AS jsonb) WHERE id=:id"
            ),
            {
                "snapshot": json.dumps(legacy, ensure_ascii=False),
                "id": turn.id,
            },
        )
    saved = store.copy_result(owner, header.id, turn.id, "已重命名的成果")
    store.delete_history(owner, header.id, header.record_revision, "local:test")

    requery, accepted = store.begin_requery(
        owner,
        "saved",
        saved.id,
        None,
        str(uuid4()),
        "legacy-requery",
        runtime.epoch,
        str(uuid4()),
    )

    assert requery.first_question == "根据已保存的完整查询条件重新查询"
    assert accepted.turn.question == requery.first_question
    assert accepted.base_state == snapshot["query_state"]
    store.finish_attempt(
        owner, accepted.token, None, {"error_code": "HISTORY_CONTEXT_INCOMPATIBLE"}
    )


def test_saved_deletion_does_not_change_source_or_other_owner_visibility(history_env):
    _engine, store, runtime, owner, _ = history_env
    header, turn, snapshot = committed_query(store, runtime, owner)
    saved = store.copy_result(owner, header.id, turn.id, "成果")
    with pytest.raises(HistoryError) as cross:
        store.saved_result(owner + 100000, saved.id)
    assert cross.value.code == "HISTORY_UNAVAILABLE"
    store.delete_saved_result(owner, saved.id, saved.record_revision)
    assert store.turn(owner, header.id, turn.id).snapshot == snapshot
    assert store.header(owner, header.id).context_revision == 1


def test_literal_search_keyset_and_lazy_turn_summary(history_env):
    _engine, store, runtime, owner, _ = history_env
    first, _, _ = committed_query(store, runtime, owner, "含%_字面标题")
    second, _, _ = committed_query(store, runtime, owner, "普通标题")
    matched, _ = store.list_histories(owner, "query", 20, None, "%_")
    assert [h.id for h in matched] == [first.id]
    page, cursor = store.list_histories(owner, "query", 1, None)
    assert page[0].id == second.id and cursor is not None
    tail, final = store.list_histories(owner, "query", 1, cursor)
    assert tail[0].id == first.id and final is None
    with pytest.raises(HistoryError) as invalid:
        store.list_histories(owner, "analysis", 1, cursor)
    assert invalid.value.code == "INVALID_REQUEST"
    summaries, _ = store.turns(owner, first.id, 20, 0)
    assert summaries[0].status == "succeeded" and summaries[0].snapshot is None


def test_analysis_delete_atomically_expires_original_run(history_env):
    engine, store, _runtime, owner, _ = history_env
    header = store.create(owner, "analysis", "两期经营分析", str(uuid4()))
    store.delete_history(owner, header.id, header.record_revision, "local:test-owner")
    from uuid import UUID

    from src.business_analysis.run_store import (
        AnalysisRunConflict,
        PostgresAnalysisRunStore,
    )

    with pytest.raises(AnalysisRunConflict, match="EXPIRED"):
        PostgresAnalysisRunStore(engine).claim(
            UUID(header.analysis_run_id),
            owner_subject="local:test-owner",
            question="两期经营分析",
        )


def test_expired_analysis_checkpoints_are_cleaned_atomically(history_env):
    engine, store, runtime, owner, config = history_env
    run_store = PostgresAnalysisRunStore(engine)
    base_time = datetime.now(UTC)
    cleanup_time = base_time + timedelta(days=2)
    deleted_header = store.create(owner, "analysis", "已删除分析", str(uuid4()))
    deleted_run_id = deleted_header.analysis_run_id
    legacy_run_id = uuid4()
    rollback_run_id = uuid4()
    active_run_id = uuid4()
    run_ids = (
        deleted_run_id,
        str(legacy_run_id),
        str(rollback_run_id),
        str(active_run_id),
    )
    pool = ConnectionPool(
        make_conninfo(**config.app_connection_kwargs()),
        kwargs={"autocommit": True, "row_factory": dict_row},
        min_size=1,
        max_size=2,
        open=True,
    )

    def checkpoint(run_id, question):
        run_store.claim(
            UUID(run_id),
            owner_subject="local:test-owner",
            question=question,
            now=base_time,
        )
        graph.invoke(
            {"value": 1},
            config={"configurable": {"thread_id": run_id}},
        )

    def checkpoint_counts(run_id):
        with engine.connect() as connection:
            return tuple(
                connection.execute(
                    text(f"SELECT count(*) FROM {table} WHERE thread_id=:run_id"),
                    {"run_id": run_id},
                ).scalar_one()
                for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes")
            )

    def run_metadata(run_id):
        with engine.connect() as connection:
            return connection.execute(
                text(
                    """SELECT status, expires_at, updated_at
                       FROM business_analysis_runs WHERE analysis_run_id=:run_id"""
                ),
                {"run_id": run_id},
            ).one()

    saver = PostgresSaver(pool)
    builder = StateGraph(_CheckpointState)
    builder.add_node("save", lambda state: {"value": state["value"] + 1})
    builder.add_edge(START, "save")
    builder.add_edge("save", END)
    graph = builder.compile(checkpointer=saver)

    try:
        checkpoint(deleted_run_id, "已删除分析")
        store.delete_history(
            owner,
            deleted_header.id,
            deleted_header.record_revision,
            "local:test-owner",
        )

        checkpoint(str(legacy_run_id), "遗留过期分析")
        checkpoint(str(rollback_run_id), "清理回滚分析")
        checkpoint(str(active_run_id), "仍有效分析")
        with engine.begin() as connection:
            connection.execute(
                text(
                    """UPDATE business_analysis_runs
                       SET status='expired', expires_at=:expired
                       WHERE analysis_run_id=:run_id"""
                ),
                {"expired": base_time - timedelta(seconds=1), "run_id": legacy_run_id},
            )
            connection.execute(
                text(
                    """UPDATE business_analysis_runs
                       SET expires_at=:expired
                       WHERE analysis_run_id=:run_id"""
                ),
                {
                    "expired": base_time - timedelta(seconds=1),
                    "run_id": rollback_run_id,
                },
            )
            connection.execute(
                text(
                    """UPDATE business_analysis_runs
                       SET expires_at=:expires
                       WHERE analysis_run_id=:run_id"""
                ),
                {
                    "expires": base_time + timedelta(days=10),
                    "run_id": active_run_id,
                },
            )

        query_header, query_turn, _snapshot = committed_query(
            store, runtime, owner, "需独立保留的结果"
        )
        saved = store.copy_result(owner, query_header.id, query_turn.id, "独立结果")
        before = {run_id: checkpoint_counts(run_id) for run_id in run_ids}
        metadata_before = {run_id: run_metadata(run_id) for run_id in run_ids}
        assert all(all(count > 0 for count in counts) for counts in before.values())

        def fail_blob_delete(
            _connection, _cursor, statement, _parameters, _context, _many
        ):
            if statement.lstrip().upper().startswith("DELETE FROM CHECKPOINT_BLOBS"):
                raise RuntimeError("injected checkpoint cleanup failure")

        event.listen(engine, "before_cursor_execute", fail_blob_delete)
        try:
            with pytest.raises(
                RuntimeError, match="injected checkpoint cleanup failure"
            ):
                run_store.cleanup_expired(now=cleanup_time)
        finally:
            event.remove(engine, "before_cursor_execute", fail_blob_delete)

        assert {run_id: checkpoint_counts(run_id) for run_id in run_ids} == before
        assert {run_id: run_metadata(run_id) for run_id in run_ids} == metadata_before

        assert run_store.cleanup_expired(now=cleanup_time) >= 3
        assert all(checkpoint_counts(run_id) == (0, 0, 0) for run_id in run_ids[:3])
        assert checkpoint_counts(str(active_run_id)) == before[str(active_run_id)]
        assert run_store.cleanup_expired(now=cleanup_time) == 0
        with pytest.raises(AnalysisRunConflict, match="EXPIRED"):
            run_store.claim(
                UUID(deleted_run_id),
                owner_subject="local:test-owner",
                question="已删除分析",
                now=cleanup_time,
            )
        with pytest.raises(AnalysisRunConflict, match="EXPIRED"):
            run_store.claim(
                legacy_run_id,
                owner_subject="local:test-owner",
                question="遗留过期分析",
                now=cleanup_time,
            )
        assert (
            run_store.claim(
                active_run_id,
                owner_subject="local:test-owner",
                question="仍有效分析",
                now=cleanup_time,
            ).status
            == "active"
        )
        assert store.saved_result(owner, saved.id)[1] == _snapshot
    finally:
        pool.close()
        with engine.begin() as connection:
            for run_id in run_ids:
                for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                    connection.execute(
                        text(f"DELETE FROM {table} WHERE thread_id=:run_id"),
                        {"run_id": run_id},
                    )
        with psycopg.connect(**config.migrator_connection_kwargs()) as connection:
            for run_id in run_ids:
                connection.execute(
                    "DELETE FROM business_analysis_runs WHERE analysis_run_id=%s",
                    (run_id,),
                )


def test_finish_transaction_failure_never_advances_context(history_env):
    _engine, store, runtime, owner, config = history_env
    h = store.create(owner, "query", "销售额", str(uuid4()))
    accepted = begin(store, runtime, owner, h.id)
    trigger = "history_test_" + uuid4().hex
    from psycopg import sql

    with psycopg.connect(**config.migrator_connection_kwargs()) as admin:
        admin.execute(
            sql.SQL(
                "CREATE FUNCTION {}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.owner_user_id={} AND NEW.context_revision>OLD.context_revision THEN RAISE EXCEPTION 'injected transaction rollback'; END IF; RETURN NEW; END $$"
            ).format(sql.Identifier(trigger), sql.Literal(owner))
        )
        admin.execute(
            sql.SQL(
                "CREATE TRIGGER {} BEFORE UPDATE ON history_records FOR EACH ROW EXECUTE FUNCTION {}()"
            ).format(sql.Identifier(trigger), sql.Identifier(trigger))
        )
    try:
        with pytest.raises(HistoryError) as rollback:
            store.finish_attempt(owner, accepted.token, {"version": 1}, None)
        assert rollback.value.code == "HISTORY_STORAGE_UNAVAILABLE"
        current = store.header(owner, h.id)
        assert current.context_revision == 0 and current.last_success_turn_id is None
        assert store.turn(owner, h.id, accepted.turn.id).status == "accepted"
    finally:
        with psycopg.connect(**config.migrator_connection_kwargs()) as admin:
            admin.execute(
                sql.SQL("DROP TRIGGER {} ON history_records").format(
                    sql.Identifier(trigger)
                )
            )
            admin.execute(sql.SQL("DROP FUNCTION {}()").format(sql.Identifier(trigger)))
    runtime.reconcile(h.id)
    assert store.turn(owner, h.id, accepted.turn.id).status == "unconfirmed"


def test_missing_runtime_permission_rejects_startup_without_losing_data(history_env):
    from src.chatbi_control.database import (
        ControlDatabaseMigrationError,
        verify_control_schema,
    )

    engine, store, runtime, owner, config = history_env
    h, turn, snapshot = committed_query(store, runtime, owner)
    from psycopg import sql

    with psycopg.connect(**config.migrator_connection_kwargs()) as admin:
        admin.execute(
            sql.SQL("REVOKE UPDATE ON history_turns FROM {}").format(
                sql.Identifier(config.app_user)
            )
        )
    try:
        with pytest.raises(ControlDatabaseMigrationError):
            verify_control_schema(engine)
    finally:
        with psycopg.connect(**config.migrator_connection_kwargs()) as admin:
            admin.execute(
                sql.SQL("GRANT UPDATE ON history_turns TO {}").format(
                    sql.Identifier(config.app_user)
                )
            )
    verify_control_schema(engine)
    assert store.turn(owner, h.id, turn.id).snapshot == snapshot


def test_v2_upgrade_repeated_migration_and_old_version_marker(
    tmp_path, history_env, monkeypatch
):
    from dataclasses import replace

    from psycopg import sql

    from src.chatbi_control.database import (
        ControlDatabaseMigrationError,
        initialize_control_database,
        verify_control_schema,
    )

    _, _, _, _, config = history_env
    upgraded = replace(config, database="history_upgrade_" + uuid4().hex)
    migrations = Path(__file__).resolve().parents[2] / "database/control"
    for migration in sorted(migrations.glob("*.sql")):
        if migration.name not in {
            "005_history_results.sql",
            "006_execution_streaming.sql",
            "007_execution_stop.sql",
        }:
            (tmp_path / migration.name).write_text(migration.read_text())
    engine = None
    try:
        initialize_control_database(upgraded, sql_directory=tmp_path)
        engine = create_control_engine(upgraded)
        with engine.begin() as connection:
            account = connection.execute(
                text(
                    "INSERT INTO users(username,password_hash) VALUES ('upgrade-test','disabled-test-account') RETURNING id"
                )
            ).scalar_one()
        with pytest.raises(ControlDatabaseMigrationError):
            verify_control_schema(engine)
        initialize_control_database(upgraded)
        verify_control_schema(engine)
        store = PostgresHistoryStore(engine)
        runtime = HistoryRuntime(engine, upgraded.app_connection_kwargs())
        try:
            h, turn, snapshot = committed_query(store, runtime, account)
            saved = store.copy_result(account, h.id, turn.id, "升级保留成果")
            initialize_control_database(upgraded)
            assert store.saved_result(account, saved.id)[1] == snapshot
            assert store.turn(account, h.id, turn.id).snapshot == snapshot
            with engine.connect() as connection:
                assert (
                    connection.execute(
                        text("SELECT count(*) FROM users WHERE id=:id"), {"id": account}
                    ).scalar_one()
                    == 1
                )
                assert "chatbi-control-v2" in set(
                    connection.execute(
                        text("SELECT version FROM schema_migrations")
                    ).scalars()
                )
        finally:
            runtime.close()
        # 停止新运行时后执行基线真实 Schema verifier，保留 v3 数据回滚兼容。
        import types

        old_source = subprocess.check_output(
            ["git", "show", "afad5ac:src/chatbi_control/database.py"], text=True
        )
        old = types.ModuleType("src.chatbi_control.rollback_database")
        old.__file__ = str(migrations.parents[1] / "src/chatbi_control/database.py")
        monkeypatch.setitem(sys.modules, old.__name__, old)
        exec(compile(old_source, old.__file__, "exec"), old.__dict__)  # noqa: S102 - isolated migration compatibility fixture
        old.verify_control_schema(engine)
        verify_control_schema(engine)
        assert store.saved_result(account, saved.id)[1] == snapshot
    finally:
        if engine is not None:
            engine.dispose()
        with psycopg.connect(
            **config.connection_kwargs(
                user=config.migrator_user,
                password=config.migrator_password,
                database="postgres",
            ),
            autocommit=True,
        ) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(upgraded.database)
                )
            )


def test_failed_analysis_can_explicitly_start_new_independent_run(history_env):
    _, store, runtime, owner, _ = history_env
    original = store.create(owner, "analysis", "原分析问题", str(uuid4()))
    attempt = store.begin_analysis_attempt(
        owner, original.id, str(uuid4()), 0, "r", runtime.epoch
    )
    store.finish_attempt(owner, attempt.token, None, {"error_code": "LLM_ERROR"})
    replacement, accepted = store.begin_requery(
        owner,
        "history",
        original.id,
        None,
        str(uuid4()),
        "new-r",
        runtime.epoch,
        str(uuid4()),
    )
    assert (
        replacement.id != original.id
        and replacement.analysis_run_id != original.analysis_run_id
    )
    assert accepted.turn.question == "原分析问题"
    assert store.header(owner, original.id).last_success_turn_id is None


def test_export_projection_is_owner_scoped_and_saved_snapshot_outlives_history(
    history_env,
):
    _engine, store, runtime, owner, _ = history_env
    header, turn, snapshot = committed_query(store, runtime, owner, "完成结果来源问题")

    history_source = store.export_snapshot(owner, "history_turn", header.id, turn.id)
    assert history_source["kind"] == "query"
    assert history_source["title"] == header.title
    assert history_source["question"] == "完成结果来源问题"
    assert history_source["result"] == {
        key: value for key, value in snapshot["result"].items() if key != "sql"
    }
    assert history_source["result_time"] is not None
    assert "query_state" not in history_source
    assert "sql" not in history_source["result"]
    with pytest.raises(HistoryError):
        store.export_snapshot(owner + 1, "history_turn", header.id, turn.id)

    saved = store.copy_result(owner, header.id, turn.id, "独立成果")
    saved_source = store.export_snapshot(owner, "saved_result", saved.id)
    assert saved_source["title"] == "独立成果"
    assert saved_source["result"] == history_source["result"]
    assert saved_source["question"] == "完成结果来源问题"
    assert saved_source["result_time"] is None
    assert saved_source["saved_time"] is not None

    store.delete_history(owner, header.id, header.record_revision, "local:test")
    assert (
        store.export_snapshot(owner, "saved_result", saved.id)["result"]
        == history_source["result"]
    )
    with pytest.raises(HistoryError):
        store.export_snapshot(owner, "history_turn", header.id, turn.id)
