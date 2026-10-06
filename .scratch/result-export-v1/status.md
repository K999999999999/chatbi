# R5 路线规划快照

Last updated: 2026-10-07
Status: in-progress
Stage: Ticket 03 PDF 字体修正和 Ticket 04 隔离真实验收中；Ticket 01 XLSX 与 Ticket 02 PNG 已完成并提交本地候选
Authorization: 用户已确认四项 Ticket 拆分与连续完成 01–04 的本地实施，含编码、适用测试 / 真实验收、Review、本地 Commit；未授权 Push / PR / 部署。
Baseline: `ee92acaa7998749d46b57d85611ec69ab14948b1`
Branch: `docs/result-export-v1-spec`; Ticket 01 candidate: `111980d`; Ticket 02 candidate / Ticket 03 baseline HEAD: `88f122c`

## Ticket progress

- 01 XLSX：实现、独立文件解析、Query API / Runtime / PostgreSQL / 浏览器、build / typecheck / targeted lint / lock 检查与 Code Review PASS；本地候选 `111980d`。
- 02 PNG：实现、隔离渲染、真实 UI 下载、完整性 / 资源检查与 Code Review PASS；本地候选 `88f122c`。
- 03 PDF：依赖 02，原 Noto PDF 文本映射把“民”“长”映射为部首码位；用户确认采用 WenQuanYi Zen Hei 修正。固定字体版本 / hash 运行清单已实现，定向 renderer 2 passed，待 Review 和最终 clean candidate 真实验收。
- 04 隔离真实闭环与候选收口：依赖 03。候选 `89bc7a6` 的浏览器当前 / 历史 / 成果及服务重启下载都通过，但独立 PDF 文本比较因 Noto 映射失败；本次字体修正后待重跑。

## Decisions and boundaries

- Spec / Design Review PASS / Ticket Readiness READY 均已完成；用户 2026-10-06 确认完整拆分及连续本地实施。
- 仅既有成功快照导出，不执行业务查询、不调用模型、不请求全量数据；保留当前 owner、权限、CSRF 与导出资源界限。
- 所有 Ticket 按 01 → 02 → 03 → 04 连续完成；R5 之外的产品 / 架构 / 权限 / 状态变化回到用户确认。
- 本地 Commit 在授权内；任何 Push、PR 或部署仍需单独明确授权。
- Ticket 01 验证绑定本地候选 `111980d`；Ticket 02 PNG 阶段验证通过；PDF 字体修正、最终独立内容解析和真实 Compose 闭环仍未完成，不将本阶段叫作 R5 完成。
