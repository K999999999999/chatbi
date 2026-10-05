"""PostgreSQL 后台执行状态表；写入与 History turn 共用事务。"""

import json

from sqlalchemy import text

from src.query_api.execution_contracts import ExecutionRecord
from src.query_api.history_contracts import HistoryError, unavailable


def _record(row):
    if row is None:
        return None
    return ExecutionRecord(
        id=str(row["id"]),
        history_id=str(row["history_id"]),
        turn_id=str(row["turn_id"]),
        operation_id=str(row["operation_id"]),
        mode=row["mode"],
        operation_kind=row["operation_kind"],
        status=row["status"],
        stop_reason=row["stop_reason"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        deadline_at=row["deadline_at"],
        finished_at=row["finished_at"],
        public_error=row["public_error"],
    )


class PostgresExecutionStore:
    """执行行的 SQL 实现；调用方可传入 History transaction connection。"""

    def __init__(self, engine):
        self.engine = engine

    def find_in_transaction(self, connection, owner, operation_id, request_hash):
        row = (
            connection.execute(
                text("""SELECT * FROM history_executions
                    WHERE owner_user_id=:owner AND operation_id=:operation
                    FOR UPDATE"""),
                {"owner": owner, "operation": operation_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        if row["request_hash"].strip() != request_hash:
            raise HistoryError(
                "HISTORY_OPERATION_CONFLICT", "操作编号与原请求不匹配", 409
            )
        return _record(row)

    def lock_operation_in_transaction(self, connection, owner, operation_id):
        key = f"{owner}:{operation_id}"
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": key},
        )

    def insert_in_transaction(
        self,
        connection,
        *,
        execution_id,
        owner,
        history_id,
        turn_id,
        operation_id,
        request_hash,
        mode,
        operation_kind,
        epoch,
        generation,
        deadline_seconds,
    ):
        row = (
            connection.execute(
                text("""INSERT INTO history_executions (
                    id,owner_user_id,history_id,turn_id,operation_id,request_hash,
                    mode,operation_kind,status,runtime_epoch,execution_generation,
                    deadline_at
                ) VALUES (
                    :id,:owner,:history,:turn,:operation,:hash,:mode,:operation_kind,
                    'accepted',:epoch,:generation,
                    CURRENT_TIMESTAMP + (:deadline_seconds * INTERVAL '1 second')
                ) RETURNING *"""),
                {
                    "id": execution_id,
                    "owner": owner,
                    "history": history_id,
                    "turn": turn_id,
                    "operation": operation_id,
                    "hash": request_hash,
                    "mode": mode,
                    "operation_kind": operation_kind,
                    "epoch": epoch,
                    "generation": generation,
                    "deadline_seconds": deadline_seconds,
                },
            )
            .mappings()
            .one()
        )
        return _record(row)

    def mark_running_in_transaction(self, connection, owner, execution_id):
        result = connection.execute(
            text("""UPDATE history_executions AS execution SET status='running',
                started_at=COALESCE(started_at,CURRENT_TIMESTAMP)
                FROM history_records AS history, history_turns AS turn,
                     history_runtime AS runtime
                WHERE execution.id=:id AND execution.owner_user_id=:owner
                  AND execution.status='accepted'
                  AND history.id=execution.history_id
                  AND history.owner_user_id=execution.owner_user_id
                  AND history.active_turn_id=execution.turn_id
                  AND history.execution_generation=execution.execution_generation
                  AND turn.id=execution.turn_id AND turn.history_id=execution.history_id
                  AND turn.status='accepted' AND turn.runtime_epoch=execution.runtime_epoch
                  AND runtime.singleton AND runtime.runtime_epoch=execution.runtime_epoch"""),
            {"id": execution_id, "owner": owner},
        )
        if result.rowcount == 1:
            return
        row = (
            connection.execute(
                text("SELECT status FROM history_executions WHERE id=:id AND owner_user_id=:owner"),
                {"id": execution_id, "owner": owner},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise unavailable()
        if row["status"] != "running":
            raise HistoryError("HISTORY_SAVE_UNCONFIRMED", "执行状态已变化，请刷新历史", 503)

    def finish_in_transaction(self, connection, owner, execution_id, status, public_error):
        result = connection.execute(
            text("""UPDATE history_executions SET status=:status,
                public_error=CAST(:error AS jsonb),finished_at=CURRENT_TIMESTAMP
                WHERE id=:id AND owner_user_id=:owner AND status IN ('accepted','running')"""),
            {
                "id": execution_id,
                "owner": owner,
                "status": status,
                "error": None if public_error is None else json.dumps(public_error),
            },
        )
        if result.rowcount != 1:
            raise HistoryError("HISTORY_SAVE_UNCONFIRMED", "结果未确认，请刷新历史", 503)

    def get(self, owner, execution_id):
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    text("SELECT * FROM history_executions WHERE id=:id AND owner_user_id=:owner"),
                    {"id": execution_id, "owner": owner},
                )
                .mappings()
                .first()
            )
        if row is None:
            raise unavailable()
        return _record(row)

    def by_operation(self, owner, operation_id, request_hash=None):
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    text("""SELECT * FROM history_executions
                        WHERE owner_user_id=:owner AND operation_id=:operation"""),
                    {"owner": owner, "operation": operation_id},
                )
                .mappings()
                .first()
            )
        if (
            row is not None
            and request_hash is not None
            and row["request_hash"].strip() != request_hash
        ):
            raise HistoryError(
                "HISTORY_OPERATION_CONFLICT", "操作编号与原请求不匹配", 409
            )
        return _record(row)
