"""Business Analysis Application Workflow 测试。"""

import unittest

from src.business_analysis.application import (
    BusinessAnalysisApplication,
    BusinessAnalysisSuccess,
)
from src.business_analysis.contracts import (
    AnalysisDecompositionContext,
    AnalysisPlanCandidate,
    AnalysisTaskCandidate,
    AnalysisTaskType,
)
from src.business_analysis.execution import TaskStatus
from src.business_analysis.reporting import BusinessAnalysisReport
from src.online_query.contracts import QueryErrorCode, QueryFailure, QuerySuccess


class BusinessAnalysisApplicationTest(unittest.TestCase):
    def test_application_decomposes_executes_and_summarizes_under_bound_identity(
        self,
    ) -> None:
        bound = _BoundService()
        authorized = _AuthorizedService(bound)
        decomposer = _Decomposer()
        summarizer = _Summarizer()
        application = BusinessAnalysisApplication(
            authorized,
            decomposer=decomposer,
            summarizer=summarizer,
            context_provider=lambda: _context(),
        )

        result = application.analyze(
            "分析销售额",
            request_id="analysis-1",
            auth_context="auth-context",
        )

        self.assertIsInstance(result, BusinessAnalysisSuccess)
        self.assertEqual(result.request_id, "analysis-1")
        self.assertEqual(result.report.title, "分析报告")
        self.assertEqual(result.task_results[0].status, TaskStatus.COMPLETED)
        self.assertEqual(authorized.bound_contexts, ["auth-context"])
        self.assertEqual(decomposer.questions, ["分析销售额"])
        self.assertEqual(summarizer.inputs[0][0], "分析销售额")

    def test_ambiguous_profit_is_clarified_before_task_execution(self) -> None:
        application = BusinessAnalysisApplication(
            _AuthorizedService(_BoundService()),
            decomposer=_ProfitDecomposer(),
            summarizer=_Summarizer(),
            context_provider=lambda: _context(),
        )

        result = application.analyze(
            "最近利润为什么下降？",
            request_id="analysis-profit",
            auth_context="auth-context",
        )

        self.assertIsInstance(result, QueryFailure)
        self.assertEqual(result.error_code, QueryErrorCode.CLARIFICATION_REQUIRED)
        self.assertEqual(result.internal_reason, "METRIC_NOT_UNIQUE")


class _Decomposer:
    def __init__(self) -> None:
        self.questions = []

    def decompose(self, question, context):
        self.questions.append(question)
        return AnalysisPlanCandidate(
            tasks=(
                AnalysisTaskCandidate(
                    task_id="root",
                    task_type=AnalysisTaskType.BASELINE,
                    description="查询销售额",
                    metrics=("销售额",),
                    dimensions=(),
                    time_range=None,
                    filters=(),
                    depends_on=(),
                    expected_output="销售额结果",
                ),
            )
        )


class _Summarizer:
    def __init__(self) -> None:
        self.inputs = []

    def summarize(self, question, task_results):
        self.inputs.append((question, task_results))
        return BusinessAnalysisReport(
            title="分析报告",
            executive_summary="基于结果生成。",
            key_findings=("发现",),
            trend_judgment="稳定",
            root_causes=(),
            action_suggestions=("建议继续观察",),
            evidence_task_ids=("root",),
            incomplete_tasks=(),
        )


class _ProfitDecomposer:
    def decompose(self, question, context):
        del question, context
        return AnalysisPlanCandidate(
            tasks=(
                AnalysisTaskCandidate(
                    task_id="profit",
                    task_type=AnalysisTaskType.TREND,
                    description="分析利润趋势",
                    metrics=("人民币毛利", "毛利率"),
                    dimensions=(),
                    time_range=None,
                    filters=(),
                    depends_on=(),
                    expected_output="利润结果",
                ),
            )
        )


class _AuthorizedService:
    def __init__(self, bound) -> None:
        self.bound = bound
        self.bound_contexts = []

    def bind(self, auth_context):
        self.bound_contexts.append(auth_context)
        return self.bound


class _BoundService:
    def query(self, request):
        return QuerySuccess(
            request_id=request.request_id or "request",
            sql="SELECT 1",
            columns=("value",),
            rows=((1,),),
            row_count=1,
            truncated=False,
            semantic_query=request.semantic_query,
        )


def _context() -> AnalysisDecompositionContext:
    return AnalysisDecompositionContext(
        current_time="2026-09-21T12:00:00+08:00",
        metric_records=(
            {
                "name": "人民币净销售额",
                "aliases": ["销售额"],
            },
        ),
        dimensions=(),
    )


if __name__ == "__main__":
    unittest.main()
