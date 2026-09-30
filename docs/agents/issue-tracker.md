# Local task tracker

本仓库使用本地 Markdown 保存当前工作的 Spec、Ticket 和路径规划。它们是工作过程中的本地产物，不依赖 GitHub、GitLab、PR、外部 Issue 或远程标签。

## 文件布局

```text
.scratch/
└── <feature-slug>/
    ├── spec.md                         ← 已确认需求和行为 Contract
    ├── status.md                       ← 当前阶段、分支、进度和下一步
    ├── wayfinder.md                    ← 规模较大且路线不清时的本地地图
    ├── issues/                          ← 实现 Ticket
    │   ├── 01-<slug>.md
    │   └── 02-<slug>.md
    └── decisions/                       ← Wayfinder 决策 Ticket
        └── 01-<slug>.md
```

目录和文件按需创建。每个确定要实施的工程改动都留下工作记录；小改动用短 Spec，不要求完整 Spec 的全部字段，也不拆 Ticket。纯问答、只读调查或尚未决定实施的探索不创建实施 Spec。

## 会话状态记录

活动工作项在 `.scratch/<feature>/status.md` 记录恢复所需的最少信息：

```md
# 工作状态
Status: open | in-progress | blocked | done
Stage: 需求发现 | 需求澄清 | Spec 待确认 | 设计审查 | Ticket 待拆分 | Ticket 待确认 | 待实施 | 实施中 | 验证 / Review | PR 检查中 | 已合并待 Harness 复盘 | 完成 | 等待用户决定
Branch: <当前 feature branch>
Worktree: <当前仓库根路径>
Spec: <路径或 None>
Tickets: <路径或 None>
Last updated: <date>

## 当前进度
<已经完成到哪里；用户做过的关键确认>

## 已确认决定
- <决定和依据>

## 未决问题
- <等待用户决定的问题；没有则写 None>

## 关联路径
- <当前工作涉及或用户修改的路径>

## 上次停点
<中断前正在做什么>

## 下一步
<唯一、可执行的下一步>
```

- `Status` 表示工作项生命周期，`Stage` 表示当前阶段；阶段变化、关键决定、Ticket 交接、PR 状态变化和会话交接时更新记录。
- 新会话以 live Git branch 为主要匹配依据；检查 `Worktree` 路径及关联路径辅助确认。只有当前 branch 唯一匹配一条非 `done` 状态记录时才自动恢复。
- 无匹配或多匹配时，报告候选并请用户选择。状态记录与实时 Git 状态冲突时，以实时状态为准并标记记录待修正，不依赖旧聊天猜测。
- 未提交改动需与状态记录的关联路径、Ticket owned files 或当前目标核对。能明确归属当前工作时，可在状态播报后继续；归属不明或属于其他工作时，暂停新的写入并由用户决定。不得自动清理、覆盖或移动改动。
- 旧活动工作尚无 `status.md` 时，在恢复该工作时补建；不批量改写已完成工作的历史记录。完成后标记 `Status: done` 并保留记录。

## Spec

- `workflow-to-spec` 将已经澄清的需求、领域语言、范围、架构影响、Contract 和验证方向写入 `.scratch/<feature>/spec.md`。
- 正式的 ChatBI Feature / Module Spec 仍以 `docs/specs/` 下的事实文档为准；`.scratch/` 用于当前新工作的规划产物。
- 小改动使用短 Spec，至少说明目标、预期结果、验收方式和验证方式；复杂 / 多阶段工作使用完整 Spec。两者都先由用户确认后才作为实施依据。
- Spec 未经用户确认时，只能作为草稿，不能作为实现授权。
- 用户确认复杂 Spec 后，必须先调用 `workflow-design-review` 完成只读 Spec / 设计审查，再进入 `workflow-to-tickets`；`PASS` 或 `PASS WITH MINOR FIXES` 才能继续，`NEED FIX` / `BLOCKED` 必须返回 Spec 阶段。
- `workflow-design-review` 不修改 Spec、代码或测试，也不替代实现完成后的 `workflow-code-review`；纯文档或小范围 Spec 可以快速审查，但不能静默跳过适用门禁。

## 实现 Ticket

- `workflow-to-tickets` 将已确认且通过 `workflow-design-review` 的复杂 Spec 拆分为可独立验证的纵向 Ticket。
- 每个 Ticket 使用独立 Markdown 文件，从 `01` 开始，按直接依赖顺序编号。
- 初始状态使用 `Status: open`。
- Ticket 至少包含 `What to build`、`Blocked by`、`Acceptance criteria`、`Result` 和 `Comments`。
- `Blocked by:` 只记录真正阻塞当前 Ticket 的直接前置 Ticket；无阻塞时使用 `None (can start immediately)`。

### Ticket Readiness Review

- `workflow-to-tickets` 先形成 Ticket 草案；在用户确认拆分前，当前 Agent 必须执行一次只读的 `workflow-ticket-readiness`。
- Review 至少检查 Scope / Out of Scope、直接依赖、owned files、可观察的成功和失败行为、状态 / 安全边界、确定性测试或 Evaluation 证据，以及可客观判断的 Done When。
- Review 结果只有 `READY` 或 `NEED FIX`。发现未解决的 Architecture、Domain、公共 Contract、权限或状态决策时，返回 Spec / `workflow-design-review` 阶段，不在 Ticket 或代码中猜测。
- 该 Review 不启动独立 Agent，也不替代 `workflow-design-review`、实现后的 `workflow-code-review` 或 PR Review。
- 用户确认 Ticket 拆分后，才能写入正式 Ticket 文件；写入后仍需用户选择具体 Ticket 才进入 `workflow-implement`。

## Wayfinder

`wayfinder` 只用于路线不清、决策较多且无法在一个上下文中完成的工作：

- 地图：`.scratch/<effort-slug>/wayfinder.md`；
- 决策 Ticket：`.scratch/<effort-slug>/decisions/<NN>-<slug>.md`；
- 决策 Ticket 解决“需要做出什么决定”，实现 Ticket 解决“已经决定后要实现什么行为”；
- 决策之间的依赖使用 `Blocked by:`；
- Wayfinder 完成后交接到 `workflow-to-spec`、`workflow-to-tickets` 或 `workflow-implement`，不会直接实现代码。

## 状态和边界

本地工作项可使用以下状态：

```text
Status: open | in-progress | done | blocked
```

本地 Ticket 不写外部 Issue ID、PR URL、triage label、远程阻塞链接或外部 assignee。需要记录历史结论时，追加到 `Comments` 或 `Result`，不要删除工作项。

`docs/architecture.md`、`docs/specs/`、`docs/designs/`、`docs/acceptance/` 和 `reports/` 分别承担架构、行为 Contract、实现设计、验收和证据职责，不因创建本地 Ticket 而被替代。
