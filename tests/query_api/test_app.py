"""Query API Adapter（查询接口适配层）测试。"""

from unittest import TestCase

from fastapi.testclient import TestClient

from src.online_query.contracts import (
    QueryErrorCode,
    QueryFailure,
    QueryRequest,
    QueryResult,
    QuerySuccess,
)
from src.query_api.app import create_app


class _RecordingService:
    def __init__(self) -> None:
        self.requests: list[QueryRequest] = []

    def query(self, request: QueryRequest) -> QueryResult:
        self.requests.append(request)
        raise AssertionError("health check must not call OnlineQueryService")


class _SuccessService:
    def __init__(self, rows: tuple[tuple[object, ...], ...]) -> None:
        self.rows = rows
        self.requests: list[QueryRequest] = []

    def query(self, request: QueryRequest) -> QueryResult:
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

    def query(self, request: QueryRequest) -> QueryResult:
        self.requests.append(request)
        return QueryFailure(
            request_id=request.request_id or "generated-request-id",
            error_code=self.error_code,
            error_message=f"错误：{self.error_code.value}",
            failure_stage="query_understanding",
            internal_reason="QUERY_TYPE_UNKNOWN",
        )


class QueryApiAppTest(TestCase):
    def test_health_returns_ok_without_calling_query_service(self) -> None:
        service = _RecordingService()
        client = TestClient(create_app(service))

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(service.requests, [])

    def test_query_returns_success_and_forwards_request_id(self) -> None:
        service = _SuccessService((("产品A", 10000),))
        client = TestClient(create_app(service))

        response = client.post(
            "/api/v1/query",
            json={"question": "查询产品销售额"},
            headers={"X-Request-ID": "req-123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
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

    def test_query_without_request_id_returns_empty_success(self) -> None:
        service = _SuccessService(())
        client = TestClient(create_app(service))

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

    def test_query_maps_each_failure_code_to_http_status(self) -> None:
        expected_statuses = {
            QueryErrorCode.INVALID_REQUEST: 400,
            QueryErrorCode.CANNOT_ANSWER: 422,
            QueryErrorCode.SQL_REJECTED: 422,
            QueryErrorCode.LLM_ERROR: 502,
            QueryErrorCode.CONTEXT_ERROR: 503,
            QueryErrorCode.DATABASE_ERROR: 503,
            QueryErrorCode.QUERY_TIMEOUT: 504,
        }

        for error_code, expected_status in expected_statuses.items():
            with self.subTest(error_code=error_code):
                service = _FailureService(error_code)
                client = TestClient(
                    create_app(service),
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
        client = TestClient(create_app(service))

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
                client = TestClient(create_app(service))

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
        client = TestClient(create_app(service))

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
