# Ticket 03：让新项目初始化和 Spec 流程采用会话约定

Status: done

## Owner

当前主 Agent。

## Blocked by

Ticket 02.

## Change Profile

- Lifetime: 长期维护的通用工程工作流。
- Size: 中；涉及初始化 Skill、Spec Skill、Plugin 说明和当前安装同步。
- Risk: 低；不自动更改其他项目仓库，不 Push 或发布。
- Evidence: Skill / Plugin 格式校验、流程走查、源仓库与当前安装缓存一致性。
- Delivery: `agent-plugins-codex-harness` 的本地源变更，并通过 Codex 支持方式更新当前本机 Plugin 安装。

## What to build

- 更新 `setup-engineering-workflow`：说明安装 Plugin 不会改变目标仓库。用户显式初始化时，将新会话入口、阶段识别和恢复规则作为适配建议；先检查仓库现状，得到用户确认后再写入项目规则。
- 更新 `workflow-to-spec` 支持短 Spec 与完整 Spec；存储格式和路径仍由目标仓库决定。
- 在 Plugin README 说明：新项目需显式运行初始化 Skill 并确认项目规则后，才会有自动会话入口。
- 源文件验证通过后，使用 Codex 支持的方式同步当前本机安装；不手工编辑缓存。

## Acceptance criteria

- 仅安装 Plugin 时，不声称目标仓库已获得新会话规则。
- 初始化 Skill 先读取目标仓库事实源，说明准确的拟修改文件和理由，等待用户确认后再写入。
- 写入项目的 Agent instructions 后，即使不调用 Skill，也能依据项目规则执行阶段识别、状态播报和工作恢复。
- 短 Spec 聚焦目标、预期结果、验收和验证；完整 Spec 覆盖复杂需求所需的边界、行为和设计依据，不要求小任务机械填满模板。
- 当前安装缓存与 Plugin 源一致；在新 Thread 中可发现 `workflow-discovery`，Skill 仍为 manual-only。

## Owned files

仓库：`/home/jojo/Projects/agent-plugins-codex-harness`

- `plugins/engineering-workflow/skills/setup-engineering-workflow/`
- `plugins/engineering-workflow/skills/workflow-to-spec/`
- `plugins/engineering-workflow/README.md`

本机 `engineering-workflow` 安装缓存仅可通过 Codex 支持的 Plugin 更新方式更新。

## Verification evidence

- 按 Plugin 仓库 README 使用 `skill-creator` 的 `quick_validate.py` 检查修改 Skill。
- 使用 `plugin-creator` 的 `validate_plugin.py` 检查 Plugin。
- 走查“只安装 Plugin”“显式初始化并确认”“短 Spec”“复杂 Spec”四种情境。
- 核对缓存与源仓库一致，并在新 Thread 检查新增 Skill 可见；若当前 Agent 无法自行启动新 Thread，明确记录为待用户会话验收。

## Migration / Rollback

- 当前本机安装仅在源仓库校验通过后同步；不 Push 或发布。
- 若缓存同步或 Skill 加载失败，通过 Codex 支持的更新方式恢复上一个有效安装；不手工修改缓存文件。

## Done When

新项目初始化边界和 Spec 粒度清楚；Skill / Plugin 校验、场景走查和可执行的安装同步核对有记录。无法在当前 Agent 会话验证的新 Thread 行为明确标记待用户验收。

## Result

更新了外置 Plugin 的 `setup-engineering-workflow`、`workflow-to-spec` 和 Plugin README：安装 Plugin 不会改动项目；显式初始化时先检查项目现状、提出具体文件方案并等待用户确认；短 Spec 至少记录目标、预期结果、验收和验证，确认后可直接实施；复杂工作使用完整 Spec，并进入设计审查和 Ticket 门禁。

- Plugin commit：`2b0bf46 docs(workflow): 补齐仓库初始化与短规格流程`（本地提交，未 Push）。
- `quick_validate.py`：两个修改过的 Skill 均通过。
- Plugin JSON 可解析；13 个 Skill 名称与目录匹配且均为 `allow_implicit_invocation: false`；`git diff --check` 通过。
- 使用 `codex plugin remove engineering-workflow@personal` 和 `codex plugin add engineering-workflow@personal` 同步缓存；Codex CLI 报告安装成功且 Plugin 仍启用。源目录与缓存 `diff -qr` 无差异；缓存含 13 个 Skill 并包含 `workflow-discovery`。
- 限制：本机没有 README 所述 `validate_plugin.py`；本会话无法启动新 Thread 检验 Skill 对话加载，需在下次新 Thread 确认可见性。

## Comments

None.
