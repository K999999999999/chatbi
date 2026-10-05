"""真实 PostgreSQL 验证执行受理、终态与 owner / operation 去重。"""

import os
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import text

from src.business_analysis.run_store import (
    AnalysisRunConflict,
    PostgresAnalysisRunStore,
)
from src.chatbi_control.database import ControlDatabaseConfig, create_control_engine
from src.chatbi_control.history import PostgresHistoryStore, operation_hash
from src.online_query.contracts import (
    ExecutionStopped,
    ExecutionStopReason,
    QuerySuccess,
)
from src.query_api.history_codec import encode_snapshot
from src.query_api.history_contracts import HistoryError
from src.query_api.history_runtime import HistoryRuntime
from src.query_api.query_response import query_payload
from tests.query_api.history_fixtures import query_state

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DEVELOPMENT_DATABASE_TESTS") != "1",
    reason="需要隔离的development PostgreSQL，并预先安装chatbi-control-v5 migration",
)


@pytest.fixture
def execution_env():
    config = ControlDatabaseConfig.from_environment()
    engine = create_control_engine(config)
    with engine.begin() as connection:
        owner = connection.execute(
            text(
                "INSERT INTO users(username,password_hash) VALUES (:name,'disabled-test-account') RETURNING id"
            ),
            {"name": "execution-test-" + str(uuid4())},
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


def begin_query(store, runtime, owner, history_id, operation_id, question, revision=0):
    request_hash = operation_hash(
        {
            "action": "query",
            "history_id": history_id,
            "question": question,
            "expected_context_revision": revision,
        }
    )
    accepted = store.begin_execution_attempt(
        owner=owner,
        history_id=history_id,
        question=question,
        operation_id=operation_id,
        request_hash=request_hash,
        revision=revision,
        request_id="execution-test",
        epoch=runtime.epoch,
        mode="query",
        operation_kind="query",
        deadline_seconds=180,
    )
    return request_hash, accepted


def test_execution_acceptance_and_success_commit_share_history_turn(execution_env):
    engine, store, runtime, owner, _config = execution_env
    history = store.create(owner, "query", "销售额", str(uuid4()))
    operation_id = str(uuid4())
    _request_hash, accepted = begin_query(
        store, runtime, owner, history.id, operation_id, "销售额"
    )
    assert accepted.created
    assert accepted.execution.status == "accepted"
    assert accepted.execution.turn_id == accepted.attempt.turn.id

    store.mark_execution_running(owner, accepted.execution.id)
    snapshot = encode_snapshot(
        "query",
        query_payload(QuerySuccess("r", "SELECT 1", ("n",), ((1,),), 1, False)),
        query_state=query_state(),
        source_question="销售额",
    )
    store.finish_execution_attempt(
        owner,
        accepted.attempt.token,
        snapshot,
        None,
        accepted.execution.id,
    )

    finished = store.execution(owner, accepted.execution.id)
    turn = store.turn(owner, history.id, accepted.execution.turn_id)
    header = store.header(owner, history.id)
    assert finished.status == turn.status == "succeeded"
    assert finished.finished_at is not None
    assert header.last_success_turn_id == turn.id
    assert header.context_revision == 1

    duplicate = begin_query(store, runtime, owner, history.id, operation_id, "销售额")[
        1
    ]
    assert not duplicate.created
    assert duplicate.attempt is None
    assert duplicate.execution.id == finished.id

    changed_hash = operation_hash({"action": "query", "question": "毛利"})
    with pytest.raises(HistoryError) as conflict:
        store.execution_by_operation(owner, operation_id, changed_hash)
    assert conflict.value.code == "HISTORY_OPERATION_CONFLICT"
    with pytest.raises(HistoryError) as cross_owner:
        store.execution(owner + 100000, finished.id)
    assert cross_owner.value.status == 404

    saved = store.copy_result(owner, history.id, turn.id, "独立成果")
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE history_records SET last_success_turn_id=NULL WHERE id=:history"
            ),
            {"history": history.id},
        )
        connection.execute(
            text("DELETE FROM history_turns WHERE id=:turn"), {"turn": turn.id}
        )
        connection.execute(
            text("DELETE FROM history_records WHERE id=:history"),
            {"history": history.id},
        )
    with pytest.raises(HistoryError) as deleted_execution:
        store.execution(owner, finished.id)
    assert deleted_execution.value.status == 404
    assert (
        store.saved_result(owner, saved.id)[1]["query_state"] == snapshot["query_state"]
    )


