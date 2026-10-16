# 审计与分析快照的嵌套安全边界


- Change Profile: 高风险；持久化/公开数据兼容；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD016、AUD019。
- Blocked by: None (can start immediately)
- owned files: src/authorization/audit_service.py；src/query_api/history_codec.py；tests/authorization/test_audit_service.py；tests/query_api/test_history_codec.py；tests/query_api/test_history_application.py；tests/query_api/test_history_api.py；tests/query_api/test_result_export_api.py；tests/chatbi_control/test_history_postgres.py；docs/specs/query-api.md；docs/specs/history-results-v1.md。扩展API测试及PostgreSQL隔离测试，是为覆盖真实公开、另存和导出调用边界；不扫描或改写日常数据库。

### What to build

递归审计dict/list敏感键校验；分析快照按report/task/error/attribution/metadata公开结构逐层验证，复用现有DTO语义而非新建通用脱敏框架。

### Acceptance criteria

1. 嵌套字典、列表内字典不能携带现有敏感键持久化；错误不回显原载荷；合法结构保留。
2. 异常旧分析快照在历史重开、另存及导出边界受控拒绝HISTORY_SNAPSHOT_UNAVAILABLE，不静默删除内部字段后当成功。
3. 合法旧缺少可选result_metadata的快照保持可读；query合法sql不被误拒；表格单元格中的普通文本不按字段名过滤。
4. 未知/不支持结构受控失败；不扫描或改写日常数据库，不扩大当前数据保留范围。

### 验证证据

用合成嵌套SQL/connection_info/Secret canary验证公开返回与持久化失败；对合法旧/新query与analysis fixtures做兼容回归。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

Status: done
Result: Commit `1b40dbf` 实现 AUD016、AUD019：审计 details 递归检查 dict/list 的现有敏感键、拒绝不可持久化值，并在写入前重新校验及复制，避免构造后修改嵌套对象绕过检查；历史 Query / Analysis 快照按公开 DTO 逐层校验，非法嵌套字段受控返回 `HISTORY_SNAPSHOT_UNAVAILABLE`，不裁字段伪装成功。保留旧分析 `result_metadata` 缺省、未知但结构受支持的 metadata 版本、旧归因分类 `new` / `discontinued`、合法 Query `sql` 和普通单元格文本。无 Schema 变化、无日常数据库扫描。
验证：候选 `1b40dbf` 上 `./dev test python` 为 1071 passed、58 skipped、155 subtests、0 failed（run `20261016T192654Z-1b40dbf-test-python-d9a0546fce35`；因条件性 skip，报告状态 `incomplete`）；`./dev test database` 为 CI 5 passed + development PostgreSQL 60 passed、0 skipped，cleanup passed（run `20261016T192900Z-1b40dbf-test-database-3a81bee9c622`）；`./dev check python` 307 files / all checks passed（run `20261016T193023Z-1b40dbf-check-python-04d97d1246ca`）；`./dev check docs` PASS（run `20261016T193040Z-1b40dbf-check-docs-083cac6a646b`）；报告 provenance 均 stable，`git diff --check` PASS。一次 Review PASS，确认并修复旧分类兼容问题；Red 阶段两种历史分类各失败一次，修复后通过。候选只验证确定性软件与隔离 PostgreSQL；未运行真实 LLM 评测及容器业务验收，由后续 Ticket 执行。
Comments: 完成并按依赖继续 Ticket 08；本 Ticket 的 PostgreSQL 测试仅创建、篡改和清理自己准确身份的隔离测试数据。
