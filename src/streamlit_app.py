"""ChatBI 的最小 Streamlit POC 页面。"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


_DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
_DEFAULT_API_TIMEOUT = 90.0
_AUTHORIZATION_ERROR_MESSAGES = {
    "AUTHENTICATION_REQUIRED": "需要有效的身份认证",
    "AUTHORIZATION_DENIED": "当前用户没有该数据资源的访问权限",
    "AUTHENTICATION_UNAVAILABLE": "身份认证服务暂时不可用",
}
_AUTHORIZATION_ERROR_CODES_BY_STATUS = {
    401: "AUTHENTICATION_REQUIRED",
    403: "AUTHORIZATION_DENIED",
    503: "AUTHENTICATION_UNAVAILABLE",
}
_CONVERSATION_ERROR_MESSAGES = {
    "CONVERSATION_UNAVAILABLE": "当前会话已失效，请点击“新建会话”后重新开始",
    "CLARIFICATION_REQUIRED": "请明确需要新增或修改的查询条件",
    "UNSUPPORTED_ANALYSIS": "当前问题超出单条查询修订范围",
    "CONVERSATION_CONFLICT": "当前会话已有进行中的查询，请稍后重试",
}
_CONVERSATION_ID_KEY = "conversation_id"
_CONVERSATION_RESET_REQUIRED_KEY = "conversation_reset_required"


class QueryAPIError(RuntimeError):
    """查询 API 返回的可展示错误。"""

    def __init__(
        self,
        error_code: str,
        error_message: str,
        request_id: str = "",
        trace_id: str = "",
    ) -> None:
        super().__init__(error_message)
        self.error_code = error_code
        self.error_message = error_message
        self.request_id = request_id
        self.trace_id = trace_id


class QueryAPIResponse(dict[str, Any]):
    """保留 JSON shape，同时在页面层保存响应头中的 Trace ID。"""

    def __init__(self, payload: dict[str, Any], *, trace_id: str = "") -> None:
        super().__init__(payload)
        self.trace_id = trace_id


def query_api(
    base_url: str,
    question: str,
    *,
    conversation_id: str | None = None,
    timeout: float = _DEFAULT_API_TIMEOUT,
    opener: Callable[..., Any] | None = None,
) -> QueryAPIResponse:
    """调用现有查询 API，不在页面层执行 LLM 或数据库逻辑。"""
    request_payload: dict[str, str] = {"question": question}
    if isinstance(conversation_id, str) and conversation_id.strip():
        request_payload["conversation_id"] = conversation_id.strip()

    request = Request(
        url=f"{base_url.rstrip('/')}/api/v1/query",
        data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    open_request = urlopen if opener is None else opener
    trace_id = ""

    try:
        with open_request(request, timeout=timeout) as response:
            trace_id = _trace_id_from_response(response)
            payload = _read_json(response.read())
    except HTTPError as exc:
        trace_id = _trace_id_from_response(exc)
        try:
            payload = _read_json(exc.read())
        except (UnicodeDecodeError, ValueError, TypeError):
            raise QueryAPIError(
                "API_ERROR",
                "查询服务返回了无效响应",
                trace_id=trace_id,
            ) from None
        raise _error_from_payload(
            payload,
            "查询服务请求失败",
            trace_id=trace_id,
            status_code=exc.code,
        ) from None
    except (URLError, TimeoutError, OSError):
        raise QueryAPIError("API_UNAVAILABLE", "无法连接查询服务") from None
    except (UnicodeDecodeError, ValueError, TypeError):
        raise QueryAPIError(
            "API_ERROR",
            "查询服务返回了无效响应",
            trace_id=trace_id,
        ) from None

    if "error_code" in payload:
        raise _error_from_payload(
            payload,
            "查询服务请求失败",
            trace_id=trace_id,
        )
    return QueryAPIResponse(payload, trace_id=trace_id)


def rows_as_records(
    columns: list[str],
    rows: list[list[Any]],
) -> list[dict[str, Any]]:
    """将 API 的二维结果转换为 Streamlit 表格可展示的记录。"""
    return [dict(zip(columns, row)) for row in rows]


def format_display_rows(
    columns: list[str],
    rows: list[list[Any]],
) -> list[dict[str, Any]]:
    """只格式化页面展示值，不修改 API 返回的原始结果。"""
    return [
        {
            column: format_display_value(column, value)
            for column, value in zip(columns, row)
        }
        for row in rows
    ]


def format_display_value(column: str, value: Any) -> Any:
    """按结果列名的最小语义约定格式化页面值。"""
    if value is None:
        return None

    normalized_column = column.casefold()
    if normalized_column.endswith("_cny"):
        return _format_decimal(value, decimals=2)
    if normalized_column.endswith("_count") or normalized_column in {"count", "数量"}:
        return _format_decimal(value, decimals=0)
    if normalized_column == "gross_margin" or normalized_column.endswith(
        ("_rate", "_ratio", "_percent", "_percentage")
    ):
        try:
            percentage = _as_decimal(value) * 100
        except (InvalidOperation, ValueError):
            return value
        return f"{_format_decimal(percentage, decimals=2)}%"
    return value


def main() -> None:
    """渲染单页查询界面。"""
    import streamlit as st

    st.set_page_config(page_title="ChatBI 查询", page_icon="📊")
    st.title("ChatBI 查询")
    st.caption("输入自然语言问题，查询 mart_sales 数据。")

    if st.button("新建会话"):
        _start_new_conversation(st)
        st.rerun()

    with st.form("query_form"):
        question = st.text_area(
            "问题",
            placeholder="例如：当前已完成订单数量是多少？",
            height=100,
        )
        submitted = st.form_submit_button("查询", type="primary")

    if submitted:
        _submit_query(st, question)

    response = st.session_state.get("last_query_response")
    error = st.session_state.get("last_query_error")
    if error is not None:
        _render_error(st, error)
    elif response is not None:
        _render_success(st, response)


def _submit_query(st: Any, question: str) -> None:
    if not question.strip():
        st.session_state.last_query_response = None
        st.session_state.last_query_error = QueryAPIError(
            "INVALID_REQUEST",
            "请输入问题",
        )
        return

    if st.session_state.get(_CONVERSATION_RESET_REQUIRED_KEY, False):
        st.session_state.last_query_response = None
        st.session_state.last_query_error = QueryAPIError(
            "CONVERSATION_UNAVAILABLE",
            _CONVERSATION_ERROR_MESSAGES["CONVERSATION_UNAVAILABLE"],
        )
        return

    base_url = os.environ.get("CHATBI_API_BASE_URL", _DEFAULT_API_BASE_URL).strip()
    if not base_url:
        base_url = _DEFAULT_API_BASE_URL
    conversation_id = st.session_state.get(_CONVERSATION_ID_KEY)
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        conversation_id = None
    else:
        conversation_id = conversation_id.strip()

    with st.spinner("正在查询..."):
        try:
            response = query_api(
                base_url,
                question,
                conversation_id=conversation_id,
            )
        except QueryAPIError as error:
            st.session_state.last_query_response = None
            st.session_state.last_query_error = error
            if error.error_code == "CONVERSATION_UNAVAILABLE":
                st.session_state[_CONVERSATION_ID_KEY] = None
                st.session_state[_CONVERSATION_RESET_REQUIRED_KEY] = True
        else:
            st.session_state.last_query_response = response
            st.session_state.last_query_error = None
            response_conversation_id = response.get(_CONVERSATION_ID_KEY)
            if (
                isinstance(response_conversation_id, str)
                and response_conversation_id.strip()
            ):
                st.session_state[_CONVERSATION_ID_KEY] = (
                    response_conversation_id.strip()
                )
            elif conversation_id is None:
                st.session_state[_CONVERSATION_ID_KEY] = None
            st.session_state[_CONVERSATION_RESET_REQUIRED_KEY] = False


def _start_new_conversation(st: Any) -> None:
    """清除页面层会话引用，不触碰服务端会话或业务状态。"""
    st.session_state[_CONVERSATION_ID_KEY] = None
    st.session_state[_CONVERSATION_RESET_REQUIRED_KEY] = False
    st.session_state.last_query_response = None
    st.session_state.last_query_error = None


def _render_error(st: Any, error: QueryAPIError) -> None:
    st.error(f"{error.error_code}：{error.error_message}")
    if error.request_id:
        st.caption(f"请求编号：{error.request_id}")
    if error.trace_id:
        st.caption(f"链路编号：{error.trace_id}")


def _render_success(st: Any, response: dict[str, Any]) -> None:
    st.subheader("查询结果")
    columns = response.get("columns", [])
    rows = response.get("rows", [])
    if rows:
        st.dataframe(
            format_display_rows(columns, rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("暂无数据")

    metric_columns = st.columns(2)
    metric_columns[0].metric("返回行数", response.get("row_count", len(rows)))
    metric_columns[1].metric(
        "结果状态",
        "已截断" if response.get("truncated", False) else "完整",
    )

    with st.expander("查看 SQL"):
        st.code(response.get("sql", ""), language="sql")

    request_id = response.get("request_id")
    if request_id:
        st.caption(f"请求编号：{request_id}")
    trace_id = getattr(response, "trace_id", "")
    if isinstance(trace_id, str) and trace_id:
        st.caption(f"链路编号：{trace_id}")


def _read_json(data: bytes) -> dict[str, Any]:
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("API 响应不是 JSON 对象")
    return payload


def _trace_id_from_response(response: Any) -> str:
    """只读取 X-Trace-ID，不把完整响应头带入页面或错误信息。"""
    headers = getattr(response, "headers", None)
    value: Any = None
    if headers is not None:
        getter = getattr(headers, "get", None)
        if callable(getter):
            value = getter("X-Trace-ID")
            if value is None:
                value = getter("x-trace-id")
    if value is None:
        getheader = getattr(response, "getheader", None)
        if callable(getheader):
            value = getheader("X-Trace-ID")
    return value.strip() if isinstance(value, str) else ""


def _format_decimal(value: Any, *, decimals: int) -> Any:
    try:
        number = _as_decimal(value)
    except (InvalidOperation, ValueError):
        return value

    quantum = Decimal(1).scaleb(-decimals)
    rounded = number.quantize(quantum, rounding=ROUND_HALF_UP)
    return format(rounded, ",.{}f".format(decimals))


def _as_decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _error_from_payload(
    payload: dict[str, Any],
    fallback_message: str,
    *,
    trace_id: str = "",
    status_code: int | None = None,
) -> QueryAPIError:
    payload_error_code = payload.get("error_code")
    error_code = (
        payload_error_code
        if isinstance(payload_error_code, str) and payload_error_code
        else _AUTHORIZATION_ERROR_CODES_BY_STATUS.get(status_code, "API_ERROR")
    )
    error_message = payload.get("error_message")
    request_id = payload.get("request_id")
    return QueryAPIError(
        error_code,
        (
            _AUTHORIZATION_ERROR_MESSAGES[error_code]
            if error_code in _AUTHORIZATION_ERROR_MESSAGES
            else _CONVERSATION_ERROR_MESSAGES[error_code]
            if error_code in _CONVERSATION_ERROR_MESSAGES
            else error_message
            if isinstance(error_message, str) and error_message
            else fallback_message
        ),
        request_id if isinstance(request_id, str) else "",
        trace_id,
    )


if __name__ == "__main__":
    main()
