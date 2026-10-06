"""真实PG验证短事务、隔离、幂等与停止后重启的迟到提交拒绝。"""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic
from uuid import uuid4

import psycopg
import pytest
from sqlalchemy import text

from src.chatbi_control.database import ControlDatabaseConfig, create_control_engine
from src.chatbi_control.history import PostgresHistoryStore
from src.online_query.contracts import QuerySuccess
from src.query_api.history_codec import encode_snapshot
from src.query_api.history_contracts import HistoryError
from src.query_api.history_runtime import HistoryRuntime
from src.query_api.query_response import query_payload
from tests.query_api.history_fixtures import query_state

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
):
    return store.begin_attempt(
        owner,
        history_id,
        question,
        operation or str(uuid4()),
        revision,
        "history-test",
        runtime.epoch,
    )


def test_success_failure_and_duplicate_are_durable(history_env):
    _engine, store, runtime, owner, _ = history_env
    creation = str(uuid4())
    header = store.create(owner, "query", "人民币净销售额", creation)
    assert store.create(owner, "query", "人民币净销售额", creation).id == header.id
    operation = str(uuid4())
    accepted = begin(store, runtime, owner, header.id, operation=operation)
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
    duplicate = begin(store, runtime, owner, header.id, operation=operation)
    assert duplicate.token is None and duplicate.turn.id == success.id
    with pytest.raises(HistoryError, match="请刷新"):
        begin(store, runtime, owner, header.id)
    second = begin(store, runtime, owner, header.id, revision=1)
    assert second.base_state == snapshot["query_state"]
    store.finish_attempt(owner, second.token, None, {"error_code": "LLM_ERROR"})
    current = store.header(owner, header.id)
    assert current.context_revision == 1 and current.last_success_turn_id == success.id
    assert store.turn(owner, header.id, success.id).snapshot == snapshot
    with pytest.raises(HistoryError) as cross_owner:
        store.header(owner + 100000, header.id)
    assert cross_owner.value.status == 404


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
    engine, store, runtime, owner, _ = history_env
    header = store.create(owner, "query", "人民币净销售额", str(uuid4()))
    accepted = begin(store, runtime, owner, header.id)
    snapshot = encode_snapshot(
        "query",
        query_payload(QuerySuccess("r", "SELECT 12", ("n",), ((12,),), 1, False)),
        query_state=query_state(),
        source_question="人民币净销售额",
    )

    lock_connection = engine.connect()
    lock_transaction = lock_connection.begin()
    lock_connection.execute(
        text("SELECT id FROM history_records WHERE id=:id FOR UPDATE"),
        {"id": header.id},
    )
    started = Event()

    def finish():
        started.set()
        return store.finish_attempt(owner, accepted.token, snapshot, None)

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(finish)
            assert started.wait(timeout=5)
            deadline = monotonic() + 5
            blocked = False
            with engine.connect() as observer:
                while monotonic() < deadline:
                    blocked = observer.execute(
                        text("""SELECT EXISTS (
                            SELECT 1 FROM pg_stat_activity
                            WHERE datname=current_database() AND pid<>pg_backend_pid()
                              AND wait_event_type='Lock' AND query ILIKE '%history_records%'
                        )""")
                    ).scalar_one()
                    if blocked:
                        break
                    Event().wait(0.01)
            assert blocked, "finish should wait on the short management transaction"
            lock_transaction.commit()
            assert future.result(timeout=5).status == "succeeded"
    finally:
        if lock_transaction.is_active:
            lock_transaction.rollback()
        lock_connection.close()


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
    header, requery = store.begin_requery(
        owner,
        "history",
        source.id,
        source_turn.id,
        operation,
        "r",
        runtime.epoch,
        str(uuid4()),
    )
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
    )
    assert (
        same_header.id == header.id
        and duplicate.token is None
        and duplicate.turn.id == finished.id
    )
    assert store.turn(owner, source.id, source_turn.id).snapshot == snapshot


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
    assert missing.value.status == 404
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
    assert cross.value.status == 404
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
    assert invalid.value.status == 400
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


def test_finish_transaction_failure_never_advances_context(history_env):
    engine, store, runtime, owner, config = history_env
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
        verify_control_schema,
        ControlDatabaseMigrationError,
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
    from pathlib import Path
    from psycopg import sql
    from src.chatbi_control.database import (
        initialize_control_database,
        verify_control_schema,
        ControlDatabaseMigrationError,
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
        import subprocess
        import types
        import sys

        old_source = subprocess.check_output(
            ["git", "show", "afad5ac:src/chatbi_control/database.py"], text=True
        )
        old = types.ModuleType("src.chatbi_control.rollback_database")
        old.__file__ = str(migrations.parents[1] / "src/chatbi_control/database.py")
        monkeypatch.setitem(sys.modules, old.__name__, old)
        exec(compile(old_source, old.__file__, "exec"), old.__dict__)
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
