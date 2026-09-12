"""Streamlit POC（概念验证）页面与 HTTP 客户端测试。"""

from io import BytesIO
import json
from unittest import TestCase
from urllib.error import HTTPError, URLError
from urllib.request import Request

from src.streamlit_app import (
    QueryAPIError,
    QueryAPIResponse,
    _render_error,
    _render_success,
    format_display_rows,
    query_api,
    rows_as_records,
)


class _Response:
    def __init__(
        self,
        payload: dict[str, object],
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self.headers = headers or {}
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class StreamlitQueryClientTest(TestCase):
    def test_query_api_posts_question_and_returns_success_payload(self) -> None:
        calls: list[tuple[Request, float]] = []
        payload = {
            "request_id": "req-1",
            "sql": "SELECT 1",
            "columns": ["value"],
            "rows": [[1]],
            "row_count": 1,
            "truncated": False,
        }

        def opener(request: Request, *, timeout: float) -> _Response:
            calls.append((request, timeout))
            return _Response(payload, headers={"X-Trace-ID": "trace-success"})

        result = query_api(
            "http://127.0.0.1:8000/",
            "查询销售额",
            opener=opener,
        )

        self.assertEqual(result, payload)
        self.assertIsInstance(result, QueryAPIResponse)
        self.assertEqual(result.trace_id, "trace-success")
        self.assertNotIn("trace_id", result)
        self.assertEqual(len(calls), 1)
        request, timeout = calls[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8000/api/v1/query")
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {"question": "查询销售额"},
        )
        self.assertEqual(timeout, 90.0)

    def test_query_api_converts_api_failure_to_controlled_error(self) -> None:
        payload = {
            "request_id": "req-2",
            "error_code": "CANNOT_ANSWER",
            "error_message": "当前结构无法回答该问题",
        }

        def opener(_request: Request, *, timeout: float) -> _Response:
            raise HTTPError(
                url="http://127.0.0.1:8000/api/v1/query",
                code=422,
                msg="Unprocessable Entity",
                hdrs={"X-Trace-ID": "trace-error"},
                fp=BytesIO(json.dumps(payload).encode("utf-8")),
            )

        with self.assertRaises(QueryAPIError) as raised:
            query_api("http://127.0.0.1:8000", "查询不存在的业务", opener=opener)

        self.assertEqual(raised.exception.error_code, "CANNOT_ANSWER")
        self.assertEqual(raised.exception.request_id, "req-2")
        self.assertEqual(raised.exception.trace_id, "trace-error")
        self.assertEqual(raised.exception.error_message, "当前结构无法回答该问题")

    def test_query_api_keeps_compatibility_when_trace_header_is_missing(self) -> None:
        payload = {
            "request_id": "req-3",
            "sql": "SELECT 1",
            "columns": ["value"],
            "rows": [[1]],
            "row_count": 1,
            "truncated": False,
        }

        def opener(_request: Request, *, timeout: float) -> _Response:
            return _Response(payload)

        result = query_api(
            "http://127.0.0.1:8000",
            "查询销售额",
            opener=opener,
        )

        self.assertEqual(result, payload)
        self.assertEqual(result.trace_id, "")

    def test_query_api_converts_unavailable_api_to_controlled_error(self) -> None:
        def opener(_request: Request, *, timeout: float) -> _Response:
            raise URLError("connection refused")

        with self.assertRaises(QueryAPIError) as raised:
            query_api("http://127.0.0.1:8000", "查询销售额", opener=opener)

        self.assertEqual(raised.exception.error_code, "API_UNAVAILABLE")
        self.assertEqual(raised.exception.request_id, "")
        self.assertEqual(raised.exception.trace_id, "")
        self.assertEqual(raised.exception.error_message, "无法连接查询服务")

    def test_rows_are_converted_to_records_for_table_display(self) -> None:
        self.assertEqual(
            rows_as_records(
                ["product_name", "sales_amount"],
                [["产品A", 10000], ["产品B", 8000]],
            ),
            [
                {"product_name": "产品A", "sales_amount": 10000},
                {"product_name": "产品B", "sales_amount": 8000},
            ],
        )

    def test_display_formats_amount_count_and_percentage(self) -> None:
        self.assertEqual(
            format_display_rows(
                [
                    "monthly_sales_cny",
                    "completed_order_count",
                    "gross_margin",
                    "product_name",
                ],
                [["49766769.735182", 1234567, "0.3567", "产品A"]],
            ),
            [
                {
                    "monthly_sales_cny": "49,766,769.74",
                    "completed_order_count": "1,234,567",
                    "gross_margin": "35.67%",
                    "product_name": "产品A",
                }
            ],
        )

    def test_display_keeps_null_and_unrecognized_values(self) -> None:
        self.assertEqual(
            format_display_rows(
                ["monthly_sales_cny", "unknown_value", "gross_margin"],
                [[None, "00123", "unknown"]],
            ),
            [
                {
                    "monthly_sales_cny": None,
                    "unknown_value": "00123",
                    "gross_margin": "unknown",
                }
            ],
        )

    def test_success_page_displays_trace_id_only_when_response_header_provided_it(self) -> None:
        displayed = _FakeStreamlit()

        _render_success(
            displayed,
            QueryAPIResponse(
                {
                    "request_id": "req-page-success",
                    "sql": "SELECT 1",
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                    "truncated": False,
                },
                trace_id="trace-page-success",
            ),
        )

        self.assertIn("链路编号：trace-page-success", displayed.captions)

        displayed_without_trace = _FakeStreamlit()
        _render_success(
            displayed_without_trace,
            {"request_id": "req-page-no-trace", "columns": [], "rows": []},
        )

        self.assertNotIn(
            "链路编号：trace-page-no-trace",
            displayed_without_trace.captions,
        )

    def test_error_page_displays_request_and_trace_ids_without_raw_exception(self) -> None:
        displayed = _FakeStreamlit()

        _render_error(
            displayed,
            QueryAPIError(
                "CANNOT_ANSWER",
                "当前结构无法回答该问题",
                request_id="req-page-error",
                trace_id="trace-page-error",
            ),
        )

        self.assertEqual(displayed.errors, ["CANNOT_ANSWER：当前结构无法回答该问题"])
        self.assertEqual(
            displayed.captions,
            ["请求编号：req-page-error", "链路编号：trace-page-error"],
        )

        displayed_without_trace = _FakeStreamlit()
        _render_error(
            displayed_without_trace,
            QueryAPIError(
                "API_ERROR",
                "查询服务返回了无效响应",
                request_id="req-page-no-trace",
            ),
        )

        self.assertNotIn(
            "链路编号：",
            "\n".join(displayed_without_trace.captions),
        )


class _FakeMetricColumn:
    def metric(self, label: str, value: object) -> None:
        return None


class _FakeContext:
    def __enter__(self) -> "_FakeContext":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _FakeStreamlit:
    def __init__(self) -> None:
        self.captions: list[str] = []
        self.errors: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def caption(self, message: str) -> None:
        self.captions.append(message)

    def subheader(self, _message: str) -> None:
        return None

    def info(self, _message: str) -> None:
        return None

    def columns(self, count: int) -> list[_FakeMetricColumn]:
        return [_FakeMetricColumn() for _ in range(count)]

    def expander(self, _label: str) -> _FakeContext:
        return _FakeContext()

    def code(self, _code: str, *, language: str) -> None:
        return None


if __name__ == "__main__":
    import unittest

    unittest.main()
