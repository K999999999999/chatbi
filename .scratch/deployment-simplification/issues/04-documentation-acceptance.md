# 04 单一使用说明与最终全量验收

Status: done
Canonical Source: [Spec](../spec.md)、[Design](../design.md)。用户确认四项拆分及完整本地实施、验证、Commit；无发布授权。


Change Profile: 本次交付关闭与持续文档 / 中等 / 中风险（证据完整、首次部署）/ 全量验证、Business Acceptance与Code Review / 默认本地交付。
Owner: 当前实施Agent。
Blocked by: 03

### What to build / Scope

整理README/Runbook，移除宿主/Stable教程，说明dev与Dockerfile用途、首次步骤、配置、测试、调试和标准构建。迁移R7剩余应用Contract，归档失效运维Spec/Design，修复当前及历史链接，同步Architecture/Product Scope/Roadmap。清理失效CI入口，完成最终候选全量测试、构建、独立首次部署与真实业务闭环。

Owned files: README.md、docs/runbook.md、architecture.md、product-scope.md、roadmap.md；docs/specs/local-deployment-v1.md、local-operations-v1.md及query-api/execution/observability/bootstrap/container-dev的相关规则；docs/designs/local-deployment-v1.md、local-operations-v1.md；.github/workflows/ci.yml、real-e2e.yml必要适配；历史文档归档与引用；.scratch/deployment-simplification验收/Review/状态证据。

Out of Scope: 功能优先级重排、历史报告重标、评测案例变化、实际Stable资源替换/删除、Push/PR。

### Acceptance criteria

- README唯一推荐dev入口，宿主仅要求Docker/Compose/Git/Bash；Runbook覆盖配置、首次/日常、测试/调试/评测，当前步骤实际可执行。
- R7应用保护规则有唯一正式权威入口，运维历史保留且不再作为当前承诺；当前/历史Markdown链接通过。
- 最终候选全量Python、两PG profile、前端类型/build/export、浏览器、renderer、质量/锁文件/文档/边界及适用安全检查完成。
- 开发和标准应用Compose各在隔离资源验证首次准备；真实登录、问数/追问、分析、历史成果、XLSX/PNG/PDF及重启持久性验证；源码热更新在开发模式验证。
- 记录所有失败/skip/未执行项及原因、候选/资源身份；未完成的必要验收不能标done。业务/模型不变的历史Evaluation只作为原基线并说明未重跑理由。
- 日常/旧Stable容器、卷、配置、备份和密钥未被更改；仅清理新建验收资源及临时账号。

Evidence: 验收报告和运行资源身份、测试结果、目标Commit关联、完整Diff/Contract Code Review、历史去向和链接、Roadmap适用性结论、Harness检查。
Migration / Rollback: 链接在归档前列出闭包，独有历史内容不丢失；验收失败修复后重跑受影响检查，不伪造完成；真实资源不做rollout，因此无平台回滚步骤。
Done When: 所有适用验收通过且限制准确披露，正式事实源/历史去向/CI/Review一致，全部Tickets完成；本地交付与发布授权边界明确。
Result: 已完成本目标范围；验证与失败处置见[验收](../acceptance.md)，当前上下文Code Review记录见[Review](../code-review.md)。
Comments: 真实模型验收按本目标确认的测试范围运行；不可用凭据或下载失败需报告并保留未完成状态。发布须另行明确授权。
