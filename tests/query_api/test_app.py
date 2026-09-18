"""Query API Adapter（查询接口适配层）测试。"""

from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from unittest import TestCase
from unittest.mock import Mock

from fastapi.testclient import TestClient

from src.authorization import (
    InMemoryAuditSink,
    StaticAuthorizationPolicyStore,
    StaticIdentityProviderAdapter,
)
from src.authorization.contracts import IdentityProviderUnavailable
from src.online_query.contracts import (
    QueryErrorCode,
    QueryFailure,
    QueryRequest,
    QueryResult,
    QuerySuccess,
)
from src.query_api.app import create_app
from src.query_api.conversation import InMemoryConversationStore
from tests.query_api.support import create_test_app


class _RecordingService:
    def __init__(self) -> None:
        self.requests: list[QueryRequest] = []

    def execute(self, request: QueryRequest) -> QueryResult:
        self.requests.append(request)
        raise AssertionError("health check must not call OnlineQueryService")


class _SuccessService:
    def __init__(self, rows: tuple[tuple[object, ...], ...]) -> None:
        self.rows = rows
        self.requests: list[QueryRequest] = []

    def execute(self, request: QueryRequest) -> QueryResult:
        self.requests.append(request)
        return QuerySuccess(
            request_id=request.request_id or "generated-request-id",
            sql="SELECT product_name, net_sales_amount_cny FROM mart_sales.fct_sales_order_line",
            columns=("product_name", "net_sales_amount_cny"),
            rows=self.rows,
            row_count=len(self.rows),
            truncated=False,
        )


class _FailureService:
    def __init__(self, error_code: QueryErrorCode) -> None:
        self.error_code = error_code
        self.requests: list[QueryRequest] = []

    def execute(self, request: QueryRequest) -> QueryResult:
        self.requests.append(request)
        return QueryFailure(
            request_id=request.request_id or "generated-request-id",
            error_code=self.error_code,
            error_message=f"错误：{self.error_code.value}",
            failure_stage="query_understanding",
            internal_reason="QUERY_TYPE_UNKNOWN",
        )


class _AuthenticationFailureProvider:
    def __init__(self, error: Exception) -> None:
        self.error = error

    @property
    def identity_provider(self) -> str:
        return "test"

    def authenticate(self, _provider_input: object = None):
        raise self.error


class _InitialQueryApiAppTest(TestCase):
    def test_health_returns_ok_without_calling_query_service(self) -> None:
        service = _RecordingService()
        client = TestClient(create_test_app(service))

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(service.requests, [])

    def test_query_returns_success_and_forwards_request_id(self) -> None:
        service = _SuccessService((("产品A", 10000),))
        client = TestClient(create_test_app(service))

        response = client.post(
            "/api/v1/query",
            json={"question": "查询产品销售额"},
            headers={"X-Request-ID": "req-123"},
        )

        self.assertEqual(response.status_code, 200)
        response_payload = response.json()
        conversation_id = response_payload.pop("conversation_id")
        self.assertTrue(conversation_id)
        self.assertEqual(
            response_payload,
            {
                "request_id": "req-123",
                "sql": "SELECT product_name, net_sales_amount_cny FROM mart_sales.fct_sales_order_line",
                "columns": ["product_name", "net_sales_amount_cny"],
                "rows": [["产品A", 10000]],
                "row_count": 1,
                "truncated": False,
            },
        )
        self.assertEqual(
            service.requests,
            [QueryRequest(question="查询产品销售额", request_id="req-123")],
        )


class _ScriptedService:
    def __init__(self, outcomes: list[QueryResult]) -> None:
        self.outcomes = outcomes
        self.requests: list[QueryRequest] = []

    def execute(self, request: QueryRequest) -> QueryResult:
        self.requests.append(request)
        if not self.outcomes:
            raise AssertionError("scripted service has no remaining outcome")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, QuerySuccess):
            return QuerySuccess(
                request_id=request.request_id or outcome.request_id,
                sql=outcome.sql,
                columns=outcome.columns,
                rows=outcome.rows,
                row_count=outcome.row_count,
                truncated=outcome.truncated,
            )
        return QueryFailure(
            request_id=request.request_id or outcome.request_id,
            error_code=outcome.error_code,
            error_message=outcome.error_message,
            failure_stage=outcome.failure_stage,
            internal_reason=outcome.internal_reason,
        )


