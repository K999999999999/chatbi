# Local task tracker

本仓库使用本地 Markdown 保存当前工作的 Spec、Ticket 和路径规划。它们是工作过程中的本地产物，不依赖 GitHub、GitLab、PR、外部 Issue 或远程标签。

## 文件布局

```text
.scratch/
└── <feature-slug>/
    ├── spec.md                         ← 已确认需求和行为 Contract
    ├── status.md                       ← 规划 / 历史快照；实时状态在 Git 公共目录
    ├── wayfinder.md                    ← 规模较大且路线不清时的本地地图
    ├── issues/                          ← 实现 Ticket
    │   ├── 01-<slug>.md
    │   └── 02-<slug>.md
    └── decisions/                       ← Wayfinder 决策 Ticket
        └── 01-<slug>.md
```

目录和文件按需创建。每个确定要实施的工程改动都留下工作记录；小改动用短 Spec，不要求完整 Spec 的全部字段，也不拆 Ticket。纯问答、只读调查或尚未决定实施的探索不创建实施 Spec。

## 长期工作记录与本机实时进度

职责分开保存：

- `.scratch/<feature>/spec.md`、Tickets、Design / 决策和验收结果是长期规划 / 项目证据，继续纳入 Git。
- 当前阶段、正在等待什么、最近验证、已授权范围和下一步是本机实时进度，保存在 Git 公共目录，不纳入 Git，也不替代项目 Contract。
- `.scratch/<feature>/status.md` 按需保留为规划 / 历史快照；不再作为合并后实时进度的权威副本。更新长期决定时同步其 Spec 或 Ticket。

使用现有 Git 命令定位同一仓库内所有 worktree 共享的目录：

```sh
git rev-parse --path-format=absolute --git-common-dir
```

实时记录位于命令输出目录下：

```text
<git-common-dir>/harness/work-items/<work-item-id>/status.md
```

`.git` 在 linked worktree 中可以是文件；不得用当前 worktree 的 `.git` 文本路径代替 Git 返回的公共目录，也不得编辑 HEAD、index、refs 等 Git 内部数据。此目录可能不存在；仅在目标确定需要实施时按需创建，不为问答或纯只读调查造记录。

实时记录至少包含：

```md
# 实时工作状态
ID: <稳定工作项 ID，与 branch 无关>
Status: open | in-progress | blocked | done
Stage: <需求发现 | 需求与技术澄清 | Spec 待确认 | 设计审查 | Ticket 待确认 | 实施中 | 验证 / Review | 待发布授权 | PR 跟进 | 已合并待复盘 | 待清理 | 完成>
Owner: <当前状态写入负责人>
Last updated: <含时区的时间>
Primary record: <主记录写 Self；关联记录写主仓库身份及相对于其 git-common-dir 的路径>
Target repository: <host / owner / repo>
Spec: <仓库身份、仓库相对路径、适用提交>
Tickets: <仓库身份、相对路径、状态和适用提交>
Repositories: <本目标涉及的 host / owner / repo>
Branches: <仓库、branch、HEAD 和用途>
Worktrees: <当前位置与生命周期；路径只表示当前位置>
Confirmed decisions: <Spec / 决策引用>
Implementation authorization: <范围、依据和确认时间；未知则写 Unknown>
Publication authorization: <Push / PR / 设置等范围、依据和时间；未知则写 Unknown>
Experiment authorization: <实验范围、依据和时间；没有写 None>
PRs: <仓库、PR 身份、head / base、实时状态和最近核实时间；没有写 None>
Verification: <命令 / 场景、对应提交或未提交范围、覆盖范围和结果>
Last checked: <相关 Git / PR 事实的核实时间>
Blocker: <具体原因和恢复条件；没有写 None>
Last stop: <上次停点>
Next: <唯一、可执行的下一步>
```

仓库身份使用可核实的 host / owner / repo；不得从可能包含凭据的 Git remote URL 复制 Token 或其他 Secret。路径引用使用仓库相对路径和提交；绝对 worktree 路径只作当前位置。跨仓库目标使用同一 ID：ChatBI 主记录保存目标授权和总体阶段，其他仓库记录只存本地交付进度并指向主记录，不复制或扩大授权。主记录不可用时，依据 `.scratch`、提交和远端事实恢复；授权不能核实时，不推定可以 Push、改远端设置或删除分支。

