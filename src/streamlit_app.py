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
_AUTHENTICATION_FAILED_MESSAGE = "用户名或密码错误"
_CONVERSATION_ERROR_MESSAGES = {
    "CONVERSATION_UNAVAILABLE": "当前会话已失效，请点击“新建会话”后重新开始",
    "CLARIFICATION_REQUIRED": "请明确需要新增或修改的查询条件",
    "UNSUPPORTED_ANALYSIS": "当前问题超出单条查询修订范围",
    "CONVERSATION_CONFLICT": "当前会话已有进行中的查询，请稍后重试",
}
_CONVERSATION_ID_KEY = "conversation_id"
_CONVERSATION_RESET_REQUIRED_KEY = "conversation_reset_required"
_CONVERSATION_TIMELINE_KEY = "conversation_timeline"
_ANALYSIS_TIMELINE_KEY = "analysis_timeline"
_AUTH_TOKEN_KEY = "auth_token"
_AUTH_USERNAME_KEY = "auth_username"
_AUTH_MUST_CHANGE_KEY = "auth_must_change_password"


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


class AuthAPIResponse(dict[str, Any]):
    """登录 API 响应的安全 JSON shape。"""

    def __init__(self, payload: dict[str, Any], *, trace_id: str = "") -> None:
        super().__init__(payload)
        self.trace_id = trace_id


