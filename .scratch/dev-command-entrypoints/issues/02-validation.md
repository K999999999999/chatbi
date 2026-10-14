# T02 定向检查、测试与评测报告校验

Status: done
Spec: [已确认行为](../spec.md)；[设计](../design.md)；[共用完成规则](../tickets-draft.md#共用done-when与证据要求)。
Authorization: 用户确认七项拆分及全部本地实现、验证与提交；远端未授权。

- Change Profile: 短期验证CLI扩展与旧runner迁移；中等；验证身份/漏测风险；确定性测试+隔离PG；本地交付。
- Owner: 当前主 Agent；长期归container_tasks/测试与evaluation。
- Blocked by: T01。
- What to build: check docs/python/boundaries、固定Ruff入口、evaluate validate；保持test各suite及all；核对旧run_database_tests独有profile/失败清理/路径能力并迁移引用。
- owned files: dev、scripts/container_tasks.sh、scripts/run_database_tests.py、对应tests/scripts/evaluation；Runbook与容器开发Contract。不改模型/案例口径。
- Acceptance Criteria: 完整check保留全部范围；定向结果不能混报；数据库ci/development覆盖及隔离清理保持；软件测试不真实问LLM；报告commit/RAG/cases不匹配拒绝，无DB/LLM调用；linked worktree提交和dirty不失真。
- 验证证据: 路由/无调用回归、报告校验回归、实际普通clone和linked worktree Git可见性；隔离数据库两profile；旧runner与新链能力逐项对照，覆盖不足保留并注明。
- Migration / Rollback: Expand新子命令，证明coverage后迁移旧runner；原参数保留；代码回滚不影响业务数据，保留迁移台账。
- Done When: check/test/evaluate公开入口完整，旧runner处置有证据，CI可直接复用；定向及完整验证各自如实记录。


## Result

定向check、固定Ruff0.16.8及报告校验接通；Python全量、双profile PG、网页与PDF测试完成。旧数据库runner独有路径/profile能力保留兼容，推荐入口统一为dev，未丢弃断言。

证据范围、故障修复及未运行验证见[整体验收记录](../acceptance.md)，[Code Review](../code-review.md)结论适用于本地候选；提交身份见Git公共目录实时记录。

## Comments

从草案正式写入，适用基线master@38e1302。