class _BlockingAfterFirstService:
    def __init__(self) -> None:
        self.requests: list[QueryRequest] = []
        self.started = Event()
        self.release = Event()

    def execute(self, request: QueryRequest) -> QueryResult:
        self.requests.append(request)
        if len(self.requests) == 2:
            self.started.set()
            if not self.release.wait(timeout=5):
                raise AssertionError("blocking service was not released")
        return QuerySuccess(
            request_id=request.request_id or "generated-request-id",
            sql="SELECT 1",
            columns=("value",),
            rows=((1,),),
            row_count=1,
            truncated=False,
        )


class _TestClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 9, 18, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.current

    def advance(self, duration: timedelta) -> None:
        self.current += duration


def _success_result() -> QuerySuccess:
    return QuerySuccess(
        request_id="generated-request-id",
        sql="SELECT 1",
        columns=("value",),
        rows=((1,),),
        row_count=1,
        truncated=False,
    )


def _failure_result(
    error_code: QueryErrorCode = QueryErrorCode.CANNOT_ANSWER,
) -> QueryFailure:
    return QueryFailure(
        request_id="generated-request-id",
        error_code=error_code,
        error_message=f"错误：{error_code.value}",
        failure_stage="query_understanding",
        internal_reason=error_code.value,
    )


