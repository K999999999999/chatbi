"""Streamlit POC（概念验证）页面与 HTTP 客户端测试。"""

from io import BytesIO
import json
from unittest import TestCase
from unittest.mock import patch
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
import src.streamlit_app as streamlit_app


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

    def test_query_api_posts_only_question_and_opaque_conversation_id(self) -> None:
        calls: list[Request] = []
        payload = {
            "request_id": "req-follow-up",
            "sql": "SELECT 1",
            "columns": ["value"],
            "rows": [[1]],
            "row_count": 1,
            "truncated": False,
            "conversation_id": "conv-1",
        }

        def opener(request: Request, *, timeout: float) -> _Response:
            del timeout
            calls.append(request)
            return _Response(payload)

        query_api(
            "http://127.0.0.1:8000",
            "按销售区域拆开",
            conversation_id="conv-1",
            opener=opener,
        )

        self.assertEqual(
            json.loads(calls[0].data.decode("utf-8")),
            {
                "question": "按销售区域拆开",
                "conversation_id": "conv-1",
            },
        )

    def test_submit_query_reuses_server_conversation_id_for_follow_up(self) -> None:
        displayed = _FakeStreamlit()
        first = QueryAPIResponse(
            {
                "request_id": "req-first",
                "sql": "SELECT 1",
                "columns": [],
                "rows": [],
                "row_count": 0,
                "truncated": False,
                "conversation_id": "conv-1",
            }
        )
        second = QueryAPIResponse(
            {
                "request_id": "req-second",
                "sql": "SELECT 1",
                "columns": [],
                "rows": [],
                "row_count": 0,
                "truncated": False,
                "conversation_id": "conv-1",
            }
        )
        third = QueryAPIResponse(
            {
                "request_id": "req-third",
                "sql": "SELECT 1",
                "columns": [],
                "rows": [],
                "row_count": 0,
                "truncated": False,
                "conversation_id": "conv-1",
            }
        )

        with patch.object(
            streamlit_app,
            "query_api",
            side_effect=[first, second, third],
        ) as api:
            streamlit_app._submit_query(displayed, "查询销售额")
            streamlit_app._submit_query(displayed, "按销售区域拆开")
            streamlit_app._submit_query(displayed, "再按月份拆开")

        self.assertEqual(displayed.session_state.conversation_id, "conv-1")
        self.assertEqual(api.call_args_list[0].kwargs["conversation_id"], None)
        self.assertEqual(api.call_args_list[1].kwargs["conversation_id"], "conv-1")
        self.assertEqual(api.call_args_list[2].kwargs["conversation_id"], "conv-1")

        timeline = displayed.session_state.conversation_timeline
        self.assertEqual(
            [record["question"] for record in timeline],
            ["查询销售额", "按销售区域拆开", "再按月份拆开"],
        )
        self.assertEqual(
            [record["status"] for record in timeline],
            ["success", "success", "success"],
        )

    def test_timeline_renders_success_and_failure_turns_in_order(self) -> None:
        displayed = _FakeStreamlit()
        timeline = [
            {
                "question": "查询销售额",
                "status": "success",
                "response": QueryAPIResponse(
                    {
                        "request_id": "req-success",
                        "sql": "SELECT 1",
                        "columns": ["value"],
                        "rows": [[1]],
                        "row_count": 1,
                        "truncated": False,
                    }
                ),
            },
            {
                "question": "改看毛利率",
                "status": "error",
                "error": QueryAPIError(
                    "CLARIFICATION_REQUIRED",
                    "请明确需要新增或修改的查询条件",
                ),
            },
        ]

        streamlit_app._render_timeline(displayed, timeline)

        self.assertEqual(
            displayed.subheaders,
            ["会话记录", "第 1 轮结果"],
        )
        self.assertIn("第 1 轮问题：查询销售额", displayed.captions)
        self.assertIn("第 2 轮问题：改看毛利率", displayed.captions)
        self.assertIn("状态：成功", displayed.captions)
        self.assertIn("状态：失败", displayed.captions)
        self.assertEqual(
            displayed.errors,
            ["CLARIFICATION_REQUIRED：请明确需要新增或修改的查询条件"],
        )
        self.assertEqual(
            displayed.expander_calls,
            [
                ("第 2 轮 · 失败 · 改看毛利率 · CLARIFICATION_REQUIRED", True),
                ("第 1 轮 · 成功 · 查询销售额 · 1 行", False),
            ],
        )

    def test_follow_up_failure_keeps_current_conversation_id(self) -> None:
        displayed = _FakeStreamlit()
        displayed.session_state.conversation_id = "conv-1"
        error = QueryAPIError(
            "CLARIFICATION_REQUIRED",
            "请明确需要新增或修改的查询条件",
        )

        with patch.object(streamlit_app, "query_api", side_effect=error):
            streamlit_app._submit_query(displayed, "再看看")

        self.assertEqual(displayed.session_state.conversation_id, "conv-1")
        self.assertIs(displayed.session_state.last_query_error, error)

    def test_expired_conversation_requires_new_session_and_clears_old_id(self) -> None:
        displayed = _FakeStreamlit()
        displayed.session_state.conversation_id = "expired-conv"
        error = QueryAPIError(
            "CONVERSATION_UNAVAILABLE",
            "当前会话已失效，请新建会话后重新开始",
        )

        with patch.object(streamlit_app, "query_api", side_effect=error):
            streamlit_app._submit_query(displayed, "继续查询")

        self.assertIsNone(displayed.session_state.conversation_id)
        self.assertTrue(displayed.session_state.conversation_reset_required)
        self.assertIs(displayed.session_state.last_query_error, error)
        self.assertEqual(
            displayed.session_state.conversation_timeline[0]["status"],
            "error",
        )

        with patch.object(streamlit_app, "query_api") as blocked_api:
            streamlit_app._submit_query(displayed, "继续查询")

        blocked_api.assert_not_called()
        self.assertEqual(
            displayed.session_state.last_query_error.error_code,
            "CONVERSATION_UNAVAILABLE",
        )
        self.assertEqual(len(displayed.session_state.conversation_timeline), 1)

        streamlit_app._start_new_conversation(displayed)

        self.assertIsNone(displayed.session_state.conversation_id)
        self.assertFalse(displayed.session_state.conversation_reset_required)
        self.assertIsNone(displayed.session_state.last_query_response)
        self.assertIsNone(displayed.session_state.last_query_error)
        self.assertEqual(displayed.session_state.conversation_timeline, [])

        response = QueryAPIResponse(
            {
                "request_id": "req-new-session",
                "sql": "SELECT 1",
                "columns": [],
                "rows": [],
                "row_count": 0,
                "truncated": False,
                "conversation_id": "conv-new",
            }
        )
        with patch.object(streamlit_app, "query_api", return_value=response) as api:
            streamlit_app._submit_query(displayed, "重新查询")

        self.assertIsNone(api.call_args.kwargs["conversation_id"])
        self.assertEqual(displayed.session_state.conversation_id, "conv-new")

    def test_query_api_uses_fixed_messages_for_conversation_failures(self) -> None:
        cases = (
            (
                404,
                "CONVERSATION_UNAVAILABLE",
                "当前会话已失效，请点击“新建会话”后重新开始",
            ),
            (
                422,
                "CLARIFICATION_REQUIRED",
                "请明确需要新增或修改的查询条件",
            ),
            (
                422,
                "UNSUPPORTED_ANALYSIS",
                "当前问题超出单条查询修订范围",
            ),
            (
                409,
                "CONVERSATION_CONFLICT",
                "当前会话已有进行中的查询，请稍后重试",
            ),
        )

        for status, error_code, expected_message in cases:
            with self.subTest(error_code=error_code):
                payload = {
                    "request_id": f"req-{error_code}",
                    "error_code": error_code,
                    "error_message": "internal conversation details",
                }

                def opener(_request: Request, *, timeout: float) -> _Response:
                    raise HTTPError(
                        url="http://127.0.0.1:8000/api/v1/query",
                        code=status,
                        msg="HTTP error",
                        hdrs={},
                        fp=BytesIO(json.dumps(payload).encode("utf-8")),
                    )

                with self.assertRaises(QueryAPIError) as raised:
                    query_api("http://127.0.0.1:8000", "继续查询", opener=opener)

                self.assertEqual(raised.exception.error_code, error_code)
                self.assertEqual(raised.exception.error_message, expected_message)

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

    def test_query_api_uses_fixed_messages_for_authorization_failures(self) -> None:
        cases = (
            (
                401,
                "AUTHENTICATION_REQUIRED",
                "需要有效的身份认证",
                "req-auth-required",
                "trace-auth-required",
            ),
            (
                403,
                "AUTHORIZATION_DENIED",
                "当前用户没有该数据资源的访问权限",
                "req-auth-denied",
                "trace-auth-denied",
            ),
            (
                503,
                "AUTHENTICATION_UNAVAILABLE",
                "身份认证服务暂时不可用",
                "req-auth-unavailable",
                "trace-auth-unavailable",
            ),
        )

        for status, error_code, expected_message, request_id, trace_id in cases:
            with self.subTest(status=status):
                payload = {
                    "request_id": request_id,
                    "error_code": error_code,
                    "error_message": "internal secret must not reach the page",
                }

                def opener(_request: Request, *, timeout: float) -> _Response:
                    raise HTTPError(
                        url="http://127.0.0.1:8000/api/v1/query",
                        code=status,
                        msg="HTTP error",
                        hdrs={"X-Trace-ID": trace_id},
                        fp=BytesIO(json.dumps(payload).encode("utf-8")),
                    )

                with self.assertRaises(QueryAPIError) as raised:
                    query_api("http://127.0.0.1:8000", "查询销售额", opener=opener)

                self.assertEqual(raised.exception.error_code, error_code)
                self.assertEqual(raised.exception.error_message, expected_message)
                self.assertEqual(raised.exception.request_id, request_id)
                self.assertEqual(raised.exception.trace_id, trace_id)

    def test_query_api_uses_status_for_malformed_auth_failure_payload(self) -> None:
        payload = {
            "request_id": "req-malformed-auth",
            "error_message": "internal provider details",
        }

        def opener(_request: Request, *, timeout: float) -> _Response:
            raise HTTPError(
                url="http://127.0.0.1:8000/api/v1/query",
                code=503,
                msg="Service Unavailable",
                hdrs={"X-Trace-ID": "trace-malformed-auth"},
                fp=BytesIO(json.dumps(payload).encode("utf-8")),
            )

        with self.assertRaises(QueryAPIError) as raised:
            query_api("http://127.0.0.1:8000", "查询销售额", opener=opener)

        self.assertEqual(raised.exception.error_code, "AUTHENTICATION_UNAVAILABLE")
        self.assertEqual(raised.exception.error_message, "身份认证服务暂时不可用")
        self.assertEqual(raised.exception.request_id, "req-malformed-auth")
        self.assertEqual(raised.exception.trace_id, "trace-malformed-auth")

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

    def test_success_page_displays_trace_id_only_when_response_header_provided_it(
        self,
    ) -> None:
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

    def test_error_page_displays_request_and_trace_ids_without_raw_exception(
        self,
    ) -> None:
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
        self.expander_calls: list[tuple[str, bool]] = []
        self.subheaders: list[str] = []
        self.session_state = _FakeSessionState()

    def error(self, message: str) -> None:
        self.errors.append(message)

    def caption(self, message: str) -> None:
        self.captions.append(message)

    def subheader(self, message: str) -> None:
        self.subheaders.append(message)

    def info(self, _message: str) -> None:
        return None

    def dataframe(
        self,
        _data: object,
        *,
        use_container_width: bool,
        hide_index: bool,
    ) -> None:
        del use_container_width, hide_index

    def columns(self, count: int) -> list[_FakeMetricColumn]:
        return [_FakeMetricColumn() for _ in range(count)]

    def expander(self, label: str, *, expanded: bool = False) -> _FakeContext:
        self.expander_calls.append((label, expanded))
        return _FakeContext()

    def code(self, _code: str, *, language: str) -> None:
        return None

    def spinner(self, _message: str) -> _FakeContext:
        return _FakeContext()


class _FakeSessionState(dict[str, object]):
    def __getattr__(self, name: str) -> object:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name: str, value: object) -> None:
        self[name] = value


if __name__ == "__main__":
    import unittest

    unittest.main()
