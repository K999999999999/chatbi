# Ticket 04：状态与最终结果阶段真实链路验收

ID: execution-streaming-v1/04
Status: complete
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
Result: clean candidate `d6478da957b7515ebb3f1387f123de8752c34192` 的 `scripts/verify_container_dev.sh real` 通过，`git_dirty=false`。真实问数与分析各以 HTTP 200 完成；SSE 均包含 snapshot / progress / terminal 和实际六阶段，最终为 succeeded，并与独立业务参考一致。刷新、第二页重连至同一执行且业务提交仅一次；取消按 running → stopping → cancelled 收敛、保留上一成功轮次，取消后新操作引用正确。强制停止 API 容器并重启后，遗留 execution / turn 均为 unconfirmed，活动指针清除、未确认快照缺失、上一成功轮次保留，Control Schema v1–v5 标记完整；重启后的历史读取 / 重登录 / 续聊 / 显式重查与数据 / RAG 身份核对通过。专用账号已禁用、活跃 Session 为0、临时凭证已清理。报告为本机 ignored 文件 `reports/browser-real/container-1791209719-real.json`，SHA256 `e22ce2e91b0140ff5041e33924eb5d6ea4308c22b4560bef733c7e5dfb37603a`；公开安全摘要见 [R4 Acceptance](../../../docs/acceptance/execution-streaming-v1.md#ticket-04-状态与结果真实验收)。同候选 `uv run --locked python scripts/run_database_tests.py --profile development` 42 passed；`npm run build` 与刷新活动历史后取消并继续提交的定向 Chromium 回归 1 passed；`git diff --check` 通过。实现与证据 Review PASS。宿主 Chrome 缺失导致的默认宿主浏览器启动限制已通过隔离 Docker Chromium 回归及正式 Compose 浏览器验收覆盖。
Comments: 若tracked证据回填产生新阶段提交，受影响真实证据按新clean身份复验，不改原report SHA。
