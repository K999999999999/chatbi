# 02: 接入 Query API 服务端身份授权

**What to build:**

将 FastAPI Query API 迁移到授权入口：

- 由服务端 Identity Provider Adapter 生成 AuthContext。
- 请求体继续只接收查询问题，不能接收 subject_id、角色或数据范围。
- 接入静态授权策略。
- 将身份失败、授权失败和认证基础设施故障映射为 401、403、503。
- 显式选择 Demo/Test Provider。
- 生产环境启用 Demo/Test Provider 时拒绝启动或拒绝请求。
- 保留现有受控错误响应和 request_id 关联。
- 保持健康检查等不执行用户数据查询的运维端点不进入用户查询授权链路。

**Blocked by:**

01: 建立授权核心与 AuthContext Application Entry

**Status:** open

## Acceptance criteria

- [ ] 已授权 HTTP 请求能够得到原有只读查询结果。
- [ ] 未认证请求返回 401，且不调用查询服务。
- [ ] 已认证但未授权请求返回 403，且不调用查询服务。
- [ ] Provider 或策略存储不可用时 Fail Closed，并返回 503 或统一服务错误。
- [ ] 伪造请求体身份字段不能冒用其他用户。
- [ ] 生产配置不能自动回退到 Demo 身份。
- [ ] 现有 request_id 和受控错误响应 Contract 保持可观察一致。
- [ ] Query API 不复制 Online Query、SQL Guard 或数据库执行逻辑。

## Result

待实现。

## Comments

本 Ticket 负责正式 HTTP 用户入口的安全接入，不接入具体企业 SSO。真实 Provider 仍由后续独立 Feature 通过 Adapter 提供。
