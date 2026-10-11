# 最后一名管理员并发保护验证

## 候选与范围

- 基线：`b7dd82386d877ccf6669bd2e02698e81da19f975`（与 `origin/master` 同步）。
- 候选分支：`fix/serialize-last-admin-change`。
- 实现：`src/chatbi_control/admin.py`；现有所有 `validate_user_mutation` 写入口共享同一 PostgreSQL 行锁。
- 回归：SQLite 管理流程测试及隔离 PostgreSQL development profile 的真实并发测试。
- Contract：`docs/specs/web-dialogue-v1.md`。

## 结果

- Red：未加入行锁时，隔离 PostgreSQL 测试确认第二个事务没有申请保护锁，测试失败；线程化事务通过服务入口并发修改两名管理员。
- Green：恢复实现后，测试观察到 PostgreSQL 第二事务等待 `admin` 角色行锁；首事务提交降级后，第二事务收到 `LastAdminError`，数据库最终仍有一名 active admin。
- `/home/jojo/Projects/chatbi-engine/.venv/bin/python scripts/run_database_tests.py --profile development`：44 passed；临时 PostgreSQL 容器由 runner 回收。
- `/home/jojo/Projects/chatbi-engine/.venv/bin/python -m pytest -q tests/chatbi_control/test_admin.py`：8 passed。
- `/home/jojo/Projects/chatbi-engine/.venv/bin/python -m pytest -q`：995 passed、42 skipped、139 subtests。
- `bash scripts/check_python_quality.sh`：PASS；`git diff --check`：PASS。
- Review：PASS。串行锁位于现有服务事务，覆盖 SQLAdmin 与 `set_user_roles` 两个现有变更入口；无需 migration、额外权限或新依赖。
- 不运行 AI Evaluation：本次不改变模型 / 检索行为。
- 路线图不更新：不改变产品里程碑、范围、优先级、依赖或完成状态。


## 三项账号并发保护整合发布候选验证（2026-10-11）

- 基线：`b7dd82386d877ccf6669bd2e02698e81da19f975`。
- 整合候选：`fix/account-state-concurrency`，验证时 HEAD `7cc30eed43c622be7e2a87c44aef7ba9ab4f3838`；合并 last-admin、login-failure、password-reset 三项已 Review 候选。合并中 PostgreSQL 测试文件只有导入区冲突，已合并保留所有三类测试需要的符号；业务代码无需冲突修正。
- 全量：`uv run --python 3.11 --locked python -m pytest -q`：**995 passed / 44 skipped / 139 subtests passed**，串行执行。
- PostgreSQL：`uv run --python 3.11 --locked python scripts/run_database_tests.py --profile development`：**46 passed**；覆盖用户锁定、最后管理员、密码重置和自行改密的真实事务 / 行锁路径；一次性数据库由 runner 清理。
- 质量：`bash scripts/check_python_quality.sh`、compileall、Markdown links、module boundaries、`git diff --check` 全部 PASS；307 个 Python 文件格式检查通过。
- 整合 Review：**PASS**。已审查 `src/authorization/auth_service.py`、`src/chatbi_control/admin.py`、完整 PostgreSQL 回归及三项 Spec；账号状态串行点与原阈值、响应、RBAC、Session 撤销规则一致，无 Schema / API / 依赖变化；未发现阻塞 Finding。
- 执行说明：曾并行启动两份全量测试，宿主机 Query API socket / 导出运行资源冲突造成无关用例失败；停止并行后账号全量测试、SQL 全量测试及本 profile 均串行通过。该并行结果不计作通过证据，也未修改对应产品代码。
- 不运行 AI Evaluation、浏览器业务验收或 Stable：目标不改变模型 / 检索、HTTP / 前端或部署行为。
- 路线图：重新核对 `docs/roadmap.md`；只落实现有身份安全 Contract，不改变目标 / 优先级 / 依赖 / 完成状态，无需更新。
