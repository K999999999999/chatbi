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

**Status:** open

## Acceptance criteria

- [ ] Streamlit 成功查询仍通过 Query API 和统一 Application Service。
- [ ] 401、403、503 被转换为受控用户提示。
- [ ] Streamlit 不直接调用 LLM、Retrieval、SQL Guard 或 PostgreSQL。
- [ ] Streamlit 不包含第二套授权规则。
- [ ] Streamlit 测试验证身份字段不会进入请求体。
- [ ] API 返回的 request_id 和可用的 trace id 仍能按现有规则展示。

## Result

待实现。

## Comments

本 Ticket 不建设正式 Web 前端，也不接入真实企业 SSO。Streamlit 继续作为 Reference Client 和作品展示入口。
