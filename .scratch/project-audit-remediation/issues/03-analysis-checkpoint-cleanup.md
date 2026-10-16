# 删除分析历史后的checkpoint回收


- Change Profile: 高风险；Control DB数据生命周期，保留tombstone；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD006。
- Blocked by: None (can start immediately)
- owned files: src/business_analysis/run_store.py；src/chatbi_control/history.py（仅必要删除标记配合）；tests/business_analysis/test_run_execution.py；tests/chatbi_control/test_history_postgres.py；tests/chatbi_control/test_postgres_dev_environment.py；docs/specs/business-analysis.md；docs/specs/history-results-v1.md。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

让到期清理覆盖已标expired但仍有checkpoint的运行，不引入新清理器或Schema；保留失效ID。

### Acceptance criteria

1. 主动删除分析历史后，checkpoints/checkpoint_blobs/checkpoint_writes均在既有清理周期内被回收。
2. 已expired遗留run同样回收；重复清理幂等且不反复无差别更新全部expired行。
3. 其他有效run和独立成果保持；原run不能claim/resume；清理失败事务回滚，不出现仅部分子表已删的成功。

### 验证证据

真实PG建立三类子表记录，执行删除+清理及遗留/重复/失败路径；明确证明保留记录及原ID失效。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

Status: completed
Result: `cleanup_expired` 现在回收所有到期运行的三类 LangGraph checkpoint 数据；expired tombstone 只有仍有 checkpoint 时才会再次进入清理，删除历史所保留的失效运行 ID 不会被重用。状态更新和子表删除共用一个事务；失败时状态、更新时间和所有 checkpoint 行均回滚。有效运行与独立保存成果保持不变。`business-analysis.md` 与 `history-results-v1.md` 已明确失效 ID 和 checkpoint 生命周期。
Verification: 真实 PostgreSQL Red 首次复现旧实现清理计数不足（预期3个本地过期运行，实际仅2）；修正测试账号的运行记录清理权限后 Green。候选 `7a46415` 上 `./dev test database` — CI 5 passed、isolated development PostgreSQL 59 passed（run `20261016T181403Z-7a46415-test-database-3cf13e780edf`）；`./dev check python` — 307 files already formatted, all checks passed（run `20261016T181403Z-7a46415-check-python-1e64d0a951bf`）；`./dev check docs` — PASS（run `20261016T181403Z-7a46415-check-docs-b7775d9ab860`）；提交 Diff 检查 PASS。数据库测试覆盖主动删除、旧 tombstone、三 checkpoint 子表、事务失败回滚（含 updated_at）、重复清理、run ID 不可恢复、有效运行与独立成果保留。正式真实LLM评测和隔离业务验收属于整体目标最终候选门禁，尚未运行。
Review: PASS；范围 `f8b19e6..7a46415`，仅本Ticket的运行清理、真实PG测试与两个相关Spec。无发现项。查询仅处理到期运行，并通过子表存在条件避免重复更新已清空的 expired tombstone；状态与三表删除原子提交。Code Review复用上述PostgreSQL验证证据，未重复运行测试。
Comments: 本地Commit `7a46415 fix(analysis): 回收已过期运行检查点`。仅完成Ticket 03，不代表整体审计修复目标完成。
