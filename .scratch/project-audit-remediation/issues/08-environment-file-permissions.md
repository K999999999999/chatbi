# 本机配置权限及读入前保护


- Change Profile: 中风险；本机文件与开发CLI可观察失败；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD015。
- Blocked by: None (can start immediately)
- owned files: scripts/environment_permissions.py；scripts/dev_environment.sh；scripts/verify_container_dev.sh；scripts/metadata/export_schema.py；scripts/metadata/export_schema_input.py；scripts/check_dev_qdrant.py；scripts/run_database_tests.py；tests/scripts/test_container_dev.py；tests/scripts/test_check_dev_qdrant.py；tests/scripts/test_run_database_tests.py；tests/metadata/test_export_schema.py；docs/runbook.md；本机原worktree .env（仅权限、不入Git）。扩展到直接读取配置及间接触发Compose加载 `.env` 的入口，是为覆盖所有实际读取边界；未修改配置内容或权限。

### What to build

在Linux配置交给Compose/读入前检查属主与group/other权限；明确拒绝和安全修复指令；新建配置说明使用安全权限，并收紧本机已识别.env。

### Acceptance criteria

1. 受控临时配置0644拒绝、0600正常；可读但非所有者等不安全情况安全拒绝；错误不打印内容；不自动递归改权限。
2. dev help及参数拒绝仍不读取.env、不调用Docker；所有配置加载调用点已盘点，不只保护日常up。
3. 原工作区.env仅chmod600，不改值；用权限元数据核验，不输出或保存Secret；不要求宿主安装Python/Node。

### 验证证据

shell/假Docker记录验证拒绝发生在配置使用前；安全模板检查；本机处置仅记录stat元数据，不记录内容Hash或值。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

Status: done
Result: Commit `cb434d9` 实现 AUD015：Linux 在读取或传给 Compose 前拒绝非普通文件、非当前用户属主以及除 owner-read 外的额外权限，安全提示给出 `chmod 600`；覆盖开发入口、容器验证入口、Qdrant检查、metadata导出及数据库测试隐式调用 Compose 的 `.env` 读取。Runbook 说明安全创建方式。本机原工作区 `.env` 仅检查元数据，uid 为当前用户、权限 `600`，无需变更；未读取、记录或改动其内容。无宿主 Python/Node 依赖。
验证：在候选 `cb434d9` 上 `./dev test python` 为 1081 passed、58 条件性 skipped、0 failed（run `20261016T194109Z-cb434d9-test-python-24425a44e317`；因 skip 报告状态 `incomplete`）；`./dev check python` 307 files / all checks passed（run `20261016T194313Z-cb434d9-check-python-a4783cdba32c`）；`./dev check docs` PASS（run `20261016T194330Z-cb434d9-check-docs-d5c2762751d7`）；shell语法与 `git diff --check` PASS；报告 provenance 均 stable。TDD 覆盖拒绝发生在 Docker / 配置读取前、无 Secret 回显、非属主和宽权限；发现 database test runner 会间接触发 Compose 读取 `.env` 后补充回归并修复。Code Review PASS。未运行隔离 PostgreSQL、真实 LLM 评测及容器业务验收，按整体计划留给后续 Ticket。
Comments: 按依赖继续 Ticket 09；本 Ticket 不读取或改写原工作区 `.env` 的秘密内容。
