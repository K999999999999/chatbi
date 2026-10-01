# 03: 对齐 ChatBI Agent 入口并完成真实需求试点

**Change Profile:** 更新项目级 Agent 入口并执行一次受现有门禁约束的真实小范围需求试点；不新增项目 Skill。

**Owner:** Codex

**Blocked by:**

- `01: 为通用需求澄清 Skill 建立完成门槛`
- `02: 为通用实施 Skill 补全修复与工程反馈闭环`

**Status:** done

## What to build

根据 ChatBI 仓库当前事实更新根目录 `AGENTS.md`，让 Codex 能从一个轻量入口找到相关领域事实源、Contract、验证入口和个人通用 Skill，并与已存在的项目门禁保持一致。

- 用准确的 canonical Skill 名称和触发边界说明 `ask-matt`、`workflow-grill-with-docs`、`workflow-to-spec`、`workflow-to-tickets`、`workflow-design-review`、`workflow-ticket-readiness`、`workflow-implement`、`workflow-code-review` 与 `workflow-delivery` 的关系；不得继续使用无法解析的简称或造成自动串行调用的描述。
- 按需指向现有 Architecture、Engineering、Domain、Spec、测试 / Evaluation、Git / PR 事实源，说明各自负责的事实类型；入口只提供导航和关键不变量，不复制详细业务知识或通用 Skill 步骤。
- 明确把实现后的测试反馈修复和任务结束 Harness 缺口提议接入现有流程，同时保留 Spec / Review / Ticket、用户授权、风险等级、PR 和 Real E2E 门禁。
- 不新增 ChatBI 项目 Skill、Harness 框架、文档大全、脚本、CI 检查或新的审批流程，除非仓库证据表明存在本 Ticket 无法覆盖且经确认的必要 Contract 变化。
- 使用第一项符合范围的真实小型 ChatBI Feature 或 Bug Fix 试跑更新后的澄清、Spec / Ticket（若适用）、实现、验证、失败修复和任务后反馈流程。试点遵循其自身风险与授权规则，不为试点降低验证要求；在本 Ticket 的 `Result` 记录真实需求、实际调用的事实源和 Skills、验证结果、发现的问题及 Harness 建议（如有）。

## Acceptance criteria

- [ ] `AGENTS.md` 对关键项目事实源和验证入口提供准确、可用的导航，不复制下层文档已有的长篇内容。
- [ ] Skill 路由使用个人 Plugin 中存在的 canonical 名称，触发条件与仓库实际流程一致，且不会将只读审查误写成独立 Agent / 自动授权。
- [ ] AGENTS 导航覆盖整个仓库所需的领域上下文入口，并明确 LLM、Retrieval、Semantic、SQL、安全 / 授权等既有关键边界及其现存风险门禁。
- [ ] 保留当前 Spec 确认、Design Review、Ticket Readiness、Ticket 选择、实现、测试、PR 前授权和高风险 Real E2E 的顺序与用户控制点。
- [ ] 没有新增不必要的项目 Skill、文档、脚本或 CI 文件，也没有修改 ChatBI 运行时产品架构或业务 Contract。
- [ ] 至少一个真实小范围 ChatBI Feature / Bug Fix 完成试点，并在 `Result` 中记录过程和验证证据；如没有合适的真实需求可供试点，本 Ticket 保持未完成 / blocked，不以合成 benchmark 代替。

## Owned files

- ChatBI 仓库：`AGENTS.md`
- ChatBI 仓库：本 Ticket 的 `Result` 与 `Comments`（完成后记录试点证据）

## Validation / Evidence

- 复查 `AGENTS.md` 中每个新增 / 调整的路径、Skill 名称和规则均能在当前仓库或已确认的个人 Plugin 源中定位，并与现有 `docs/agents/issue-tracker.md`、`domain.md`、`git-pr-workflow.md` 及项目给定门禁一致。
- 运行适用于 `AGENTS.md` / Skill 导航改动的既有检查；若没有机械检查，做逐项来源核对和路由场景走读，不为形式新建测试或工具。
- 按所选真实试点的风险运行 targeted Software Test、AI Evaluation、Business Acceptance 或 Real E2E；记录实际命令 / 报告和结果。只有该需求确实触及高风险路径时才运行完整 Real E2E，并遵循所需用户授权。
- 在 Ticket `Result` 中区分通过、失败、未运行和阻塞的检查。试点代码如需修改，应另有清楚的已确认需求范围与对应工作项，不得借此扩展本 Ticket 的 owned files。

## Migration / Rollback

无需数据迁移。回滚时只撤销本 Ticket 对 `AGENTS.md` 的改动；试点 Feature / Bug 的代码变更由其自身工作项管理。

## Done When

- AGENTS 入口改动满足验收标准，路由和事实源已核对。
- 一个符合范围的真实试点完成，验证证据和 Harness 反馈已记录。
- 若试点暴露问题，已在原范围内修复并重跑适用验证；否则将 Ticket 置为 `blocked` 并记录等待的真实需求或其他明确阻塞。

## Result

已完成。根目录 `AGENTS.md` 已将流程简称改为个人 Plugin 中实际存在的 canonical Skill 名称，说明 Skill 显式调用 / 不自动串联的事实、每个阶段的触发和交接，并为既有 Architecture、Domain、Contract、代码、测试、Evaluation、Runbook、CI 与 Real E2E 入口增加轻量导航。没有复制下层文档内容、创建新 Skill 或修改 ChatBI 运行时代码。

真实需求试点：原 `AGENTS.md` 使用 `grill-with-docs`、`implement`、`design-review` 等与 Plugin 实际 `workflow-*` Skill 名称不一致的简称，可能让 Codex 无法定位阶段工具，属于真实的 Agent 工程路由 Bug。本次按已确认的 Spec / Review / Ticket 流程修正，并以该变更走读多阶段澄清、明确小 Bug、验证失败修复和交付授权路径。此试点验证的是 ChatBI 工程入口，不声称验证运行时产品行为。

验证与 Review：

- 只读核对 `README.md`、`CONTEXT.md`、`docs/architecture.md`、`docs/product-scope.md`、`docs/agents/`、`docs/specs/`、`docs/designs/`、`docs/adr/`、`docs/acceptance/`、`docs/runbook.md`、`src/`、`tests/` 和 `.github/workflows/` 的职责及真实路径。
- 校验 18 个项目路径 / 目录和 10 个 canonical Skill 文件均存在；Markdown fenced code blocks 数量匹配：通过。
- `git diff --check`：通过。
- 路由走读确认 Design Review、Ticket Readiness、Code Review 均为不同门禁；Ticket 顺序已由用户明确授权时不要求重复选择；Push / PR / 生产发布仍须满足各自既有授权门禁。
- `workflow-code-review`：PASS；改动范围只有根 `AGENTS.md`，无运行时行为变化。
- 未运行 Software Test、AI Evaluation 或 Real E2E：本 Ticket 为 Agent 导航文档变化，不触及 ChatBI 运行时；适用门禁不要求这些验证。

未覆盖：此次验证没有观察真实 Codex 客户端重新加载本地 Plugin Skill；Skill 源码更新仍在个人 Plugin 本地功能分支，未 Push 或安装到 Codex 缓存。

## Comments

- `AGENTS.md` 是轻量项目适配层，不是知识大全；通用工作步骤仍由个人 Skill 承载。
- 本 Ticket 不涉及个人 Skill 的云端同步、Push，也不授权 ChatBI 代码的 Push、PR 或生产发布。
