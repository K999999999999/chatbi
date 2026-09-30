# Ticket 01：建立 ChatBI 会话入口与工作进度恢复规则

Status: done

## Owner

当前主 Agent。

## Blocked by

None (can start immediately)

## Change Profile

- Lifetime: 长期维护的仓库工作流约定。
- Size: 中；涉及多份 Harness 文档，不涉及产品代码。
- Risk: 低；风险集中在阶段状态不清和未提交改动归属判断。
- Evidence: 文档链接 / 名称检查和工作流情境走查。
- Delivery: ChatBI Harness 文档变更；遵守 Git / PR 规则。

## What to build

- 在 `AGENTS.md` 定义每个新会话的仓库入口检查和状态播报；自动判断不依赖手动调用 Skill。
- 在 `docs/agents/issue-tracker.md` 定义工作阶段、短 / 完整 Spec 分流，以及 `.scratch/<slug>/status.md` 的字段、生命周期和更新时机。
- 状态记录关联当前分支 / worktree。新会话按分支 / worktree 唯一匹配活动记录；零匹配或多匹配时列出候选并请用户选择，不根据旧聊天或目录名猜测。
- 定义未提交改动处理：先报告并核对归属；归属不明或属于其他工作项时，暂停新的写入操作并由用户决定。不得自动 stash、reset、checkout、commit、覆盖或移动改动。
- 定义旧活动工作没有 `status.md` 时，在恢复该工作时补建记录；不批量改写已完成历史记录。
- 在 `docs/agents/git-pr-workflow.md` 与 `docs/agents/agent-harness.md` 对齐会话恢复、PR 检查、合并后 Harness 复盘和 Plugin / Skill 边界；同步 PR 模板。

## Acceptance criteria

- 新会话的首个工程响应包含阶段、工作项、工作区状态、上次停点和下一步；只读咨询标为只读咨询。
- 阶段能区分需求发现、需求澄清、Spec 待确认、待拆 Ticket、待实施、实施中、验证 / Review、PR 检查中、已合并待 Harness 复盘、完成和等待用户决定。
- 只有唯一匹配当前分支 / worktree 的活动记录时才自动恢复；无匹配或多匹配时报告并询问。
- 工作区不干净时先列出改动并判断归属；无法确认时暂停新的写入，且不丢失、覆盖或混入改动。
- 小型工程改动可使用短 Spec 并直接实施；复杂改动遵循 Spec 确认、设计审查、Ticket 草案与 readiness、用户确认拆分后实施。
- 需求发现与需求澄清由项目规则区分，不依赖 Plugin Skill 自动调用。
- 对仓库外或本机 Plugin 状态的断言必须有当前配置 / 文件证据；证据不足时标为未确认。
- PR 合并后记录 Harness 复盘；无缺口时记录“无新增缺口”，有缺口时创建独立 Harness 改进项。

## Owned files

- `AGENTS.md`
- `docs/agents/issue-tracker.md`
- `docs/agents/git-pr-workflow.md`
- `docs/agents/agent-harness.md`
- `.github/pull_request_template.md`

## Verification evidence

- 检查修改文档中的 Skill 名称、相对链接和阶段术语。
- 走查干净工作区、当前工作未提交改动、无关未提交改动、无活动记录、唯一匹配、多条候选、需求发现、Spec 待确认、待实施、PR 检查和合并后复盘场景。
- 未运行 ChatBI 产品测试；本 Ticket 不修改产品行为或可执行代码。

## Migration / Rollback

- 不迁移或重命名历史 Ticket 文件。
- 旧活动工作按需补状态记录；已完成历史工作不批量改写。
- 若新规则阻止合法恢复，修订规则并保留原工作记录；不通过自动清理绕过冲突。

## Done When

新会话状态播报、工作项恢复和改动归属规则均可从仓库文档直接执行；上述情境走查完成，Harness 文档彼此一致。

## Result

已更新会话入口、阶段恢复、短 / 完整 Spec 门禁、PR 合并后 Harness 复盘及 PR 模板。`git diff --check` 通过；`python3 scripts/check_markdown_links.py --root .` 通过。未运行 ChatBI 产品测试，因为本 Ticket 仅修改文档。

## Comments

Implementation baseline: `c78cf06c3c37339720f32990ebdca9ea8e7a34a7`.
Initial Git state: current worktree clean except for the active `.scratch/harness-session-flow/` work records.
