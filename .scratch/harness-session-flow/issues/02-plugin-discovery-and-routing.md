# Ticket 02：对齐 Plugin 的需求发现、澄清与路由

Status: done

## Owner

当前主 Agent。

## Blocked by

Ticket 01.

## Change Profile

- Lifetime: 长期维护的通用工程工作流。
- Size: 中；涉及新增一个 Skill 和更新现有路由说明。
- Risk: 低；不会自动调用 Skill 或修改目标仓库。
- Evidence: Skill / Plugin 格式校验和工作流情境走查。
- Delivery: `agent-plugins-codex-harness` 中 `engineering-workflow` Plugin 的本地变更；不 Push 或发布。

## What to build

- 新增 manual-only 的 `workflow-discovery` Skill，帮助用户从问题 / 机会中探索候选目标；未经用户认可，不创建实施 Spec 或进入实现。
- 更新 `workflow-grill-with-docs`，明确它处理候选目标已存在、但重要行为 / 边界 / 验收仍不清楚的需求澄清；不要求先运行 `ask-matt`。
- 更新 `ask-matt`、Plugin README 和路由描述：它是用户主动询问下一步时使用的可选路由器，能区分需求发现和需求澄清；所有 Plugin Skills 继续保持 manual-only。
- 检查 `workflow-to-tickets`、`workflow-ticket-readiness` 的说明继续使用 Ticket 作为可追踪实施工作项，并遵循目标仓库门禁。

## Acceptance criteria

- 用户尚不知道想做什么时，需求发现先讨论问题、证据、候选结果和选项；不会把探索描述成已澄清需求。
- 用户已有候选目标但存在影响结果的重要歧义时，进入需求澄清；完成条件和需求发现分别说明。
- `ask-matt` 只在用户主动请求阶段导航时路由；目标仓库 `AGENTS.md` 可独立驱动自动会话状态播报。
- 所有 Plugin Skills 仍为 manual-only；没有自动调用 Skill 或静默推进阶段的规则。
- Plugin README、Skill 路由和 Skill 正文使用一致的阶段名及 Ticket 术语。
- 变更仅涉及 `engineering-workflow`；不修改 `agent-engineering-skills`。

## Owned files

仓库：`/home/jojo/Projects/agent-plugins-codex-harness`

- `plugins/engineering-workflow/skills/ask-matt/`
- `plugins/engineering-workflow/skills/workflow-discovery/`
- `plugins/engineering-workflow/skills/workflow-grill-with-docs/`
- `plugins/engineering-workflow/README.md`
- `README.md`

## Verification evidence

- 按 Plugin 仓库 README 使用 `skill-creator` 的 `quick_validate.py` 检查新增 / 修改 Skill。
- 使用 `plugin-creator` 的 `validate_plugin.py` 检查 `engineering-workflow`。
- 走查模糊问题、候选目标待澄清、手动询问下一步三种情况。
- Plugin 源修改完成后，由 Ticket 03 负责本机安装同步与新 Thread 加载检查。

## Migration / Rollback

- 不改动本机安装缓存；本机同步属于 Ticket 03。
- 不 Push 或发布 Plugin。
- 若新 Skill 校验失败或破坏现有路由，修复或回退 Plugin 源文件。

## Done When

需求发现、需求澄清和可选阶段路由边界明确；Skill / Plugin 校验与三种流程走查完成并记录。

## Result

已在外置 Plugin 新增 manual-only `workflow-discovery`；明确其与 `workflow-grill-with-docs`（需求澄清）的职责边界。`ask-matt` 调整为可选导航器，并对齐短 Spec 直接实施、完整 Spec 进入设计审查与 Ticket 的路由。Plugin / 仓库 README 与元数据同步更新，Ticket / Readiness 中 Ticket 术语检查通过。

- Plugin commit：`695fa88 docs(workflow): 区分需求发现与澄清`（本地提交，未 Push）。
- `quick_validate.py`：新 Skill、`ask-matt`、`workflow-grill-with-docs` 均通过。
- 自检：Plugin JSON 可解析；13 个 Skill 名称与目录匹配且均为 `allow_implicit_invocation: false`；`git diff --check` 通过；三类流程场景走查通过。
- 限制：本机未找到 README 所述 `validate_plugin.py`，因此使用 JSON / Skill 元数据检查代替该 Plugin 专用 validator。

## Comments

Ticket 01 已完成；开始按依赖顺序处理本 Ticket。
