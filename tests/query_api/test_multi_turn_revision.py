"""Multi-Turn Query V1 的 Application 语义修订测试。"""

from datetime import UTC, datetime
from unittest import TestCase
from unittest.mock import Mock

from fastapi.testclient import TestClient

from src.authorization import InMemoryAuditSink, StaticIdentityProviderAdapter
from src.authorization.contracts import (
    AuthorizationDecision,
    AuthorizationDecisionCode,
)
from src.online_query.contracts import (
    QueryErrorCode,
    QueryFailure,
    QueryRequest,
    QueryResult,
    QuerySuccess,
)
from src.online_query.query_understanding import (
    QueryType,
    SemanticQueryCandidate,
    TimeGranularity,
    ValidatedTime,
    ValidatedSemanticQuery,
)
from src.query_api.app import create_app
from tests.query_api.support import create_test_app


def _initial_query() -> ValidatedSemanticQuery:
    return ValidatedSemanticQuery(
        query_type=QueryType.METRIC_ANALYSIS,
        subjects=("销售",),
        metrics=("人民币销售额",),
        dimensions=(),
        time=ValidatedTime(
            text="2025 年第一季度",
            granularity=TimeGranularity.QUARTER,
            start=datetime(2025, 1, 1, tzinfo=UTC),
            end=datetime(2025, 4, 1, tzinfo=UTC),
        ),
        filters=(),
        original_question="2025 年第一季度的人民币销售额是多少？",
    )


class _RevisionAdapter:
    def __init__(self) -> None:
        self.questions: list[str] = []

    def understand_revision(
        self,
        previous: ValidatedSemanticQuery,
        question: str,
    ) -> SemanticQueryCandidate:
        del previous
        self.questions.append(question)
        if question == "按销售区域拆开":
            return SemanticQueryCandidate(
                query_type=QueryType.METRIC_ANALYSIS,
                subjects=(),
                metrics=(),
                dimensions=("销售区域",),
                time=None,
                filters=(),
            )
        if question == "改看毛利率":
            return SemanticQueryCandidate(
                query_type=QueryType.METRIC_ANALYSIS,
                subjects=(),
                metrics=("毛利率",),
                dimensions=(),
                time=None,
                filters=(),
            )
        if question == "再看看":
            return SemanticQueryCandidate(
                query_type=QueryType.UNKNOWN,
                subjects=(),
                metrics=(),
                dimensions=(),
                time=None,
                filters=(),
            )
        raise AssertionError(f"unexpected revision question: {question}")


class _StatefulService:
    def __init__(self) -> None:
        self.requests: list[QueryRequest] = []
        self.initial = _initial_query()

    def execute(self, request: QueryRequest) -> QueryResult:
        self.requests.append(request)
        state = request.semantic_query or self.initial
        return QuerySuccess(
            request_id=request.request_id or "generated-request-id",
            sql="SELECT 1",
            columns=("value",),
            rows=((1,),),
            row_count=1,
            truncated=False,
            semantic_query=state,
        )


class _FailingRevisionService(_StatefulService):
    def __init__(self) -> None:
        super().__init__()
        self.fail_next_revision = True

    def execute(self, request: QueryRequest) -> QueryResult:
        self.requests.append(request)
        if request.semantic_query is not None and self.fail_next_revision:
            self.fail_next_revision = False
            return QueryFailure(
                request_id=request.request_id or "generated-request-id",
                error_code=QueryErrorCode.DATABASE_ERROR,
                error_message="数据库连接或执行失败",
                failure_stage="database",
                internal_reason="TEST_FAILURE",
            )
        state = request.semantic_query or self.initial
        return QuerySuccess(
            request_id=request.request_id or "generated-request-id",
            sql="SELECT 1",
            columns=("value",),
            rows=((1,),),
            row_count=1,
            truncated=False,
            semantic_query=state,
        )


