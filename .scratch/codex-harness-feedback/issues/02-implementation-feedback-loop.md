# 02: 为通用实施 Skill 补全修复与工程反馈闭环

**Change Profile:** 更新既有个人 `engineering-workflow` Plugin Skill；不新增 Skill。

**Owner:** Codex

**Blocked by:**

None (can start immediately)

**Status:** done

## What to build

改进个人 `agent-plugins` 仓库中的 `plugins/engineering-workflow/skills/workflow-implement/SKILL.md`，使 Codex 在已确认的 Contract 和范围内执行改动、验证、依据反馈修复，并在任务结束时识别有证据的 Harness 改进机会。

- 按仓库规则选择与改动风险相符的验证；运行后阅读实际失败输出，继续定位和修复本次范围内的问题，并重跑失败项及受影响的回归验证。
- 只有验证通过，或遇到清楚说明且无法在当前范围内解除的阻塞时，才能结束任务。报告需区分通过、失败、未运行和被阻塞的验证，不得把局部通过说成整体通过。
- 保护用户已有修改并遵守项目规定的 Contract、风险、授权和交付门禁；不得因修复验证失败而擅自扩大范围。
- 任务结束时，仅在问题重复出现或一次但有明确证据的结构性缺口时提出 Harness 改进建议；没有足够证据时明确报告未观察到符合门槛的缺口。
- 每条建议至少说明：缺口类别（上下文、事实源、工具、测试、反馈、架构约束、可观测性之一）、任务证据、建议沉淀位置 / 机制（如 AGENTS、docs、test、lint、CI、Skill、script 或 observability）、以及它如何降低同类问题复发或改善下次验证。Harness / Skill / Contract 等持久规则的修改须先由用户决定是否采纳。

保留现有 Skill 的实现职责和与测试、Code Review、Delivery Skill 的交接，不新增重复流程或自动自改规则机制。

## Acceptance criteria

- [ ] 实施流程明确包含“运行适用验证 → 读取失败反馈 → 定位并修复 → 重跑相关验证”的闭环。
- [ ] 未通过或未执行的验证会被如实报告；阻塞结束时说明证据、影响和所需下一步。
- [ ] 修复始终限定于已确认 Scope，且验证范围随行为改动重新判断。
- [ ] 任务结束报告使用已确认的七类缺口分类，包含证据、持久化位置 / 机制与预期复发改善；证据不足时明确报告没有符合门槛的建议。
- [ ] Codex 不会仅凭偶发偏好或无证据猜测自动修改 Harness，也不会绕过用户决定直接修改持久规则。
- [ ] 原有安全、分支、PR、Real E2E 和高风险验证授权规则仍由项目规则与现有交接控制。

## Owned files

- `agent-plugins` 个人工作仓库：`plugins/engineering-workflow/skills/workflow-implement/SKILL.md`
- 本仓库：本 Ticket 的 `Result` 与 `Comments`（完成后记录证据）

开始修改前确认 `agent-plugins` 的可编辑工作副本、Git 根目录、当前分支和工作区状态；保留已有本地修改。不得编辑 Codex 安装缓存或 Marketplace 临时副本。如果找不到安全的可编辑工作副本，则停止本 Ticket 并报告阻塞原因。

## Validation / Evidence

- 对更新后的 Skill 做流程和项目门禁边界审查，并走读一个“测试失败后可修复并通过”的场景及一个“当前环境无法解除阻塞”的场景，确认两者都能给出正确终态和验证报告。
- 走读任务结束反馈：分别检查一个有明确结构性缺口、一个重复问题和一个偶发但无证据的问题，确认建议门槛、类别、证据、沉淀位置和用户决策要求符合本 Ticket。
- 检查 Plugin 仓库中是否已有适用的 Skill 校验命令；若存在则运行并记录结果。若没有适用的自动检查，不为形式新建脚本或测试。
- 在 Ticket `Result` 中记录实际校验方式、结果和未覆盖项；没有运行的检查不得记为通过。

## Migration / Rollback

无需数据迁移。回滚时只撤销本 Ticket 在上述 Skill 文件中的改动，保留其他已有工作区修改。

## Done When

- 验收标准全部满足，适用的 Plugin 校验和场景走读结果已记录。
- 若验证发现不合格，已修正并重新执行受影响的验证；无法完成时将状态置为 `blocked` 并记录具体原因。

## Result

已完成。`workflow-implement` 明确要求按目标仓库风险选择验证；失败后读取输出、定位并在 Scope 内修复，再重跑失败项和受影响的回归。遇到 Contract / 架构关键决策或外部环境阻塞时有明确停点，报告逐项区分通过、失败、未运行和阻塞。

验证与 Review：

- `python3 /home/jojo/.codex/skills/.system/skill-creator/scripts/quick_validate.py plugins/engineering-workflow/skills/workflow-implement`：通过。
- `git diff --check`：通过。
- 失败修复走读：验证失败后根据输出分类并修复，在原范围内重跑失败和受影响检查；Contract 不明确时返回设计 / 澄清阶段。
- 外部依赖阻塞走读：记录阻塞与影响，继续可执行的独立检查，报告中不虚报通过。
- Harness 反馈走读：结构性缺口和重复问题要求列出证据、类别、建议落点及预期作用；一次性无证据问题不触发建议；已有 Ticket 覆盖的问题不重复登记。
- `workflow-code-review`：PASS；验证和反馈边界保持在既有项目授权内。
- 本地 Commit：`26bbac4 docs(engineering-workflow): 增加验证修复和反馈闭环`；未 Push。

未覆盖：本 Ticket 没有引入自动 Skill 行为 Evaluation；该行为将在后续真实项目需求中继续观察。

## Comments

- 这是个人通用 Skill 的本地改进；本 Ticket 不授权云端同步、Push 或发布。
- Harness 改进提议属于任务后的证据反馈，不代表授权 Codex 在同一任务中自行扩大范围并修改 Harness。
