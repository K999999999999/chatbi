# Git / Branch / Pull Request Workflow

本文档定义 ChatBI Coding Agent（编码代理）的 Git 协作流程，补充根目录 `AGENTS.md` 的强制规则。

## Source of Truth

- `AGENTS.md`：Agent 必须遵守的项目规则和授权边界；
- 本文档：Branch、worktree、Commit、candidate、PR 和清理的详细工作顺序；
- `.scratch/<feature>/`：当前 Feature 的 Spec、Ticket 和长期过程 / 验收记录，不等于 Git branch，也不等于 PR；本机实时状态保存在 Git 公共目录；
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

同时运行 `python -m scripts.check_harness_state`。先处理当前目标相关 ERROR；逐项记录 REVIEW 的归属、授权、暂缓 / 接手决定。存在其他独立待发布候选时，可以推进无冲突工作，但须保留其可发现的下一步，不能把 Git clean 表述为所有目标均完成。

如果发现已有同目标 branch，先判断它是否是当前 candidate、已被主干吸收、已被其他 branch supersede，或只是 backup；不得仅根据 branch 名称继续追加提交。

### 2. Define the work

- 每个确定要实施的工程改动都创建工作记录；小范围单会话修改使用短 Spec，不要求拆 Ticket；
- 需求、Contract、范围或架构影响不清楚时，先建立并确认 Spec；
- 多阶段 Feature 在完整 Spec 确认并通过 `workflow-design-review` 后拆分 Ticket；
- `workflow-to-tickets` 形成草案后，必须先通过当前上下文的 `workflow-ticket-readiness`，再由用户确认 Ticket 拆分；
- Ticket 拆分确认与整体实施授权分别记录；用户已授权整个目标时，按依赖顺序连续实施全部 Ticket，不逐 Ticket 请求选择或继续确认；范围授权有限时只执行已授权 Ticket / 范围；
- Spec / Ticket 的确认不自动授权 Push、PR 或 Merge。

计划合入 `master` 的变更，无论大小，都在形成 candidate 后通过一个 PR 交付；小变更使用短 Spec、不拆 Ticket，但不跳过 targeted tests、Diff Review、candidate 检查、required checks 和合并后清理。只读咨询、诊断和不准备合入仓库的临时实验不进入 PR 流程。

### 3. Implement on one branch

- 在同一个 Feature branch 中按 Ticket 实施；
- 开始实现前确认 Ticket 拆分已通过 Ticket Readiness Review，且没有遗留的 Contract / Architecture 决策；完整目标授权后无需再次通过用户选择具体 Ticket 才开始；
- 每个逻辑阶段运行对应 targeted tests；
- 通过 `workflow-tdd`、`workflow-code-review` 和 Diff Review 收敛实现；
- 只提交当前目标相关文件；
- Commit Message 使用 `<type>(<scope>): <中文摘要>`；
- 不因某个 Ticket 完成就自动创建 PR。

### 4. Form a candidate

当一个清晰目标已经形成可交付 candidate 时，先确认：

