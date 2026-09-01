"""Query API Adapter（查询接口适配层）测试。"""

from unittest import TestCase

from fastapi.testclient import TestClient

from src.online_query.contracts import QueryRequest, QueryResult
from src.query_api.app import create_app


class _RecordingService:
    def __init__(self) -> None:
        self.requests: list[QueryRequest] = []

    def query(self, request: QueryRequest) -> QueryResult:
        self.requests.append(request)
        raise AssertionError("health check must not call OnlineQueryService")


class QueryApiAppTest(TestCase):
    def test_health_returns_ok_without_calling_query_service(self) -> None:
        service = _RecordingService()
        client = TestClient(create_app(service))

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(service.requests, [])
