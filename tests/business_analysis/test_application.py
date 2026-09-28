"""经营分析 StateGraph 公共应用行为测试。"""

import unittest
from uuid import UUID

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from src.authorization.contracts import AuthContext
from src.business_analysis.application import (
    BusinessAnalysisApplication,
    BusinessAnalysisSuccess,
)
from src.business_analysis.contracts import (
    AnalysisDecompositionContext,
    AnalysisRequestCandidate,
    AnalysisTimeRange,
)
from src.business_analysis.execution import TaskStatus
from src.business_analysis.reporting import BusinessAnalysisReport
from src.business_analysis.run_store import AnalysisRun, AnalysisRunStatus
from src.business_analysis.runtime import _checkpoint_allowed_types
from src.online_query.contracts import QueryErrorCode, QueryFailure, QuerySuccess
from src.online_query.query_understanding import TimeGranularity

_DEFAULT_PERIOD = AnalysisTimeRange("2025年2月", TimeGranularity.MONTH)


class BusinessAnalysisApplicationTest(unittest.TestCase):
    def test_graph_builds_fixed_tasks_and_executes_each_through_authorized_query(
        self,
    ) -> None:
        bound = _BoundService()
        authorized = _AuthorizedService(bound)
        decomposer = _Decomposer(_candidate())
        summarizer = _Summarizer()
        application = _application(authorized, decomposer, summarizer)

        result = application.analyze(
            "2025年3月毛利为什么比2月下降？",
            request_id="analysis-1",
            auth_context="auth-context",
        )

        self.assertIsInstance(result, BusinessAnalysisSuccess)
        self.assertEqual(result.request_id, "analysis-1")
        self.assertEqual(result.report.title, "分析报告")
        self.assertEqual(result.attribution.total_change, 0)
        self.assertEqual(
            result.report.to_payload()["attribution"]["reconciliation_passed"],
            True,
        )
        self.assertEqual(len(result.plan.tasks), 4)
        self.assertEqual(len(bound.requests), 4)
        self.assertTrue(
            all(item.status is TaskStatus.COMPLETED for item in result.task_results)
        )
        self.assertEqual(authorized.bound_contexts, ["auth-context"] * 4)
        self.assertEqual(decomposer.questions, ["2025年3月毛利为什么比2月下降？"])
        self.assertEqual(summarizer.inputs[0][0], "2025年3月毛利为什么比2月下降？")
        self.assertEqual(summarizer.inputs[0][2], result.attribution)
        self.assertEqual(
            [request.semantic_query.metrics for request in bound.requests],
            [
                ("人民币毛利",),
                ("人民币毛利",),
                ("人民币净销售额", "已完成销售数量", "人民币销售成本"),
                ("人民币净销售额", "已完成销售数量", "人民币销售成本"),
            ],
        )
        self.assertEqual(
            [request.semantic_query.dimensions for request in bound.requests],
            [(), (), ("产品",), ("产品",)],
        )
        self.assertEqual(
            [request.semantic_query.time.text for request in bound.requests],
            ["2025年2月", "2025年3月", "2025年2月", "2025年3月"],
        )

    def test_ambiguous_profit_is_clarified_before_query_or_summary(self) -> None:
        bound = _BoundService()
        summarizer = _Summarizer()
        application = _application(
            _AuthorizedService(bound),
            _Decomposer(_candidate(metric_text="利润")),
            summarizer,
        )

        result = application.analyze(
            "2025年利润为什么比2024年下降？",
            request_id="analysis-profit",
            auth_context="auth-context",
        )

        self.assertIsInstance(result, QueryFailure)
        self.assertEqual(result.request_id, "analysis-profit")
        self.assertEqual(result.error_code, QueryErrorCode.CLARIFICATION_REQUIRED)
        self.assertEqual(result.internal_reason, "METRIC_NOT_UNIQUE")
        self.assertEqual(bound.requests, [])
        self.assertEqual(summarizer.inputs, [])

    def test_unsupported_region_breakdown_is_refused_before_query_or_summary(
        self,
    ) -> None:
        bound = _BoundService()
        summarizer = _Summarizer()
        application = _application(
            _AuthorizedService(bound),
            _Decomposer(_candidate()),
            summarizer,
        )

        result = application.analyze(
            "2025年3月毛利为什么比2月下降？请按销售区域拆解原因。",
            request_id="analysis-region",
            auth_context="auth-context",
        )

        self.assertIsInstance(result, QueryFailure)
        self.assertEqual(result.error_code, QueryErrorCode.CANNOT_ANSWER)
        self.assertEqual(result.internal_reason, "DIMENSION_UNSUPPORTED")
        self.assertEqual(bound.requests, [])
        self.assertEqual(summarizer.inputs, [])

    def test_missing_comparison_period_is_clarified_before_query(self) -> None:
        candidate = _candidate(comparison_period=None)
        bound = _BoundService()
        application = _application(
            _AuthorizedService(bound),
            _Decomposer(candidate),
            _Summarizer(),
        )

        result = application.analyze(
            "2025年毛利为什么变化？",
            request_id="analysis-period",
            auth_context="auth-context",
        )

        self.assertIsInstance(result, QueryFailure)
        self.assertEqual(result.error_code, QueryErrorCode.CLARIFICATION_REQUIRED)
        self.assertEqual(result.internal_reason, "COMPARISON_PERIOD_REQUIRED")
        self.assertEqual(bound.requests, [])

    def test_failed_query_does_not_call_summary_model(self) -> None:
        bound = _BoundService(fail_count=2)
        summarizer = _Summarizer()
        application = _application(
            _AuthorizedService(bound),
            _Decomposer(_candidate()),
            summarizer,
        )

        result = application.analyze(
            "2025年3月毛利为什么比2月下降？",
            request_id="analysis-failed",
            auth_context="auth-context",
        )

        self.assertIsInstance(result, QueryFailure)
        self.assertEqual(result.error_code, QueryErrorCode.CANNOT_ANSWER)
        self.assertEqual(result.internal_reason, "ANALYSIS_TASK_FAILED")
        self.assertEqual(summarizer.inputs, [])
        self.assertEqual(len(bound.requests), 2)

    def test_reconciliation_failure_does_not_call_summary_model(self) -> None:
        bound = _BoundService(overall_value=1)
        summarizer = _Summarizer()
        application = _application(
            _AuthorizedService(bound),
            _Decomposer(_candidate()),
            summarizer,
        )

        result = application.analyze(
            "2025年3月毛利为什么比2月下降？",
            request_id="analysis-reconcile",
            auth_context="auth-context",
        )

        self.assertIsInstance(result, QueryFailure)
        self.assertEqual(
            result.internal_reason,
            "PERIOD_TOTAL_RECONCILIATION_FAILED",
        )
        self.assertEqual(summarizer.inputs, [])

    def test_retry_resumes_from_checkpoint_without_repeating_completed_tasks(
        self,
    ) -> None:
        bound = _BoundService(fail_count=2)
        authorized = _AuthorizedService(bound)
        decomposer = _Decomposer(_candidate())
        summarizer = _Summarizer()
        saver = MemorySaver(
            serde=JsonPlusSerializer(
                allowed_msgpack_modules=_checkpoint_allowed_types()
            )
        )
        run_store = _RunStore()
        auth_context = AuthContext(
            subject_id="user-1",
            identity_provider="test-provider",
        )
        first_app = _application(
            authorized,
            decomposer,
            summarizer,
            checkpointer=saver,
            run_store=run_store,
        )
        run_id = "f5607b24-84cf-4f09-b7c5-9ea5a332e225"

        first_result = first_app.analyze(
            "2025年3月毛利为什么比2月下降？",
            request_id="request-first",
            auth_context=auth_context,
            analysis_run_id=run_id,
        )
        self.assertIsInstance(first_result, QueryFailure)
        self.assertEqual(len(bound.requests), 2)
        self.assertEqual(run_store.completed, set())

        resumed_app = _application(
            authorized,
            decomposer,
            summarizer,
            checkpointer=saver,
            run_store=run_store,
        )
        resumed = resumed_app.analyze(
            "2025年3月毛利为什么比2月下降？",
            request_id="request-resume",
            auth_context=auth_context,
            analysis_run_id=run_id,
        )

        self.assertIsInstance(resumed, BusinessAnalysisSuccess)
        self.assertEqual(len(bound.requests), 6)
        self.assertEqual(len(decomposer.questions), 1)
        self.assertEqual(run_store.completed, {UUID(run_id)})
        self.assertEqual(resumed.request_id, "request-resume")


