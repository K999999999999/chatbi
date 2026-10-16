# 兼容历史入口的共享保护与准确终态


- Change Profile: 高风险；跨Application/Store内部协作，公开HTTP Contract保持；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD003、AUD004、AUD005。
- Blocked by: None (can start immediately)
- owned files: src/query_api/history.py；src/query_api/history_api.py；src/query_api/history_contracts.py；src/chatbi_control/history.py；src/query_api/admission.py；src/query_api/execution.py；src/query_api/execution_runtime.py；src/query_api/app.py；tests/history_support.py；tests/query_api/test_history_api.py；tests/query_api/test_history_application.py；tests/query_api/test_execution_application.py；tests/query_api/test_execution_runtime.py；tests/chatbi_control/test_history_postgres.py；对应readiness/history/execution Specs。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

按Spec设计约束复用就绪/owner额度和同步control，在幂等校验后、新attempt写入前受理；业务层授权拒绝映射revoked；真实succeeded轮次正确记录SUCCESS。

### Acceptance criteria

1. 四类兼容写入口未就绪503、超额429，拒绝无新attempt/history及下游调用；错误外壳兼容。
2. 同账号跨history、同步/后台及不同账号全局额度共享；幂等成功/失败重放在未就绪或额度已满时仍不重复占额；请求摘要冲突仍拒绝。
3. 事务/执行/持久化异常释放同一租约；断开或停止等待不能提前释放真实工作；180秒/1200秒控制下传，analysis guard不双重取得。
4. HistoryError授权错误与HTTP401/403均为AUTHORIZATION_REVOKED，其他鉴权依赖故障为UNAVAILABLE；真实worker succeeded trace为SUCCESS，既有失败分类保持。

### 验证证据

Application/API可控替身与事件同步并发测试；PG验证受理前拒绝、事务回滚、幂等及历史状态；容器test database覆盖CI/development。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

Status: completed
Result: 四个历史兼容写入口现在只在存储事务完成归属、幂等、revision和来源校验后、写入新attempt/history前调用Application准入回调；复用共享owner额度和ready状态。重放不重新准入；租约由Application退出栈持有到同步工作及终态保存完成，事务异常会释放。问数180秒、分析1200秒控制传入业务执行；同步超时写入`QUERY_TIMEOUT`失败轮次，后台预占路径不二次取得额度。业务层`AUTHORIZATION_DENIED` / `AUTHENTICATION_REQUIRED`及HTTP401/403映射为既有授权撤销终态，依赖故障保持不可用分类；真实`succeeded` worker轮次记录Trace `SUCCESS`。
Verification: Red run `20261016T174512Z-e68009d-test-python-014301950d52` 首轮6项失败（准入缺失、鉴权/Trace分类错误）；`./dev test python tests/query_api` — 237 passed, 2 skipped, 14 subtests（run `20261016T175600Z-e68009d-test-python-d20304180efe`）；`./dev test database` — CI 5 passed、development PostgreSQL 58 passed（run `20261016T175728Z-e68009d-test-database-9561785bb76e`，使用仓库临时隔离数据库）；`bash scripts/check_python_quality.sh` — 307 files already formatted, all checks passed；`python3 -m scripts.check_documentation` — PASS；`git diff --check` — PASS。补充超时/真实Worker Trace定向回归通过（run `20261016T175530Z-e68009d-test-python-1387c788eef1`）。2个Skip按测试报告记录，未改写为通过。
Review: 当前切片只读Code Review PASS；拒绝准入前无状态写入；PostgreSQL回滚验证；不重复计费及Analysis guard不双重预占；ExitStack覆盖受理、持久化和执行生命周期；后台执行原有worker租约保持独立。Diff检查PASS。
Comments: 正式运行结果对应候选基线`e68009d`；文档已同步`application-readiness.md`和`execution-streaming-v1.md`。仅完成Ticket 02，不代表整体审计修复目标完成。
