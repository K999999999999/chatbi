# 重查受理不确定时保留同一操作


- Change Profile: 高风险；前端状态与服务端幂等；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD009。
- Blocked by: None (can start immediately)
- owned files: frontend/src/Chat.tsx；frontend/tests/execution.spec.ts；frontend/tests/history.spec.ts；docs/specs/execution-streaming-v1.md（若需补充现有验收）。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

复用已有uncertainExecution恢复流程，保留requery原path/body/operationId和来源；原请求显式恢复不生成新UUID。

### Acceptance criteria

1. 服务端已受理但提交响应丢失、首次by-operation查询又失败时，页面进入未确认且保留原请求。
2. 显式恢复/重试复用同一ID；迟到受理只观察同一execution；确定拒绝允许按既有语义新请求，不自动重发。
3. 问数历史、分析历史及saved-result来源都覆盖；401/403、退出、切换账号清理私有状态；原成果和快照不被失败改写。

### 验证证据

浏览器故障注入提交/查找双失败与迟到响应，核对实际请求ID、路径、body和执行次数，运行execution/history测试。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

Status: completed
Result: 历史与保存成果重查在提交响应、首次 operation 查询都失败时保留原 path、body 和 operation ID；页面标记受理未确认，不自动重发、不覆盖原结果。用户显式重试后复用原请求；若确定拒绝则清除待恢复状态，允许用户再次主动发起新操作。
Comments:
- TDD Red：`20261016T184239Z-6f69b47-test-web-7ec050ceb946` 中新增的问数历史、分析历史、保存成果三项均失败，确认双失败时没有呈现未确认操作。
- 只读 Code Review：PASS。恢复请求直接复用保存的 path/body/operationId；operation 查询找到迟到受理后观察响应中的唯一 execution；双失败期间保留源快照；401/403复用既有私有状态清理路径；确定拒绝只解锁后续显式操作，不自动换ID重发。Review 后无未解决问题。
- 定向候选 `51d8f48`：`./dev test web frontend/tests/history.spec.ts` 12/12 passed（`20261016T185132Z-6f69b47-test-web-47706fa566bb`）；覆盖三种来源、原 operation、迟到受理、确定拒绝、401/403、退出与账号切换。
- 完整候选 `51d8f48`：`./dev test web` 79/79 passed（78 packaged + 1 dev；`20261016T185258Z-51d8f48-test-web-cad932127fe9`），provenance stable；`./dev check docs` PASS（`20261016T185510Z-51d8f48-check-docs-d766433937dd`）；typecheck、Vite build、`git diff --check` PASS。现有 [后台执行 Contract](../../../docs/specs/execution-streaming-v1.md) 已覆盖幂等恢复行为，本Ticket未改变Contract，无需更新。
- 未运行数据库、renderer、真实LLM评测或隔离Compose业务验收；这些由对应后续Ticket处理。
