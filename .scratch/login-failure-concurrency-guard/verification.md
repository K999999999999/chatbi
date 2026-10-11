# 登录失败计数并发保护验证

## 候选与范围

- 基线：`b7dd82386d877ccf6669bd2e02698e81da19f975`，与 `origin/master` 同步。
- 分支：`fix/serialize-login-failures`。
- 代码候选：`6e9e316825fe54e3afe5dc7830e5844523fb0fd2`；全部软件验证在其代码与测试内容提交前完成，提交后未改变这些文件。
- 变更：认证服务对用户行使用 PostgreSQL `FOR UPDATE`，使锁定状态检查、失败计数、成功重置和 Session 创建按同一账号串行；正式登录 Contract 补充并发判定；新增隔离 PostgreSQL 并发回归。
- 范围外：AI Evaluation、真实模型、Stable、Push / PR。

## Red / Green 与验证

- Red：未加入行锁时运行 `uv run --locked python scripts/run_database_tests.py --profile development`，仅新增并发用例失败（43 passed、1 failed）：PostgreSQL 未观察到第二个登录请求等待首个事务持有的账号行锁。首次尝试中的测试工具 `NameError` 已修正后重跑，所得为此单一预期失败。
- Green：加锁后同一 development profile 44 passed。测试从失败次数 3 开始，验证第二请求在 PostgreSQL 等待首请求提交，最终计数为 5、账号进入 15 分钟锁定、没有创建 Session，锁定期间正确密码也被拒绝。
- `uv run --locked python -m pytest -q`：995 passed、42 skipped、139 subtests。
- `bash scripts/check_python_quality.sh`：307 files 格式检查与 lint 通过。
- `uv run --locked python -m scripts.check_markdown_links`：通过。
- `git diff --check`：通过。
- Code Review：PASS；变更只锁定同一账号记录，保持现有锁定阈值、时长、登录失败响应与事务内审计 / Session 行为；无 Schema、依赖或接口变化。
- 路线图不更新：本修复不改变已确认里程碑、范围、优先级、依赖或完成事实。
- Harness 反馈：未观察到达到记录门槛的结构性缺口。

## 限制

- PostgreSQL development profile 验证真实行锁。SQLite 单元测试不模拟 PostgreSQL `FOR UPDATE` 并发语义。
- 未运行 AI Evaluation、真实浏览器验收或 Stable 验收；本修复不触及其行为。