class _Decomposer:
    def __init__(self, candidate: AnalysisRequestCandidate) -> None:
        self.candidate = candidate
        self.questions: list[str] = []

    def decompose(self, question, context):
        del context
        self.questions.append(question)
        return self.candidate


class _Summarizer:
    def __init__(self) -> None:
        self.inputs = []

    def summarize(self, question, task_results, attribution):
        self.inputs.append((question, task_results, attribution))
        return BusinessAnalysisReport(
            title="分析报告",
            executive_summary="基于结果生成。",
            key_findings=("发现",),
            trend_judgment="稳定",
            root_causes=(),
            action_suggestions=("建议继续观察",),
            evidence_task_ids=tuple(result.task_id for result in task_results),
            incomplete_tasks=(),
            attribution=attribution,
        )


class _AuthorizedService:
    def __init__(self, bound) -> None:
        self.bound = bound
        self.bound_contexts = []

    def bind(self, auth_context):
        self.bound_contexts.append(auth_context)
        return self.bound


class _BoundService:
    def __init__(self, *, fail_count: int = 0, overall_value: object = 0) -> None:
        self.fail_count = fail_count
        self.overall_value = overall_value
        self.requests = []

    def query(self, request):
        self.requests.append(request)
        if len(self.requests) <= self.fail_count:
            return QueryFailure(
                request_id=request.request_id or "request",
                error_code=QueryErrorCode.DATABASE_ERROR,
                error_message="数据库暂时不可用",
                internal_reason="DATABASE_CONNECTION_LOST",
            )
        if request.semantic_query.dimensions:
            columns = (
                "产品",
                "人民币净销售额",
                "已完成销售数量",
                "人民币销售成本",
            )
            rows = ()
        else:
            columns = ("人民币毛利",)
            rows = ((self.overall_value,),)
        return QuerySuccess(
            request_id=request.request_id or "request",
            sql="SELECT 1",
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=False,
            semantic_query=request.semantic_query,
        )


