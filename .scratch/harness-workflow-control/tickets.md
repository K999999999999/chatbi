# Ticket 拆分与确认记录：Harness 工作流控制与交付闭环

Status: confirmed; formal Tickets are in `issues/`
Date: 2026-10-01
Spec: spec.md（用户已确认）
Design Review: design-review.md（最终 PASS；R01–R05 已落实）
Owner: 当前主 Agent；关键决定由用户确认。

用户已确认本拆分并授权按依赖顺序完成全部 5 项；正式 Ticket 位于 `issues/`，其状态以各 Ticket 文件为准。实施授权不包含尚未取得的 Push / PR 授权。

## 依赖与公共边界

```text
01 共享状态与恢复
  → 02 ChatBI 确认、实施与交付闭环
  → 03 通用 Skill 阶段调用与关键方案控制
  → 04 通用恢复与交付、依赖合并保护
  → 05 场景验收、当前任务迁移与安装同步
```

每项只列直接前置，不为每个 Ticket 创建 branch。ChatBI 使用当前工作线；Plugin 实施前核实自身 Git / worktree / 源与 marketplace 状态，从同步的默认分支建立当前目标工作线，保留用户原有改动和旧分支。

Canonical Source：本 Spec 是当前目标 Contract；正式项目规则在 ChatBI docs/agents 与 AGENTS；通用规则在 Plugin 源。Runtime、安装缓存和验收 fixture 不能定义新授权或反向覆盖已确认方案。

所有 Ticket 共用以下限制：不改产品业务 / 数据库 / 运行时，不改无关 Plugin，不直接 Merge，不批量迁移历史，不擅自发布或关闭 CI 保护。关键方案变化返回用户确认；范围内修复持续推进。无需真实流量 Rollout 或 Feature Flag。

## Ticket 01：共享本机状态与安全恢复

Status: done
Owner: 当前主 Agent
Blocked by: None (can start immediately)

### Change Profile

长期规则；中等大小；风险为进度丢失、用户工作被覆盖和授权推断错误；证据为隔离 Git / worktree 场景；交付为 ChatBI 状态 / 入口文档与可执行的操作约定。

### What to build

- 定义公共 Git 目录内的 Markdown 状态位置、工作项 ID、字段、Owner、更新和保留方式。
- 区分长期 .scratch 记录与本机实时状态；长期引用包含仓库相对路径与提交，临时路径失效仍可恢复。
- 定义单写入、重读核对、完整替换、损坏保留和跨仓库主 / 关联记录规则。
- 新会话区分实施恢复和 PR 收尾；无活动工作直接处理请求，master checkout 不使未完成交付丢失。
- 旧记录仅在恢复当前活动任务时导入；无依据的授权不重建为已授权。

### Owned files

- ChatBI：docs/agents/issue-tracker.md 的状态、保存、恢复与迁移部分。
- ChatBI：docs/agents/agent-harness.md 的组成、入口与本机记录说明。
- ChatBI：AGENTS.md 的状态入口、恢复与改动归属规则。
- 当前工作项的结果与验收引用；本机状态模板可置于上述文档，不新增生产模块。

### Acceptance criteria / Evidence

- S03–S07、S17、S19–S20 有具体可观察结果：多个 worktree 解析同一目录，状态更新不改变 git status，worktree 删除后引用仍可核实。
- 损坏、缺字段、写入冲突和未知授权时保留文件并说明恢复条件。
- 用户修改阻碍清理时不执行删除；无活动任务不强制用户选择旧记录。
- 本 Ticket 的文档与字段检查通过；实际场景覆盖和证据汇总由 Ticket 05 完成，不提前宣称全部验收。

### Migration / Rollback / Done When

保留历史 .scratch 文件和用户修改。旧机制迁移在 Ticket 05 执行；回滚规则时保留共享记录供诊断。Done When：保存、字段、引用、授权与恢复规则无歧义且可由现有工具执行，适用本地检查完成。

### Result / Comments

已完成；证据与结论见 `issues/01-shared-local-state-and-recovery.md`。对应 D02、D05、D13，设计修订 R01、R02、R05。

## Ticket 02：ChatBI 确认、实施和交付闭环

Status: done
Owner: 当前主 Agent
Blocked by: Ticket 01

### Change Profile

长期工程规则；中等大小；风险为重复确认、越过关键决定与过早报告完成；证据为规则核对和阶段 / 授权场景；交付为 ChatBI 流程 Contract。

### What to build

- 明确需求与关键技术澄清覆盖、完成条件、用户确认与小实验边界。
- 明确短 Spec 先留存、明确小任务指令作为实施授权；复杂目标仍经过完整 Spec、设计审查、拆分确认。
- 整体授权后连续推进；有条件通过先落实修订；关键变化重新确认。
- 验证证据绑定版本、基线和覆盖范围，按实际影响复用 / 重跑；同步正式事实源作为 Done When。
- 发布前说明默认自动合并，不新增用户 PR Review；发布授权在同目标内延续至 PR 更新、范围内修复、复盘和安全清理。
- 明确持续监控、真实中断交接、合并后复盘与清理阻塞；完整结果在聊天汇报。

