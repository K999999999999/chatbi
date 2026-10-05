"""真实 PostgreSQL 验证执行受理、终态与 owner / operation 去重。"""

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import text

from src.chatbi_control.database import ControlDatabaseConfig, create_control_engine
from src.chatbi_control.history import PostgresHistoryStore, operation_hash
from src.online_query.contracts import QuerySuccess
from src.query_api.history_codec import encode_snapshot
from src.query_api.history_contracts import HistoryError
from src.query_api.history_runtime import HistoryRuntime
from src.query_api.query_response import query_payload
from tests.query_api.history_fixtures import query_state

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DEVELOPMENT_DATABASE_TESTS") != "1",
    reason="需要隔离的development PostgreSQL，并预先安装chatbi-control-v4 migration",
)


@pytest.fixture
def execution_env():
    config = ControlDatabaseConfig.from_environment()
    engine = create_control_engine(config)
    with engine.begin() as connection:
        owner = connection.execute(
            text("INSERT INTO users(username,password_hash) VALUES (:name,'disabled-test-account') RETURNING id"),
            {"name": "execution-test-" + str(uuid4())},
        ).scalar_one()
    runtime = HistoryRuntime(engine, config.app_connection_kwargs())
    try:
        yield engine, PostgresHistoryStore(engine), runtime, owner, config
    finally:
        runtime.close()
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE history_records SET active_turn_id=NULL,last_success_turn_id=NULL WHERE owner_user_id=:owner"),
                {"owner": owner},
            )
            connection.execute(
                text("DELETE FROM history_turns WHERE history_id IN (SELECT id FROM history_records WHERE owner_user_id=:owner)"),
                {"owner": owner},
            )
            connection.execute(
                text("DELETE FROM saved_results WHERE owner_user_id=:owner"),
                {"owner": owner},
            )
            connection.execute(text("DELETE FROM history_records WHERE owner_user_id=:owner"), {"owner": owner})
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

    duplicate = begin_query(
        store, runtime, owner, history.id, operation_id, "销售额"
    )[1]
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
    assert store.saved_result(owner, saved.id)[1]["query_state"] == snapshot[
        "query_state"
    ]


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
        assert store.turn(owner, history.id, accepted.execution.turn_id).status == "unconfirmed"
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
        assert store.turn(owner, history.id, accepted.execution.turn_id).status == "accepted"
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
    assert store.turn(owner, history.id, accepted.execution.turn_id).status == "unconfirmed"
    assert store.header(owner, history.id).last_success_turn_id is None


def test_migration_contains_v4_execution_table_and_runtime_role_grant():
    migration = Path("database/control/006_execution_streaming.sql").read_text(
        encoding="utf-8"
    )
    assert "CREATE TABLE IF NOT EXISTS history_executions" in migration
    assert "UNIQUE (owner_user_id, operation_id)" in migration
    assert "ON DELETE CASCADE" in migration
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE history_executions" in migration
