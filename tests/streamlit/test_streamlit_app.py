"""Streamlit POC（概念验证）页面与 HTTP 客户端测试。"""

from io import BytesIO
import json
from unittest import TestCase
from urllib.error import HTTPError, URLError
from urllib.request import Request

from src.streamlit_app import QueryAPIError, query_api, rows_as_records


class _Response:
    def __init__(self, payload: dict[str, object], status: int = 200) -> None:
        self.status = status
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
            return _Response(payload)

        result = query_api(
            "http://127.0.0.1:8000/",
            "查询销售额",
            opener=opener,
        )

        self.assertEqual(result, payload)
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
                hdrs=None,
                fp=BytesIO(json.dumps(payload).encode("utf-8")),
            )

        with self.assertRaises(QueryAPIError) as raised:
            query_api("http://127.0.0.1:8000", "查询不存在的业务", opener=opener)

        self.assertEqual(raised.exception.error_code, "CANNOT_ANSWER")
        self.assertEqual(raised.exception.request_id, "req-2")
        self.assertEqual(raised.exception.error_message, "当前结构无法回答该问题")

    def test_query_api_converts_unavailable_api_to_controlled_error(self) -> None:
        def opener(_request: Request, *, timeout: float) -> _Response:
            raise URLError("connection refused")

        with self.assertRaises(QueryAPIError) as raised:
            query_api("http://127.0.0.1:8000", "查询销售额", opener=opener)

        self.assertEqual(raised.exception.error_code, "API_UNAVAILABLE")
        self.assertEqual(raised.exception.request_id, "")
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


if __name__ == "__main__":
    import unittest

    unittest.main()
