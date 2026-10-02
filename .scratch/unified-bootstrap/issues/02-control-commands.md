# 02 — 统一数据库迁移和管理员命令，移除旧入口

Status: done
Owner: 当前主 Agent
Canonical Source: ../spec.md；../design.md

Blocked by: None (can start immediately)

### What to build

建立统一命令分发，提供 migrate、create-admin，迁移命令解析与装配，继续调用 Control DB 所属实现。一次完成全部消费者迁移和旧 Control DB CLI 入口删除，不保留转发。

### owned files

- src/bootstrap/__main__.py、commands.py 和数据库命令装配文件；package 入口仅必要编辑。
- 移除 src/chatbi_control/__main__.py、cli.py 的旧命令职责；保留 bootstrap.py、database.py 的具体实现。
- scripts/run_database_tests.py、reset_dev_postgres.py（仅命令调用替换）。
- .github/workflows/ci.yml 的数据库命令调用、相关 CLI / bootstrap / 集成 / reset 测试。
- README.md、docs/runbook.md、docs/architecture.md 当前数据库初始化入口说明。

### Acceptance criteria / 验证证据

- 新命令帮助、参数、退出码符合 Spec；帮助和 migrate 不加载在线服务 / Embedding。
- migration 可重复安装 Schema、RBAC、checkpoint 和 grants，不创建用户。
- create-admin 隐藏密码及确认，首次成功，重复拒绝，权限与 Secret 边界保持。
- 旧 python -m src.chatbi_control 入口不可执行；无可执行消费者残留，历史记录除外。
- reset 和测试 runner 操作语义保持，仅调用新入口。
- 证据：CLI / 故障测试、既有隔离 PostgreSQL dev profile migration / 权限 / 管理员生命周期、调用替换回归与静态搜索。

### Migration / Rollback / Done When

新命令、删除旧入口与调用迁移同一切片完成；无数据变更。参数 / 权限回归和隔离集成通过，说明更新、Diff / Review 完成后本地提交。回滚整组入口及消费者，不保留半迁移状态。

## Result

实现、关联文档和验证完成；实现 Review PASS，详细证据见 ../verification.md（待最终候选记录固化）。

## Comments

用户在聊天确认三项拆分及整体实施；不包含远端发布授权。
