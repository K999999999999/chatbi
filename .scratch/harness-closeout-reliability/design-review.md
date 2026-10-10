# Design Review：Harness 收尾与提交分支护栏

Review: PASS WITH MINOR FIXES
Review Target: `.scratch/harness-closeout-reliability/spec.md`
Reference: 未读取 Architecture Knowledge Core；本目标不修改产品架构、模块边界、公共业务 Contract、依赖方向或部署边界。

## Findings

### 1. Hook 安装必须尊重所有 Git 配置层级

- Signal: 只看仓库 local config 可能以 local `core.hooksPath` 覆盖用户既有的 global / system Hook。
- Evidence: 初始 Spec 仅说明“仓库本地”配置；Git 的 `core.hooksPath` 可来自不同配置层级，现有仓库无 Hook 安装器可复用。
- Impact: 安装改动可能静默移除用户原有 Hook，导致提交前安全或质量检查停止运行。
- Recommendation: 安装器先检查有效配置；仅未配置时设置 local `.githooks`，已有其他有效路径时拒绝安装且不修改配置。Spec 已修订并要求对各配置层级回归测试。

### 2. 分支护栏应拒绝 detached HEAD

- Signal: 仅拒绝 `master` 会放过 detached HEAD 提交。
- Evidence: 本仓库 Git 流程要求从 `master` 建立命名 Feature branch；detached HEAD 没有可用于交付的命名 branch。
- Impact: 提交可能变成不易发现的孤立候选，增加状态恢复和交付遗漏风险。
- Recommendation: 对 detached HEAD fail closed，并给出切换到命名 Feature branch 的提示。Spec 已修订并纳入隔离仓库测试。

## Repository / Runtime Reality

- 当前分支由 `git branch --show-current` 可读；detached HEAD 返回空字符串，因此 Hook 可确定性阻断。
- Git 官方 `githooks` 文档说明非 bare Hook 在工作树根运行，Git `core.hooksPath` 文档说明相对路径相对于 Hook 运行目录解析；`.githooks` 可用于本仓库和 linked worktree。
- Git 要求 Hook 文件有 executable bit；实现和测试必须保留 / 检查该权限。
- `.scratch/harness-closeout-reliability/spec.md` 现在记录同范围边界修订。

## Alternatives / Complexity

- 仅保留文档提醒最简单，但不能阻止普通 `git commit` 的误操作。
- 仅用脚本包装提交不会覆盖用户直接运行的 `git commit`。
- 服务端保护可形成更强门禁，但会改变远端设置，且不属于已授权目标。
- 可安装本地 Hook 符合当前范围；其限制是未安装或 `--no-verify` 可以绕过，Spec 已明确，不把它描述为安全边界。

## Evidence Sources

- `AGENTS.md`、`docs/agents/issue-tracker.md`、`docs/agents/git-pr-workflow.md`
- `.github/pull_request_template.md`
- `scripts/check_harness_state.py` 与 `tests/scripts/test_check_harness_state.py`
- Git 官方手册：[githooks](https://git-scm.com/docs/githooks)、[git-config: core.hooksPath](https://git-scm.com/docs/git-config#Documentation/git-config.txt-corehooksPath)

Next: `workflow-to-tickets` 起草两个可独立验证的 Ticket，然后执行当前上下文的 `workflow-ticket-readiness`。
