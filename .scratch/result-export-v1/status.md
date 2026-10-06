# R5 路线规划快照

Last updated: 2026-10-07
Status: completed
Stage: Ticket 01–04 与 R5 clean candidate 验收已完成；PR #56 已合并至 master（`367a42a`），required CI 全部通过；未做生产部署
Authorization: 用户于 2026-10-06 确认四项 Ticket 拆分与连续完成 01–04；2026-10-07 用户指令“提交pr”授权 R5 范围 Push、创建 / 更新 PR 与 CI 修复跟进；未授权生产部署。
Baseline: `ee92acaa7998749d46b57d85611ec69ab14948b1`
Branch: `docs/result-export-v1-spec` (已清理); final clean code candidate: `71d72d2` (Ticket 01 `111980d`; Ticket 02 `88f122c`); PR #56 merge commit: `367a42a`

## Ticket progress

- 01 XLSX：实现、独立文件解析、Query API / Runtime / PostgreSQL / 浏览器、build / typecheck / targeted lint / lock 检查与 Code Review PASS；本地候选 `111980d`。
- 02 PNG：实现、隔离渲染、真实 UI 下载、完整性 / 资源检查与 Code Review PASS；本地候选 `88f122c`。
- 03 PDF：已完成；Noto PDF ToUnicode 对“民”“长”的部首映射由 WenQuanYi Zen Hei 修正。字体包版本 / 许可证 / runtime manifest hash 锁定，字体清单单测 3 passed、Query API 181 passed / 2 skipped / 14 subtests、隔离 PDF renderer 2 passed、Review PASS。
- 04 隔离真实闭环与候选收口：clean candidate `71d72d2` 上隔离 Compose、真实浏览器和文件解析均 PASS；12 个下载文件、导出期间 execution POST 为 0，API 重启后恢复与下载通过，临时账号 / Session / worker / 容器 / 卷 / 网络清理通过。

## Decisions and boundaries

- Spec / Design Review PASS / Ticket Readiness READY 均已完成；用户 2026-10-06 确认完整拆分及连续本地实施。
- 仅既有成功快照导出，不执行业务查询、不调用模型、不请求全量数据；保留当前 owner、权限、CSRF 与导出资源界限。
- 所有 Ticket 按 01 → 02 → 03 → 04 连续完成；R5 之外的产品 / 架构 / 权限 / 状态变化回到用户确认。
- 发布授权于 2026-10-07 获得并用于 PR #56；PR 已合并，required CI 全部通过。生产部署仍未授权。
- Ticket 01 验证绑定候选 `111980d`，Ticket 02 绑定 `88f122c`；Ticket 03 / 04 和完整 R5 验收绑定 clean candidate `71d72d2`。四项实现与本地验收完成，PR #56 已合并。
