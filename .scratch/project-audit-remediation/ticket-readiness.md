# 审计修复 Ticket Readiness

Ticket Readiness: READY

Scope: [已确认Spec](spec.md)与[12项Ticket草案](ticket-drafts.md)，适用基线`8d01740474b2c727131e54a70a2f186713b306ad`。当前主Agent只读审查，未启动独立Agent，未创建正式issues文件或产品修复。

## Change Profile / Owner

长期维护的22项缺陷修复，分12个有界切片，按同一branch顺序推进；各项包含实现、回归和文档。高风险范围包括SQL Guard、共享额度/幂等、账号事务、数据清理与公开边界。Owner为当前主Agent，维护归现有模块；无新团队、依赖、SDK、锁文件或Schema迁移。仅本地candidate，远端发布未授权。

## Findings 与处置

1. **编号覆盖。** 程序核对22个AUD在草案中各归属一次；AUD014不计缺陷。12项均包含Change Profile、Owner、直接依赖、owned files、What to build、正常/失败验收、证据、恢复和Done When。结果尚未执行，没有把规划当测试通过。
2. **行为切片。** 01查询安全、02历史执行保护、03checkpoint、04分析展示/文件、05重查、06检索资源/故障、07嵌套安全、08本机配置、09初始化、10验证入口、11隔离验收生命周期、12历史状态及最终证据，各自有可观察结果。02的多个AUD沿同一执行生命周期验证；10的多个入口保留各自测试seam与失败判定，不伪装为一次真实场景全部覆盖。
3. **关键设计。** [设计审查](design-review.md)D1–D4已落实并复核。Spec明确幂等后/新写入前的Application受理回调、租约归属、PG事务初始化互斥、expired遗留回收及tombstone、逐层公开结构验证和隔离故障清理，没有需要在代码中猜测的Contract或权限决定。
4. **环境准备。** 已只读核实Docker client/server `29.5.3`、Compose `5.1.4`；新worktree缺.env与模型缓存，原配置仅核对模式0644、原模型缓存目录存在，未读取值。这是实施准备，不是产品已通过。草案已明确准备0600独立配置、专属Compose资源/输出，以及固定revision模型准备，不能退回日常环境。
5. **可恢复边界。** 可处理INT/TERM执行恢复；不可捕获SIGKILL保留准确身份与备份供恢复，不承诺当场清理成功。checkpoint删除和模型调用费用不可回滚；不通过回退代码伪造数据恢复。该细化避免无法兑现的验收，不改变隔离与清理目标。
6. **事实源与文件归属。** Spec定义行为，审查记录定义已核对约束，正式Docs保持权威，Tickets不重定义业务。重叠文件按同branch顺序修改；新增必要测试文件可在现有目录内记录，不能扩展行为。原worktree已有审计导航修改保留，不自动加入本次Commit。

## Dependencies

01–11独立启动；仅共享文件不构成阻塞依赖。12直接依赖01–11全部完成，不存在循环依赖、逐Ticket PR或另一个集成候选。连续实施仍按用户确认的同一整体范围执行。

## Migration / Rollback

无Schema/公开协议替换，无真实生产发布，不新增Feature Flag。代码可按相关Commit回退；回退会重新暴露原缺陷。按既有Contract清理的到期checkpoint不可恢复；验收专用账号按准确id+username禁用并撤销Session。原.env只变更权限、值不变，原工作区其他修改保持。意外出现迁移或公共Contract变更须返回Spec/Design Review。

## Evidence

软件层采用Guard/API/Application/Store/browser/renderer/脚本回归；PG事务和checkpoint用真实数据库；正式三套真实AI评测与隔离容器业务验收只对clean candidate执行并核对provenance。实际PDF验证名称/索引/值对应；故障路径采用合成canary和可控事件。所有结果分层汇报，skip、host平台和托管runner未执行不冒称通过；首轮失败报告保留。规划检查与覆盖断言通过，产品回归尚未运行。

Next: 用户已确认12项拆分及整体本地实施授权；12项正式Tickets已写入[issues](issues/)，按依赖连续完成全部工作，不逐项等待“继续”。不含Push、PR或远端工作流触发。