- 当前 branch 和最终 HEAD；
- `git_dirty=false`，没有未跟踪文件；
- Contract、相关测试、Diff Review 和 `git diff --check` 已完成；
- 对代码质量检查记录实际命令、工具版本和覆盖目录 / 文件；局部定向检查必须标明范围，不能表述为全量通过。Python 格式与 lint 统一运行 `bash scripts/check_python_quality.sh`，该入口同时由 CI 调用；
- 已核对 `docs/roadmap.md`，按 [路线图维护规则](agent-harness.md#路线图读取与维护) 同步受影响的目标、依赖和验收状态，并对照产品范围 / Spec 检查需求状态、当前能力、不包含 / 后续范围无矛盾；记录核对位置与结果，或不适用理由；优先级与范围变化已经用户确认；
- 高风险链路是否需要 Real E2E；
- 当前 PR 目标、commit 范围、未执行验证和剩余风险。

候选阶段只形成本地可验收状态，不自动 Push 或创建 PR。

### 5. 发布授权与 PR

形成 candidate 后，Agent 在聊天中向用户说明 PR 的唯一目标、提交范围、风险、验证证据和自动合并行为，再取得明确的 Push / PR 发布授权。PR 正文用于保留事实，不能替代聊天中的发布授权或后续交接。

发布授权绑定当前工作项与已说明的范围。授权后可持续执行该范围内的 Push、创建 / 更新 PR、CI 修复、状态跟进、复盘和安全清理，不为每次正常推进重复询问；目标、范围或关键决定变化时重新确认。

按以下顺序执行：

```text
发布授权
→ 最终确认 branch、HEAD 和 git_dirty=false
→ 按风险运行 targeted tests / AI Evaluation / Business Acceptance / Real E2E
→ 检查测试结果、Evaluation 报告和未验证范围
→ 核对已有验证是否绑定当前 HEAD、base 和范围；相关行为 / 基线改变时重跑受影响检查，未受影响的证据可复用
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

当前仓库的 `.github/workflows/enable-auto-merge.yml` 会在符合条件的 PR 事件后请求 Squash Auto-merge。动作前会读取 GitHub 上的实时 PR，核对 `state`、Draft、head SHA、base branch 和 head repository 是否仍与事件快照一致；旧事件、状态未知、PR 已关闭、仍为 Draft、base 不再是 `master` 或 head 已变化时跳过，不调用启用动作。普通独立 PR 以 required checks 自动合并为默认，不额外要求用户 PR Review；Agent 不直接人工 Merge。依赖 PR 必须依照依赖门禁保持 Draft，直到前置 PR、最终 base 和适用检查均满足。聊天授权前必须说明目标仓库的真实 Auto-merge 行为，之后核实 PR 的真实状态。Stacked / 依赖 PR 不得提前启用 Auto-merge。

### 6. PR 后状态检查与自动收尾

每次创建或更新 PR 后，Agent 必须执行一次统一的 Post-PR（PR 后）状态检查，不再要求用户为正常的合并收尾重复确认。

#### 6.1 等待和检查

1. 创建 / 更新后立即记录 PR number、URL、head branch、base branch、提交 HEAD、授权范围和时间，并核实一次真实状态；在聊天中交接 PR 链接、自动合并状态、CI 进度和下一检查条件；
2. 若 CI 或合并仍在等待，使用事件或 monitor；否则按约两分钟的间隔继续核实，不因达到某个等待时长而结束任务。任何单次阻塞等待不得超过 60 秒，必要时分段等待，并在聊天中报告有意义的进展；
3. 每次核实时读取真实状态，至少检查：
   - `state`、`mergedAt`、`mergeStateStatus`；
   - `headRefName`、`baseRefName`；
   - `autoMergeRequest` 和 Auto-merge（自动合并）策略；
   - CI、required checks（必需检查）和失败原因。

推荐使用：

```text
gh pr view <PR> --json number,url,state,isDraft,mergedAt,mergeStateStatus,headRefOid,headRefName,baseRefName,autoMergeRequest,statusCheckRollup
```

#### 6.2 合并后 Harness 复盘

PR 确认已 `MERGED` 后，每个交付都必须完成一次简短 Harness 复盘，再清理 Feature branch。即使自动清理因工作区修改或其他依赖而暂停，也要完成复盘。

同时核对合并事实是否影响路线图状态；沿用 [路线图维护规则](agent-harness.md#路线图读取与维护) 复核受影响能力的当前描述，记录核对位置与结果或不适用理由，并同步主工作项及关联实时记录的顶部当前字段和下一步，不能只追加末尾收尾记录。不将合并或 CI 通过视为真实 Evaluation 或生产验收通过。

列出本次交付涉及的工作项记录和关联产品汇总，逐项同步后运行 `python -m scripts.check_harness_state`，记录 ERROR 数及每项 REVIEW 的处置。无法核对的事项如实保留；存在未解释的相关发现时不得写“无新增缺口”或“全部收尾完成”。工具无 ERROR 不替代路线图 / 产品范围 / Spec 的语义核对，也不自动授权发布其他候选。

检查本次 Agent 工作是否因项目背景、规则、工具或验证方式不足而发生误解、漏验、返工或需要用户纠正：

- 没有发现缺口：在 PR 的“合并后 Harness 复盘”栏记录“无新增缺口”。
- 发现缺口：记录具体表现和根因，创建后续 Harness 改进项并关联到 PR；改进项要说明要调整的规则、文档、Skill、工具或验证方式，以及如何检查改进有效。
- 如果问题来自产品实现本身，按产品 Bug / Regression 处理；如果 Agent 的工作环境也导致问题，同时创建 Harness 改进项。

复盘只记录可行动的缺口，不要求每个 PR 另写一份复盘文档。已合并的产品 PR 不因复盘发现而追加无关改动；Harness 改进按独立目标交付。

#### 6.3 已合并时的自动清理

只有 PR 已明确为 `MERGED`，且满足下方 Routine cleanup authorization 的全部条件时，才执行：

1. `git fetch origin --prune`；
2. 确认当前 worktree 没有用户的 staged、unstaged 或 untracked 修改；
3. 确认本次 head branch 没有合并后新增的本地 Commit、未 Push 工作、Open PR、Stacked PR 或其他 worktree 依赖；
4. 回到 `master`，使用 `git merge --ff-only origin/master` 同步合并结果；
5. 删除本次 PR 对应的本地 Feature worktree / branch；
6. 检查远端 head branch；如果仓库没有自动删除，且能够确认它就是本次已合并 PR 的唯一 head branch，则删除远端 branch；
7. 再次执行 `git fetch origin --prune`，确认当前 branch、HEAD、tracking、工作区和远端 branch 状态；
8. 保留仍有回滚价值的 `backup/*` 和 `codex/backup-*` branch，不把它们当作日常开发线；
9. 只有以上检查全部通过，才能在完成报告中明确说明：“当前工作区已恢复到干净的 `master`，可以开始下一个 Feature”。

#### 6.4 PR 尚未合并或异常时

- `OPEN`、`BLOCKED`、CI / required checks 仍在运行或失败：保留 head branch，不执行分支清理，报告 PR 状态、检查进度和下一等待条件；
- `CLOSED` 但未 `MERGED`：不删除可能仍有价值的 Feature branch，报告关闭状态并暂停；
- 发现用户修改、未推送 Commit、Stacked PR、其他 worktree 依赖或 branch 归属不确定：暂停自动收尾并请求用户决定；
- 不因为 branch 看起来旧、PR 看起来已经过期或名称相似就批量删除历史 branch。

#### 6.5 Post-PR 完成报告

PR 后报告至少包含：

- PR URL、最终 `state`、`mergedAt` 和 merge commit；
- CI / required checks 的通过、失败或仍在运行状态；
- 当前 `master`、HEAD 和 `git status`；
- 删除的本地 / 远端 Feature branch 和保留的 backup branch；
- 合并后 Harness 复盘结论及后续改进项链接；无新增缺口时明确记录“无新增缺口”；
- 是否存在未处理问题、等待条件或风险；
- 只有完成自动收尾并验证干净时，明确告知可以开始下一个 Feature。

#### Routine cleanup authorization

当前 PR 的正常合并收尾属于同一交付范围，不需要用户为每一次清理再次确认。满足以下全部条件时，Agent 可以自动完成清理：

- 当前 branch 是本次 PR 的唯一 head branch，PR 已经 `MERGED`；
- worktree 干净，没有用户的 staged、unstaged 或 untracked 修改；
- branch 没有 PR 合并后新增的本地 Commit，也没有未 Push 的用户工作；
- 没有 Open PR、Stacked PR 或其他 worktree 依赖该 branch；
- 目标不是 `master`、受保护 branch、`backup/*` 或 `codex/backup-*`。

自动清理顺序为：确认 PR 已合并且状态事实最新 → 回到 `master` → fast-forward 同步 `master` → 删除当前 Feature 的本地 worktree / branch → 检查仓库的 `delete_branch_on_merge` → 在持续发布授权范围内必要时删除已确认的远端 head branch → 再次检查工作区和远端引用。

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
- parent 合并后如何将 child branch 更新到最终 base，并重跑 / 复用哪些验证。

依赖未满足前，child PR 保持 Draft。parent 全部合并后，核对 child 的实时 head、base 和 Draft 状态，将 base 更新到最终目标，再按实际影响重跑受 base 变化影响的 CI / 验证。只有 parent 已合并、head 与最终 base 核对完成、适用 required checks 通过后才转为 Ready；切换 base 前的旧检查不能单独作为最终验收证据。无法读取依赖或 PR 实时状态时继续保持 Draft 并记录阻塞。

如果这些条件不清楚，使用单一 Feature branch 和单一 PR。

### Resume

恢复工作时，不默认相信旧对话、Spec 摘要、branch 名称或历史报告。先读取 Git 公共目录的共享实时状态，再核对当前 checkout 的 branch、HEAD、status、worktree、远端关系、`.scratch` 长期记录和 PR 实况；按工作项 ID 与仓库 / PR 身份恢复，不要求当前 branch 唯一匹配。若归属、授权或工作之间存在无法消解的冲突，列出已核实事实并只询问解决冲突所需的决定；没有相关未完成工作时正常响应当前请求。
