"""进度事件共享缓冲、快照衔接与订阅限额。"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.query_api.execution_contracts import ExecutionRecord
from src.query_api.execution_events import (
    ExecutionEventChannel,
    ExecutionSubscriberLimit,
)


def execution():
    now = datetime.now(UTC)
    return ExecutionRecord(
        id=str(uuid4()),
        history_id=str(uuid4()),
        turn_id=str(uuid4()),
        operation_id=str(uuid4()),
        mode="analysis",
        operation_kind="analysis_resume",
        status="accepted",
        stop_reason=None,
        created_at=now,
        started_at=None,
        deadline_at=now + timedelta(minutes=20),
        stop_requested_at=None,
        finished_at=None,
        public_error=None,
    )


def test_subscriber_receives_atomic_snapshot_then_ordered_progress():
    channel = ExecutionEventChannel(execution())
    subscription = channel.subscribe()
    channel.set_status("running")
    channel.set_stage("analysis_query_tasks")
    channel.set_task_progress(1, 3)

    assert subscription.snapshot["type"] == "snapshot"
    assert subscription.snapshot["sequence"] == 0
    events = subscription.read(timeout=0)
    assert [event["sequence"] for event in events] == [1, 2, 3]
    assert [event["type"] for event in events] == ["progress"] * 3
    assert events[-1]["payload"] == {
        "stage": "analysis_query_tasks",
        "completed_tasks": 1,
        "total_tasks": 3,
    }
    subscription.close()


def test_slow_reader_resynchronizes_from_latest_snapshot_after_ring_overflow():
    channel = ExecutionEventChannel(execution(), max_events=4, max_bytes=4096)
    subscription = channel.subscribe()
    for index in range(7):
        channel.set_stage("analysis_report_generation")
        channel.set_task_progress(index, 7)

    events = subscription.read(timeout=0)
    assert len(events) == 1
    assert events[0]["type"] == "snapshot"
    assert events[0]["sequence"] == 14
    assert events[0]["payload"]["completed_tasks"] == 6
    subscription.close()


def test_shared_buffer_caps_active_subscribers_and_releases_slots():
    channel = ExecutionEventChannel(execution(), max_subscribers=2)
    first = channel.subscribe()
    second = channel.subscribe()
    with pytest.raises(ExecutionSubscriberLimit):
        channel.subscribe()

    first.close()
    third = channel.subscribe()
    third.close()
    second.close()


def test_default_subscriber_limit_is_eight():
    channel = ExecutionEventChannel(execution())
    subscriptions = [channel.subscribe() for _ in range(8)]
    with pytest.raises(ExecutionSubscriberLimit):
        channel.subscribe()

    for subscription in subscriptions:
        subscription.close()


def test_default_ring_retains_at_most_64_frames_and_resynchronizes():
    channel = ExecutionEventChannel(execution())
    subscription = channel.subscribe()
    for _ in range(100):
        channel.set_stage("analysis_report_generation")

    assert len(channel._ring) == 64
    assert channel.ring_bytes <= 1024 * 1024
    events = subscription.read(timeout=0)
    assert len(events) == 1
    assert events[0]["type"] == "snapshot"
    assert events[0]["sequence"] == 100
    subscription.close()


def test_ring_byte_limit_evicts_old_frames_and_keeps_one_snapshot():
    channel = ExecutionEventChannel(execution(), max_events=100, max_bytes=512)
    subscription = channel.subscribe()
    for _ in range(10):
        channel.set_stage("analysis_report_generation")

    assert channel.ring_bytes <= 512
    events = subscription.read(timeout=0)
    assert len(events) == 1
    assert events[0]["type"] == "snapshot"
    assert events[0]["sequence"] == 10
    subscription.close()


def test_terminal_event_is_included_in_reconnect_snapshot_and_closes_channel():
    channel = ExecutionEventChannel(execution())
    subscription = channel.subscribe()
    channel.finish("succeeded")
    events = subscription.read(timeout=0)

    assert events[-1]["type"] == "terminal"
    assert events[-1]["payload"]["status"] == "succeeded"
    assert channel.terminal
    subscription.close()
