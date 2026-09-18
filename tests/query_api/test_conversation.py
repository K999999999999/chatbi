"""Query API/Application 短期会话 Adapter 测试。"""

from datetime import UTC, datetime, timedelta
from unittest import TestCase

from src.query_api.conversation import (
    ConversationConflictError,
    ConversationUnavailableError,
    InMemoryConversationStore,
)


class _TestClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 9, 18, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.current

    def advance(self, duration: timedelta) -> None:
        self.current += duration


class InMemoryConversationStoreTest(TestCase):
    def test_commit_updates_success_time_and_keeps_structured_state_opaque(
        self,
    ) -> None:
        clock = _TestClock()
        store = InMemoryConversationStore(clock=clock)
        created = store.create(subject_id="analyst-1")
        lease = store.acquire(
            created.conversation_id,
            subject_id="analyst-1",
        )
        structured_state = {"metric": "net_sales", "dimensions": ("region",)}
        clock.advance(timedelta(seconds=1))

        committed = store.commit(
            lease,
            structured_query_state=structured_state,
        )
        next_lease = store.acquire(
            created.conversation_id,
            subject_id="analyst-1",
        )

        self.assertEqual(committed.structured_query_state, structured_state)
        self.assertEqual(next_lease.record.structured_query_state, structured_state)
        self.assertEqual(committed.last_success_at, clock.current)
        store.abort(next_lease)

    def test_abort_releases_only_in_flight_turn_without_changing_state(self) -> None:
        store = InMemoryConversationStore()
        created = store.create(subject_id="analyst-1")
        first_lease = store.acquire(
            created.conversation_id,
            subject_id="analyst-1",
        )

        with self.assertRaises(ConversationConflictError):
            store.acquire(created.conversation_id, subject_id="analyst-1")

        store.abort(first_lease)
        second_lease = store.acquire(
            created.conversation_id,
            subject_id="analyst-1",
        )

        self.assertEqual(second_lease.record.last_success_at, created.last_success_at)
        self.assertIsNone(second_lease.record.structured_query_state)
        store.abort(second_lease)

    def test_unknown_expired_and_other_user_conversations_are_unavailable(self) -> None:
        clock = _TestClock()
        store = InMemoryConversationStore(clock=clock)
        created = store.create(subject_id="analyst-1")

        with self.assertRaises(ConversationUnavailableError):
            store.acquire("unknown", subject_id="analyst-1")
        with self.assertRaises(ConversationUnavailableError):
            store.acquire(created.conversation_id, subject_id="analyst-2")

        clock.advance(timedelta(minutes=30))
        with self.assertRaises(ConversationUnavailableError):
            store.acquire(created.conversation_id, subject_id="analyst-1")


if __name__ == "__main__":
    import unittest

    unittest.main()