class MultiTurnRevisionTest(TestCase):
    def test_follow_up_adds_dimension_then_replaces_metric(self) -> None:
        service = _StatefulService()
        adapter = _RevisionAdapter()
        client = TestClient(
            create_test_app(service, query_understanding=adapter),
        )

        first = client.post(
            "/api/v1/query",
            json={"question": "2025 年第一季度的人民币销售额是多少？"},
        )
        conversation_id = first.json()["conversation_id"]

        second = client.post(
            "/api/v1/query",
            json={
                "question": "按销售区域拆开",
                "conversation_id": conversation_id,
            },
        )
        third = client.post(
            "/api/v1/query",
            json={
                "question": "改看毛利率",
                "conversation_id": conversation_id,
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(third.status_code, 200)
        self.assertEqual(len(service.requests), 3)

        second_state = service.requests[1].semantic_query
        third_state = service.requests[2].semantic_query
        self.assertIsNotNone(second_state)
        self.assertIsNotNone(third_state)
        assert second_state is not None
        assert third_state is not None
        self.assertEqual(second_state.metrics, ("人民币销售额",))
        self.assertEqual(second_state.dimensions, ("销售区域",))
        self.assertEqual(second_state.time, _initial_query().time)
        self.assertEqual(third_state.metrics, ("毛利率",))
        self.assertEqual(third_state.dimensions, ("销售区域",))
        self.assertEqual(third_state.time, _initial_query().time)
        self.assertEqual(adapter.questions, ["按销售区域拆开", "改看毛利率"])

    def test_ambiguous_follow_up_does_not_execute_or_mutate_state(self) -> None:
        service = _StatefulService()
        adapter = _RevisionAdapter()
        client = TestClient(
            create_test_app(service, query_understanding=adapter),
        )

        first = client.post(
            "/api/v1/query",
            json={"question": "2025 年第一季度的人民币销售额是多少？"},
        )
        conversation_id = first.json()["conversation_id"]
        ambiguous = client.post(
            "/api/v1/query",
            json={"question": "再看看", "conversation_id": conversation_id},
        )
        retry = client.post(
            "/api/v1/query",
            json={
                "question": "按销售区域拆开",
                "conversation_id": conversation_id,
            },
        )

        self.assertEqual(ambiguous.status_code, 422)
        self.assertEqual(ambiguous.json()["error_code"], "CLARIFICATION_REQUIRED")
        self.assertNotIn("conversation_id", ambiguous.json())
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(len(service.requests), 2)
        self.assertEqual(
            service.requests[1].semantic_query.dimensions,
            ("销售区域",),
        )

    def test_unsupported_analysis_does_not_execute_or_mutate_state(self) -> None:
        service = _StatefulService()
        adapter = _RevisionAdapter()
        client = TestClient(
            create_test_app(service, query_understanding=adapter),
        )

        first = client.post(
            "/api/v1/query",
            json={"question": "2025 年第一季度的人民币销售额是多少？"},
        )
        conversation_id = first.json()["conversation_id"]
        unsupported = client.post(
            "/api/v1/query",
            json={"question": "看同比", "conversation_id": conversation_id},
        )
        retry = client.post(
            "/api/v1/query",
            json={
                "question": "改看毛利率",
                "conversation_id": conversation_id,
            },
        )

        self.assertEqual(unsupported.status_code, 422)
        self.assertEqual(unsupported.json()["error_code"], "UNSUPPORTED_ANALYSIS")
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(len(service.requests), 2)
        self.assertEqual(adapter.questions, ["改看毛利率"])

    def test_downstream_failure_keeps_last_successful_semantic_state(self) -> None:
        service = _FailingRevisionService()
        adapter = _RevisionAdapter()
        client = TestClient(
            create_test_app(service, query_understanding=adapter),
        )

        first = client.post(
            "/api/v1/query",
            json={"question": "2025 年第一季度的人民币销售额是多少？"},
        )
        conversation_id = first.json()["conversation_id"]
        failed = client.post(
            "/api/v1/query",
            json={
                "question": "按销售区域拆开",
                "conversation_id": conversation_id,
            },
        )
        retry = client.post(
            "/api/v1/query",
            json={
                "question": "改看毛利率",
                "conversation_id": conversation_id,
            },
        )

        self.assertEqual(failed.status_code, 503)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(service.requests[1].semantic_query.dimensions, ("销售区域",))
        self.assertEqual(service.requests[2].semantic_query.metrics, ("毛利率",))
        self.assertEqual(service.requests[2].semantic_query.dimensions, ())

    def test_each_turn_rechecks_current_authorization(self) -> None:
        service = _StatefulService()
        adapter = _RevisionAdapter()
        policy = Mock()
        policy.authorize.side_effect = [
            AuthorizationDecision.allow(policy_version="policy-v1"),
            AuthorizationDecision.allow(policy_version="policy-v1"),
            AuthorizationDecision.deny(
                reason_code=AuthorizationDecisionCode.SUBJECT_NOT_ALLOWED,
                policy_version="policy-v2",
            ),
        ]
        client = TestClient(
            create_app(
                service,
                identity_provider=StaticIdentityProviderAdapter(
                    identity_provider="test",
                    subject_id="analyst-1",
                ),
                policy_store=policy,
                query_understanding=adapter,
                audit_sink=InMemoryAuditSink(),
            )
        )

        first = client.post(
            "/api/v1/query",
            json={"question": "2025 年第一季度的人民币销售额是多少？"},
        )
        conversation_id = first.json()["conversation_id"]
        second = client.post(
            "/api/v1/query",
            json={
                "question": "按销售区域拆开",
                "conversation_id": conversation_id,
            },
        )
        third = client.post(
            "/api/v1/query",
            json={
                "question": "改看毛利率",
                "conversation_id": conversation_id,
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(third.status_code, 403)
        self.assertEqual(len(service.requests), 2)
        self.assertEqual(policy.authorize.call_count, 3)


if __name__ == "__main__":
    import unittest

    unittest.main()
