# 06: 收口旧查询入口 Contract

**What to build:**

完成 Expand–Migrate–Contract 的收口阶段：

- 确认 Query API、Evaluation 和所有测试调用方都已经使用授权入口。
- 删除或封闭缺少 AuthContext 的旧查询入口。
- 防止未来新增内部调用绕过授权。
- 对最终 Application Contract、错误行为和审计行为做一次集成验证。

**Blocked by:**

02: 接入 Query API 服务端身份授权；03: 迁移 Evaluation 与内部调用到显式 Test Identity；04: 接入授权审计事件与 AuditSink

**Status:** open

## Acceptance criteria

- [ ] 没有正式入口可以在缺少可信 AuthContext 时执行用户查询。
- [ ] Query API、Evaluation、Streamlit 和测试全部使用统一授权边界。
- [ ] 旧入口删除或明确限制为不能执行查询的内部过渡接口。
- [ ] mart_sales:query:read_only 之外的访问全部默认拒绝。
- [ ] 最终确定性测试、Query API 测试和 Streamlit 测试通过。
- [ ] 允许、拒绝、故障和审计路径均有可观察证据。
- [ ] 没有新增具体企业 SSO、正式 Web 前端或权限中心范围。

## Result

待实现。

## Comments

这是 Contract 阶段。只有确认 02、03、04 的调用迁移、审计和验证完成后，才能移除旧查询入口。
