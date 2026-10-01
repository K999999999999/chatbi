# 01: 为通用需求澄清 Skill 建立完成门槛

**Change Profile:** 更新既有个人 `engineering-workflow` Plugin Skill；不新增 Skill。

**Owner:** Codex

**Blocked by:**

None (can start immediately)

**Status:** done

## What to build

改进个人 `agent-plugins` 仓库中的 `plugins/engineering-workflow/skills/workflow-grill-with-docs/SKILL.md`，让澄清依据当前仓库事实开展，并有明确、可检查的结束条件。

- 先查找与需求相关的代码、事实源、Contract 和验证入口；清楚区分仓库已确认事实、用户决定、假设与未知信息。
- 根据需求影响检查目标、可观察行为、成功与失败情形、范围、关键边界和验收方式。只有可能改变需求结果的问题才需要继续追问；不要求每次机械遍历无关清单。
- 每轮只问一个最关键的问题。得到回答后继续判断是否还有会改变目标、行为、范围、架构 / 安全约束或验收方式的未决问题，不因用户回答了一个问题就自动结束。
- 只有上述重要问题均已解决，或用户明确接受的剩余假设已标明且不改变关键 Contract，才可结束澄清。影响关键 Contract 的决定不得伪装成实施阶段细节。
- 结束时汇总已确认决定、显式假设、仍未解决且会阻塞的事项，以及可以留给 Ticket / 实施阶段按 Contract 决定的细节；随后按现有流程交接到 Spec、Ticket 或小范围实施。

保留现有 `ask-matt`、`workflow-to-spec` 和其他 Skill 的职责边界，不把 ChatBI 项目知识复制进通用 Skill。

## Acceptance criteria

- [ ] 需求澄清有明确的完成门槛，并覆盖目标、行为、范围、关键约束和验收中与当前需求相关的部分。
- [ ] 澄清流程会用仓库证据减少重复提问，并标明事实、决定、假设和未知信息。
- [ ] 对可能改变需求结果的未决问题不会提前结束；问题已回答后仍会检查是否还有其他重要缺口。
- [ ] 每轮只提出一个最关键问题；结束摘要能区分阻塞事项与可留给实施阶段的选择。
- [ ] 未引入 ChatBI 专属知识、新 Skill、重复的 Spec / Ticket 工作流或必答但不相关的固定问卷。

## Owned files

- `agent-plugins` 个人工作仓库：`plugins/engineering-workflow/skills/workflow-grill-with-docs/SKILL.md`
- 本仓库：本 Ticket 的 `Result` 与 `Comments`（完成后记录证据）

开始修改前确认 `agent-plugins` 的可编辑工作副本、Git 根目录、当前分支和工作区状态；保留已有本地修改。不得编辑 Codex 安装缓存或 Marketplace 临时副本。如果找不到安全的可编辑工作副本，则停止本 Ticket 并报告阻塞原因。

## Validation / Evidence

- 对更新后的 Skill 做职责边界和内容审查，并按 `ask-matt` / `workflow-to-spec` 的既有交接走读一个信息不足的需求和一个边界清楚的小 Bug，确认前者会继续询问关键缺口、后者不会被无关问题拖住。
- 检查 Plugin 仓库中是否已有适用的 Skill 校验命令；若存在则运行并记录结果。若没有适用的自动检查，不为形式新建脚本或测试。
- 在 Ticket `Result` 中记录使用的校验方式、实际结果和未覆盖项；没有运行的检查不得记为通过。

## Migration / Rollback

无需数据迁移。回滚时只撤销本 Ticket 在上述 Skill 文件中的改动，保留其他已有工作区修改。

## Done When

- 验收标准全部满足，适用的 Plugin 校验和场景走读结果已记录。
- 若验证发现不合格，已修正并重新执行受影响的验证；无法完成时将状态置为 `blocked` 并记录具体原因。

## Result

已完成。`workflow-grill-with-docs` 现在先以目标仓库事实建立底稿，再逐项标记相关维度；每轮回答后重新检查未决项。会改变目标、行为、范围、关键边界或验收的问题必须继续澄清，用户要求暂缓时标记阻塞；只有不改变 Contract 的实现细节才可留给 Ticket / 实施阶段。

验证与 Review：

- `python3 /home/jojo/.codex/skills/.system/skill-creator/scripts/quick_validate.py /home/jojo/Projects/agent-plugins-codex-harness/plugins/engineering-workflow/skills/workflow-grill-with-docs`：通过。
- `git diff --check`：通过。
- 信息不足需求走读：缺目标 / 场景等关键事实时继续单问，并在回答后重新检查其他相关维度。
- 边界清楚的小 Bug 走读：从代码和测试填入已知事实，不问无关边界问题。
- `workflow-code-review`：PASS；范围仅为本 Ticket 的 Skill 文件，无发现。
- 本地 Commit：`20b5840 docs(engineering-workflow): 完善需求澄清完成门槛`；未 Push。

未覆盖：真实用户后续运行的行为仍需观察；本 Ticket 未增加脚本或自动化问答 Evaluation。

## Comments

- 这是个人通用 Skill 的本地改进；本 Ticket 不授权云端同步、Push 或发布。
- Spec Design Review 的 `PASS WITH MINOR FIXES` 要求任务结束时的 Harness 改进建议包含证据和明确去向，相关细节在 Ticket 02 实施。
