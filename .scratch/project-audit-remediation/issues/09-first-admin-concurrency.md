# 首个管理员事务并发互斥


- Change Profile: 高风险；账号初始化不变量；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD017。
- Blocked by: None (can start immediately)
- owned files: src/chatbi_control/bootstrap.py；tests/chatbi_control/test_bootstrap.py；tests/chatbi_control/test_postgres_dev_environment.py；tests/bootstrap/test_control_commands.py；docs/specs/bootstrap.md。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

按Spec以专用PG事务advisory lock保护先查后建，覆盖有预置角色和空初始化路径；保留原CLI与强制改密。

### Acceptance criteria

1. 真实PG两个不同用户名在无管理员时同步初始化，只能一个提交成功，另一个明确已有管理员且无额外用户。
2. 预置admin角色存在和首次seed场景均覆盖；失败回滚释放锁，后续合法初始化可成功。
3. 锁身份不与HistoryRuntime/其他用途共用；SQLite仅验证串行；普通管理后台、恢复管理员、密码与审计语义不变。

### 验证证据

PG线程/独立事务配合屏障和有界超时，观察目标事务互斥；检查最终用户/角色关系；不依赖sleep碰运气或串行mock。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

Status: done
Result: Commit `2eb1aa3` 实现 AUD017：PostgreSQL 在检查现有管理员前取得固定、专用的事务级 advisory lock，锁定范围覆盖检查、固定 RBAC seed 与管理员创建；SQLite 保持原串行路径，不引入 Schema 变化。`create-admin` CLI、强制改密、恢复管理员和常规后台管理语义未变；正式行为依据已更新至 `docs/specs/bootstrap.md`。
验证：真实隔离 PostgreSQL 线程测试分别覆盖预置 admin 角色与首次 RBAC seed，两用户名同步初始化时确认第二事务实际等待 advisory lock；最终恰有第一个事务创建的管理员，另一个收到“首个管理员已经初始化”受控拒绝。失败注入发生在锁已取得、RBAC seed 之后；事务回滚后同一用户名可成功初始化。Red 阶段两条竞态用例在无锁实现上按预期失败（run `20261016T194906Z-db8cf06-test-database-67fda92c41f3`）；候选 `2eb1aa3` 上 `./dev test python` 为1081 passed、61条件性 skipped、155 subtests、0 failed（run `20261016T195538Z-2eb1aa3-test-python-7ecbbc7cd978`；报告因 skip 为 `incomplete`）；`./dev test database` 为 CI 5 passed + development PostgreSQL 63 passed、0 skipped，cleanup passed（run `20261016T195743Z-2eb1aa3-test-database-fe96c3eb91b1`）；`./dev check python` 307 files / all checks passed（run `20261016T195911Z-2eb1aa3-check-python-4d39efe7f3f2`）；`./dev check docs` PASS（run `20261016T195931Z-2eb1aa3-check-docs-0db4dc376256`）；候选报告 provenance stable，Review 与 `git diff --check` PASS。没有运行真实 LLM 评测或隔离容器业务验收，留给后续 Ticket。
Comments: 完成并按依赖继续 Ticket 10；PG 线程、用户、关联关系和 RBAC 清理均限定在临时隔离数据库与本测试创建的准确身份。
