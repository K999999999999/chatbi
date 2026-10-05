# Ticket 04：状态与最终结果阶段真实链路验收

ID: execution-streaming-v1/04
Status: in-progress
Authorization: 用户于 2026-10-05 确认六项拆分及连续完成整个 R4 的本地实施，包含编码、适用测试与真实验收、Review 和本地 Commit；不含远端发布。

Change Profile: 收敛型阶段验收 /中 /高风险证据 /真实Compose+浏览器+PG /本地状态阶段candidate。
Owner: 当前主Agent。
Blocked by: 03

### What to build / Scope

- 扩展既有container真实验收profile，固定01–03的clean候选验证问数 /追问 /analysis真实阶段、正式结果、刷新 /多页 /断连重连 /取消与重新操作。
- 核对真实模型 /RAG /只读Sales DB与独立业务参考，实际PG重启 /cancelrun封锁 /v3保留数据回滚；不可立即中断Provider的表现如实记录。
- 若发现缺陷，只修复01–03已确认范围，Review并新候选复验；通过后才进入文字流式切片。

Out of Scope: 文字真实stream证据、全产品生产验收 /容量、R4最终三套正式基线（06）。

Owned files: `scripts/verify_container_dev.sh` /既有helpers /真实验收入口、`frontend/tests/container-real.spec.ts` /real配置、受影响PG /checkpoint验收辅助、`.scratch/execution-streaming-v1/`阶段证据 /正式Acceptance入口；发现缺陷仅01–03 owned files。

### Acceptance criteria / Evidence

1. clean候选真实桌面浏览器 /HTTP /实际模型 /RAG /DB完成已确认阶段链、问数 /分析最终结果与参考一致；记录候选、RAG /模型 /数据身份与退出状态。
2. 断连 /刷新 /多页同execution无重复业务执行、取消前后状态与额度真实表现可观测；故障竞态的替身 /PG证据与真实Provider证据分开，不能将不可立即中断写为已立即停止。
3. 实际停止原进程再重启，unconfirmed /原TTL /迟到fencing正确；保留数据切换v3 /回到v4，既有结果 /独立成果可用、cancelled原run不恢复、旧版删除不被新FK阻断。
4. 临时账号 /Session /凭证清理完成，业务DB /原账号 /开发卷 /RAG不受破坏；无secret进报告。状态阶段证据不改称05或最终R4成绩。

验证：Runbook中既有真实验收方式、独立SQL /归因参考、真实PG进程 /migration回滚检查；文档identity /links /Diff核对。原报告保留身份。
Migration / Rollback: 验收只使用已确认隔离资源和本地开发实例；回滚明确停止worker，不DROP业务数据，不做生产rollout。
Done When: 1–4通过、Code Review /证据核对PASS；固定clean阶段候选并在Git公共目录记录报告，tracked入口不预写“新HEAD通过”；才能启动05。
Result: 已扩展真实 Profile，覆盖问数 / 分析 SSE 阶段与终态、多页重连 / 刷新 / 取消，以及 API 进程强制停止后的真实 PostgreSQL 未确认恢复检查；旧版本 Schema verifier 迁移用例已修正并在开发 PostgreSQL 通过。前端 build / typecheck 通过；默认 Playwright 因宿主机缺少 Chrome 未能启动浏览器用例。正式 clean candidate 的真实调用与重启验收待运行。
Comments: 若tracked证据回填产生新阶段提交，受影响真实证据按新clean身份复验，不改原report SHA。