关联仓库记录使用相同的 ID，并在 `Primary record` 指向主仓库身份及相对于主仓库 `git-common-dir` 的状态路径；可附当前机器上的绝对路径用于定位，但它不是稳定身份。其授权字段只能写“见主记录”，不能复制成独立授权。每个 Git 公共目录单独保存本仓库状态，因此关联记录不得被误认为整个目标已完成。

### 同仓库关联与本机检查

产品总目标与功能子工作项用以下可选字段明确引用，ID 指向同一 Git 公共目录的当前记录：

```md
Related work items: result-export-v1, harness-delivery-consistency
Active work item: harness-delivery-consistency
Follow-up work item: None
Ticket files: .scratch/example/issues/01-example.md
```

`Related work items` / `Ticket files` 使用逗号分隔；另外两项只接受一个 ID 或 `None`。字段放在当前部分，历史正文使用 `## 历史…` 或 `## History…` 标题；字段示例放在代码块。旧记录无需批量迁移。产品汇总引用子工作项的 Ticket、PR、验证及授权证据，避免复制成另一份可独立过期的进度；产品总体状态与产品级决定仍由总目标保存。关联只用于发现与交接，不继承或扩大授权。显式暂缓 / 被后续工作接手的候选保留其独立生命周期、原因及 `Follow-up work item`，直到替代交付与归档核实完成。

会话恢复、PR 合并收尾和新目标实施前运行：

```bash
python -m scripts.check_harness_state
python -m scripts.check_harness_state --json
```

入口只读本机 Git、Git common-dir 的 `work-items/*/status.md` 及显式 Ticket；支持 linked worktree，不读取同目录历史快照，不访问远端、不更新记录、不清理分支。`--repo` 可指定目标 worktree。Git 命令关闭可选写锁。

- `ERROR`：当前字段无效 / 重复、引用缺失、active 子工作项已完成、done 工作项声明的 Ticket 未完成、Ticket 越出仓库，或检查未完成；退出码 1，修复后才能宣称收尾完整。
- `REVIEW`：未完成目标、工作区有修改、保留分支有 master 不可达提交，或缺少本机记录 / master。逐项结合授权、真实 PR、归属与保留原因核对；明确处置或后续引用，不能默默忽略，也不自动阻止其他无冲突目标。
- 仅含 `INFO` / `REVIEW` 时退出 0；这只表示没有发现可确定错误，不表示所有工作完成。时间较旧或文档出现历史关键词不构成错误；不可达提交不能单独证明未合并，Squash 后仍可能不可达。

新 clone 缺少本机记录时必须依据长期记录和 Git / PR 恢复；工具不会生成记录。GitHub CI 无法读取开发机 `.git/harness`，既有确定性测试验证工具行为，本机实际检查由会话 / 交付执行。工具不判断任意自然语言状态矛盾，也不能替代产品文档语义 Review。

写入与恢复规则：

- 一个目标同一时间由一个主 Agent / 会话写实时状态；不能同时由两个未协调的 writer 更新。交接时先读取最新记录，再明确由新的 writer 接手。
- 每次写前重新读取最新记录；若 `Last updated` 或进度已经前进，先合并已证实的信息，不覆盖后来的状态。
- 准备完整内容后写到同目录临时文件，再用同文件系统的原子替换完成更新，避免半写文件。发现记录损坏、字段缺失或归属冲突时保留原件，核实事实后恢复；不从损坏状态推定授权。
- `Status` 表示整个目标生命周期，`Stage` 表示当前主阶段。普通 CI / Review 等待为 `in-progress`，不是阻塞；只有无法继续且有明确解除条件才标 `blocked`。
- 阶段转换、关键决定、Ticket 交接、验证、PR 创建 / 更新 / 合并、真实阻塞和会话交接时更新；`Next` 必须可直接执行。
- 新会话同时检查当前 branch、HEAD、worktree、Git 状态、`.scratch` 和公共目录实时记录；根据工作项 ID、仓库身份和 branch / worktree / PR 事实匹配。已合并工作在当前 master 上也能通过 PR 身份恢复。
- 对记录中的活动 PR 只读核实 GitHub 实时状态后续做已授权跟进；不要只因当前 branch 不匹配就忽略，也不要求用户选择明确归属的旧记录。若同时有多个互不冲突工作，不因此停顿；仅报告当前请求相关状态。
- 仅在任务归属、授权或互相冲突不能核实时向用户询问。发现 staged、unstaged 或 untracked 用户改动时继续遵守改动归属规则；未知或其他目标的改动不覆盖、不移动、不清理。
- 合并后清理 Feature branch / worktree 时保留本机共享状态记录和长期 `.scratch` 证据。未提交的规划文件仍位于某个 worktree 时，先迁移到其指定长期位置并核实，不得删除唯一副本。
- 换机器或状态文件丢失时，以长期记录、远端 PR、required checks 和 live Git 恢复；标注推断和未知。只读报告不强制创建工程状态记录。

