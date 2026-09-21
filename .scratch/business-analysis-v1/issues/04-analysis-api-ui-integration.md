# Ticket 04：经营分析 API、UI 与普通查询状态隔离

- Status: open
- Owner: Query API / Streamlit Application
- Blocked by: Ticket 01、Ticket 02、Ticket 03
- Canonical Source: `.scratch/business-analysis-v1/spec.md`

## Change Profile

- Lifetime：经营分析 V1 的用户可观察入口和公共 Application Contract。
- Size：中等偏大；影响 API、Streamlit、文档和普通查询回归。
- Risk：高；涉及公共请求/响应 Contract 和 Multi-Turn 状态边界。
- Evidence：API 确定性测试、Streamlit 测试和普通查询回归。
- Delivery：向后兼容的可选 `mode` 扩展；当前无生产发布要求。

## What to build

- 在现有 `POST /api/v1/query` 增加可选 `mode`。
- 缺失 `mode` 默认按 `query` 处理。
- `mode=query` 保持现有请求、响应、授权、会话和 Multi-Turn 行为。
- `mode=analysis` 调用 Business Analysis Application Workflow。
- `mode=analysis` 携带 `conversation_id` 时，在会话 Store、授权查询和任何 LLM 调用前返回 `400 / INVALID_REQUEST`。
- 增加 `AnalysisSuccessResponse` 和统一 `QueryFailure` 响应映射。
- 更新 `docs/specs/query-api.md`，记录 Query API 只负责模式分派和响应序列化，不拥有经营分析业务编排。
- Streamlit 增加“普通查询”和“经营分析”两个明确入口。
- 经营分析请求不发送普通查询 `conversation_id`。
- 从经营分析切回普通查询时恢复原普通查询会话。
- 经营分析报告不写入 `QueryState`，不作为普通查询隐式上下文。

## Owned files

- `src/query_api/app.py`
- `src/streamlit_app.py`
- `docs/specs/query-api.md`
- `tests/query_api/test_app.py`
- `tests/streamlit/test_streamlit_app.py`

## Acceptance criteria

- 旧的只提交 `question` 的调用继续可用。
- `mode=query` 的旧成功和失败响应保持兼容。
- `analysis + conversation_id` 不读取、创建或修改普通查询会话。
- 经营分析成功响应包含自然语言报告和有界的 TaskResult。
- 经营分析失败响应保持统一 `QueryFailure` 形状。
- 两个 UI 入口提交正确的模式。
- 切换模式时普通查询会话不串入经营分析，切回后普通查询仍能继续。
- API Adapter 不直接调用 LLM、SQL Guard 或数据库。

## Verification evidence

- `tests/query_api/test_app.py` 覆盖 mode 默认值、未知 mode、conversation_id 冲突、响应模型和普通查询回归。
- `tests/streamlit/test_streamlit_app.py` 覆盖两个模式、会话隔离和切换行为。
- 现有 Query API、Multi-Turn 和 Online Query 回归测试继续通过。
- 更新后的 `docs/specs/query-api.md` 与 Feature Spec 一致。

## Migration / Rollback

这是可选请求字段的向后兼容扩展，不涉及数据库或会话数据迁移。回滚后旧调用方仍按普通查询运行；不创建 AnalysisState，也不删除普通查询状态。

## Done When

- 用户能够从同一个 Streamlit 页面明确选择普通查询或经营分析。
- API、UI 和普通查询会话边界测试通过。
- Query API Module Contract 已同步更新。
- 普通查询现有行为无回归。

## Result

Not started.

## Comments

- Ticket Readiness Review：READY。
- 该 Ticket 不引入自动 `QueryRouter`，用户选择的 UI mode 就是顶层路由。

