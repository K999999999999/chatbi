# Git / Branch / Pull Request Workflow

本文档定义 ChatBI Coding Agent（编码代理）的 Git 协作流程，补充根目录 `AGENTS.md` 的强制规则。

## Source of Truth

- `AGENTS.md`：Agent 必须遵守的项目规则和授权边界；
- 本文档：Branch、worktree、Commit、candidate、PR 和清理的详细工作顺序；
- `.scratch/<feature>/`：当前 Feature 的 Spec、Ticket 和过程记录，不等于 Git branch，也不等于 PR；
- `.github/pull_request_template.md`：PR 提交时的目标、风险、验证和 Review Checklist；
- `.github/workflows/`：GitHub 上实际执行的 CI、Real E2E 和 Auto-merge automation。

如果本文档与 GitHub workflow 的实际行为不一致，必须明确报告差异；不能把文档描述当成已经发生的远程状态。

## Core Model

```text
一个确认的 Feature / 工程目标
→ 一个 active branch
→ 一个 active worktree
→ 多个 Ticket（如确有必要）
→ 多个逻辑 Commit
→ 一个 candidate
→ 一个 PR
```

规则：

- 不为每个 Ticket 创建 branch；Ticket 是同一 Feature branch 内的实施切片；
- 不为每个 Commit 创建 branch；Commit 是同一目标的逻辑交付记录；
- 不同时维护多个同目标 candidate；需要替换 candidate 时，先标记旧线停止使用；
- 并行 branch 或 stacked PR 只用于独立目标或明确依赖的交付，并记录最终 base、依赖 PR 和清理责任；
- backup branch 只做回滚保护，不作为 active development branch，也不创建 PR。

## Standard Flow

### 1. Start from the baseline

开始新目标前：

1. 检查当前 branch、HEAD、worktree 和 `git status`；
2. 确认没有用户未处理的 staged、unstaged 或 untracked 修改；
3. 更新并确认 `master` 是当前可用基线；
4. 从 `master` 创建一个命名清晰的 Feature branch，例如 `feat/<slug>`、`fix/<slug>`、`refactor/<slug>` 或 `docs/<slug>`。

如果发现已有同目标 branch，先判断它是否是当前 candidate、已被主干吸收、已被其他 branch supersede，或只是 backup；不得仅根据 branch 名称继续追加提交。

### 2. Define the work

- 小范围单会话修改可以直接实施，不强制创建 Spec 或 Ticket；
- 需求、Contract、范围或架构影响不清楚时，先建立并确认 Spec；
- 多阶段 Feature 在 Spec 确认后拆分 Ticket；
- 用户确认 Ticket 拆分后，按依赖顺序选择 Ticket 实施；
- Spec / Ticket 的确认不自动授权 Push、PR 或 Merge。

### 3. Implement on one branch

- 在同一个 Feature branch 中按 Ticket 实施；
- 每个逻辑阶段运行对应 targeted tests；
- 通过 TDD、Code Review 和 Diff Review 收敛实现；
- 只提交当前目标相关文件；
- Commit Message 使用 `<type>(<scope>): <中文摘要>`；
- 不因某个 Ticket 完成就自动创建 PR。

### 4. Form a candidate

当一个清晰目标已经形成可交付 candidate 时，先确认：

- 当前 branch 和最终 HEAD；
- `git_dirty=false`，没有未跟踪文件；
- Contract、相关测试、Diff Review 和 `git diff --check` 已完成；
- 高风险链路是否需要 Real E2E；
- 当前 PR 目标、commit 范围、未执行验证和剩余风险。

候选阶段只形成本地可验收状态，不自动 Push 或创建 PR。

### 5. User confirmation and PR

Agent 必须先向用户说明：

- PR 的唯一目标；
- 包含的 commit 范围；
- 是否涉及 Retrieval、Prompt、Semantic、RAG、Embedding、Qdrant、LLM、Evaluation cases 或 SQL 生成；
- 必须执行的最终验证和仍缺少的证据。

用户确认后，按以下顺序执行：

```text
用户确认
→ 最终确认 branch、HEAD 和 git_dirty=false
→ 按风险运行 targeted tests / Real E2E
→ 检查测试结果、Evaluation 报告和未验证范围
→ Push
→ 创建或更新一个 PR
→ 检查 CI、required checks 和 PR 状态
```

以下动作必须区分：

- Commit：本地版本记录；
- Push：写入 remote branch；
- Create / Update PR：创建或更新合并请求；
- Auto-merge：请求满足条件后自动合并；
- Merge：实际合并 PR。

当前仓库的 `.github/workflows/enable-auto-merge.yml` 可能在符合条件的 PR 事件后自动请求 Squash Auto-merge。Agent 不直接 Merge；创建或更新 PR 前必须向用户说明这一自动行为，并在之后验证 PR 的真实状态。Stacked PR 不得默认启用 Auto-merge。

### 6. Finish and clean up

PR 合并后：

1. 回到 `master`；
2. 更新本地 `master`；
3. 确认没有需要保留的用户修改、未推送 Commit 或 backup；
4. 删除已完成目标的本地 Feature worktree 和 branch；
5. 保留仍有回滚价值的 backup branch，并明确其用途；
6. 下一项工作重新从 `master` 创建新的 Feature branch。

#### Routine cleanup authorization

当前 PR 的正常合并收尾属于同一交付范围，不需要用户为每一次清理再次确认。满足以下全部条件时，Agent 可以自动完成清理：

- 当前 branch 是本次 PR 的唯一 head branch，PR 已经 `MERGED`；
- worktree 干净，没有用户的 staged、unstaged 或 untracked 修改；
- branch 没有 PR 合并后新增的本地 Commit，也没有未 Push 的用户工作；
- 没有 Open PR、Stacked PR 或其他 worktree 依赖该 branch；
- 目标不是 `master`、受保护 branch、`backup/*` 或 `codex/backup-*`。

自动清理顺序为：回到 `master` → fast-forward 同步 `master` → 删除当前 Feature 的本地 worktree / branch → 检查仓库的 `delete_branch_on_merge`；如果远端 branch 仍未被仓库自动删除，且仍能确认它就是本次已合并 PR 的 head branch，才删除该远端 branch。

以下情况仍必须暂停并请求用户确认：无法确认 branch 与当前 PR 的唯一归属、PR 未合并、存在 Stacked PR 或其他依赖、发现用户修改、目标是 backup / protected branch，或要批量处理当前交付之外的历史遗留 branch。不得因为“看起来旧”就自动删除历史 branch。

## Exceptional Flows

### Parallel work

只有当两个目标相互独立，或用户明确要求并行开发时，才创建多个 active branch。每条线必须有独立目标、独立验证和明确的最终去向。

### Stacked PR

Stacked PR 必须记录：

- 每个 PR 的唯一目标；
- parent PR 和最终 base；
- required checks 和 branch protection；
- 合并顺序；
- parent 合并后如何更新 child branch。

如果这些条件不清楚，使用单一 Feature branch 和单一 PR。

### Resume

恢复工作时，不默认相信旧的对话、Spec 摘要、branch 名称或历史报告。先检查 live checkout 的 branch、HEAD、status、worktree、远端关系和当前 `.scratch` 记录，再决定继续、切回 `master`、保留为 backup 或停止使用。
