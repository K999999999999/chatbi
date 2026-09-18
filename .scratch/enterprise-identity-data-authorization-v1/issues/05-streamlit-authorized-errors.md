# 05: 适配 Streamlit Reference Client 的授权错误

**What to build:**

让 Streamlit 继续作为 Reference Client，但正确处理服务端授权结果：

- 继续通过 Query API 发起查询。
- 不在 Streamlit 中复制身份白名单或授权规则。
- 正确展示 401、403 和 503 的受控错误。
- 不允许通过页面参数提交或切换身份。
- 保留现有结果展示、请求编号和链路编号能力。

**Blocked by:**

02: 接入 Query API 服务端身份授权

**Status:** done

## Acceptance criteria

- [x] Streamlit 成功查询仍通过 Query API 和统一 Application Service。
- [x] 401、403、503 被转换为受控用户提示。
- [x] Streamlit 不直接调用 LLM、Retrieval、SQL Guard 或 PostgreSQL。
- [x] Streamlit 不包含第二套授权规则。
- [x] Streamlit 测试验证身份字段不会进入请求体。
- [x] API 返回的 request_id 和可用的 trace id 仍能按现有规则展示。

## Result

已完成 Streamlit Reference Client 的授权错误适配：

- 成功查询继续只通过 Query API 发起，请求体仍只有 `question`，没有 subject、Provider、role 或数据范围字段。
- 401、403、503 使用前端固定的受控提示；即使错误响应正文含内部信息，也不会原样展示到页面。
- 保留 API 返回的 `request_id` 和 `X-Trace-ID` 展示；Streamlit 不直接连接 LLM、Retrieval、SQL Guard 或 PostgreSQL，也不复制授权规则。

验证证据：

- `uv run --with pytest python -m pytest -q tests/streamlit/test_streamlit_app.py`：11 passed，3 subtests passed。
- `uv run --with pytest python -m pytest -q tests/streamlit tests/query_api`：39 passed，13 subtests passed。
- `uv run --with pytest python -m pytest -q`：328 passed，6 skipped，110 subtests passed。
- `uv run python -m compileall -q src tests`：通过。
- `uv run --python 3.11 --with ruff==0.16.8 ruff format --check src tests`：通过。
- `uv run --python 3.11 --with ruff==0.16.8 ruff check --select E4,E7,E9,F src tests`：通过。
- `git diff --check`：通过。

## Comments

本 Ticket 不建设正式 Web 前端，也不接入真实企业 SSO。Streamlit 继续作为 Reference Client 和作品展示入口。
