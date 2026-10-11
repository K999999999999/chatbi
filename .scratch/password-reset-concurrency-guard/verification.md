# 密码重置并发保护验证

## 候选身份

- 基线：`b7dd82386d877ccf6669bd2e02698e81da19f975`（`origin/master`，2026-10-11 fetch 后核实）
- 验证范围：AuthService 自行改密、SQLAdmin 密码重置、Control DB Session 撤销
- 环境：`scripts/run_database_tests.py --profile development` 创建的一次性 PostgreSQL 16 容器；不连接日常开发库或 Stable

## Red-Green

- Red：在生产代码未修改时运行 development profile，新增的 `test_sqladmin_password_reset_wins_over_inflight_self_change` 失败。确定性交错暂停自行改密，再让 SQLAdmin 密码重置提交；旧实现最终保存自行改密密码，并将 `must_change_password` 清为 false。
- Green：增加用户状态行锁与锁后 Session 重读；SQLAdmin 重置也在 Session 撤销前锁住并刷新用户行。development profile 通过：44 passed。
- PostgreSQL 测试观察到 SQLAdmin 重置等待同一用户行锁；事务完成后确认管理员设置的密码仍有效、`must_change_password=true`、旧 Session 已撤销。

## 其他验证

- `uv run --python 3.11 --locked python -m pytest -q`：995 passed，42 skipped，139 subtests passed。
- `bash scripts/check_python_quality.sh`：307 个文件格式检查及 lint 通过。
- `uv run python -m compileall -q src tests`：通过。
- `uv run python scripts/check_markdown_links.py`：通过。
- `git diff --check`：通过。
- 路线图：核对 `docs/roadmap.md`；此修复落实现有身份安全 Contract，不改变产品目标、依赖或优先级，无需更新路线图。
- 未运行：真实 LLM、浏览器 E2E、Stable 验收；本修复不触及这些范围。