def _application(
    authorized,
    decomposer,
    summarizer,
    *,
    checkpointer=None,
    run_store=None,
) -> BusinessAnalysisApplication:
    return BusinessAnalysisApplication(
        authorized,
        decomposer=decomposer,
        summarizer=summarizer,
        context_provider=_context,
        checkpointer=checkpointer,
        run_store=run_store,
    )


class _RunStore:
    def __init__(self) -> None:
        self.statuses = {}
        self.completed = set()

    def cleanup_expired(self):
        return 0

    def claim(self, analysis_run_id, *, owner_subject, question):
        del owner_subject, question
        status = self.statuses.get(analysis_run_id)
        if status is None:
            self.statuses[analysis_run_id] = AnalysisRunStatus.ACTIVE
            status = AnalysisRunStatus.NEW
        return AnalysisRun(analysis_run_id, status)

    def mark_completed(self, analysis_run_id):
        self.statuses[analysis_run_id] = AnalysisRunStatus.COMPLETED
        self.completed.add(analysis_run_id)


def _candidate(
    *,
    metric_text: str = "毛利",
    comparison_period: AnalysisTimeRange | None = _DEFAULT_PERIOD,
) -> AnalysisRequestCandidate:
    return AnalysisRequestCandidate(
        metric_text=metric_text,
        current_period=AnalysisTimeRange("2025年3月", TimeGranularity.MONTH),
        comparison_period=comparison_period,
    )


def _context() -> AnalysisDecompositionContext:
    return AnalysisDecompositionContext(
        current_time="2026-09-21T12:00:00+08:00",
        metric_records=(
            {"name": "人民币净销售额", "aliases": ["销售额", "营收"]},
            {"name": "人民币销售成本", "aliases": ["销售成本", "成本"]},
            {"name": "人民币毛利", "aliases": ["毛利"]},
            {"name": "已完成销售数量", "aliases": ["销售数量", "销量"]},
        ),
        dimensions=("产品", "产品线", "销售区域"),
    )


if __name__ == "__main__":
    unittest.main()