Ticket 状态和独立完成条件仍保存在各 Ticket 的 `Status` / `Result`。整个目标只有所有适用 Ticket、PR、复盘与已决定的清理步骤完成后才是 `done`；清理被用户改动阻碍时报告准确阻塞，不能冒称清理完成。

## Spec

- `workflow-to-spec` 将已经澄清的需求、领域语言、范围、架构影响、Contract 和验证方向写入 `.scratch/<feature>/spec.md`。
- 正式的 ChatBI Feature / Module Spec 仍以 `docs/specs/` 下的事实文档为准；`.scratch/` 用于当前新工作的规划产物。
- 小改动先保存短 Spec，至少说明目标、预期结果、验收方式、验证方式和授权依据；用户明确给出的稳定任务同时构成该范围的实施授权，不再重复请求确认短 Spec。
- 复杂 / 多阶段工作使用完整 Spec；用户确认 Spec 表示需求 Contract 已定，不自动代表实施授权。整体实施授权与 Ticket 拆分确认分别记录；用户确认完成整个目标后按依赖连续实施全部 Tickets，无需逐个等待选择或“继续”；只授权部分范围时仅实施该范围。
- 未确认的 Spec 不能作为已同意的 Contract；小任务的实施授权以用户明确任务指令为依据，不从草稿 Spec 本身推定。
- 用户确认复杂 Spec 后，必须先调用 `workflow-design-review` 完成只读 Spec / 设计审查，再进入 `workflow-to-tickets`；`PASS WITH MINOR FIXES` 时逐项落实并核对修订，只有改变用户决定的修订才重新确认；`NEED FIX` / `BLOCKED` 必须返回 Spec 阶段。
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
- 用户确认 Ticket 拆分后，才能写入正式 Ticket 文件。用户已授权整个目标时，按依赖顺序开始第一项并连续推进；若没有整体或具体范围的实施授权，先一次说明范围并请求授权，不把逐 Ticket 选择当作默认门禁。

## Wayfinder

`wayfinder` 只用于路线不清、决策较多且无法在一个上下文中完成的工作：

- 地图：`.scratch/<effort-slug>/wayfinder.md`；
- 决策 Ticket：`.scratch/<effort-slug>/decisions/<NN>-<slug>.md`；
- 决策 Ticket 解决“需要做出什么决定”，实现 Ticket 解决“已经决定后要实现什么行为”；
- 决策之间的依赖使用 `Blocked by:`；
- Wayfinder 完成后交接到 `workflow-to-spec`、`workflow-to-tickets` 或 `workflow-implement`，不会直接实现代码。

## 状态和边界

长期 Ticket 工作项可使用以下状态：

```text
Status: open | in-progress | done | blocked
```

本地 Ticket 不写外部 Issue ID、PR URL、triage label、远程阻塞链接或外部 assignee。需要记录历史结论时，追加到 `Comments` 或 `Result`，不要删除工作项。

实时进度记录可保存 PR URL / number 及真实状态，以便新会话定位；这不改变长期 Ticket 不写远端跟踪字段的约定，也不让本机状态取代 GitHub 事实。

`docs/architecture.md`、`docs/specs/`、`docs/designs/`、`docs/acceptance/` 和 `reports/` 分别承担架构、行为 Contract、实现设计、验收和证据职责，不因创建本地 Ticket 而被替代。