class QueryApiAppTest(TestCase):
    def test_successful_conversation_can_be_continued_with_server_id(self) -> None:
        service = _SuccessService((("产品A", 10000),))
        client = TestClient(create_test_app(service))

        first_response = client.post(
            "/api/v1/query",
            json={"question": "查询产品销售额"},
        )
        conversation_id = first_response.json()["conversation_id"]

        second_response = client.post(
            "/api/v1/query",
            json={
                "question": "按销售区域拆开",
                "conversation_id": conversation_id,
            },
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            second_response.json()["conversation_id"],
            conversation_id,
        )
        self.assertEqual(
            [request.question for request in service.requests],
            ["查询产品销售额", "按销售区域拆开"],
        )

    def test_unknown_conversation_is_unavailable_without_calling_service(self) -> None:
        service = _SuccessService((("产品A", 10000),))
        client = TestClient(create_test_app(service))

        response = client.post(
            "/api/v1/query",
            json={
                "question": "按销售区域拆开",
                "conversation_id": "unknown-conversation",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_code"], "CONVERSATION_UNAVAILABLE")
        self.assertNotIn("detail", response.json())
        self.assertEqual(service.requests, [])

    def test_blank_conversation_id_is_unavailable_without_calling_service(self) -> None:
        service = _SuccessService((("产品A", 10000),))
        client = TestClient(create_test_app(service))

        response = client.post(
            "/api/v1/query",
            json={
                "question": "继续查询",
                "conversation_id": "   ",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_code"], "CONVERSATION_UNAVAILABLE")
        self.assertEqual(service.requests, [])

    def test_first_failure_does_not_create_conversation(self) -> None:
        service = _FailureService(QueryErrorCode.CANNOT_ANSWER)
        client = TestClient(create_test_app(service))

        response = client.post(
            "/api/v1/query",
            json={"question": "无法回答的问题"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertNotIn("conversation_id", response.json())

    def test_existing_failure_keeps_conversation_available_for_retry(self) -> None:
        service = _ScriptedService(
            [_success_result(), _failure_result(), _success_result()]
        )
        client = TestClient(create_test_app(service))

        first_response = client.post(
            "/api/v1/query",
            json={"question": "查询销售额"},
        )
        conversation_id = first_response.json()["conversation_id"]

        failed_response = client.post(
            "/api/v1/query",
            json={
                "question": "查询不支持的内容",
                "conversation_id": conversation_id,
            },
        )
        retry_response = client.post(
            "/api/v1/query",
            json={
                "question": "重新查询销售额",
                "conversation_id": conversation_id,
            },
        )

        self.assertEqual(failed_response.status_code, 422)
        self.assertNotIn("conversation_id", failed_response.json())
        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(retry_response.json()["conversation_id"], conversation_id)

    def test_expired_conversation_is_unavailable_without_calling_service(self) -> None:
        clock = _TestClock()
        store = InMemoryConversationStore(clock=clock)
        service = _SuccessService((("产品A", 10000),))
        client = TestClient(
            create_test_app(service, conversation_store=store),
        )

        first_response = client.post(
            "/api/v1/query",
            json={"question": "查询销售额"},
        )
        conversation_id = first_response.json()["conversation_id"]
        clock.advance(timedelta(minutes=30))

        expired_response = client.post(
            "/api/v1/query",
            json={
                "question": "继续查询",
                "conversation_id": conversation_id,
            },
        )

        self.assertEqual(expired_response.status_code, 404)
        self.assertEqual(
            expired_response.json()["error_code"],
            "CONVERSATION_UNAVAILABLE",
        )
        self.assertEqual(len(service.requests), 1)

    def test_conversation_is_invalid_after_app_restart(self) -> None:
        first_service = _SuccessService((("产品A", 10000),))
        first_client = TestClient(create_test_app(first_service))
        first_response = first_client.post(
            "/api/v1/query",
            json={"question": "查询销售额"},
        )
        conversation_id = first_response.json()["conversation_id"]

        restarted_service = _SuccessService((("产品B", 20000),))
        restarted_client = TestClient(create_test_app(restarted_service))
        response = restarted_client.post(
            "/api/v1/query",
            json={
                "question": "继续查询",
                "conversation_id": conversation_id,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(restarted_service.requests, [])

    def test_conversation_from_another_user_is_unavailable_without_query(self) -> None:
        store = InMemoryConversationStore()
        owner_service = _SuccessService((("产品A", 10000),))
        owner_client = TestClient(
            create_test_app(owner_service, conversation_store=store),
        )
        first_response = owner_client.post(
            "/api/v1/query",
            json={"question": "查询销售额"},
        )
        conversation_id = first_response.json()["conversation_id"]

        other_service = _SuccessService((("产品B", 20000),))
        other_client = TestClient(
            create_test_app(
                other_service,
                conversation_store=store,
                subject_id="analyst-2",
                allowed_subjects=("analyst-2",),
            ),
        )
        response = other_client.post(
            "/api/v1/query",
            json={
                "question": "读取其他用户的会话",
                "conversation_id": conversation_id,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_code"], "CONVERSATION_UNAVAILABLE")
        self.assertEqual(other_service.requests, [])

    def test_authorization_failure_does_not_lock_existing_conversation(self) -> None:
        store = InMemoryConversationStore()
        owner_service = _SuccessService((("产品A", 10000),))
        owner_client = TestClient(
            create_test_app(owner_service, conversation_store=store),
        )
        first_response = owner_client.post(
            "/api/v1/query",
            json={"question": "查询销售额"},
        )
        conversation_id = first_response.json()["conversation_id"]

        denied_service = _SuccessService((("产品B", 20000),))
        denied_client = TestClient(
            create_app(
                denied_service,
                identity_provider=StaticIdentityProviderAdapter(
                    identity_provider="test",
                    subject_id="analyst-1",
                ),
                policy_store=StaticAuthorizationPolicyStore(
                    allowed_subjects=frozenset(),
                    policy_version="test-policy-v2",
                ),
                audit_sink=InMemoryAuditSink(),
                conversation_store=store,
            ),
        )
        denied_response = denied_client.post(
            "/api/v1/query",
            json={
                "question": "查询受限内容",
                "conversation_id": conversation_id,
            },
        )
        retry_response = owner_client.post(
            "/api/v1/query",
            json={
                "question": "再次查询销售额",
                "conversation_id": conversation_id,
            },
        )

        self.assertEqual(denied_response.status_code, 403)
        self.assertEqual(denied_service.requests, [])
        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(retry_response.json()["conversation_id"], conversation_id)

    def test_concurrent_turn_returns_conflict_and_does_not_enter_downstream(
        self,
    ) -> None:
        service = _BlockingAfterFirstService()
        client = TestClient(create_test_app(service))
        first_response = client.post(
            "/api/v1/query",
            json={"question": "查询销售额"},
        )
        conversation_id = first_response.json()["conversation_id"]

        first_turn_response: dict[str, object] = {}

        def send_first_turn() -> None:
            first_turn_response["response"] = client.post(
                "/api/v1/query",
                json={
                    "question": "按区域拆开",
                    "conversation_id": conversation_id,
                },
            )

        thread = Thread(target=send_first_turn)
        thread.start()
        self.assertTrue(service.started.wait(timeout=5))

        conflict_response = client.post(
            "/api/v1/query",
            json={
                "question": "改看毛利率",
                "conversation_id": conversation_id,
            },
        )

        service.release.set()
        thread.join(timeout=5)

        self.assertEqual(conflict_response.status_code, 409)
        self.assertEqual(
            conflict_response.json()["error_code"],
            "CONVERSATION_CONFLICT",
        )
        self.assertEqual(len(service.requests), 2)
        self.assertEqual(
            getattr(first_turn_response["response"], "status_code", None),
            200,
        )

    def test_query_audit_event_can_be_correlated_by_request_id(self) -> None:
        service = _SuccessService((("产品A", 10000),))
        audit_sink = InMemoryAuditSink()
        client = TestClient(create_test_app(service, audit_sink=audit_sink))

        response = client.post(
            "/api/v1/query",
            json={"question": "查询产品销售额"},
            headers={"X-Request-ID": "req-audit-http"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(audit_sink.events), 1)
        self.assertEqual(audit_sink.events[0].request_id, "req-audit-http")
        self.assertEqual(audit_sink.events[0].decision, "allow")

    def test_query_without_request_id_returns_empty_success(self) -> None:
        service = _SuccessService(())
        client = TestClient(create_test_app(service))

        response = client.post(
            "/api/v1/query",
            json={"question": "查询没有数据的产品"},
        )

        self.assertEqual(response.status_code, 200)
        generated_request_id = response.json()["request_id"]
        self.assertTrue(generated_request_id)
        self.assertEqual(
            service.requests,
            [
                QueryRequest(
                    question="查询没有数据的产品", request_id=generated_request_id
                )
            ],
        )
        self.assertEqual(response.json()["rows"], [])
        self.assertEqual(response.json()["row_count"], 0)
        self.assertFalse(response.json()["truncated"])
        self.assertTrue(response.json()["conversation_id"])

    def test_query_maps_each_failure_code_to_http_status(self) -> None:
        expected_statuses = {
            QueryErrorCode.INVALID_REQUEST: 400,
            QueryErrorCode.CANNOT_ANSWER: 422,
            QueryErrorCode.SQL_REJECTED: 422,
            QueryErrorCode.LLM_ERROR: 502,
            QueryErrorCode.CONTEXT_ERROR: 503,
            QueryErrorCode.DATABASE_ERROR: 503,
            QueryErrorCode.QUERY_TIMEOUT: 504,
            QueryErrorCode.CONVERSATION_UNAVAILABLE: 404,
            QueryErrorCode.CLARIFICATION_REQUIRED: 422,
            QueryErrorCode.UNSUPPORTED_ANALYSIS: 422,
            QueryErrorCode.CONVERSATION_CONFLICT: 409,
        }

        for error_code, expected_status in expected_statuses.items():
            with self.subTest(error_code=error_code):
                service = _FailureService(error_code)
                client = TestClient(
                    create_test_app(service),
                    raise_server_exceptions=False,
                )

                response = client.post(
                    "/api/v1/query",
                    json={"question": "查询销售额"},
                )

                self.assertEqual(response.status_code, expected_status)
                expected_request_id = service.requests[0].request_id
                self.assertTrue(expected_request_id)
                self.assertEqual(
                    response.json(),
                    {
                        "request_id": expected_request_id,
                        "error_code": error_code.value,
                        "error_message": f"错误：{error_code.value}",
                    },
                )
                self.assertNotIn("failure_stage", response.json())
                self.assertNotIn("internal_reason", response.json())
                self.assertNotIn("detail", response.json())

    def test_blank_question_returns_invalid_request(self) -> None:
        service = _FailureService(QueryErrorCode.INVALID_REQUEST)
        client = TestClient(create_test_app(service))

        response = client.post(
            "/api/v1/query",
            json={"question": "   "},
            headers={"X-Request-ID": "req-invalid"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "INVALID_REQUEST")
        self.assertEqual(response.json()["request_id"], "req-invalid")
        self.assertEqual(
            service.requests,
            [QueryRequest(question="   ", request_id="req-invalid")],
        )

    def test_invalid_http_body_returns_failure_shape(self) -> None:
        invalid_bodies = (
            {},
            {"question": 123},
            {"question": "查询销售额", "unexpected": True},
        )

        for body in invalid_bodies:
            with self.subTest(body=body):
                service = _FailureService(QueryErrorCode.INVALID_REQUEST)
                client = TestClient(create_test_app(service))

                response = client.post(
                    "/api/v1/query",
                    json=body,
                    headers={"X-Request-ID": "req-invalid-body"},
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error_code"], "INVALID_REQUEST")
                self.assertEqual(response.json()["request_id"], "req-invalid-body")
                self.assertNotIn("detail", response.json())

    def test_invalid_json_returns_failure_shape(self) -> None:
        service = _FailureService(QueryErrorCode.INVALID_REQUEST)
        client = TestClient(create_test_app(service))

        response = client.post(
            "/api/v1/query",
            content=b"{invalid-json",
            headers={
                "Content-Type": "application/json",
                "X-Request-ID": "req-invalid-json",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "INVALID_REQUEST")
        self.assertEqual(response.json()["request_id"], "req-invalid-json")
        self.assertNotIn("detail", response.json())

    def test_missing_identity_returns_401_without_calling_query_service(self) -> None:
        service = _SuccessService((("产品A", 10000),))
        client = TestClient(create_app(service, audit_sink=InMemoryAuditSink()))

        response = client.post(
            "/api/v1/query",
            json={"question": "查询销售额"},
            headers={"X-Request-ID": "req-no-auth"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error_code"], "AUTHENTICATION_REQUIRED")
        self.assertEqual(response.json()["request_id"], "req-no-auth")
        self.assertEqual(service.requests, [])

    def test_unauthorized_identity_returns_403_without_calling_query_service(
        self,
    ) -> None:
        service = _SuccessService((("产品A", 10000),))
        client = TestClient(
            create_test_app(service, subject_id="blocked-user"),
        )

        response = client.post(
            "/api/v1/query",
            json={"question": "查询销售额"},
            headers={"X-Request-ID": "req-denied"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error_code"], "AUTHORIZATION_DENIED")
        self.assertEqual(response.json()["request_id"], "req-denied")
        self.assertEqual(service.requests, [])

    def test_identity_provider_failure_returns_503_without_calling_query_service(
        self,
    ) -> None:
        service = _SuccessService((("产品A", 10000),))
        policy = Mock()
        policy.authorize.return_value = Mock(allowed=True)
        audit_sink = InMemoryAuditSink()
        client = TestClient(
            create_app(
                service,
                identity_provider=_AuthenticationFailureProvider(
                    IdentityProviderUnavailable("provider unavailable")
                ),
                policy_store=policy,
                audit_sink=audit_sink,
            )
        )

        response = client.post(
            "/api/v1/query",
            json={"question": "查询销售额"},
            headers={"X-Request-ID": "req-provider-error"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error_code"],
            "AUTHENTICATION_UNAVAILABLE",
        )
        self.assertEqual(service.requests, [])
        self.assertEqual(len(audit_sink.events), 1)
        self.assertEqual(audit_sink.events[0].request_id, "req-provider-error")
        self.assertEqual(audit_sink.events[0].decision, "deny")
        self.assertEqual(audit_sink.events[0].identity_provider, "test")

    def test_missing_policy_returns_503_without_calling_query_service(self) -> None:
        service = _SuccessService((("产品A", 10000),))
        client = TestClient(
            create_app(
                service,
                identity_provider=StaticIdentityProviderAdapter(
                    identity_provider="test",
                    subject_id="analyst-1",
                ),
                audit_sink=InMemoryAuditSink(),
            )
        )

        response = client.post(
            "/api/v1/query",
            json={"question": "查询销售额"},
            headers={"X-Request-ID": "req-policy-error"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error_code"],
            "AUTHENTICATION_UNAVAILABLE",
        )
        self.assertEqual(service.requests, [])

    def test_client_identity_fields_are_rejected_from_request_body(self) -> None:
        service = _SuccessService((("产品A", 10000),))
        client = TestClient(create_test_app(service))

        response = client.post(
            "/api/v1/query",
            json={"question": "查询销售额", "subject_id": "analyst-1"},
            headers={"X-Request-ID": "req-spoof"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "INVALID_REQUEST")
        self.assertEqual(service.requests, [])