def query_api(
    base_url: str,
    question: str,
    *,
    conversation_id: str | None = None,
    mode: str = "query",
    timeout: float = _DEFAULT_API_TIMEOUT,
    access_token: str | None = None,
    opener: Callable[..., Any] | None = None,
) -> QueryAPIResponse:
    """调用现有查询 API，不在页面层执行 LLM 或数据库逻辑。"""
    request_payload: dict[str, str] = {"question": question}
    if mode != "query":
        request_payload["mode"] = mode
    if mode != "analysis" and isinstance(conversation_id, str) and conversation_id.strip():
        request_payload["conversation_id"] = conversation_id.strip()

    headers = {"Content-Type": "application/json"}
    if isinstance(access_token, str) and access_token.strip():
        headers["Authorization"] = f"Bearer {access_token.strip()}"
    request = Request(
        url=f"{base_url.rstrip('/')}/api/v1/query",
        data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
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


def login_api(
    base_url: str,
    username: str,
    password: str,
    *,
    timeout: float = _DEFAULT_API_TIMEOUT,
    opener: Callable[..., Any] | None = None,
) -> AuthAPIResponse:
    """调用本地账号登录 API；Token 只返回给当前页面状态。"""

    payload = _auth_json_request(
        base_url,
        "/auth/login",
        {"username": username, "password": password},
        timeout=timeout,
        opener=opener,
    )
    return AuthAPIResponse(payload)


def change_password_api(
    base_url: str,
    access_token: str,
    current_password: str,
    new_password: str,
    *,
    timeout: float = _DEFAULT_API_TIMEOUT,
    opener: Callable[..., Any] | None = None,
) -> None:
    """修改密码；成功后服务端会撤销旧 Token。"""

    _auth_json_request(
        base_url,
        "/auth/change-password",
        {"current_password": current_password, "new_password": new_password},
        access_token=access_token,
        timeout=timeout,
        opener=opener,
        expect_json=False,
    )


def logout_api(
    base_url: str,
    access_token: str,
    *,
    timeout: float = _DEFAULT_API_TIMEOUT,
    opener: Callable[..., Any] | None = None,
) -> None:
    """撤销当前本地账号 Session。"""

    _auth_json_request(
        base_url,
        "/auth/logout",
        {},
        access_token=access_token,
        timeout=timeout,
        opener=opener,
        expect_json=False,
    )


def _auth_json_request(
    base_url: str,
    path: str,
    payload: dict[str, str],
    *,
    access_token: str | None = None,
    timeout: float,
    opener: Callable[..., Any] | None,
    expect_json: bool = True,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if isinstance(access_token, str) and access_token.strip():
        headers["Authorization"] = f"Bearer {access_token.strip()}"
    request = Request(
        url=f"{base_url.rstrip('/')}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    open_request = urlopen if opener is None else opener
    try:
        with open_request(request, timeout=timeout) as response:
            trace_id = _trace_id_from_response(response)
            body = response.read()
    except HTTPError as exc:
        trace_id = _trace_id_from_response(exc)
        try:
            error_payload = _read_json(exc.read())
        except (UnicodeDecodeError, ValueError, TypeError):
            error_payload = {}
        if path == "/auth/login" and exc.code == 401:
            raise QueryAPIError(
                "AUTHENTICATION_FAILED",
                _AUTHENTICATION_FAILED_MESSAGE,
                trace_id=trace_id,
            ) from None
        raise _error_from_payload(
            error_payload,
            "账号服务请求失败",
            trace_id=trace_id,
            status_code=exc.code,
        ) from None
    except (URLError, TimeoutError, OSError):
        raise QueryAPIError("API_UNAVAILABLE", "无法连接账号服务") from None

    if not expect_json:
        return {}
    try:
        return _read_json(body)
    except (UnicodeDecodeError, ValueError, TypeError):
        raise QueryAPIError(
            "API_ERROR",
            "账号服务返回了无效响应",
            trace_id=trace_id,
        ) from None


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

    _initialize_auth_state(st)
    if not _access_token(st):
        _render_login(st)
        return
    if st.session_state.get(_AUTH_MUST_CHANGE_KEY, False):
        _render_change_password(st)
        return

    st.sidebar.caption(f"当前用户：{st.session_state.get(_AUTH_USERNAME_KEY, '')}")
    if st.sidebar.button("退出登录"):
        _logout_current_user(st)
        st.rerun()

    if st.button("新建会话"):
        _start_new_conversation(st)
        st.rerun()

    selected_mode = st.radio(
        "模式",
        options=("普通查询", "经营分析"),
        horizontal=True,
    )
    if selected_mode == "经营分析":
        with st.form("analysis_form"):
            question = st.text_area(
                "经营问题",
                placeholder="例如：最近三个月销售额为什么下降？",
                height=100,
            )
            submitted = st.form_submit_button("开始经营分析", type="primary")
        if submitted:
            _submit_analysis(st, question)
        _render_analysis_timeline(
            st,
            st.session_state.get(_ANALYSIS_TIMELINE_KEY, []),
        )
    else:
        with st.form("query_form"):
            question = st.text_area(
                "问题",
                placeholder="例如：当前已完成订单数量是多少？",
                height=100,
            )
            submitted = st.form_submit_button("查询", type="primary")
        if submitted:
            _submit_query(st, question)
        timeline = st.session_state.get(_CONVERSATION_TIMELINE_KEY, [])
        _render_timeline(st, timeline)


def _initialize_auth_state(st: Any) -> None:
    st.session_state.setdefault(_AUTH_TOKEN_KEY, None)
    st.session_state.setdefault(_AUTH_USERNAME_KEY, "")
    st.session_state.setdefault(_AUTH_MUST_CHANGE_KEY, False)


def _access_token(st: Any) -> str | None:
    token = st.session_state.get(_AUTH_TOKEN_KEY)
    return token.strip() if isinstance(token, str) and token.strip() else None


def _render_login(st: Any) -> None:
    st.subheader("登录")
    with st.form("login_form"):
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        submitted = st.form_submit_button("登录", type="primary")
    if not submitted:
        return
    base_url = _api_base_url()
    try:
        response = login_api(base_url, username, password)
    except QueryAPIError as error:
        _render_error(st, error)
        return
    st.session_state[_AUTH_TOKEN_KEY] = response.get("access_token")
    st.session_state[_AUTH_USERNAME_KEY] = response.get("username", username)
    st.session_state[_AUTH_MUST_CHANGE_KEY] = bool(
        response.get("must_change_password", False)
    )
    st.rerun()


def _render_change_password(st: Any) -> None:
    st.subheader("首次登录需要修改密码")
    with st.form("change_password_form"):
        current_password = st.text_input("当前密码", type="password")
        new_password = st.text_input("新密码（至少 12 位）", type="password")
        submitted = st.form_submit_button("修改密码", type="primary")
    if not submitted:
        return
    try:
        change_password_api(
            _api_base_url(),
            _access_token(st) or "",
            current_password,
            new_password,
        )
    except QueryAPIError as error:
        if error.error_code == "AUTHENTICATION_REQUIRED":
            _logout_current_user(st)
            st.rerun()
        _render_error(st, error)
        return
    st.session_state[_AUTH_TOKEN_KEY] = None
    st.session_state[_AUTH_MUST_CHANGE_KEY] = False
    st.success("密码已修改，请重新登录。")


def _logout_current_user(st: Any) -> None:
    token = _access_token(st)
    if token:
        try:
            logout_api(_api_base_url(), token)
        except QueryAPIError:
            pass
    st.session_state[_AUTH_TOKEN_KEY] = None
    st.session_state[_AUTH_USERNAME_KEY] = ""
    st.session_state[_AUTH_MUST_CHANGE_KEY] = False


def _api_base_url() -> str:
    base_url = os.environ.get("CHATBI_API_BASE_URL", _DEFAULT_API_BASE_URL).strip()
    return base_url or _DEFAULT_API_BASE_URL


def _submit_query(st: Any, question: str) -> None:
    if not question.strip():
        error = QueryAPIError(
            "INVALID_REQUEST",
            "请输入问题",
        )
        st.session_state.last_query_response = None
        st.session_state.last_query_error = error
        _append_timeline_error(st, question, error)
        return

    if st.session_state.get(_CONVERSATION_RESET_REQUIRED_KEY, False):
        st.session_state.last_query_response = None
        st.session_state.last_query_error = QueryAPIError(
            "CONVERSATION_UNAVAILABLE",
            _CONVERSATION_ERROR_MESSAGES["CONVERSATION_UNAVAILABLE"],
        )
        return

    base_url = _api_base_url()
    access_token = _access_token(st)
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
                access_token=access_token,
            )
        except QueryAPIError as error:
            st.session_state.last_query_response = None
            st.session_state.last_query_error = error
            _append_timeline_error(st, question, error)
            if error.error_code == "AUTHENTICATION_REQUIRED":
                _logout_current_user(st)
                st.rerun()
            if error.error_code == "CONVERSATION_UNAVAILABLE":
                st.session_state[_CONVERSATION_ID_KEY] = None
                st.session_state[_CONVERSATION_RESET_REQUIRED_KEY] = True
        else:
            st.session_state.last_query_response = response
            st.session_state.last_query_error = None
            _append_timeline_success(st, question, response)
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


def _submit_analysis(st: Any, question: str) -> None:
    """提交经营分析；不读取或修改普通查询 conversation_id。"""

    if not question.strip():
        error = QueryAPIError("INVALID_REQUEST", "请输入经营分析问题")
        st.session_state.last_analysis_response = None
        st.session_state.last_analysis_error = error
        _append_analysis_timeline_error(st, question, error)
        return

    with st.spinner("正在生成经营分析报告..."):
        try:
            response = query_api(
                _api_base_url(),
                question,
                mode="analysis",
                access_token=_access_token(st),
            )
        except QueryAPIError as error:
            st.session_state.last_analysis_response = None
            st.session_state.last_analysis_error = error
            _append_analysis_timeline_error(st, question, error)
            if error.error_code == "AUTHENTICATION_REQUIRED":
                _logout_current_user(st)
                st.rerun()
        else:
            st.session_state.last_analysis_response = response
            st.session_state.last_analysis_error = None
            _append_analysis_timeline_success(st, question, response)


def _analysis_timeline_records(st: Any) -> list[dict[str, Any]]:
    records = st.session_state.get(_ANALYSIS_TIMELINE_KEY)
    if not isinstance(records, list):
        records = []
        st.session_state[_ANALYSIS_TIMELINE_KEY] = records
    return records


def _append_analysis_timeline_success(
    st: Any,
    question: str,
    response: QueryAPIResponse,
) -> None:
    _analysis_timeline_records(st).append(
        {"question": question, "status": "success", "response": response}
    )


def _append_analysis_timeline_error(
    st: Any,
    question: str,
    error: QueryAPIError,
) -> None:
    _analysis_timeline_records(st).append(
        {"question": question, "status": "error", "error": error}
    )


def _render_analysis_timeline(st: Any, timeline: list[dict[str, Any]]) -> None:
    if not timeline:
        return
    st.subheader("经营分析记录")
    latest_index = len(timeline)
    for index in range(latest_index, 0, -1):
        record = timeline[index - 1]
        with st.expander(
            f"第 {index} 次 · {'成功' if record.get('status') == 'success' else '失败'}",
            expanded=index == latest_index,
        ):
            st.caption(f"问题：{record.get('question', '')}")
            if record.get("status") == "success":
                response = record.get("response")
                if isinstance(response, dict):
                    _render_analysis_report(st, response)
            else:
                error = record.get("error")
                if isinstance(error, QueryAPIError):
                    _render_error(st, error)


def _render_analysis_report(st: Any, response: dict[str, Any]) -> None:
    report = response.get("report")
    if not isinstance(report, dict):
        st.error("经营分析报告格式无效")
        return
    title = report.get("title")
    if isinstance(title, str) and title.strip():
        st.subheader(title)
    for label, key in (
        ("分析摘要", "executive_summary"),
        ("趋势判断", "trend_judgment"),
        ("关键发现", "key_findings"),
        ("原因分析", "root_causes"),
        ("行动建议", "action_suggestions"),
    ):
        value = report.get(key)
        if isinstance(value, list):
            value = "\n".join(f"- {item}" for item in value)
        if isinstance(value, str) and value.strip():
            st.markdown(f"**{label}**\n\n{value}")

    task_results = response.get("task_results", [])
    if isinstance(task_results, list):
        st.caption(f"已执行 {len(task_results)} 个分析 Task")
        for item in task_results:
            if not isinstance(item, dict):
                continue
            task_id = item.get("task_id", "unknown")
            status = item.get("status", "unknown")
            st.caption(f"Task {task_id}：{status}")
            rows = item.get("rows", [])
            columns = item.get("columns", [])
            if isinstance(rows, list) and rows:
                st.dataframe(
                    rows_as_records(columns, rows),
                    use_container_width=True,
                    hide_index=True,
                )


def _start_new_conversation(st: Any) -> None:
    """清除页面层会话引用，不触碰服务端会话或业务状态。"""
    st.session_state[_CONVERSATION_ID_KEY] = None
    st.session_state[_CONVERSATION_RESET_REQUIRED_KEY] = False
    st.session_state.last_query_response = None
    st.session_state.last_query_error = None
    st.session_state[_CONVERSATION_TIMELINE_KEY] = []


def _timeline_records(st: Any) -> list[dict[str, Any]]:
    records = st.session_state.get(_CONVERSATION_TIMELINE_KEY)
    if not isinstance(records, list):
        records = []
        st.session_state[_CONVERSATION_TIMELINE_KEY] = records
    return records


def _append_timeline_success(
    st: Any,
    question: str,
    response: QueryAPIResponse,
) -> None:
    _timeline_records(st).append(
        {
            "question": question,
            "status": "success",
            "response": response,
        }
    )


def _append_timeline_error(
    st: Any,
    question: str,
    error: QueryAPIError,
) -> None:
    _timeline_records(st).append(
        {
            "question": question,
            "status": "error",
            "error": error,
        }
    )


def _render_timeline(st: Any, timeline: list[dict[str, Any]]) -> None:
    if not timeline:
        return

    st.subheader("会话记录")
    latest_index = len(timeline)
    for index in range(latest_index, 0, -1):
        record = timeline[index - 1]
        with st.expander(
            _timeline_label(index, record),
            expanded=index == latest_index,
        ):
            question = record.get("question", "")
            st.caption(f"第 {index} 轮问题：{question}")
            if record.get("status") == "success":
                st.caption("状态：成功")
                response = record.get("response")
                if isinstance(response, dict):
                    _render_success(
                        st,
                        response,
                        title=f"第 {index} 轮结果",
                        show_sql_expander=False,
                    )
            else:
                st.caption("状态：失败")
                error = record.get("error")
                if isinstance(error, QueryAPIError):
                    _render_error(st, error)


def _timeline_label(index: int, record: dict[str, Any]) -> str:
    question = record.get("question", "")
    if record.get("status") == "success":
        response = record.get("response")
        if isinstance(response, dict):
            rows = response.get("rows", [])
            row_count = response.get("row_count", len(rows))
            summary = f"{row_count} 行"
            if response.get("truncated", False):
                summary += " · 已截断"
            return f"第 {index} 轮 · 成功 · {question} · {summary}"
        return f"第 {index} 轮 · 成功 · {question}"

    error = record.get("error")
    error_code = error.error_code if isinstance(error, QueryAPIError) else "错误"
    return f"第 {index} 轮 · 失败 · {question} · {error_code}"


def _render_error(st: Any, error: QueryAPIError) -> None:
    st.error(f"{error.error_code}：{error.error_message}")
    if error.request_id:
        st.caption(f"请求编号：{error.request_id}")
    if error.trace_id:
        st.caption(f"链路编号：{error.trace_id}")


def _render_success(
    st: Any,
    response: dict[str, Any],
    *,
    title: str = "查询结果",
    show_sql_expander: bool = True,
) -> None:
    st.subheader(title)
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

    if show_sql_expander:
        with st.expander("查看 SQL"):
            st.code(response.get("sql", ""), language="sql")
    else:
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
