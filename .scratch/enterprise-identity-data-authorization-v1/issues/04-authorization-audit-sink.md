# 04: 接入授权审计事件与 AuditSink

**What to build:**

在认证授权决策处生成结构化审计事件，并接入可替换的 AuditSink：

- allow 和 deny 都生成事件。
- 事件包含 request_id、subject_id、identity_provider、resource、action、decision、reason_code、policy_version 和 timestamp。
- 事件不包含 Token、Secret、原始问题、完整 SQL 或查询结果。
- API 请求可以通过 request_id 关联审计事件。
- 使用测试收集器验证事件内容，而不是建设独立审计中心。

**Blocked by:**

01: 建立授权核心与 AuthContext Application Entry

**Status:** open

## Acceptance criteria

- [ ] 授权成功产生一条完整的 allow 事件。
- [ ] 未认证或无权限产生一条完整的 deny 事件。
- [ ] 审计事件不包含 Token、Secret、原始问题、完整 SQL 或查询结果。
- [ ] 审计事件能够关联对应请求。
- [ ] AuditSink 的实现可以被测试替换。
- [ ] 审计事件的 policy_version 和 reason_code 可被确定性验证。
- [ ] AuditSink 不可用时的处理方式在实现前被明确记录，不得静默选择。

## Result

待实现。

## Comments

Spec 尚未确定 AuditSink 不可用时是 Fail Closed 还是受控降级。实现本 Ticket 前必须记录该安全取舍；本 Ticket 不自行补做该决定。
