# 真实评测与兼容验收入口修复


- Change Profile: 中风险；CI/host验证入口，不触发远端写入；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD011、AUD012、AUD020。
- Blocked by: None (can start immediately)
- owned files: .github/workflows/real-e2e.yml；frontend/test-support/report-path.ts；frontend/playwright.real.config.ts（仅必要对齐）；scripts/run_database_tests.py；tests/scripts/test_real_e2e_workflow.py；tests/scripts/test_run_database_tests.py；tests/bootstrap/test_model_command.py；frontend/tests/report-path.spec.ts；tests/browser_support.py；tests/chatbi_control/test_postgres_dev_environment.py（仅收紧已存在并发测试的同步观察）；docs/runbook.md。扩展模型命令测试以覆盖空缓存/复用固定revision；修正浏览器测试服务中的旧快照fixture，是因为 T10 报告路径 Web 回归启动该服务时，T07 的公开快照 Contract 会拒绝不完整fixture。旧 runner 复测还暴露 T09 并发测试在发出锁请求前就开始观察的调度敏感性，因此等待锁请求事件后再检查 PG 锁状态。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

Real E2E在build-rag前prepare-model并使用同revision本地路径；报告helper兼容host run目录；旧PG测试入口使用正式TCP探测/查询。

### Acceptance criteria

1. 工作流步骤顺序、空缓存/复用缓存、失败传播有回归；不以移除本地快照校验修复；普通CI不新增真实LLM调用。
2. 报告helper变量优先级为非空container、real、/reports，空值与文件名穿越校验保持；实际能读取本次host start.json。
3. pg_isready与fixture readiness查询均指定正式TCP host；临时socket实例不能放行，超时和错误保持；CI/development两profile保留。
4. 未在GitHub runner或Windows执行的范围如实记录，不冒称托管工作流已通过。

### 验证证据

工作流测试核验prepare/build配置；报告helper实际文件读写夹具；旧脚本subprocess探测回归，真实临时PG验证由最终数据库套件/兼容定向入口提供。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

Status: done
Result: Commit `7ff3399` 实现 AUD011、AUD012、AUD020：手动 Real E2E 工作流先从 `DEFAULT_MODEL_DIR` 解析固定 revision 的本地路径，将同一 `RAG_MODEL_DIR` 写入后续 GitHub steps 并在 `build-rag` 前运行 `prepare-model`；准备失败由 `set -e` 阻断构建和正式评测，普通 CI 工作流未增加真实 LLM 调用。报告路径按非空 `CHATBI_CONTAINER_REPORT_DIR`、非空 `CHATBI_REAL_E2E_REPORT_DIR`、`/reports` 回退，保留文件名穿越拒绝，并能读取 host 创建的 `start.json`。旧 PostgreSQL runner 的 `pg_isready` 与开发 fixture `psql` 查询均显式连接容器内 `127.0.0.1` TCP。Runbook 已补充运行说明。T10 Web 回归另补齐一份旧浏览器快照测试fixture，使其满足 T07 已实施的公开快照 DTO Contract；旧入口复测也促使 T09 PostgreSQL 并发测试先等待第二线程发起 advisory lock 后再观察 `pg_stat_activity`，消除调度延迟造成的假失败。
验证：Red 阶段工作流缺少模型准备和旧 runner 缺少 TCP host 的回归按预期失败（run `20261016T200301Z-09a5d26-test-python-016f436ffdf1`；4 failed / 22 passed）。候选 `7ff3399` 上完整 `./dev test python` 为1085 passed、61条件性 skipped、155 subtests、0 failed（run `20261016T201322Z-7ff3399-test-python-420a3a5ddba3`；报告因 skip 为 `incomplete`）；`./dev test database` 为 CI 5 + development PostgreSQL 63 passed、cleanup passed（run `20261016T201525Z-7ff3399-test-database-65fddca4ba3e`）；`./dev test web` 81 passed（run `20261016T201647Z-7ff3399-test-web-7cc036188bb0`）；旧兼容入口 `uv run --python 3.11 --locked python -m scripts.run_database_tests --profile development` 56 passed，临时容器已退出且无残留；`./dev check python` 307 files PASS（run `20261016T201837Z-7ff3399-check-python-6bc5fb280aa1`）；`./dev check docs` PASS（run `20261016T201853Z-7ff3399-check-docs-6542290a7060`）。候选报告 provenance stable，Review 与 `git diff --check` PASS。未在 GitHub runner / Windows 执行托管工作流；未下载真实 BGE-M3 或调用真实 LLM，正式三套评测由 T12 clean candidate 验收。
Comments: 完成并按依赖继续 Ticket 11；本 Ticket 只在本地执行合成 workflow 脚本、浏览器测试和一次性 PostgreSQL profile，没有触发远端 workflow。