### Owned files

- ChatBI：AGENTS.md 的阶段、授权、验证与交付规则。
- ChatBI：docs/agents/issue-tracker.md 的澄清、Spec、设计审查、Ticket 和授权部分。
- ChatBI：docs/agents/git-pr-workflow.md。
- ChatBI：docs/agents/agent-harness.md 的流程与 Skill 依赖说明。
- ChatBI：.github/pull_request_template.md 的实际结果与复盘记录约定。

### Acceptance criteria / Evidence

- D01、D03、D06–D15 在对应事实源中可追溯，旧的重复确认与两分钟后结束规则不与新 Contract 冲突。
- Spec 确认、Ticket 拆分、实施授权和发布授权分别表达；已明确授权的同范围动作不重复请求。
- S08–S12、S14–S16 有可执行判断标准；未授权的关键变化和实验必须暂停。
- 实施、合并、复盘、清理分别有结果，清理阻塞不等于全部 done。
- 文档检查、当前上下文 Review 与 Diff 检查通过。

### Migration / Rollback / Done When

与 Ticket 01 的状态接口保持一致；不删除历史决定和 Ticket。Done When：完整流程可从入口连续执行，所需确认点、停止条件、证据与完成报告一致。

### Result / Comments

完成；ChatBI 流程规则、PR 模板、文档链接 / Diff 检查及当前上下文 Review 结果见 `issues/02-chatbi-workflow-closure.md`。

## Ticket 03：通用 Skill 阶段调用与关键方案控制

Status: done
Owner: 当前主 Agent
Blocked by: Ticket 02

### Change Profile

长期 Plugin 规则；中等大小；风险为自动调用绕过授权或继续强制逐阶段手动调用；证据为 Skill / 元数据校验与已授权 / 未授权场景；交付为 Plugin 源的本地变更。

### What to build

- 对齐 discovery、grill、to-spec 的关键技术澄清、小实验、短 / 完整 Spec 与记录门禁。
- 对齐 design-review、to-tickets、ticket-readiness 的修订核对、草案 / 正式区分和整体授权延续。
- 对齐 implement、tdd、code-review 的范围控制、验证复用、正式事实源同步与范围外反馈。
- 阶段 Skills 可在任务和授权满足时按阶段使用；同步 policy.allow_implicit_invocation 与正文，允许调用不等于授权写入。
- ask-matt 保持可选导航，setup / Wayfinder 保留显式启动边界；专项 agent-engineering-skills 不变。

### Owned files

- Plugin 源：上述 9 个阶段 Skill 的 SKILL.md、agents/openai.yaml 和实际受影响的 references。
- Plugin 源：ask-matt 的 SKILL.md、阶段 / Readiness / 项目适配 / 交付门禁 references（只更新与新流程冲突的内容）。
- Plugin 源：engineering-workflow README 和仓库 README 的阶段调用说明。

### Acceptance criteria / Evidence

- 9 个阶段 Skill 的调用政策与确认边界一致；delivery 的对应修改由 Ticket 04 完成。
- setup、Wayfinder、导航与其他 9 个专项 Skill 的调用配置未被误改。
- 同一目标整体授权后允许连续推进；纯问答、未确认复杂 Spec、未授权实验和关键方案变化不自动进入实施。
- 使用已有 quick_validate 检查修改的 Skills；Plugin JSON 和调用元数据检查通过。专用 validator 不可用时记录未运行及替代检查，不伪称运行。
- Plugin 源检查和本地 Review 完成；本 Ticket 不直接编辑安装缓存或写远端。

### Migration / Rollback / Done When

通用 Plugin 沿用目标仓库事实源，不强加 ChatBI 路径或自动合并默认。本机同步在 Ticket 05 做。Done When：源中阶段调用与范围控制完整一致，校验通过；尚未同步的缓存明确区分。

### Result / Comments

已完成；九个目标 Skill 的 `quick_validate.py` 全部通过；YAML 检查确认恰好九个阶段 Skill 为 `allow_implicit_invocation: true`，其余四个本 Plugin Skill 为 `false`；Plugin manifest JSON 解析通过；`git diff --check` 通过。当前上下文 Code Review：PASS。源修改未提交，安装同步留到 Ticket 05。对应 D06–D10、D12–D15。

## Ticket 04：通用恢复、交付与依赖合并保护

Status: done
Owner: 当前主 Agent
Blocked by: Ticket 03

### Change Profile

长期交付规则；中等大小；风险为合并早于告知、旧事件启用合并、依赖检查或安装来源失效；证据为 PR fixture 与 Bash / 元数据检查；交付为 Plugin 源和必要的 ChatBI workflow 防护。

### What to build

