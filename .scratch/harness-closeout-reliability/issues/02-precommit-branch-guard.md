# 02 增加可安装的提交前分支 Hook

Status: done
Owner: 当前主 Agent
Blocked by: None (can start immediately)

## What to build

按 `.scratch/harness-closeout-reliability/spec.md` 定义，新增 `.githooks/pre-commit`，在 `master` 和 detached HEAD 上拒绝普通提交，在命名 Feature branch 上允许提交。新增幂等安装入口：检查 Git 可见的所有 `core.hooksPath` 配置来源；无设置或仅一次性 command scope 为 `.githooks` 时持久写入仓库 local `.githooks`；已有持久 `.githooks` 设置时不重复修改；其他路径或冲突值出现时停止且不覆盖任何来源。

在 `AGENTS.md` 和 `docs/runbook.md` 说明新 clone 安装步骤、验证方式及可逆清理方法。清理只在 local `core.hooksPath` 仍严格等于 `.githooks` 时移除该值。

## Scope / Out of Scope

- In Scope: 本仓库本地 Hook、安装脚本、隔离仓库测试、开发说明。
- Out of Scope: 自动安装到所有 clone、修改 global / system 配置、GitHub Branch Protection / Ruleset、阻止 `--no-verify` 绕过。

## Owned files

- `.githooks/pre-commit`
- `scripts/install_git_hooks.sh`
- `tests/scripts/test_git_hooks.py`
- `AGENTS.md` 中新会话 / 新目标起步规则
- `docs/runbook.md` 中开发仓库初始化 / Hook 管理说明

## Acceptance criteria

- 无有效配置时安装器设置 local `core.hooksPath=.githooks`；若只有 command-scoped `.githooks`，安装器仍持久写入 local；已有持久 `.githooks` 时重复运行不改配置。
- 任何有效配置来源存在非 `.githooks` 路径或冲突值时安装拒绝，配置前后均不变。
- 在已安装的隔离仓库中，`master` 与 detached HEAD 的普通 commit 失败并输出切换提示，Feature branch commit 成功。
- Hook 有可执行权限；说明步骤可复现，且不覆盖安装后用户改写的设置。

## Verification plan

- `python3 -m pytest -q tests/scripts/test_git_hooks.py`
- 隔离 Git 仓库覆盖无配置、global custom path、local custom path、冲突多值配置及提交行为，并比较配置修改前后快照。
- Markdown 链接检查、`git diff --check`、当前上下文 Code Review。

## Migration / Rollback

不会自动改动用户配置。回滚仅在本地设置严格等于 `.githooks` 时执行 `git config --local --unset core.hooksPath`；不删除 Hook 文件，不改其他配置层级。无产品数据迁移。

## Result

实现完成；隔离仓库定向测试 `12 passed`，全量 Python 测试 `995 passed, 41 skipped, 139 subtests passed`；当前上下文 Code Review PASS。当前 clone 已安装 local `.githooks`。

## Comments

- Canonical Source: `.scratch/harness-closeout-reliability/spec.md`。
- Ticket Readiness: READY；用户于 2026-10-11 确认此拆分。
- Roadmap: 无需更新；本 Ticket 只增加工程提交护栏，不改变产品路线、依赖或优先级。
