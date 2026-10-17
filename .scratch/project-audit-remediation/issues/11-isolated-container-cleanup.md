# 隔离容器热更新与验收账号异常清理


- Change Profile: 高风险；测试写入、账号和临时资源生命周期；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD013、AUD021。
- Blocked by: None (can start immediately)
- owned files: scripts/verify_container_dev.sh；scripts/container_hot_reload.sh（隔离副本建立 / 恢复 helper）；tests/container_dev_support.py；frontend/tests/container-real.spec.ts；tests/scripts/test_container_dev.py；tests/scripts/test_container_hot_reload.py、tests/test_container_dev_support.py（定向故障注入）；docs/specs/container-dev-environment.md；docs/runbook.md。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

仅隔离验收提供受控热更新写入路径与源码恢复；为prepare账号创建建立无身份丢失窗口的记录/异常补偿；独立模型缓存显式准备。

### Acceptance criteria

1. 默认初始阶段实际观测Python和Vite热更新；不将用例skip或把原日常源码目录整体改为可写。
2. 成功、write失败、浏览器失败、prepare失败及可处理的INT/TERM都恢复原源码，最终Hash一致，报告记录失败不伪装成功；不可处理强杀保留可恢复证据，不承诺捕获SIGKILL。
3. 模拟账号提交前后account.json写入失败仍能精确识别本次账号并禁用、撤销Session；不得前缀批量操作；cleanup失败要保留证据和非成功状态。
4. 不对日常项目执行restart/kill/down；临时project/volume明确标签；prepare-model/build-rag先后关系正确，日常RAG指针不被覆盖。

### 验证证据

脚本/工具故障注入验证挂载范围、信号恢复、精确账号清理；真实完整isolated验收在最终候选执行，原intentional skip计数规则保持。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

Status: done
Result: Commit `0c4be10` 修复 AUD013、AUD021。隔离模式从固定revision导出当前worktree私有模型缓存路径，显式执行`prepare-model`后才`build-rag`，RAG输出使用隔离临时目录。API 与 Web 分别覆盖挂载本次临时可写的单文件副本；Playwright 只改写副本，退出时使用备份恢复并核对原始 / 最终SHA-256。INT/TERM走同一清理路径；SIGKILL保留带准确Compose身份、报告路径和源码哈希的recovery manifest与备份。real模式不执行隔离热更新用例。账号身份在数据库事务提交前原子、持久化写入`account.pending.json`，提交后改名为`account.json`；异常清理接受两类记录，只按精确id+username禁用账号并撤销Session；事务回滚且记录已落盘时确认无账号资源后记为空操作成功。Runbook及容器开发Spec已更新。
验证：修复前账号提交后最终身份文件写入故障注入按预期失败（run `20261016T202312Z-c2a3d92-test-python-f515a13aa72f`，2 failed）；staged候选 `c2a3d92` + tracked diff `61725da1064e117f742854359f069e336286f34736258ff6e74991255b46fe14` 上，定向Python套件52 passed / 0 skipped（run `20261016T203505Z-c2a3d92-test-python-465ba47ff3b6`）、完整Web 81 passed / 0 skipped（run `20261016T203533Z-c2a3d92-test-web-8c18f3093293`）、Python质量309 files PASS（run `20261016T203505Z-c2a3d92-check-python-d4e9002dd543`）、文档与Markdown链接PASS（run `20261016T203505Z-c2a3d92-check-docs-2f6fb0a1eca9`），报告provenance均stable；含INT/TERM、失败恢复、文件缺失、备份损坏、事务提交前后和同前缀无关账号的故障注入全部通过；Bash语法、`git diff --check`、Review PASS。完整isolated Compose业务验收尚未运行，按Ticket约定由T12最终候选执行；T12还需执行三套真实LLM评测，不把当前Ticket记录等同于整体验收完成。
Comments: 本Ticket代码与定向验证完成；最终isolated业务验收作为T12最终候选门禁，当前整体验收仍未完成。