def test_restart_marks_durable_execution_unconfirmed_without_rerunning(execution_env):
    engine, store, runtime, owner, config = execution_env
    history = store.create(owner, "query", "销售额", str(uuid4()))
    _request_hash, accepted = begin_query(
        store, runtime, owner, history.id, str(uuid4()), "销售额"
    )
    runtime.close()

    restarted = HistoryRuntime(engine, config.app_connection_kwargs())
    try:
        assert store.execution(owner, accepted.execution.id).status == "unconfirmed"
        assert (
            store.turn(owner, history.id, accepted.execution.turn_id).status
            == "unconfirmed"
        )
        assert store.header(owner, history.id).active_turn_id is None
    finally:
        restarted.close()


def test_success_transaction_failure_keeps_turn_execution_and_context_unconfirmed(
    execution_env,
):
    _engine, store, runtime, owner, config = execution_env
    history = store.create(owner, "query", "销售额", str(uuid4()))
    _request_hash, accepted = begin_query(
        store, runtime, owner, history.id, str(uuid4()), "销售额"
    )
    store.mark_execution_running(owner, accepted.execution.id)
    trigger = "execution_test_" + uuid4().hex
    with psycopg.connect(**config.migrator_connection_kwargs()) as admin:
        admin.execute(
            sql.SQL(
                "CREATE FUNCTION {}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.owner_user_id={} AND NEW.context_revision>OLD.context_revision THEN RAISE EXCEPTION 'injected execution commit rollback'; END IF; RETURN NEW; END $$"
            ).format(sql.Identifier(trigger), sql.Literal(owner))
        )
        admin.execute(
            sql.SQL(
                "CREATE TRIGGER {} BEFORE UPDATE ON history_records FOR EACH ROW EXECUTE FUNCTION {}()"
            ).format(sql.Identifier(trigger), sql.Identifier(trigger))
        )
    snapshot = encode_snapshot(
        "query",
        query_payload(QuerySuccess("r", "SELECT 1", ("n",), ((1,),), 1, False)),
        query_state=query_state(),
        source_question="销售额",
    )
    try:
        with pytest.raises(HistoryError) as rollback:
            store.finish_execution_attempt(
                owner,
                accepted.attempt.token,
                snapshot,
                None,
                accepted.execution.id,
            )
        assert rollback.value.code == "HISTORY_STORAGE_UNAVAILABLE"
        assert store.execution(owner, accepted.execution.id).status == "running"
        assert (
            store.turn(owner, history.id, accepted.execution.turn_id).status
            == "accepted"
        )
        current = store.header(owner, history.id)
        assert current.context_revision == 0
        assert current.active_turn_id == accepted.execution.turn_id
    finally:
        with psycopg.connect(**config.migrator_connection_kwargs()) as admin:
            admin.execute(
                sql.SQL("DROP TRIGGER {} ON history_records").format(
                    sql.Identifier(trigger)
                )
            )
            admin.execute(sql.SQL("DROP FUNCTION {}()").format(sql.Identifier(trigger)))

    runtime.reconcile(history.id)
    assert store.execution(owner, accepted.execution.id).status == "unconfirmed"
    assert (
        store.turn(owner, history.id, accepted.execution.turn_id).status
        == "unconfirmed"
    )


def _successful_query_snapshot(question):
    return encode_snapshot(
        "query",
        query_payload(QuerySuccess("r", "SELECT 1", ("n",), ((1,),), 1, False)),
        query_state=query_state(),
        source_question=question,
    )


