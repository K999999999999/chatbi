"""Query API Adapter（查询接口适配层）测试。"""

from unittest import TestCase

from fastapi.testclient import TestClient

from src.online_query.contracts import QueryRequest, QueryResult, QuerySuccess
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
        self.assertEqual(response.json()["request_id"], "generated-request-id")
        self.assertEqual(response.json()["rows"], [])
        self.assertEqual(response.json()["row_count"], 0)
        self.assertFalse(response.json()["truncated"])
        self.assertEqual(
            service.requests,
            [QueryRequest(question="查询没有数据的产品", request_id=None)],
        )
