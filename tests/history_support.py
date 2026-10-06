"""浏览器HTTP的确定性Port替身；事务正确性由隔离PG验证。"""

from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.query_api.execution_contracts import ExecutionAcceptance, ExecutionRecord
from src.query_api.history_codec import public_snapshot
from src.query_api.history_contracts import (
    AcceptedAttempt,
    ExecutionToken,
    HistoryError,
    HistoryHeader,
    HistoryTurn,
    SavedResultHeader,
    busy,
    stale,
    unavailable,
)


class BrowserHistoryRuntime:
    epoch = "browser-test-epoch"

    def __init__(self, store):
        self.store, self.running = store, set()

    def check(self):
        pass

    @contextmanager
    def executing(self, id):
        if id in self.running:
            raise busy()
        self.running.add(id)
        try:
            yield
        finally:
            self.running.remove(id)

    def reserve(self, id):
        if id in self.running:
            raise busy()
        self.running.add(id)
        runtime = self

        class Lease:
            released = False

            def release(self):
                if self.released:
                    return
                self.released = True
                runtime.running.discard(id)

        return Lease()

    def reconcile(self, id):
        if id not in self.running:
            owner, h = self.store.headers[id]
            if h.active_turn_id:
                t = self.store.turn_data[h.active_turn_id]
                self.store.turn_data[t.id] = replace(t, status="unconfirmed")
                self.store.headers[id] = (
                    owner,
                    replace(
                        h, active_turn_id=None, record_revision=h.record_revision + 1
                    ),
                )


