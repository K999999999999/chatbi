"""浏览器HTTP的确定性Port替身；事务正确性由隔离PG验证。"""

from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

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

    def finish_attempt(self, owner, token, snapshot, error):
        h = self.header(owner, token.history_id)
        t = replace(
            self.turn_data[token.turn_id],
            status="succeeded" if snapshot else "failed",
            snapshot=snapshot,
            public_error=error,
        )
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
