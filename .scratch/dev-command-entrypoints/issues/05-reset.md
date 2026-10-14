# T05 开发项目数据重置

Status: done
Spec: [已确认行为](../spec.md)；[设计](../design.md)；[共用完成规则](../tickets-draft.md#共用done-when与证据要求)。
Authorization: 用户确认七项拆分及全部本地实现、验证与提交；远端未授权。

- Change Profile: 短期维护入口迁移；中等；高风险不可逆删除；纯校验+真实专属临时资源；本地交付。
- Owner: 当前主 Agent；长期归dev维护。归属或停止验证失败立即停止，不扩大删除集合。
- Blocked by: T01。
- What to build: reset postgres/qdrant宿主编排与容器内校验/迁移；复用现有卷验证和删除确认；迁移旧宿主执行边界。
- owned files: dev、scripts/reset_dev_postgres.py、reset_dev_qdrant.py、compose_volume_reset.py及必要Bash编排、tests/scripts重置回归；Runbook与容器开发Contract。
- Acceptance Criteria: 仅dev；明确目标和范围；取消/EOF/标签错/外部卷/停止失败不删除；先停止API/Web及目标服务并复核归属；仅删目标卷；PG基础Seed+完整迁移、无管理员；QD无索引；API/Web保持停止，其他资源不变。
- 验证证据: 拒绝路径确定性回归；真实临时项目删除确认、卷身份、停止保护、权限与重新迁移；保留另一卷内容与其他项目身份对照。测试资源带专属标签，清理也验证归属。
- Migration / Rollback: 先提供新入口再迁移旧CLI消费者；代码可回滚，卷删除不可回滚，不承诺自动恢复；测试失败只清理有归属证明的测试资源。
- Done When: 两种重置完整闭环及安全拒绝证据，旧调用处置明确，无Docker socket扩权。


## Result

dev专属PG/Qdrant重置和旧CLI委派完成。真实临时资源验证取消、外部/错标签拒绝、停止失败保护、仅目标卷删除与重新迁移；另一卷、另一项目保持，API/Web停止。

证据范围、故障修复及未运行验证见[整体验收记录](../acceptance.md)，[Code Review](../code-review.md)结论适用于本地候选；提交身份见Git公共目录实时记录。

## Comments

从草案正式写入，适用基线master@38e1302。
