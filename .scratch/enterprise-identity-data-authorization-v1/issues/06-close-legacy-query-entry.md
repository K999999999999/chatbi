# 06: 收口旧查询入口 Contract

**What to build:**

完成 Expand–Migrate–Contract 的收口阶段：

- 确认 Query API、Evaluation 和所有测试调用方都已经使用授权入口。
- 删除或封闭缺少 AuthContext 的旧查询入口。
- 防止未来新增内部调用绕过授权。
- 对最终 Application Contract、错误行为和审计行为做一次集成验证。

**Blocked by:**

02: 接入 Query API 服务端身份授权；03: 迁移 Evaluation 与内部调用到显式 Test Identity；04: 接入授权审计事件与 AuditSink

**Status:** done

## Acceptance criteria

- [x] 没有正式入口可以在缺少可信 AuthContext 时执行用户查询。
- [x] Query API、Evaluation、Streamlit 和测试全部使用统一授权边界。
- [x] 旧入口删除或明确限制为不能执行查询的内部过渡接口。
- [x] mart_sales:query:read_only 之外的访问全部默认拒绝。
- [x] 最终确定性测试、Query API 测试和 Streamlit 测试通过。
- [x] 允许、拒绝、故障和审计路径均有可观察证据。
- [x] 没有新增具体企业 SSO、正式 Web 前端或权限中心范围。

## Result

已完成 Query Entry Contract 的收口：

- `AuthorizedQueryService.query(auth_context=...)` 是 Query API 的正式用户查询入口；Evaluation 使用绑定显式测试身份的 `BoundAuthorizedQueryService.query()`；Streamlit 只能通过 HTTP 调用 Query API。
- 删除旧 `OnlineQueryService.query()` 方法，改为只供授权入口调用的下游 `OnlineQueryService.execute()`；`src.online_query` 不再导出旧 Service 入口。低层 Online Query 单元测试仍可验证执行器业务行为，但不再把它当作用户查询入口。
- Query API 生产装配、Evaluation 评测装配和授权 Contract 测试均验证身份缺失、授权拒绝、策略/Provider 故障、审计失败和授权成功路径；`mart_sales:query:read_only` 之外仍由静态策略默认拒绝。
- 未新增具体企业 SSO、正式 Web 前端、权限中心或独立审计中心。

验证证据：

- `uv run --with pytest python -m pytest -q tests/authorization tests/query_api tests/online_query tests/evaluation tests/streamlit`：274 passed，6 skipped，98 subtests passed。
- `uv run --with pytest python -m pytest -q`：329 passed，6 skipped，110 subtests passed。
- `uv run python -m compileall -q src tests`：通过。
- `uv run --python 3.11 --with ruff==0.16.8 ruff format --check src tests`：通过。
- `uv run --python 3.11 --with ruff==0.16.8 ruff check --select E4,E7,E9,F src tests`：通过。
- `git diff --check`：通过。

## Comments

这是 Contract 阶段。只有确认 02、03、04 的调用迁移、审计和验证完成后，才能移除旧查询入口。
