# HTTP API 与短期多轮查询：整理前的过程记录

来源：`docs/specs/query-api.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 整理前入口说明

# Query API Adapter Spec

当前 Web 长期状态以 [R3 History Spec](../../../docs/specs/history-results-v1.md) 为准：显式 `/api/v1/histories` 与 `/api/v1/saved-results` 保存私人快照，刷新只读，续聊恢复完整条件；旧 `/api/v1/query` 继续原短期 Contract。网页执行使用 R4 后台执行受理、正式结果读取和 SSE 状态观察；完整行为见 [R4 Spec](../../../docs/specs/execution-streaming-v1.md)，实现设计见 [R4 Design](../../../docs/designs/execution-streaming-v1.md)。本文的 R1 / R2 阶段状态描述保留历史边界，不能用来否定 R3 / R4。
## 实现状态

- API Adapter 已落位于 `src/query_api/`。
- `app.py` 提供应用工厂、请求/响应模型、路由和错误映射。
- `main.py` 仅创建无运行资源副作用的应用，`src/bootstrap/` 在 lifespan 内装配真实依赖并执行就绪门禁，`create_app()` 将查询服务绑定为 `AuthorizedQueryService`；失败清理与关闭规则见 [初始化与运行资源 Spec](../../../docs/specs/bootstrap.md)。
- FastAPI 运行依赖已写入 `pyproject.toml`，具体解析版本由 `uv.lock` 锁定。
- API 确定性测试与原有 Online Query、Evaluation 回归测试已通过。
- 已使用真实 `.env` 完成一次 HTTP 到 LLM、SQL Guard 和 PostgreSQL 的闭环验证，返回 `200` 和 1 行结果。
- Multi-Turn Query V1 的公共 Contract 已确认并完成文档同步；Ticket 01～04 已完成会话生命周期、结构化语义修订、Streamlit 当前会话联动和分层验收；真实 AI Evaluation、Real E2E 及本次三轮场景的 Business Acceptance 证据见 `docs/acceptance/multi-turn-query-v1-20260919.md`。

当前 React + TypeScript + Vite 电脑端网页通过同源 HTTP 调用本 API；Streamlit 已移除。历史多轮验收仍按对应运行日期与提交解释。
