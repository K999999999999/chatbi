"""PostgreSQL历史Adapter：完整操作的短事务与条件提交。"""

import json
from dataclasses import replace
from functools import wraps
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.chatbi_control.execution import PostgresExecutionStore
from src.query_api.execution_contracts import ExecutionAcceptance
from src.query_api.history_contracts import (
    AcceptedAttempt,
    ExecutionToken,
    HistoryError,
    HistoryHeader,
    HistoryTurn,
    SavedResultHeader,
    busy,
    operation_hash,
    stale,
    storage_unavailable,
    unavailable,
)


def _database_errors(method):
    @wraps(method)
    def call(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except SQLAlchemyError as exc:
            if getattr(getattr(exc, "orig", None), "sqlstate", None) == "55P03":
                raise busy() from None
            raise storage_unavailable() from None

    return call


def _header(row):
    fields = HistoryHeader.__dataclass_fields__
    values = {field: row[field] for field in fields if field in row}
    for key in ("id", "last_success_turn_id", "active_turn_id", "analysis_run_id"):
        if values[key] is not None:
            values[key] = str(values[key])
    return HistoryHeader(**values)


def _turn(row):
    values = {field: row.get(field) for field in HistoryTurn.__dataclass_fields__}
    values["id"], values["history_id"] = str(values["id"]), str(values["history_id"])
    return HistoryTurn(**values)


def _owned(connection, owner, history_id, *, lock=False, wait=False):
    statement = "SELECT * FROM history_records WHERE id=:id AND owner_user_id=:owner AND deleted_at IS NULL"
    if lock:
        statement += " FOR UPDATE" if wait else " FOR UPDATE NOWAIT"
    row = (
        connection.execute(text(statement), {"id": history_id, "owner": owner})
        .mappings()
        .first()
    )
    if row is None:
        raise unavailable()
    return row


def _saved_header(row):
    values = {field: row[field] for field in SavedResultHeader.__dataclass_fields__}
    for field in ("id", "source_history_id", "source_turn_id"):
        values[field] = str(values[field])
    return SavedResultHeader(**values)


def _owned_saved(connection, owner, result_id, *, lock=False):
    statement = "SELECT * FROM saved_results WHERE id=:id AND owner_user_id=:owner"
    if lock:
        statement += " FOR UPDATE NOWAIT"
    row = (
        connection.execute(text(statement), {"id": result_id, "owner": owner})
        .mappings()
        .first()
    )
    if row is None:
        raise unavailable()
    return row


class PostgresHistoryStore:
    def __init__(self, engine):
        self.engine = engine
        self.executions = PostgresExecutionStore(engine)

    @_database_errors
    def execution(self, owner, execution_id):
        return self.executions.get(owner, execution_id)

    @_database_errors
    def execution_by_operation(self, owner, operation_id, request_hash=None):
        return self.executions.by_operation(owner, operation_id, request_hash)

    @_database_errors
    def mark_execution_running(self, owner, execution_id):
        with self.engine.begin() as connection:
            self.executions.mark_running_in_transaction(
                connection, owner, execution_id
            )

    @_database_errors
    def begin_execution_attempt(
        self,
        *,
        owner,
        history_id,
        question,
        operation_id,
        request_hash,
        revision,
        request_id,
        epoch,
        mode,
        operation_kind,
        deadline_seconds,
        expected_record_revision=None,
    ):
        with self.engine.begin() as connection:
            self.executions.lock_operation_in_transaction(
                connection, owner, operation_id
            )
            existing = self.executions.find_in_transaction(
                connection, owner, operation_id, request_hash
            )
            if existing is not None:
                return ExecutionAcceptance(existing, None, False)

            header = _owned(connection, owner, history_id, lock=True)
            if header["kind"] != mode:
                raise HistoryError("INVALID_REQUEST", "执行模式与历史类型不匹配", 400)
            if mode == "analysis":
                if expected_record_revision is None:
                    raise HistoryError("INVALID_REQUEST", "分析恢复版本缺失", 400)
                if header["record_revision"] != expected_record_revision:
                    raise stale()
                digest = operation_hash(
                    {"action": "resume", "record_revision": expected_record_revision}
                )
                accepted = self._begin(
                    connection,
                    owner,
                    history_id,
                    header["first_question"],
                    operation_id,
                    header["context_revision"],
                    request_id,
                    epoch,
                    digest,
                )
            else:
                if revision is None:
                    raise HistoryError("INVALID_REQUEST", "查询版本缺失", 400)
                accepted = self._begin(
                    connection,
                    owner,
                    history_id,
                    question,
                    operation_id,
                    revision,
                    request_id,
                    epoch,
                    operation_hash({"question": question, "context_revision": revision}),
                )
            if accepted.token is None:
                raise HistoryError(
                    "HISTORY_OPERATION_CONFLICT", "操作编号已用于其他执行", 409
                )
            execution = self.executions.insert_in_transaction(
                connection,
                execution_id=str(uuid4()),
                owner=owner,
                history_id=history_id,
                turn_id=accepted.turn.id,
                operation_id=operation_id,
                request_hash=request_hash,
                mode=mode,
                operation_kind=operation_kind,
                epoch=epoch,
                generation=accepted.token.generation,
                deadline_seconds=deadline_seconds,
            )
            return ExecutionAcceptance(execution, accepted, True)

    @_database_errors
    def begin_requery(
        self,
        owner,
        source_kind,
        source_id,
        source_turn_id,
        operation_id,
        request_id,
        epoch,
        new_id,
        *,
        execution_data=None,
    ):
        digest = operation_hash(
            {
                "action": "requery",
                "source_kind": source_kind,
                "source_id": source_id,
                "source_turn_id": source_turn_id,
            }
        )
        with self.engine.begin() as connection:
            if execution_data is not None:
                self.executions.lock_operation_in_transaction(
                    connection, owner, operation_id
                )
                execution = self.executions.find_in_transaction(
                    connection,
                    owner,
                    operation_id,
                    execution_data["request_hash"],
                )
                if execution is not None:
                    header = _header(
                        _owned(connection, owner, execution.history_id)
                    )
                    turn = (
                        connection.execute(
                            text("SELECT * FROM history_turns WHERE id=:turn AND history_id=:history"),
                            {
                                "turn": execution.turn_id,
                                "history": execution.history_id,
                            },
                        )
                        .mappings()
                        .one()
                    )
                    return (
                        header,
                        AcceptedAttempt(None, _turn(turn), None),
                        execution,
                        False,
                    )
            existing = (
                connection.execute(
                    text(
                        "SELECT * FROM history_records WHERE owner_user_id=:owner AND creation_operation_id=:op FOR UPDATE NOWAIT"
                    ),
                    {"owner": owner, "op": operation_id},
                )
                .mappings()
                .first()
            )
            if existing is not None:
                if execution_data is not None:
                    raise HistoryError(
                        "HISTORY_OPERATION_CONFLICT", "操作编号已用于其他执行", 409
                    )
                if existing["creation_operation_hash"] != digest:
                    raise HistoryError(
                        "HISTORY_OPERATION_CONFLICT", "操作标识与原请求不符", 409
                    )
                if existing["deleted_at"] is not None:
                    raise unavailable()
                turn = (
                    connection.execute(
                        text(
                            "SELECT * FROM history_turns WHERE history_id=:id AND operation_id=:op"
                        ),
                        {"id": existing["id"], "op": operation_id},
                    )
                    .mappings()
                    .one()
                )
                if turn["status"] == "accepted":
                    raise busy()
                if turn["status"] == "unconfirmed":
                    raise HistoryError(
                        "HISTORY_SAVE_UNCONFIRMED", "结果未确认，请刷新历史", 503
                    )
                return _header(existing), AcceptedAttempt(None, _turn(turn), None)
            history_title = None
            if source_kind == "history":
                source = _owned(connection, owner, source_id, lock=True)
                kind = source["kind"]
                if kind == "analysis":
                    question = source["first_question"]
                    snapshot = {"original_question": question}
                else:
                    row = (
                        connection.execute(
                            text(
                                "SELECT question,snapshot FROM history_turns WHERE history_id=:id AND id=:turn AND status='succeeded'"
                            ),
                            {"id": source_id, "turn": source_turn_id},
                        )
                        .mappings()
                        .first()
                    )
                    if row is None:
                        raise HistoryError(
                            "HISTORY_RESULT_NOT_SAVABLE",
                            "问数来源必须是已保存的成功结果",
                            422,
                        )
                    snapshot, question = row["snapshot"], row["question"]
            else:
                source = (
                    connection.execute(
                        text(
                            "SELECT * FROM saved_results WHERE id=:id AND owner_user_id=:owner FOR UPDATE NOWAIT"
                        ),
                        {"id": source_id, "owner": owner},
                    )
                    .mappings()
                    .first()
                )
                if source is None:
                    raise unavailable()
                snapshot, kind = source["snapshot"], source["kind"]
                history_title = source["title"]
                if kind == "query":
                    question = (
                        snapshot.get("source_question")
                        or "根据已保存的完整查询条件重新查询"
                    )
                else:
                    question = snapshot["original_question"]
            if kind == "query" or source_kind == "saved":
                from src.query_api.history_codec import public_snapshot

                public_snapshot(snapshot)
            inserted = connection.execute(
                text("""INSERT INTO history_records(id,owner_user_id,kind,title,first_question,creation_operation_id,creation_operation_hash,analysis_run_id)
                VALUES (:id,:owner,:kind,:title,:question,:op,:hash,:run)
                ON CONFLICT (owner_user_id,creation_operation_id) DO NOTHING RETURNING id"""),
                {
                    "id": new_id,
                    "owner": owner,
                    "kind": kind,
                    "title": history_title or question[:120],
                    "question": question,
                    "op": operation_id,
                    "hash": digest,
                    "run": (
                        execution_data.get("analysis_run_id") or str(uuid4())
                        if kind == "analysis" and execution_data is not None
                        else str(uuid4()) if kind == "analysis" else None
                    ),
                },
            )
            if inserted.scalar_one_or_none() is None:
                existing_hash = connection.execute(
                    text(
                        "SELECT creation_operation_hash FROM history_records WHERE owner_user_id=:owner AND creation_operation_id=:op"
                    ),
                    {"owner": owner, "op": operation_id},
                ).scalar_one()
                if existing_hash != digest:
                    raise HistoryError(
                        "HISTORY_OPERATION_CONFLICT", "操作标识与原请求不符", 409
                    )
                raise busy()
            accepted = self._begin(
                connection,
                owner,
                new_id,
                question,
                operation_id,
                0,
                request_id,
                epoch,
                digest,
            )
            connection.execute(
                text(
                    "UPDATE history_turns SET attempt_input=CAST(:input AS jsonb) WHERE id=:turn"
                ),
                {
                    "turn": accepted.turn.id,
                    "input": json.dumps(snapshot, ensure_ascii=False, allow_nan=False),
                },
            )
            execution = None
            if execution_data is not None:
                execution = self.executions.insert_in_transaction(
                    connection,
                    execution_id=str(uuid4()),
                    owner=owner,
                    history_id=new_id,
                    turn_id=accepted.turn.id,
                    operation_id=operation_id,
                    request_hash=execution_data["request_hash"],
                    mode=kind,
                    operation_kind=execution_data["operation_kind"],
                    epoch=epoch,
                    generation=accepted.token.generation,
                    deadline_seconds=execution_data["deadline_seconds"],
                )
            header = _header(_owned(connection, owner, new_id))
            attempt = AcceptedAttempt(
                accepted.token, accepted.turn, snapshot.get("query_state"), snapshot
            )
            if execution_data is not None:
                return header, attempt, execution, True
            return header, attempt

    @_database_errors
    def begin_execution_requery(
        self,
        *,
        owner,
        source_kind,
        source_id,
        source_turn_id,
        operation_id,
        request_id,
        epoch,
        new_id,
        request_hash,
        operation_kind,
        deadline_seconds,
        analysis_run_id=None,
    ):
        return self.begin_requery(
            owner,
            source_kind,
            source_id,
            source_turn_id,
            operation_id,
            request_id,
            epoch,
            new_id,
            execution_data={
                "request_hash": request_hash,
                "operation_kind": operation_kind,
                "deadline_seconds": deadline_seconds,
                "analysis_run_id": analysis_run_id,
            },
        )

    @_database_errors
    def create(self, owner, kind, question, operation_id):
        digest = operation_hash({"kind": kind, "first_question": question})
        with self.engine.begin() as connection:
            connection.execute(
                text("""
                INSERT INTO history_records(id, owner_user_id, kind, title, first_question,
                    creation_operation_id, creation_operation_hash, analysis_run_id)
                VALUES (:id,:owner,:kind,:title,:question,:operation,:hash,:run)
                ON CONFLICT (owner_user_id, creation_operation_id) DO NOTHING
            """),
                {
                    "id": str(uuid4()),
                    "owner": owner,
                    "kind": kind,
                    "title": question[:120],
                    "question": question,
                    "operation": operation_id,
                    "hash": digest,
                    "run": str(uuid4()) if kind == "analysis" else None,
                },
            )
            row = (
                connection.execute(
                    text(
                        "SELECT * FROM history_records WHERE owner_user_id=:owner AND creation_operation_id=:operation"
                    ),
                    {"owner": owner, "operation": operation_id},
                )
                .mappings()
                .one()
            )
            if row["deleted_at"] is not None:
                raise unavailable()
            if row["creation_operation_hash"] != digest:
                raise HistoryError(
                    "HISTORY_OPERATION_CONFLICT", "操作标识与原请求不符", 409
                )
            return _header(row)

    @_database_errors
    def header(self, owner, history_id):
        with self.engine.connect() as connection:
            header = _header(_owned(connection, owner, history_id))
            if header.kind == "analysis":
                run = (
                    connection.execute(
                        text(
                            "SELECT status, expires_at>CURRENT_TIMESTAMP AS current FROM business_analysis_runs WHERE analysis_run_id=:run"
                        ),
                        {"run": header.analysis_run_id},
                    )
                    .mappings()
                    .first()
                )
                latest = (
                    connection.execute(
                        text(
                            "SELECT status,public_error FROM history_turns WHERE history_id=:id ORDER BY ordinal DESC LIMIT 1"
                        ),
                        {"id": history_id},
                    )
                    .mappings()
                    .first()
                )
                retryable = (
                    latest is None
                    or latest["status"] != "failed"
                    or (latest["public_error"] or {}).get("error_code")
                    in {
                        "LLM_ERROR",
                        "CONTEXT_ERROR",
                        "DATABASE_ERROR",
                        "QUERY_TIMEOUT",
                        "AUTHENTICATION_UNAVAILABLE",
                        "HISTORY_BUSY",
                    }
                )
                return replace(
                    header,
                    analysis_recovery_available=retryable
                    and (
                        run is None or (run["status"] != "expired" and run["current"])
                    ),
                )
            return header

    @_database_errors
    def begin_attempt(
        self, owner, history_id, question, operation_id, revision, request_id, epoch
    ):
        digest = operation_hash({"question": question, "context_revision": revision})
        with self.engine.begin() as connection:
            return self._begin(
                connection,
                owner,
                history_id,
                question,
                operation_id,
                revision,
                request_id,
                epoch,
                digest,
            )

    @_database_errors
    def begin_analysis_attempt(
        self, owner, history_id, operation_id, revision, request_id, epoch
    ):
        with self.engine.begin() as connection:
            header = _owned(connection, owner, history_id, lock=True)
            digest = operation_hash({"action": "resume", "record_revision": revision})
            existing = connection.execute(
                text(
                    "SELECT 1 FROM history_turns WHERE history_id=:id AND operation_id=:op"
                ),
                {"id": history_id, "op": operation_id},
            ).first()
            if existing is None and header["record_revision"] != revision:
                raise stale()
            return self._begin(
                connection,
                owner,
                history_id,
                header["first_question"],
                operation_id,
                header["context_revision"],
                request_id,
                epoch,
                digest,
            )

    def _begin(
        self,
        connection,
        owner,
        history_id,
        question,
        operation_id,
        revision,
        request_id,
        epoch,
        digest,
    ):
        header = _owned(connection, owner, history_id, lock=True)
        previous = (
            connection.execute(
                text(
                    "SELECT * FROM history_turns WHERE history_id=:id AND operation_id=:operation"
                ),
                {"id": history_id, "operation": operation_id},
            )
            .mappings()
            .first()
        )
        if previous is not None:
            if previous["operation_hash"] != digest:
                raise HistoryError(
                    "HISTORY_OPERATION_CONFLICT", "操作标识与原请求不符", 409
                )
            if previous["status"] == "accepted":
                raise busy()
            if previous["status"] == "unconfirmed":
                raise HistoryError(
                    "HISTORY_SAVE_UNCONFIRMED", "结果未确认，请刷新历史", 503
                )
            return AcceptedAttempt(None, _turn(previous), None)
        if header["active_turn_id"] is not None:
            raise busy()
        if header["context_revision"] != revision:
            raise stale()
        current_epoch = connection.execute(
            text("SELECT runtime_epoch FROM history_runtime WHERE singleton")
        ).scalar_one_or_none()
        if str(current_epoch) != epoch:
            raise storage_unavailable()
        turn_id = str(uuid4())
        generation = header["execution_generation"] + 1
        turn = (
            connection.execute(
                text("""
            INSERT INTO history_turns(id,history_id,ordinal,operation_id,operation_hash,
                question,request_id,status,runtime_epoch,execution_generation)
            VALUES (:turn,:id,:ordinal,:operation,:hash,:question,:request,'accepted',:epoch,:generation)
            RETURNING *
        """),
                {
                    "turn": turn_id,
                    "id": history_id,
                    "ordinal": header["next_ordinal"],
                    "operation": operation_id,
                    "hash": digest,
                    "question": question,
                    "request": request_id,
                    "epoch": epoch,
                    "generation": generation,
                },
            )
            .mappings()
            .one()
        )
        connection.execute(
            text("""
            UPDATE history_records SET active_turn_id=:turn,execution_generation=:generation,
                next_ordinal=next_ordinal+1,record_revision=record_revision+1,updated_at=CURRENT_TIMESTAMP
            WHERE id=:id
        """),
            {"id": history_id, "turn": turn_id, "generation": generation},
        )
        base_state = None
        if header["last_success_turn_id"] is not None:
            snapshot = connection.execute(
                text(
                    "SELECT snapshot FROM history_turns WHERE id=:turn AND history_id=:id AND status='succeeded'"
                ),
                {"turn": header["last_success_turn_id"], "id": history_id},
            ).scalar_one()
            if header["kind"] == "query":
                from src.query_api.history_codec import (
                    decode_query_state,
                    public_snapshot,
                )

                public_snapshot(snapshot)
                base_state = snapshot.get("query_state")
                decode_query_state(base_state)
        return AcceptedAttempt(
            ExecutionToken(history_id, turn_id, epoch, generation),
            _turn(turn),
            base_state,
        )

    @_database_errors
    def finish_attempt(self, owner, token, snapshot, error, *, execution_id=None):
        with self.engine.begin() as connection:
            # Completion must survive a short metadata/copy/delete transaction that
            # observed the still-active turn. Returning NOWAIT here can strand a
            # completed business request as unconfirmed.
            header = _owned(connection, owner, token.history_id, lock=True, wait=True)
            epoch = connection.execute(
                text("SELECT runtime_epoch FROM history_runtime WHERE singleton")
            ).scalar_one_or_none()
            if (
                str(header["active_turn_id"]) != token.turn_id
                or header["execution_generation"] != token.generation
                or str(epoch) != token.epoch
            ):
                raise HistoryError(
                    "HISTORY_SAVE_UNCONFIRMED", "结果未确认，请刷新历史", 503
                )
            status = "succeeded" if snapshot is not None else "failed"
            row = (
                connection.execute(
                    text("""
                UPDATE history_turns SET status=:status, snapshot=CAST(:snapshot AS jsonb),
                    snapshot_version=:version, public_error=CAST(:error AS jsonb), completed_at=CURRENT_TIMESTAMP
                WHERE id=:turn AND history_id=:id AND status='accepted'
                    AND runtime_epoch=:epoch AND execution_generation=:generation
                RETURNING *
            """),
                    {
                        "status": status,
                        "snapshot": json.dumps(
                            snapshot, ensure_ascii=False, allow_nan=False
                        )
                        if snapshot is not None
                        else None,
                        "version": 1 if snapshot is not None else None,
                        "error": json.dumps(error) if error is not None else None,
                        "turn": token.turn_id,
                        "id": token.history_id,
                        "epoch": token.epoch,
                        "generation": token.generation,
                    },
                )
                .mappings()
                .first()
            )
            if row is None:
                raise HistoryError(
                    "HISTORY_SAVE_UNCONFIRMED", "结果未确认，请刷新历史", 503
                )
            connection.execute(
                text("""
                UPDATE history_records SET active_turn_id=NULL,record_revision=record_revision+1,
                    context_revision=context_revision+:success,
                    last_success_turn_id=CASE WHEN :success=1 THEN :turn ELSE last_success_turn_id END,
                    updated_at=CURRENT_TIMESTAMP WHERE id=:id
            """),
                {
                    "success": int(snapshot is not None),
                    "turn": token.turn_id,
                    "id": token.history_id,
                },
            )
            if execution_id is not None:
                self.executions.finish_in_transaction(
                    connection,
                    owner,
                    execution_id,
                    "succeeded" if snapshot is not None else "failed",
                    error,
                )
            return _turn(row)

    @_database_errors
    def finish_execution_attempt(
        self, owner, token, snapshot, error, execution_id
    ):
        return self.finish_attempt(
            owner, token, snapshot, error, execution_id=execution_id
        )

    @_database_errors
    def turn(self, owner, history_id, turn_id):
        with self.engine.connect() as connection:
            _owned(connection, owner, history_id)
            row = (
                connection.execute(
                    text(
                        "SELECT * FROM history_turns WHERE id=:turn AND history_id=:id"
                    ),
                    {"turn": turn_id, "id": history_id},
                )
                .mappings()
                .first()
            )
            if row is None:
                raise unavailable()
            return _turn(row)

    @_database_errors
    def list_histories(self, owner, kind, limit, cursor, q=""):
        return self._list("history_records", owner, kind, limit, cursor, q)

    @_database_errors
    def list_saved_results(self, owner, kind, limit, cursor, q=""):
        return self._list("saved_results", owner, kind, limit, cursor, q)

    def _list(self, table, owner, kind, limit, cursor, q):
        from base64 import urlsafe_b64decode, urlsafe_b64encode
        from binascii import Error as Base64Error
        from datetime import datetime
        from uuid import UUID

        params = {"owner": owner, "limit": limit + 1}
        clauses = ["owner_user_id=:owner"]
        if table == "history_records":
            clauses.append("deleted_at IS NULL")
        if kind is not None:
            clauses.append("kind=:kind")
            params["kind"] = kind
        if q:
            clauses.append("title ILIKE :search ESCAPE '\\'")
            params["search"] = (
                "%"
                + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                + "%"
            )
        filter_hash = operation_hash({"kind": kind, "q": q, "table": table})
        if cursor is not None:
            try:
                if len(cursor) > 1000:
                    raise ValueError()
                value = json.loads(urlsafe_b64decode(cursor))
                if (
                    set(value) != {"updated_at", "id", "filter"}
                    or value["filter"] != filter_hash
                ):
                    raise ValueError()
                boundary = datetime.fromisoformat(value["updated_at"])
                if boundary.tzinfo is None:
                    raise ValueError()
                params.update(boundary=boundary, boundary_id=str(UUID(value["id"])))
            except (ValueError, TypeError, KeyError, AttributeError, Base64Error):
                raise HistoryError(
                    "INVALID_REQUEST", "分页游标非法，请重新加载列表", 400
                ) from None
            clauses.append("(updated_at,id)<(:boundary,:boundary_id)")
        fields = (
            "*"
            if table == "history_records"
            else ",".join(SavedResultHeader.__dataclass_fields__)
        )
        # SQL identifiers / predicate fragments are internal constants; user values stay bound.
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        "SELECT "  # nosec B608
                        + fields
                        + " FROM "
                        + table
                        + " WHERE "
                        + " AND ".join(clauses)
                        + " ORDER BY updated_at DESC,id DESC LIMIT :limit"
                    ),
                    params,
                )
                .mappings()
                .all()
            )
        encode = _header if table == "history_records" else _saved_header
        items = [encode(row) for row in rows[:limit]]
        next_cursor = None
        if len(rows) > limit:
            last = items[-1]
            next_cursor = urlsafe_b64encode(
                json.dumps(
                    {
                        "updated_at": last.updated_at.isoformat(),
                        "id": last.id,
                        "filter": filter_hash,
                    }
                ).encode()
            ).decode()
        return items, next_cursor

    @_database_errors
    def rename_history(self, owner, history_id, title, revision):
        with self.engine.begin() as connection:
            header = _owned(connection, owner, history_id, lock=True)
            if header["record_revision"] != revision:
                raise stale()
            row = (
                connection.execute(
                    text(
                        "UPDATE history_records SET title=:title, record_revision=record_revision+1, updated_at=CURRENT_TIMESTAMP WHERE id=:id RETURNING *"
                    ),
                    {"id": history_id, "title": title},
                )
                .mappings()
                .one()
            )
            return _header(row)

    @_database_errors
    def delete_history(self, owner, history_id, revision, owner_subject):
        with self.engine.begin() as connection:
            header = _owned(connection, owner, history_id, lock=True)
            if header["active_turn_id"] is not None:
                raise busy()
            if header["record_revision"] != revision:
                raise stale()
            if header["kind"] == "analysis":
                connection.execute(
                    text("""INSERT INTO business_analysis_runs(analysis_run_id, owner_subject, question_sha256, status, expires_at)
                    VALUES (:run,:owner,:hash,'expired',CURRENT_TIMESTAMP)
                    ON CONFLICT(analysis_run_id) DO UPDATE SET status='expired',expires_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP"""),
                    {
                        "run": header["analysis_run_id"],
                        "owner": owner_subject,
                        "hash": sha256(header["first_question"].encode()).hexdigest(),
                    },
                )
            connection.execute(
                text("""UPDATE history_records SET title='',first_question='',last_success_turn_id=NULL,
                active_turn_id=NULL,deleted_at=CURRENT_TIMESTAMP,execution_generation=execution_generation+1,
                record_revision=record_revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=:id"""),
                {"id": history_id},
            )
            connection.execute(
                text("DELETE FROM history_turns WHERE history_id=:id"),
                {"id": history_id},
            )

    @_database_errors
    def copy_result(self, owner, history_id, turn_id, title):
        with self.engine.begin() as connection:
            source = _owned(connection, owner, history_id, lock=True)
            snapshot = connection.execute(
                text(
                    "SELECT snapshot FROM history_turns WHERE history_id=:id AND id=:turn AND status='succeeded'"
                ),
                {"id": history_id, "turn": turn_id},
            ).scalar_one_or_none()
            if snapshot is None:
                raise HistoryError(
                    "HISTORY_RESULT_NOT_SAVABLE", "仅已保存的成功结果可另存", 422
                )
            from src.query_api.history_codec import public_snapshot

            public_snapshot(snapshot)
            row = (
                connection.execute(
                    text("""INSERT INTO saved_results(id,owner_user_id,kind,title,source_history_id,source_turn_id,snapshot_version,snapshot)
                VALUES (:id,:owner,:kind,:title,:history,:turn,1,CAST(:snapshot AS jsonb)) RETURNING *"""),
                    {
                        "id": str(uuid4()),
                        "owner": owner,
                        "kind": source["kind"],
                        "title": title,
                        "history": history_id,
                        "turn": turn_id,
                        "snapshot": json.dumps(
                            snapshot, ensure_ascii=False, allow_nan=False
                        ),
                    },
                )
                .mappings()
                .one()
            )
            return _saved_header(row)

    @_database_errors
    def saved_result(self, owner, result_id):
        with self.engine.connect() as connection:
            row = _owned_saved(connection, owner, result_id)
            return _saved_header(row), row["snapshot"]

    @_database_errors
    def rename_saved_result(self, owner, result_id, title, revision):
        with self.engine.begin() as connection:
            row = _owned_saved(connection, owner, result_id, lock=True)
            if row["record_revision"] != revision:
                raise stale()
            changed = (
                connection.execute(
                    text(
                        "UPDATE saved_results SET title=:title,record_revision=record_revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=:id RETURNING *"
                    ),
                    {"id": result_id, "title": title},
                )
                .mappings()
                .one()
            )
            return _saved_header(changed)

    @_database_errors
    def delete_saved_result(self, owner, result_id, revision):
        with self.engine.begin() as connection:
            row = _owned_saved(connection, owner, result_id, lock=True)
            if row["record_revision"] != revision:
                raise stale()
            connection.execute(
                text("DELETE FROM saved_results WHERE id=:id"), {"id": result_id}
            )

    @_database_errors
    def turns(self, owner, history_id, limit, cursor):
        with self.engine.connect() as connection:
            _owned(connection, owner, history_id)
            rows = (
                connection.execute(
                    text(
                        "SELECT id,history_id,ordinal,question,status,request_id,created_at,public_error FROM history_turns WHERE history_id=:id AND ordinal>:cursor ORDER BY ordinal LIMIT :limit"
                    ),
                    {"id": history_id, "cursor": cursor, "limit": limit + 1},
                )
                .mappings()
                .all()
            )
            return [_turn(row) for row in rows[:limit]], rows[limit - 1][
                "ordinal"
            ] if len(rows) > limit else None