- 更新 setup 与本地 tracker 参考：显式初始化仍先检查项目规则；共享状态机制按项目适配，不直接把 ChatBI 目录写成所有项目事实。
- 更新 delivery 和 CI Feedback：发布前说明自动合并，持续授权 / 监控，真实中断交接，复盘、范围外反馈、安全清理和聊天报告。
- delivery 调用元数据与 Ticket 03 的阶段约定一致；完成 README 中全部 10 个阶段 Skill 的说明。
- 依赖 PR 记录前置和最终 base，保持 Draft，切换 base 后核对最新 head 与基线证据，再转 Ready。
- 对 ChatBI Auto-merge workflow 做必要一致性防护：动作前查询实时 Draft / head / base；与过期事件冲突时不启用不满足条件的 PR。
- 明确新机器恢复、跨仓库主 / 关联记录和 marketplace 来源不能因清理失效；不自动修改远端保护设置。

### Owned files

- Plugin 源：workflow-delivery 的 SKILL.md、agents/openai.yaml、references/ci-feedback.md。
- Plugin 源：setup-engineering-workflow 的 SKILL.md、issue-tracker-local.md；必要的 README 同步。
- ChatBI：.github/workflows/enable-auto-merge.yml；docs/agents/git-pr-workflow.md 中对应依赖 / 实时检查说明。

### Acceptance criteria / Evidence

- S01、S02、S06、S13、S15、S16 可以用明确 fixture 验证持续跟进、依赖门禁和完成报告。
- PR 创建前告知；未知状态、Draft、错误 base、变动 head 或依赖未解决时不调用启用合并动作。
- 同目标已授权的范围内更新和复盘不重复询问；无发布授权不写远端。
- 模拟工具调用、YAML / Bash 检查与 Skill 校验通过，真实与模拟证据明确区分。
- 未调用直接人工 Merge，未削弱 required checks、未新增用户 PR Review。

### Migration / Rollback / Done When

保持默认独立 PR 自动合并，依赖交付受到已确认门禁保护。若远端状态不可核实保留 Draft / 分支并记录原因。Done When：项目 workflow 与 Plugin delivery / setup 的调用顺序、恢复和保护规则一致。

### Result / Comments

已完成；Plugin delivery / recovery 文档与 ChatBI Auto-merge live-state guard 已实现。十个阶段 Skill 和 setup 的快速校验、YAML / manifest、模拟 GitHub fixture、Bash 语法、Diff 与当前上下文 Review 均通过；`actionlint` / 专用 `validate_plugin.py` 不可用，替代证据详见 Ticket 04 Result。未改远端保护设置、未 Push、未创建 PR。整体场景与安装同步由 Ticket 05 验收。

## Ticket 05：整体验收、当前任务迁移与本机安装同步

Status: in-progress
Owner: 当前主 Agent
Blocked by: Ticket 04

### Change Profile

目标内验收与迁移；中等大小；风险为规则看似一致但实际不能恢复、缓存未更新或虚报真实验证；证据为 S01–S20、源 / 缓存核对和新 Thread；交付为长期验收记录与已核实的安装状态。

### What to build

- 构建隔离 Git / worktree 和模拟 PR 状态场景，逐项执行 S01–S20，保存输入、授权、动作、结果、证据类型和重现方式。
- 对关键确认边界、新会话恢复与阶段调用做适用的新 Thread 情境验收，验证实际行为，不只给模型复述规则。
- 核实支持的安装更新来源，校验源后按支持方式同步 engineering-workflow；逐文件核对源 / 缓存，并验证新 Thread 加载。
- 将本工作项实时阶段迁移到共享本机状态，当前 `.scratch/<feature>/status.md` 留作历史规划快照；保留长期 Spec / Tickets / 证据。
- 最终检查 15 项决定在正式规则中的覆盖、证据版本和用户已有修改；记录尚未验证的真实远端范围。

### Owned files

- ChatBI：docs/acceptance/harness-workflow-control.md（实际验收结果，按需创建，不生成空文档）。
- 当前工作项：issues/ 的 Result / Comments、必要的隔离 fixture 与重现记录。
- 两个仓库的当前目标共享本机状态与来源引用，不提交实时状态。
- engineering-workflow 安装缓存仅由支持的安装命令更新，不直接编辑缓存。

### Acceptance criteria / Evidence

- S01–S20 逐项给出通过、失败、未运行或阻塞及证据；必要场景未通过时不能宣称 Harness 行为完成。
- Git / worktree 共享、状态更新不污染工作区、引用存活、冲突保留和未知授权拒绝有实际动作证据。
- 源与缓存一致、新 Thread 加载及越权拒绝有可核查结果；当前 Thread 不称为热更新成功。
- 未授权的旧 PR / 真实远端写入不用于验收；模拟通过不能表述为真实 PR 已验证。
- 不运行无关 ChatBI 产品测试；若 workflow 或 fixture 有可执行变更，完成对应确定性检查。

### Migration / Rollback / Done When

迁移只处理本目标及经核实需要恢复的活动记录，不批量改旧历史，不删除其他工作线。同步失败时保留源和诊断，按支持方式恢复已知有效安装；不能通过手改缓存换取一致。

Done When：本地适用验收、Review、Diff 和安装核对完成，两个仓库形成可审阅的 candidate；报告当前目标仍待发布授权，不能将本地实施完成表述为整个交付完成。

### Result / Comments

待实施；覆盖全部决定和 S01–S20。发布阶段仍需取得明确授权，按各仓库实际保护、自动化与发布边界执行，之后持续跟进直至收尾。