def test_cancel_winner_blocks_late_success_and_preserves_last_success(execution_env):
    _engine, store, runtime, owner, _config = execution_env
    history = store.create(owner, "query", "销售额", str(uuid4()))
    _request_hash, first = begin_query(
        store, runtime, owner, history.id, str(uuid4()), "销售额"
    )
    store.mark_execution_running(owner, first.execution.id)
    store.finish_execution_attempt(
        owner,
        first.attempt.token,
        _successful_query_snapshot("销售额"),
        None,
        first.execution.id,
    )
    before = store.header(owner, history.id)

    _request_hash, pending = begin_query(
        store, runtime, owner, history.id, str(uuid4()), "继续查询", revision=1
    )
    store.mark_execution_running(owner, pending.execution.id)
    stopping = store.request_execution_stop(
        owner, pending.execution.id, ExecutionStopReason.USER_CANCELLED.value
    )
    duplicate = store.request_execution_stop(
        owner, pending.execution.id, ExecutionStopReason.DEADLINE_EXCEEDED.value
    )
    assert stopping.status == duplicate.status == "stopping"
    assert stopping.stop_reason == duplicate.stop_reason == "user_cancelled"
    assert stopping.stop_requested_at is not None

    with pytest.raises(ExecutionStopped) as late_success:
        store.finish_execution_attempt(
            owner,
            pending.attempt.token,
            _successful_query_snapshot("继续查询"),
            None,
            pending.execution.id,
        )
    assert late_success.value.reason is ExecutionStopReason.USER_CANCELLED
    assert store.execution(owner, pending.execution.id).status == "stopping"
    assert (
        store.header(owner, history.id).last_success_turn_id
        == before.last_success_turn_id
    )

    store.finish_execution_stopped(
        owner,
        pending.attempt.token,
        pending.execution.id,
        "cancelled",
        {
            "request_id": "cancel-test",
            "error_code": "EXECUTION_CANCELLED",
            "error_message": "执行已取消",
        },
    )
    after = store.header(owner, history.id)
    assert after.active_turn_id is None
    assert after.last_success_turn_id == before.last_success_turn_id
    assert after.context_revision == before.context_revision
    assert store.turn(owner, history.id, pending.execution.turn_id).status == "failed"
    assert store.execution(owner, pending.execution.id).status == "cancelled"


def test_success_winner_makes_later_cancel_idempotently_return_success(execution_env):
    _engine, store, runtime, owner, _config = execution_env
    history = store.create(owner, "query", "销售额", str(uuid4()))
    _request_hash, accepted = begin_query(
        store, runtime, owner, history.id, str(uuid4()), "销售额"
    )
    store.mark_execution_running(owner, accepted.execution.id)
    store.finish_execution_attempt(
        owner,
        accepted.attempt.token,
        _successful_query_snapshot("销售额"),
        None,
        accepted.execution.id,
    )

    after_cancel = store.request_execution_stop(
        owner, accepted.execution.id, ExecutionStopReason.USER_CANCELLED.value
    )
    assert after_cancel.status == "succeeded"
    assert after_cancel.stop_reason is None
    assert after_cancel.stop_requested_at is None
    assert (
        store.header(owner, history.id).last_success_turn_id
        == accepted.execution.turn_id
    )


def test_analysis_cancel_expires_run_before_old_checkpoint_can_be_claimed(
    execution_env,
):
    engine, store, runtime, owner, config = execution_env
    question = "分析净销售额变化"
    history = store.create(owner, "analysis", question, str(uuid4()))
    header = store.header(owner, history.id)
    operation_id = str(uuid4())
    accepted = store.begin_execution_attempt(
        owner=owner,
        history_id=history.id,
        question=question,
        operation_id=operation_id,
        request_hash=operation_hash(
            {"action": "analysis_resume", "history_id": history.id}
        ),
        revision=header.context_revision,
        request_id="analysis-cancel-test",
        epoch=runtime.epoch,
        mode="analysis",
        operation_kind="analysis_resume",
        deadline_seconds=1200,
        expected_record_revision=header.record_revision,
    )
    assert accepted.created
    store.mark_execution_running(owner, accepted.execution.id)
    owner_subject = f"test:analysis-owner:{uuid4()}"
    try:
        store.request_execution_stop(
            owner,
            accepted.execution.id,
            ExecutionStopReason.USER_CANCELLED.value,
            analysis_owner_subject=owner_subject,
        )
        run_store = PostgresAnalysisRunStore(engine)
        with pytest.raises(AnalysisRunConflict) as expired:
            run_store.claim(
                UUID(header.analysis_run_id),
                owner_subject=owner_subject,
                question=question,
            )
        assert expired.value.reason == "ANALYSIS_RUN_EXPIRED"
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT status,expires_at FROM business_analysis_runs WHERE analysis_run_id=:id"
                ),
                {"id": header.analysis_run_id},
            ).one()
        assert row.status == "expired"
        assert row.expires_at == header.created_at + timedelta(hours=24)

        store.finish_execution_stopped(
            owner,
            accepted.attempt.token,
            accepted.execution.id,
            "cancelled",
            {
                "request_id": "analysis-cancel-test",
                "error_code": "EXECUTION_CANCELLED",
                "error_message": "执行已取消",
            },
        )
        assert store.execution(owner, accepted.execution.id).status == "cancelled"
        assert store.header(owner, history.id).active_turn_id is None
        assert store.header(owner, history.id).last_success_turn_id is None
    finally:
        with psycopg.connect(**config.migrator_connection_kwargs()) as admin:
            admin.execute(
                "DELETE FROM business_analysis_runs WHERE owner_subject=%s",
                (owner_subject,),
            )


