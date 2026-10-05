"""查询结果说明通过实际任务执行、API边界和Checkpoint，不进入报告提示。"""

from datetime import datetime
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from src.business_analysis.contracts import AnalysisPlan
from src.business_analysis.execution import (
    TaskExecutor,
    TaskSemanticAdapter,
    TaskResult,
    TaskStatus,
)
from src.business_analysis.runtime import _checkpoint_allowed_types
from src.online_query.contracts import QuerySuccess
from src.online_query.result_contracts import ResultMetadata
from src.query_api.query_response import (
    analysis_task_result_payload as _analysis_task_result_payload,
)
from tests.business_analysis.test_execution import _task


def test_query_metadata_survives_task_api_and_checkpoint():
    metadata = ResultMetadata.from_payload(
        {"version": 1, "columns": [], "scope": {}, "time_axis": None}
    )

    class Service:
        def query(self, request):
            return QuerySuccess(
                request.request_id,
                "SELECT 1",
                ("value",),
                ((1,),),
                1,
                False,
                result_metadata=metadata,
            )

    service = Service()
    task = TaskExecutor(service, TaskSemanticAdapter()).execute(
        AnalysisPlan(tasks=(_task("root"),)),
        request_id="analysis",
        now=datetime(2026, 9, 21),
    )[0]
    assert task.result_metadata == metadata
    assert (
        _analysis_task_result_payload(task)["result_metadata"] == metadata.to_payload()
    )
    serde = JsonPlusSerializer(allowed_msgpack_modules=_checkpoint_allowed_types())
    restored = serde.loads_typed(serde.dumps_typed(task))
    assert restored.result_metadata == metadata


def test_old_task_without_metadata_keeps_public_shape_and_loads():
    task = TaskResult("old", TaskStatus.COMPLETED, ("value",), ((1,),), 1)
    assert "result_metadata" not in _analysis_task_result_payload(task)
    serde = JsonPlusSerializer(allowed_msgpack_modules=_checkpoint_allowed_types())
    restored = serde.loads_typed(serde.dumps_typed(task))
    assert restored.result_metadata is None


def test_checkpoint_written_before_optional_field_remains_readable():
    from dataclasses import make_dataclass
    from src.business_analysis.execution import TaskError

    legacy_type = make_dataclass(
        "TaskResult",
        [
            ("task_id", str),
            ("status", TaskStatus),
            ("columns", tuple),
            ("rows", tuple),
            ("row_count", int),
            ("truncated", bool),
            ("error", TaskError | None),
        ],
        frozen=True,
        slots=True,
    )
    legacy_type.__module__ = "src.business_analysis.execution"
    legacy = legacy_type(
        "old", TaskStatus.COMPLETED, ("value",), ((1,),), 1, False, None
    )
    serde = JsonPlusSerializer(allowed_msgpack_modules=_checkpoint_allowed_types())
    restored = serde.loads_typed(serde.dumps_typed(legacy))
    assert isinstance(restored, TaskResult)
    assert restored.result_metadata is None
    assert [list(row) for row in restored.rows] == [[1]]
