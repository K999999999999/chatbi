# Agent Harness Engineering 项目说明

本仓库采用 Harness Engineering 思路维护 AI Coding Agent 的项目工作环境。这样，后续进入仓库的 AI 不必依赖之前的对话，也能发现项目规则、事实源、验证方式和交付流程。

这里的 Harness 指围绕编码代理组织的仓库知识、工作规则、工具依赖和结果反馈。它是项目协作方式的说明，不是 ChatBI 产品功能的行为 Contract，也不取代下面列出的事实源。

## 从哪里开始

`AGENTS.md` 是本仓库规定的 AI 工作入口，也是项目稳定规则的精简索引。AI 进入仓库后应先读它，再按当前任务读取对应的架构、产品、领域、Spec、验证和交付文档。本文用于解释 Harness 的组成和文档边界；如果本文与 `AGENTS.md` 或对应的事实源不一致，以事实源为准。

## Harness 由什么组成

| 组成 | 仓库位置 | 用途 |
| --- | --- | --- |
| 项目入口与稳定边界 | `AGENTS.md` | 告诉 Agent 应遵循的核心原则和下一步读取位置 |
| 架构、产品与行为事实 | `docs/architecture.md`、`docs/product-scope.md`、`docs/specs/`、`docs/designs/` | 说明系统边界、当前产品范围、行为 Contract 和实现设计 |
| 路线与优先级 | `docs/roadmap.md` | 汇总当前目标、依赖、验收状态与优先级确认状态；受产品边界和已确认 Contract 约束 |
| 领域事实读取边界 | `docs/agents/domain.md` | 说明领域任务的事实源读取顺序和文档边界 |
| 工程工作流程 | `docs/agents/issue-tracker.md`、`docs/agents/git-pr-workflow.md` | 说明 `.scratch/` 长期工作记录、本机实时状态、实施门禁、分支、PR 和交付规则 |
| 正确性反馈 | `tests/`、`evaluation/`、`.github/workflows/ci.yml`、`.github/workflows/real-e2e.yml` | 提供确定性测试、AI Evaluation、集成检查和真实 E2E 证据 |
| 本地运行说明 | `docs/runbook.md` | 说明开发环境、服务、数据库、RAG 构建、测试和评测的操作方式 |

ChatBI 产品本身也有模型输出的确定性护栏，例如业务语义解析、授权检查和 SQL Guard。它们属于产品架构；本说明关注的是 AI 如何在这个仓库里安全、可验证地协作开发。

## Workflow Skill 依赖

`AGENTS.md` 中引用的部分 workflow Skill 由 Codex 环境安装的 `engineering-workflow` Plugin 提供，Skill 实现没有复制进本仓库。新环境缺少该 Plugin 时，Agent 应先遵循仓库中已有的 `AGENTS.md` 和 `docs/agents/` 规则；无法执行某个 Skill 专属流程时，说明缺失，不应假设 Skill 已运行。阶段 Skill 可在目标和授权门槛满足时按流程调用；Skill 调用不会代替用户确认完整 Spec、实施范围、关键方案或发布授权。

## 会话状态与恢复

新会话开始时，Agent 检查实时 Git / worktree、长期 `.scratch/` 记录和 Git 公共目录中的本机共享进度，按工作项 ID 与真实 PR 身份核验恢复当前阶段、工作区状态、上次停点和下一步；不能仅按当前 branch 匹配。状态查找与冲突规则见 [`issue-tracker.md`](issue-tracker.md)。Plugin 安装本身不会修改项目规则；要让其他项目获得相同入口，应通过 `setup-engineering-workflow` 检查该项目现有约定，并经用户确认后写入其 Agent instructions。

执行 `python -m scripts.check_harness_state` 汇总本机当前记录、显式关联 / Ticket 矛盾和保留分支。`ERROR` 必须处理；`REVIEW` 须说明授权、归属与后续处置。检查退出 0、工作区 clean 或 CI 全绿均不能独立证明全部收尾完成。具体字段、输出边界和新 clone 恢复见 [本机检查说明](issue-tracker.md#同仓库关联与本机检查)。

PR 合并后按 [`git-pr-workflow.md`](git-pr-workflow.md) 执行 Harness 复盘；产品实现缺陷与 Agent 工作环境缺口分别记录，避免相互替代。

## 路线图读取与维护

判断下一步、启动新目标或调整计划时，读取 `docs/roadmap.md`，结合 `docs/product-scope.md` 和相关 Spec、Design、Acceptance、工作记录及可核实的 Git / 验证事实判断当前状态。旧文档中的“后续”可能已被后续工作完成，不能直接当作当前待办；文档不一致时依据已确认事实源和证据核对，不从旧实现反推新范围。

以下变化影响路线图时，在相应规划或交付中同步维护：用户确认目标或优先级、直接依赖变化、能力验收、工作完成，以及新证据表明现有描述过期。每次交付记录路线图更新位置或不适用理由；合并后核对是否有新的状态事实需要维护，必要时沿用同一目标的授权边界处理。

Agent 可依据明确证据更新完成状态、依赖事实和过期描述，并关联适用 Spec / 验收证据；证据不足时标为未确认。优先级重排、新增承诺或范围变化先提出建议并取得用户确认；建议与已确认决定分别标记，不能把讨论顺序或技术偏好写成已确认优先级。尚未排定的工作注明“优先级待确认”，不强制为所有事项分配 P0 / P1 等级。

交付核对须覆盖受影响能力在需求表 / 阶段状态、当前能力、明确不包含 / 后续范围中的全部当前描述，并与产品范围和适用 Spec 对照；新增完成事实时同步修正旧描述。记录具体核对位置与结果，不能以“文件已修改”或 Markdown 链接检查通过代替内容一致性检查。历史阶段描述须明确标为历史，不用它表达当前状态。

合并后同步工作项主记录及关联实时记录的顶部当前字段，包括 Stage、branch / worktree、PR、授权引用、Last stop 和 Next；不能只在末尾追加合并结果而保留相反的当前字段。旧进度按 issue-tracker 规则保留为历史，授权依据不扩大。下一步须与已确认路线顺序和实际交付一致。

产品汇总通过显式工作项引用定位功能进度；交付前列明受影响记录，合并后逐项核对并运行本机检查。待发布 / 暂缓的独立文档候选须保留原因、长期证据和接手工作项；后续目标开始时重新判断其适用性，不能仅因为当前 PR 完成就将其遗漏。复盘结论以实际检查结果为依据，已有规则漏执行或重复发生的缺口仍须记录。

路线图保存跨工作项的方向和顺序，不复制 Git 公共目录的会话实时进度，也不改写日期化历史 Acceptance。评测成绩仍绑定报告中的 commit、案例集及资源身份；路线图更新不能把旧报告改称当前 HEAD 已通过，候选变化后的验证要求仍按对应 Contract 执行。

## 什么时候更新本文

- 当 `AGENTS.md`、文档地图、工程工作流程、验证入口或 Skill 依赖发生变化，且这些变化让本文的说明不再准确时，更新本文。
- 普通产品功能或业务规则变化，更新它所属的 Spec、Design、Domain 文档、测试、Evaluation 或验收记录；只有 Harness 入口或组成随之改变时才更新本文。
- 不把本文当作每次功能更新的变更日志，也不在这里重复维护各事实源里的规则。
