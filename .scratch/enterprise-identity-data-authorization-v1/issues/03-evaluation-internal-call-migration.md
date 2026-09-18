# 03: 迁移 Evaluation 与内部调用到显式 Test Identity

**What to build:**

将 Evaluation、Online Query 测试和其他直接调用查询服务的内部调用迁移到统一授权入口：

- 使用显式 Test IdentityProvider 或授权测试身份。
- 不再通过缺少 AuthContext 的方式执行完整查询。
- 保持既有 Evaluation、PostgreSQL 集成和确定性测试的业务行为。
- 将测试中的授权身份、拒绝身份和下游 Spy 固定为可观察 Fixture。
- 不改变指标、Retrieval、Prompt、SQL Guard 或 Evaluation 业务规则。

**Blocked by:**

01: 建立授权核心与 AuthContext Application Entry

**Status:** open

## Acceptance criteria

- [ ] Evaluation 在显式测试身份下可以复用正式 Online Query 链路。
- [ ] 现有确定性测试和 PostgreSQL 集成测试保持通过。
- [ ] 缺少 AuthContext 的非测试查询调用不能绕过授权。
- [ ] 测试能够覆盖允许、未授权和基础设施失败路径。
- [ ] 既有 AI Evaluation 的查询语义和结果比较行为不被改变。
- [ ] 内部测试调用使用统一 Application-level Query Entry，而不是保留另一套授权逻辑。

## Result

待实现。

## Comments

这是迁移阶段。它覆盖 Evaluation、Online Query 测试和其他已确认的内部直接调用，不引入生产身份 Provider。
