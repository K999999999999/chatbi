"""Query API 经营分析模式测试。"""

from unittest import TestCase

from fastapi.testclient import TestClient

from src.online_query.contracts import QueryErrorCode, QueryFailure
from src.business_analysis.execution import TaskResult, TaskStatus
from src.business_analysis.reporting import BusinessAnalysisReport
from src.business_analysis.application import BusinessAnalysisSuccess
from tests.query_api.support import create_test_app


class AnalysisModeApiTest(TestCase):
    def test_analysis_success_does_not_read_or_create_conversation(self) -> None:
        analysis = _AnalysisService(
            BusinessAnalysisSuccess(
                request_id="analysis-1",
                report=_report(),
                task_results=(
                    TaskResult(
                        task_id="root",
                        status=TaskStatus.COMPLETED,
                        columns=("value",),
                        rows=((1,),),
                        row_count=1,
                        truncated=False,
                    ),
                ),
            )
        )
        client = TestClient(create_test_app(_QueryService(), analysis_service=analysis))

        response = client.post(
            "/api/v1/query",
            json={"question": "分析销售额", "mode": "analysis"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "analysis")
        self.assertEqual(payload["report"]["title"], "分析报告")
        self.assertEqual(payload["task_results"][0]["task_id"], "root")
        self.assertNotIn("conversation_id", payload)
        self.assertEqual(analysis.calls[0]["auth_context"].subject_id, "analyst-1")

    def test_analysis_with_conversation_id_is_rejected_before_workflow(self) -> None:
        analysis = _AnalysisService(_report_failure())
        client = TestClient(create_test_app(_QueryService(), analysis_service=analysis))

        response = client.post(
            "/api/v1/query",
            json={
                "question": "分析销售额",
                "mode": "analysis",
                "conversation_id": "must-not-be-read",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "INVALID_REQUEST")
        self.assertEqual(analysis.calls, [])

    def test_analysis_failure_uses_existing_query_failure_shape(self) -> None:
        analysis = _AnalysisService(_report_failure())
        client = TestClient(create_test_app(_QueryService(), analysis_service=analysis))

        response = client.post(
            "/api/v1/query",
            json={"question": "分析销售额", "mode": "analysis"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error_code"], "CANNOT_ANSWER")
        self.assertNotIn("detail", response.json())

    def test_unknown_mode_is_invalid_request_without_calling_services(self) -> None:
        analysis = _AnalysisService(_report_failure())
        query = _QueryService()
        client = TestClient(create_test_app(query, analysis_service=analysis))

        response = client.post(
            "/api/v1/query",
            json={"question": "分析销售额", "mode": "router"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "INVALID_REQUEST")
        self.assertEqual(analysis.calls, [])
        self.assertEqual(query.calls, 0)


class _AnalysisService:
    def __init__(self, result) -> None:
        self.result = result
        self.calls = []

    def analyze(self, question, *, request_id, auth_context):
        self.calls.append(
            {
                "question": question,
                "request_id": request_id,
                "auth_context": auth_context,
            }
        )
        return self.result


class _QueryService:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, request):
        self.calls += 1
        raise AssertionError("analysis mode must not call ordinary query service")


def _report() -> BusinessAnalysisReport:
    return BusinessAnalysisReport(
        title="分析报告",
        executive_summary="基于数据生成。",
        key_findings=("发现",),
        trend_judgment="稳定",
        root_causes=(),
        action_suggestions=("建议继续观察",),
        evidence_task_ids=("root",),
        incomplete_tasks=(),
    )


def _report_failure() -> QueryFailure:
    return QueryFailure(
        request_id="analysis-1",
        error_code=QueryErrorCode.CANNOT_ANSWER,
        error_message="当前没有足够的完成结果",
    )
