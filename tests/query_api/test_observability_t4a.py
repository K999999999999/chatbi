"""T4A Query API HTTP trace lifecycle tests."""

import re
import unittest

from fastapi.testclient import TestClient

from src.observability.contracts import QuerySource
from src.observability.tracing import create_in_memory_recorder
from src.online_query.contracts import (
    QueryErrorCode,
    QueryFailure,
    QueryRequest,
    QuerySuccess,
)
from tests.query_api.support import create_test_app


class _SuccessService:
    def __init__(self) -> None:
        self.requests: list[QueryRequest] = []

    def query(self, request: QueryRequest) -> QuerySuccess:
        self.requests.append(request)
        return QuerySuccess(
            request_id=request.request_id or "missing",
            sql="SELECT 1",
            columns=("value",),
            rows=((1,),),
            row_count=1,
            truncated=False,
        )


class _FailureService:
    def __init__(self) -> None:
        self.requests: list[QueryRequest] = []

    def query(self, request: QueryRequest) -> QueryFailure:
        self.requests.append(request)
        return QueryFailure(
            request_id=request.request_id or "missing",
            error_code=QueryErrorCode.INVALID_REQUEST,
            error_message="invalid request",
        )


class T4AQueryApiObservabilityTest(unittest.TestCase):
    def test_health_is_outside_query_trace_middleware(self) -> None:
        recorder, exporter = create_in_memory_recorder()
        client = TestClient(create_test_app(_SuccessService(), trace_recorder=recorder))

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertNotIn("X-Trace-ID", response.headers)
        self.assertEqual(exporter.get_finished_spans(), ())

    def test_success_uses_one_local_root_and_returns_matching_trace_header(
        self,
    ) -> None:
        service = _SuccessService()
        recorder, exporter = create_in_memory_recorder()
        client = TestClient(create_test_app(service, trace_recorder=recorder))

        response = client.post(
            "/api/v1/query",
            json={"question": "查询销售额"},
            headers={"X-Request-ID": "req-t4a-success"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["request_id"], "req-t4a-success")
        self.assertNotIn("trace_id", response.json())
        trace_id = response.headers["X-Trace-ID"]
        self.assertRegex(trace_id, re.compile(r"^[0-9a-f]{32}$"))
        self.assertEqual(service.requests[0].request_id, "req-t4a-success")

        spans = exporter.get_finished_spans()
        self.assertEqual(spans[-1].name, "query.request")
        root = spans[-1]
        self.assertEqual(
            root.attributes["chatbi.request.source"], QuerySource.HTTP.value
        )
        self.assertEqual(root.attributes["chatbi.request.id"], "req-t4a-success")
        self.assertEqual(root.context.trace_id, int(trace_id, 16))
        serialized = [span for span in spans if span.name == "response.serialize"]
        self.assertEqual(len(serialized), 1)
        self.assertEqual(serialized[0].parent.span_id, root.context.span_id)

    def test_invalid_json_gets_request_and_trace_ids_before_body_parse(self) -> None:
        service = _FailureService()
        recorder, exporter = create_in_memory_recorder()
        client = TestClient(create_test_app(service, trace_recorder=recorder))

        response = client.post(
            "/api/v1/query",
            content=b"{invalid-json",
            headers={
                "Content-Type": "application/json",
                "X-Request-ID": "req-t4a-invalid-json",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["request_id"], "req-t4a-invalid-json")
        self.assertIn("X-Trace-ID", response.headers)
        self.assertEqual(service.requests, [])
        names = [span.name for span in exporter.get_finished_spans()]
        self.assertEqual(names[-1], "query.request")
        self.assertEqual(names.count("response.serialize"), 1)

    def test_missing_request_id_is_generated_and_client_trace_headers_are_ignored(
        self,
    ) -> None:
        service = _SuccessService()
        recorder, exporter = create_in_memory_recorder()
        client = TestClient(create_test_app(service, trace_recorder=recorder))
        spoofed_trace_id = "a" * 32

        response = client.post(
            "/api/v1/query",
            json={"question": "查询销售额"},
            headers={
                "traceparent": f"00-{spoofed_trace_id}-{'b' * 16}-01",
                "tracestate": "vendor=spoofed",
            },
        )

        request_id = response.json()["request_id"]
        trace_id = response.headers["X-Trace-ID"]
        self.assertTrue(request_id)
        self.assertRegex(trace_id, re.compile(r"^[0-9a-f]{32}$"))
        self.assertNotEqual(trace_id, spoofed_trace_id)
        self.assertEqual(service.requests[0].request_id, request_id)
        root = next(
            span
            for span in exporter.get_finished_spans()
            if span.name == "query.request"
        )
        self.assertEqual(root.attributes["chatbi.request.id"], request_id)
        self.assertEqual(root.context.trace_id, int(trace_id, 16))


if __name__ == "__main__":
    unittest.main()