def test_analysis_cancel_after_completed_checkpoint_preserves_ttl_and_blocks_reclaim(
    execution_env,
):
    engine, store, runtime, owner, config = execution_env
    question = "分析毛利变化"
    history = store.create(owner, "analysis", question, str(uuid4()))
    header = store.header(owner, history.id)
    run_id = UUID(header.analysis_run_id)
    owner_subject = f"test:completed-analysis:{uuid4()}"
    run_store = PostgresAnalysisRunStore(engine)
    try:
        run_store.claim(run_id, owner_subject=owner_subject, question=question)
        run_store.mark_completed(run_id)
        with engine.connect() as connection:
            original_expiry = connection.execute(
                text(
                    "SELECT expires_at FROM business_analysis_runs WHERE analysis_run_id=:id"
                ),
                {"id": header.analysis_run_id},
            ).scalar_one()

        operation_id = str(uuid4())
        accepted = store.begin_execution_attempt(
            owner=owner,
            history_id=history.id,
            question=question,
            operation_id=operation_id,
            request_hash=operation_hash(
                {"action": "analysis_resume", "history_id": history.id}
            ),
            revision=header.context_revision,
            request_id="analysis-checkpoint-cancel-test",
            epoch=runtime.epoch,
            mode="analysis",
            operation_kind="analysis_resume",
            deadline_seconds=1200,
            expected_record_revision=header.record_revision,
        )
        store.mark_execution_running(owner, accepted.execution.id)
        store.request_execution_stop(
            owner,
            accepted.execution.id,
            ExecutionStopReason.USER_CANCELLED.value,
            analysis_owner_subject=owner_subject,
        )
        with engine.connect() as connection:
            status, expiry = connection.execute(
                text(
                    "SELECT status,expires_at FROM business_analysis_runs WHERE analysis_run_id=:id"
                ),
                {"id": header.analysis_run_id},
            ).one()
        assert status == "expired"
        assert expiry == original_expiry
        with pytest.raises(AnalysisRunConflict) as expired:
            run_store.claim(run_id, owner_subject=owner_subject, question=question)
        assert expired.value.reason == "ANALYSIS_RUN_EXPIRED"

        store.finish_execution_stopped(
            owner,
            accepted.attempt.token,
            accepted.execution.id,
            "cancelled",
            {
                "request_id": "analysis-checkpoint-cancel-test",
                "error_code": "EXECUTION_CANCELLED",
                "error_message": "执行已取消",
            },
        )
    finally:
        with psycopg.connect(**config.migrator_connection_kwargs()) as admin:
            admin.execute(
                "DELETE FROM business_analysis_runs WHERE owner_subject=%s",
                (owner_subject,),
            )


def test_migration_contains_v4_execution_table_and_runtime_role_grant():
    migration = Path("database/control/006_execution_streaming.sql").read_text(
        encoding="utf-8"
    )
    assert "CREATE TABLE IF NOT EXISTS history_executions" in migration
    assert "UNIQUE (owner_user_id, operation_id)" in migration
    assert "ON DELETE CASCADE" in migration
    assert (
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE history_executions" in migration
    )


def test_stop_migration_adds_durable_stop_timestamp():
    migration = Path("database/control/007_execution_stop.sql").read_text(
        encoding="utf-8"
    )
    assert "ADD COLUMN IF NOT EXISTS stop_requested_at TIMESTAMPTZ" in migration
    assert "chatbi-control-v5" in migration
