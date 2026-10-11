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
