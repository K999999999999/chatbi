# Local task tracker

本仓库使用本地 Markdown 保存当前工作的 Spec、Ticket 和路径规划。它们是工作过程中的本地产物，不依赖 GitHub、GitLab、PR、外部 Issue 或远程标签。

## 文件布局

```text
.scratch/
└── <feature-slug>/
    ├── spec.md                         ← 已确认需求和行为 Contract
    ├── wayfinder.md                    ← 规模较大且路线不清时的本地地图
    ├── issues/                          ← 实现 Ticket
    │   ├── 01-<slug>.md
    │   └── 02-<slug>.md
    └── decisions/                       ← Wayfinder 决策 Ticket
        └── 01-<slug>.md
```

目录和文件按需创建。小范围、单会话可完成的工作不需要为了形式创建 Spec 或 Ticket。

## Spec

- `to-spec` 将已经澄清的需求、领域语言、范围、架构影响、Contract 和验证方向写入 `.scratch/<feature>/spec.md`。
- 正式的 ChatBI Feature / Module Spec 仍以 `docs/specs/` 下的事实文档为准；`.scratch/` 用于当前新工作的规划产物。
- Spec 未经用户确认时，只能作为草稿，不能作为实现授权。
- 用户确认 Spec 后，必须先调用 `design-review` 完成只读 Spec / 设计审查，再进入 `to-tickets`；`PASS` 或 `PASS WITH MINOR FIXES` 才能继续，`NEED FIX` / `BLOCKED` 必须返回 Spec 阶段。
- `design-review` 不修改 Spec、代码或测试，也不替代实现完成后的 `code-review`；纯文档或小范围 Spec 可以快速审查，但不能静默跳过门禁。

## 实现 Ticket

- `to-tickets` 将已确认且通过 `design-review` 的 Spec 拆分为可独立验证的纵向切片。
- 每个 Ticket 使用独立 Markdown 文件，从 `01` 开始，按直接依赖顺序编号。
- 初始状态使用 `Status: open`。
- Ticket 至少包含 `What to build`、`Blocked by`、`Acceptance criteria`、`Result` 和 `Comments`。
- `Blocked by:` 只记录真正阻塞当前 Ticket 的直接前置 Ticket；无阻塞时使用 `None (can start immediately)`。
- 用户确认 Ticket 拆分后，才能写入 Ticket 文件；写入后仍需用户选择具体 Ticket 才进入 `implement`。

## Wayfinder

`wayfinder` 只用于路线不清、决策较多且无法在一个上下文中完成的工作：

- 地图：`.scratch/<effort-slug>/wayfinder.md`；
- 决策 Ticket：`.scratch/<effort-slug>/decisions/<NN>-<slug>.md`；
- 决策 Ticket 解决“需要做出什么决定”，实现 Ticket 解决“已经决定后要实现什么行为”；
- 决策之间的依赖使用 `Blocked by:`；
- Wayfinder 完成后交接到 `to-spec`、`to-tickets` 或 `implement`，不会直接实现代码。

## 状态和边界

本地工作项可使用以下状态：

```text
Status: open | in-progress | done | blocked
```

本地 Ticket 不写外部 Issue ID、PR URL、triage label、远程阻塞链接或外部 assignee。需要记录历史结论时，追加到 `Comments` 或 `Result`，不要删除工作项。

`docs/architecture.md`、`docs/specs/`、`docs/designs/`、`docs/acceptance/` 和 `reports/` 分别承担架构、行为 Contract、实现设计、验收和证据职责，不因创建本地 Ticket 而被替代。