class BrowserHistoryStore:
    def __init__(self):
        self.headers, self.turn_data, self.results = {}, {}, {}
        self.executions, self.operations, self.operation_hashes = {}, {}, {}
        self.completed_times = {}

    def create(self, owner, kind, question, operation_id, *, id=None, title=None):
        now = datetime.now(UTC)
        h = HistoryHeader(
            id or str(uuid4()),
            kind,
            (title or question)[:120],
            question,
            now,
            now,
            0,
            0,
            None,
            None,
            str(uuid4()) if kind == "analysis" else None,
        )
        self.headers[h.id] = (owner, h)
        return h

    def header(self, owner, id):
        row = self.headers.get(id)
        if row is None or row[0] != owner:
            raise unavailable()
        return row[1]

    def begin_attempt(
        self, owner, id, question, operation_id, revision, request_id, epoch
    ):
        h = self.header(owner, id)
        if h.active_turn_id:
            raise busy()
        if h.context_revision != revision:
            raise stale()
        ordinal = 1 + max(
            (t.ordinal for t in self.turn_data.values() if t.history_id == id),
            default=0,
        )
        t = HistoryTurn(
            str(uuid4()),
            id,
            ordinal,
            question,
            "accepted",
            request_id,
            datetime.now(UTC),
            None,
            None,
        )
        self.turn_data[t.id] = t
        self.headers[id] = (
            owner,
            replace(h, active_turn_id=t.id, record_revision=h.record_revision + 1),
        )
        state = (
            self.turn_data[h.last_success_turn_id].snapshot.get("query_state")
            if h.last_success_turn_id
            else None
        )
        return AcceptedAttempt(ExecutionToken(id, t.id, epoch, ordinal), t, state)

    def begin_analysis_attempt(
        self, owner, id, operation_id, revision, request_id, epoch
    ):
        h = self.header(owner, id)
        if h.record_revision != revision:
            raise stale()
        return self.begin_attempt(
            owner,
            id,
            h.first_question,
            operation_id,
            h.context_revision,
            request_id,
            epoch,
        )

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
        expected_record_revision,
    ):
        existing = self.execution_by_operation(owner, operation_id, request_hash)
        if existing is not None:
            return ExecutionAcceptance(existing, None, False)
        if mode == "query":
            attempt = self.begin_attempt(
                owner, history_id, question, operation_id, revision, request_id, epoch
            )
        else:
            if expected_record_revision is None:
                raise HistoryError("INVALID_REQUEST", "分析恢复版本缺失", 400)
            attempt = self.begin_analysis_attempt(
                owner,
                history_id,
                operation_id,
                expected_record_revision,
                request_id,
                epoch,
            )
        execution = self._create_execution(
            owner,
            history_id,
            attempt.turn.id,
            operation_id,
            request_hash,
            mode,
            operation_kind,
            deadline_seconds,
        )
        self.turn_data[attempt.turn.id] = replace(
            attempt.turn, execution_id=execution.id
        )
        return ExecutionAcceptance(
            execution, replace(attempt, turn=self.turn_data[attempt.turn.id]), True
        )

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
        existing = self.execution_by_operation(owner, operation_id, request_hash)
        if existing is not None:
            history = self.header(owner, existing.history_id)
            turn = self.turn(owner, existing.history_id, existing.turn_id)
            return history, AcceptedAttempt(None, turn, None), existing, False
        history, attempt = self.begin_requery(
            owner,
            source_kind,
            source_id,
            source_turn_id,
            operation_id,
            request_id,
            epoch,
            new_id,
        )
        if analysis_run_id is not None:
            history = replace(history, analysis_run_id=analysis_run_id)
            self.headers[history.id] = (owner, history)
        execution = self._create_execution(
            owner,
            history.id,
            attempt.turn.id,
            operation_id,
            request_hash,
            history.kind,
            operation_kind,
            deadline_seconds,
        )
        turn = replace(self.turn_data[attempt.turn.id], execution_id=execution.id)
        self.turn_data[turn.id] = turn
        return history, replace(attempt, turn=turn), execution, True

    def _create_execution(
        self,
        owner,
        history_id,
        turn_id,
        operation_id,
        request_hash,
        mode,
        operation_kind,
        deadline_seconds,
    ):
        now = datetime.now(UTC)
        execution = ExecutionRecord(
            str(uuid4()),
            history_id,
            turn_id,
            operation_id,
            mode,
            operation_kind,
            "accepted",
            None,
            now,
            None,
            now + timedelta(seconds=deadline_seconds),
            None,
            None,
            None,
        )
        self.executions[execution.id] = (owner, request_hash, execution)
        self.operations[(owner, operation_id)] = execution.id
        self.operation_hashes[(owner, operation_id)] = request_hash
        return execution

    def execution(self, owner, execution_id):
        row = self.executions.get(execution_id)
        if row is None or row[0] != owner:
            raise unavailable()
        return row[2]

    def execution_by_operation(self, owner, operation_id, request_hash=None):
        execution_id = self.operations.get((owner, operation_id))
        if execution_id is None:
            return None
        if (
            request_hash is not None
            and self.operation_hashes[(owner, operation_id)] != request_hash
        ):
            raise HistoryError(
                "HISTORY_OPERATION_CONFLICT", "操作编号与原请求不匹配", 409
            )
        return self.execution(owner, execution_id)

    def mark_execution_running(self, owner, execution_id):
        execution = self.execution(owner, execution_id)
        if execution.status == "accepted":
            updated = replace(execution, status="running", started_at=datetime.now(UTC))
            row = self.executions[execution_id]
            self.executions[execution_id] = (row[0], row[1], updated)

    def finish_execution_attempt(self, owner, token, snapshot, error, execution_id):
        turn = self.finish_attempt(owner, token, snapshot, error)
        execution = self.execution(owner, execution_id)
        updated = replace(
            execution,
            status="succeeded" if snapshot is not None else "failed",
            public_error=error,
            finished_at=datetime.now(UTC),
        )
        row = self.executions[execution_id]
        self.executions[execution_id] = (row[0], row[1], updated)
        self.turn_data[turn.id] = replace(turn, execution_id=execution_id)
        return self.turn_data[turn.id]

    def finish_attempt(self, owner, token, snapshot, error):
        h = self.header(owner, token.history_id)
        t = replace(
            self.turn_data[token.turn_id],
            status="succeeded" if snapshot else "failed",
            snapshot=snapshot,
            public_error=error,
        )
        if snapshot:
            self.completed_times[t.id] = datetime.now(UTC)
        else:
            self.completed_times.pop(t.id, None)
        self.turn_data[t.id] = t
        self.headers[h.id] = (
            owner,
            replace(
                h,
                active_turn_id=None,
                context_revision=h.context_revision + int(snapshot is not None),
                record_revision=h.record_revision + 1,
                last_success_turn_id=t.id if snapshot else h.last_success_turn_id,
                updated_at=datetime.now(UTC),
            ),
        )
        return t

    def seed_successful_query(self, owner, question, snapshot, *, title):
        now = datetime.now(UTC)
        header = self.create(owner, "query", question, str(uuid4()), title=title)
        turn = HistoryTurn(
            str(uuid4()),
            header.id,
            1,
            question,
            "succeeded",
            str(uuid4()),
            now,
            None,
            snapshot,
        )
        self.turn_data[turn.id] = turn
        self.completed_times[turn.id] = now
        self.headers[header.id] = (
            owner,
            replace(
                header,
                context_revision=1,
                record_revision=1,
                last_success_turn_id=turn.id,
            ),
        )
        return header, turn

    def turn(self, owner, id, turn_id):
        self.header(owner, id)
        t = self.turn_data.get(turn_id)
        if t is None or t.history_id != id:
            raise unavailable()
        return t

    def turns(self, owner, id, limit, cursor):
        self.header(owner, id)
        items = sorted(
            (
                t
                for t in self.turn_data.values()
                if t.history_id == id and t.ordinal > cursor
            ),
            key=lambda t: t.ordinal,
        )
        return [replace(t, snapshot=None) for t in items[:limit]], items[
            limit - 1
        ].ordinal if len(items) > limit else None

    def list_histories(self, owner, kind, limit, cursor, q=""):
        items = [
            h
            for o, h in self.headers.values()
            if o == owner
            and (kind is None or h.kind == kind)
            and q.lower() in h.title.lower()
        ]
        return sorted(items, key=lambda h: (h.updated_at, h.id), reverse=True)[
            :limit
        ], None

    def rename_history(self, owner, id, title, revision):
        h = self.header(owner, id)
        if h.record_revision != revision:
            raise stale()
        h = replace(h, title=title, record_revision=h.record_revision + 1)
        self.headers[id] = (owner, h)
        return h

    def delete_history(self, owner, id, revision, owner_subject):
        h = self.header(owner, id)
        if h.active_turn_id:
            raise busy()
        if h.record_revision != revision:
            raise stale()
        del self.headers[id]
        self.turn_data = {
            key: t for key, t in self.turn_data.items() if t.history_id != id
        }

    def copy_result(self, owner, id, turn_id, title):
        t, h = self.turn(owner, id, turn_id), self.header(owner, id)
        if t.status != "succeeded":
            raise HistoryError("HISTORY_RESULT_NOT_SAVABLE", "仅成功结果可另存", 422)
        now = datetime.now(UTC)
        result = SavedResultHeader(
            str(uuid4()), h.kind, title, 0, now, now, id, turn_id
        )
        self.results[result.id] = (owner, result, t.snapshot)
        return result

    def saved_result(self, owner, id):
        row = self.results.get(id)
        if row is None or row[0] != owner:
            raise unavailable()
        return row[1], row[2]

    def export_snapshot(self, owner, source_kind, source_id, turn_id=None):
        if source_kind == "history_turn":
            header = self.header(owner, source_id)
            turn = self.turn(owner, source_id, turn_id)
            if turn.status != "succeeded" or turn.snapshot is None:
                raise unavailable()
            envelope = turn.snapshot
            question = turn.question
            completed_at = self.completed_times.get(turn.id)
            result_time = completed_at.isoformat() if completed_at else None
            saved_time = None
            title = header.title
        elif source_kind == "saved_result" and turn_id is None:
            saved, envelope = self.saved_result(owner, source_id)
            question = envelope.get("source_question") or envelope.get(
                "original_question"
            )
            result_time = None
            saved_time = saved.created_at.isoformat()
            title = saved.title
        else:
            raise unavailable()
        kind = envelope.get("kind")
        result = public_snapshot(envelope)
        if kind == "query":
            result = {key: value for key, value in result.items() if key != "sql"}
        return {
            "kind": kind,
            "title": title,
            "question": question,
            "result_time": result_time,
            "saved_time": saved_time,
            "result": result,
        }

    def list_saved_results(self, owner, kind, limit, cursor, q=""):
        return [
            h
            for o, h, _ in self.results.values()
            if o == owner
            and (kind is None or h.kind == kind)
            and q.lower() in h.title.lower()
        ][:limit], None

    def rename_saved_result(self, owner, id, title, revision):
        h, snapshot = self.saved_result(owner, id)
        if h.record_revision != revision:
            raise stale()
        h = replace(h, title=title, record_revision=h.record_revision + 1)
        self.results[id] = (owner, h, snapshot)
        return h

    def delete_saved_result(self, owner, id, revision):
        h, _ = self.saved_result(owner, id)
        if h.record_revision != revision:
            raise stale()
        del self.results[id]

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
    ):
        history_title = None
        if source_kind == "saved":
            source, snapshot = self.saved_result(owner, source_id)
            kind = source.kind
            history_title = source.title
            if kind == "query":
                question = snapshot.get("source_question") or (
                    "根据已保存的完整查询条件重新查询"
                )
            else:
                question = snapshot.get("original_question")
        else:
            source = self.header(owner, source_id)
            kind = source.kind
            if kind == "analysis":
                question = source.first_question
                snapshot = {"original_question": question}
            else:
                turn = self.turn(owner, source_id, source_turn_id)
                question, snapshot = turn.question, turn.snapshot
        h = self.create(
            owner, kind, question, operation_id, id=new_id, title=history_title
        )
        accepted = self.begin_attempt(
            owner, h.id, question, operation_id, 0, request_id, epoch
        )
        return h, replace(
            accepted, base_state=snapshot.get("query_state"), source_snapshot=snapshot
        )
