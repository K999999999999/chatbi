"""Business Analysis Task Adapter 和 Executor 测试。"""

import unittest
from datetime import datetime

from src.business_analysis.contracts import (
    AnalysisPlan,
    AnalysisTask,
    AnalysisTaskType,
    AnalysisTimeRange,
)
from src.business_analysis.execution import (
    TaskExecutor,
    TaskSemanticAdapter,
    TaskSemanticAdapterError,
    TaskStatus,
)
from src.online_query.contracts import QueryErrorCode, QueryFailure, QuerySuccess
from src.online_query.query_understanding import QueryType, TimeGranularity

NOW = datetime(2026, 9, 21, 12, 0)


class TaskExecutionTest(unittest.TestCase):
    def test_adapter_builds_canonical_query_request(self) -> None:
        task = _task(
            "root",
            metrics=("人民币净销售额",),
            dimensions=("销售区域",),
        )

        request = TaskSemanticAdapter().to_query_request(
            task,
            request_id="analysis:root",
            now=NOW,
        )

        self.assertEqual(request.request_id, "analysis:root")
        self.assertIn("指标=人民币净销售额", request.question)
        self.assertIn("维度=销售区域", request.question)
        self.assertNotIn("SELECT", request.question.upper())
        self.assertIsNotNone(request.semantic_query)
        assert request.semantic_query is not None
        self.assertEqual(request.semantic_query.query_type, QueryType.METRIC_ANALYSIS)
        self.assertEqual(request.semantic_query.original_question, request.question)
        self.assertIsNone(request.semantic_query.time)
        self.assertIn("时间=无", request.question)

    def test_canonical_comparison_question_drops_discrete_time_range(self) -> None:
        task = AnalysisTask(
            task_id="comparison",
            task_type=AnalysisTaskType.COMPARISON,
            description="比较年份",
            metrics=("人民币净销售额",),
            dimensions=("年份",),
            time_range=AnalysisTimeRange(
                text="2024年和2025年",
                granularity=TimeGranularity.YEAR,
            ),
            filters=(),
            depends_on=(),
            expected_output="年度比较",
        )

        request = TaskSemanticAdapter().to_query_request(task, now=NOW)

        self.assertIn("维度=年份", request.question)
        self.assertIn("时间=无", request.question)
        self.assertNotIn("2024年和2025年", request.question)

    def test_adapter_rejects_invalid_semantics_before_query(self) -> None:
        task = _task("invalid", metrics=())

        with self.assertRaises(TaskSemanticAdapterError) as raised:
            TaskSemanticAdapter().to_query_request(task)

        self.assertEqual(raised.exception.reason, "METRIC_REQUIRED")

    def test_comparison_by_year_does_not_use_discrete_years_as_one_range(self) -> None:
        task = AnalysisTask(
            task_id="comparison",
            task_type=AnalysisTaskType.COMPARISON,
            description="比较两个年份",
            metrics=("人民币净销售额",),
            dimensions=("年份",),
            time_range=AnalysisTimeRange(
                text="2024年和2025年",
                granularity=TimeGranularity.YEAR,
            ),
            filters=(),
            depends_on=(),
            expected_output="按年份比较",
        )

        request = TaskSemanticAdapter().to_query_request(task, now=NOW)

        self.assertIsNotNone(request.semantic_query)
        assert request.semantic_query is not None
        self.assertIsNone(request.semantic_query.time)

    def test_executor_runs_dependencies_serially_and_skips_downstream_failure(
        self,
    ) -> None:
        service = _BoundQueryService(
            [
                QueryFailure(
                    request_id="analysis:root",
                    error_code=QueryErrorCode.DATABASE_ERROR,
                    error_message="数据库暂时不可用",
                    internal_reason="DATABASE_CONNECTION_LOST",
                ),
                QuerySuccess(
                    request_id="analysis:independent",
                    sql="SELECT 1",
                    columns=("value",),
                    rows=((1,),),
                    row_count=1,
                    truncated=False,
                ),
            ]
        )
        plan = AnalysisPlan(
            tasks=(
                _task("root"),
                _task("dependent", depends_on=("root",)),
                _task("independent"),
            )
        )

        results = TaskExecutor(service, TaskSemanticAdapter()).execute(
            plan,
            request_id="analysis",
            now=NOW,
        )

        self.assertEqual(
            [request.question for request in service.requests],
            [
                "指标=人民币净销售额；维度=无；时间=无；筛选=无",
                "指标=人民币净销售额；维度=无；时间=无；筛选=无",
            ],
        )
        self.assertEqual(
            [result.status for result in results],
            [TaskStatus.FAILED, TaskStatus.SKIPPED, TaskStatus.COMPLETED],
        )
        self.assertEqual(results[1].error.code, "DEPENDENCY_FAILED")
        self.assertEqual(results[2].row_count, 1)
        self.assertNotIn("database", results[0].error.message.lower())
        self.assertEqual(
            results[0].error.internal_reason,
            "DATABASE_CONNECTION_LOST",
        )

    def test_empty_result_is_completed_and_does_not_skip_ready_task(self) -> None:
        service = _BoundQueryService(
            [
                QuerySuccess(
                    request_id="analysis:root",
                    sql="SELECT 1",
                    columns=("value",),
                    rows=(),
                    row_count=0,
                    truncated=False,
                ),
                QuerySuccess(
                    request_id="analysis:child",
                    sql="SELECT 1",
                    columns=("value",),
                    rows=((2,),),
                    row_count=1,
                    truncated=False,
                ),
            ]
        )
        plan = AnalysisPlan(tasks=(_task("root"), _task("child", depends_on=("root",))))

        results = TaskExecutor(service, TaskSemanticAdapter()).execute(
            plan,
            request_id="analysis",
            now=NOW,
        )

        self.assertEqual(
            [result.status for result in results],
            [TaskStatus.COMPLETED, TaskStatus.COMPLETED],
        )
        self.assertEqual(len(service.requests), 2)


class _BoundQueryService:
    def __init__(self, outcomes: list[QuerySuccess | QueryFailure]) -> None:
        self.outcomes = outcomes
        self.requests = []

    def query(self, request):
        self.requests.append(request)
        if not self.outcomes:
            raise AssertionError("missing query outcome")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, QuerySuccess):
            return QuerySuccess(
                request_id=request.request_id or outcome.request_id,
                sql=outcome.sql,
                columns=outcome.columns,
                rows=outcome.rows,
                row_count=outcome.row_count,
                truncated=outcome.truncated,
                semantic_query=request.semantic_query,
            )
        return QueryFailure(
            request_id=request.request_id or outcome.request_id,
            error_code=outcome.error_code,
            error_message=outcome.error_message,
            failure_stage=outcome.failure_stage,
            internal_reason=outcome.internal_reason,
        )


def _task(
    task_id: str,
    *,
    metrics: tuple[str, ...] = ("人民币净销售额",),
    dimensions: tuple[str, ...] = (),
    time_range: AnalysisTimeRange | None = None,
    depends_on: tuple[str, ...] = (),
) -> AnalysisTask:
    return AnalysisTask(
        task_id=task_id,
        task_type=AnalysisTaskType.BASELINE,
        description="查询业务指标",
        metrics=metrics,
        dimensions=dimensions,
        time_range=time_range,
        filters=(),
        depends_on=depends_on,
        expected_output="结构化查询结果",
    )


if __name__ == "__main__":
    unittest.main()
