# Ticket 拆分草案（已确认；正式 Ticket 为当前事实源）

Spec: `spec.md`（用户已确认；Design Review: `PASS WITH MINOR FIXES`）

正式 Ticket：`issues/01-chatbi-session-entry-and-resume.md`、`issues/02-plugin-discovery-and-routing.md`、`issues/03-project-setup-and-spec-sizing.md`。

## Ticket 01：建立 ChatBI 会话入口与工作进度恢复规则

**Change Profile**：Lifetime: 长期；Size: 中；Risk: 低（仓库协作规则与 Markdown）；Evidence: 文档检查、阶段场景走查；Delivery: ChatBI Harness 文档变更。

**Owner**：当前主 Agent。

**Blocked by**：None (can start immediately)

**What to build**：

- 在 `AGENTS.md` 定义新会话入口检查和首条状态播报；该逻辑不依赖手动调用 Skill。
- 在 `docs/agents/issue-tracker.md` 定义工作阶段、短 / 完整 Spec 分流，以及 `.scratch/<slug>/status.md` 的字段和更新时机。
- 工作状态记录关联分支 / worktree；按当前分支 / worktree 唯一匹配活动记录。无匹配或多匹配时列出候选并询问，不猜测。
- 定义未提交改动的检查与处理：先报告、核对归属；未归属改动未解决前不开始新的写入，不自动清理或挪动内容。
- 在 `docs/agents/git-pr-workflow.md` 和 `docs/agents/agent-harness.md` 对齐 PR 检查、合并后 Harness 复盘、会话恢复和 Skill 边界说明；同步更新 PR 模板。
- 对没有 `status.md` 的历史活动工作，定义按需恢复时补建记录的规则；不批量改写已完成历史记录。

**Acceptance Criteria**：

- 新会话首个工程响应说明阶段、工作项、工作区、上次停点和下一步；只读咨询明确标成只读。
- 状态记录能区分需求发现、需求澄清、Spec 待确认、待拆 Ticket、待实施、实施中、验证 / Review、PR 检查中、已合并待 Harness 复盘、完成和等待用户决定。
- 当前分支 / worktree 与状态记录匹配唯一时能恢复；匹配失败或不唯一时明确报告并询问。
- 有未提交改动时先报告并判断归属；不明确时停止新的写入，不自动 stash、reset、commit 或覆盖。
- 小型实施项有短 Spec；复杂实施项需确认完整 Spec 并完成设计审查和 Ticket readiness 后再由用户确认拆分。
- 需求发现与需求澄清可以由仓库 `AGENTS.md` 指导 Agent 直接开展，不依赖 Plugin Skill 自动调用。
- PR 已合并后记录复盘结论；没有缺口时记录“无新增缺口”，有缺口时建立独立 Harness 改进项。

**Owned files**：`AGENTS.md`、`docs/agents/issue-tracker.md`、`docs/agents/git-pr-workflow.md`、`docs/agents/agent-harness.md`、`.github/pull_request_template.md`。

**Verification Evidence**：检查 Skill 名称和本地 Markdown 链接；逐项走查干净工作区、当前工作未提交修改、无关未提交修改、零 / 多条活动记录、需求发现、Spec 待确认、待实施、PR 检查中和合并后复盘情境。

**Migration / Rollback**：不迁移或重命名历史 Ticket 文件。若会话入口规则使合法恢复被阻止，修订规则并保留原工作记录；不通过自动清理绕过阻塞。

**Done When**：上述状态和工作区情境均有可观察的规则与检查结果，所有被修改的仓库入口文档彼此一致。

## Ticket 02：对齐 engineering-workflow Plugin 的需求阶段与 Spec 能力

**Change Profile**：Lifetime: 长期；Size: 中；Risk: 低（Skills 和 Plugin 文档）；Evidence: Skill / Plugin 结构验证、工作流场景走查、当前安装缓存同步检查；Delivery: 独立 Plugin 源仓库本地变更，并按支持方式更新当前本机安装，不 Push / 发布。

**Owner**：当前主 Agent。

**Blocked by**：Ticket 01。

**What to build**：

- 新增 manual-only 的 `workflow-discovery` Skill，帮助用户从问题 / 机会探索出候选目标；未得到用户认可的目标前，不创建实施 Spec 或进入实现。
- 更新 `workflow-grill-with-docs`，明确它处理候选目标已有但关键行为 / 边界 / 验收仍不清楚的需求澄清，不要求先运行 `ask-matt`。
- 更新 `ask-matt`、Plugin README 和路由描述：它是用户主动请求时使用的可选路由器；能区分需求发现和需求澄清；保持所有 Skills manual-only。
- 检查 `workflow-to-tickets`、`workflow-ticket-readiness` 和相关说明继续使用 Ticket 表示实施工作项，并遵守目标仓库的 Spec / Ticket 确认门禁。

