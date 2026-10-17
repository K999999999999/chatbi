# 查询安全裁决与授权拒绝保护


- Change Profile: 高风险；局部Guard与授权测试；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD001、AUD002。
- Blocked by: None (can start immediately)
- owned files: src/online_query/sql_guard/sql_guard_multi_metric.py；src/online_query/semantic_state.py（仅必要的分组语义校验）；tests/online_query/test_multi_metric.py；tests/online_query/test_sql_guard.py；tests/authorization/test_authorization_core.py；docs/specs/online-query.md。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

拒绝多指标GROUPING SETS/ROLLUP/CUBE及组合AST形式；修正授权拒绝测试观察的真实下游方法，保留合法查询路径。

### Acceptance criteria

1. 非法扩展分组在数据库执行前返回SQL_REJECTED；普通多指标分组仍可执行并保持结果形状。
2. 有/无普通分组表达式和组合扩展都覆盖；合法时间分组、单指标及历史条件不回归。
3. 无身份/无权限时实际执行路径零调用；合法对照能命中同一个执行替身，不以未用mock断言冒充保护。

### 验证证据

容器内定向运行上述Guard/授权测试；保留失败前/修复后的结果；最终test python及三套Evaluation验证正式链路。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

Status: completed
Result: 多指标 SQL Guard 现按 SQLGlot AST 拒绝 `GROUPING SETS`、`ROLLUP`、`CUBE`，涵盖有/无普通分组表达式的组合；授权拒绝测试改为断言真实 `execute` 下游零调用。`docs/specs/online-query.md` 已补充 fail-closed Contract。未改变单指标校验路径。
Verification: `./dev test python tests/online_query/test_sql_guard.py tests/authorization/test_authorization_core.py` — 41 passed, 54 subtests passed；`bash scripts/check_python_quality.sh` — 307 files formatted, all checks passed；`git diff --check` — PASS。早期Red验证见本机记录 run `20261016T173953Z-8d01740-test-python-ccc1350eee85`（扩展分组被放行）；首次Green run `20261016T174022Z-8d01740-test-python-d884153326ff`（41 passed, 51 subtests）；当前最终定向回归在以上追加3个无普通表达式用例后再次通过。正式真实LLM评测与隔离容器验收属于最终clean candidate门禁，尚未运行。
Review: 当前切片只读Review PASS；扩展分组检查位于多指标专用输出验证路径，在指标公式/分组校验前拒绝不支持的AST字段；现有合法多指标与授权调用路径均由同一测试模块覆盖。Diff检查PASS。
Comments: 按已确认Spec、设计审查和READY拆分登记；仅完成Ticket 01，不代表整体审计修复目标完成。