**Acceptance Criteria**：

- 用户不知道想要什么时，需求发现流程先讨论问题、证据、候选结果和选项；不会把探索冒充已澄清需求。
- 用户已有候选目标但仍有改变结果的重要歧义时，进入需求澄清；完成条件和发现阶段分开描述。
- Plugin 所有 Skill 仍为 manual-only；自动会话状态播报只由目标仓库 Agent instructions 承担。
- Plugin README、Skill 路由表和 Skill 正文使用一致的阶段名和准确的 Ticket 术语。
- 变更范围限于 `engineering-workflow` Plugin；不改动 `agent-engineering-skills`。

**Owned files**：`agent-plugins-codex-harness` 仓库中 `plugins/engineering-workflow/skills/ask-matt/`、`workflow-discovery/`、`workflow-grill-with-docs/`、`plugins/engineering-workflow/README.md`、仓库 `README.md`。

**Verification Evidence**：使用仓库说明的 `skill-creator` `quick_validate.py` 检查新增 / 修改 Skill；用 `plugin-creator` `validate_plugin.py` 检查 `engineering-workflow`；走查“模糊痛点”“目标未决歧义”“手动路由”三种请求。

**Migration / Rollback**：不改动安装缓存，不 Push 或发布。若新增 Skill 未通过 Plugin 验证或现有路由被破坏，修复或回退源文件。

**Done When**：需求发现、需求澄清和可选路由的边界可区分，Plugin 与目标仓库规则兼容，校验和场景走查有记录。

## Ticket 03：让新项目初始化和 Spec 流程采用会话约定

**Change Profile**：Lifetime: 长期；Size: 小；Risk: 低（Skill 说明和工作流约定）；Evidence: Skill / Plugin 结构验证、设置流程与短 / 完整 Spec 场景走查；Delivery: 依赖 Ticket 02，在 Plugin 源仓库本地交付。

**Owner**：当前主 Agent。

**Blocked by**：Ticket 02。

**What to build**：

- 更新 `setup-engineering-workflow`：说明安装 Plugin 不会改变目标仓库；用户显式初始化时，将会话入口、阶段识别和恢复规则作为项目适配建议，经现状检查和用户确认后再写入。
- 更新 `workflow-to-spec` 支持短 Spec 与完整 Spec 两种产物，保存格式和路径仍由目标仓库决定。
- 在 Plugin README 中说明新项目需显式运行初始化 Skill 并确认项目规则；Skill 保持 manual-only。
- 完成 Plugin 源修改后，按 Codex 支持的方式更新当前安装，核对源仓库与安装缓存一致；不直接编辑缓存。

**Acceptance Criteria**：

- 用户只安装 Plugin 时，不宣称目标仓库已获得自动会话入口；显式初始化时先检查事实源，再提出精确文件修改建议并等待确认。
- 初始化后的目标仓库规则可在不调用 Skill 的情况下，于新会话执行阶段播报与恢复检查。
- 短 Spec 聚焦目标、结果、验收和验证；完整 Spec 保留多阶段需求需要的边界、行为和设计依据，不要求小任务填满模板。
- 当前安装缓存与 Plugin 源一致；安装后在新 Thread 可以发现新增需求发现 Skill，且所有 Skill 仍为 manual-only。

**Owned files**：`agent-plugins-codex-harness` 仓库中 `plugins/engineering-workflow/skills/setup-engineering-workflow/`、`workflow-to-spec/`、`plugins/engineering-workflow/README.md`；本机 `engineering-workflow` 安装缓存仅通过支持的 Plugin 更新命令更新。

**Verification Evidence**：使用 `skill-creator` `quick_validate.py` 和 `plugin-creator` `validate_plugin.py`；走查“只安装”“显式初始化并确认”“短 Spec”“复杂 Spec”情境；核对安装缓存与源内容一致。新 Thread 的交互结果如当前环境无法独立启动，则明确标记为待用户会话验收。

**Migration / Rollback**：本地安装更新不 Push 或发布；若缓存同步或 Skill 加载异常，通过 Codex 支持的 Plugin 更新机制恢复到上一个有效源版本。

**Done When**：新项目初始化边界和两种 Spec 粒度清楚，验证记录齐全，缓存同步结果可核对。

## 拆分依赖

- Ticket 01 定义 ChatBI 的状态记录与阶段语义。
- Ticket 02 依赖 Ticket 01 已确认的发现 / 澄清阶段和 Ticket 边界，再修改通用 Plugin。
- Ticket 03 依赖 Ticket 02，统一 Plugin 的初始化、Spec 和 README 说明并同步当前本机安装。
