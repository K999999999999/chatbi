---
name: design-review
description: "审查「模块设计」Skill 产出的 Module Implementation Design 是否符合正式 Architecture、Feature/Module Contract、Engineering Rules 与真实 Repository；必须启动独立只读 Reviewer Agent，禁止重新设计或实现。"
---

# 设计审查

## 定位与边界

本 Skill 只用于：

> Review Existing Design Against Formal Contract（依据正式 Contract 审查既有设计）。

输入必须是「模块设计」Skill 已产生的最终版 `Module Implementation Design`。本 Skill 不是第二个设计器，不重新选择自己偏好的架构、技术或目录，也不执行 Implementation。

固定链路：

```text
模块设计 Agent
    ↓
Module Implementation Design
    ↓
上下文隔离
    ↓
module_design_reviewer（独立只读 Reviewer Agent）
    ↓
Review Result
    ↓
主 Agent 返回结果
    ↓
人工 Gate
```

审查行为本身是 Read-Only，不需要在正式 Review 前再次请求用户批准；审查完成后必须保留人工决定 Gate，不得自动进入编码。

## 目标解析

先从用户请求、当前对话和仓库中确定唯一的：

- `Feature`；
- `Module`；
- 最终版 `Implementation Design` 文件路径；
- 本次 `Review Scope`。

如果目标不唯一、Implementation Design 不是最终版，或无法定位所属正式 Feature / Module Contract，不得猜测。直接返回 `BLOCKED`，说明缺失的定位信息；不要为了开始 Review 自行补写设计或修改正式文档。

## 强制启动独立 Reviewer

在正式读取和评价设计之前，必须优先创建新的独立 Subagent / Agent Thread：

1. 使用当前 Codex 的 Subagent spawn capability；当前桌面环境优先使用 `multi_agent_v1__spawn_agent`。
2. 设置 `fork_context=false`，或使用等价的“仅新上下文”选项。不得 fork 当前设计 Agent 的历史上下文。
3. 明确请求使用项目级 Custom Agent `module_design_reviewer`，其配置位于 `.codex/agents/module_design_reviewer.toml`。
4. 只传递 Review Target 的路径、名称和范围，以及本 Skill 的审查清单路径；不得传递设计 Agent 的 Chain of Thought、中间分析、自我辩护或预设结论。
5. 由 Reviewer 自己重新读取正式事实源、真实仓库和最终版 Implementation Design，并独立形成 Findings。

推荐传给新 Agent 的最小任务如下；路径必须替换为当前真实值：

```text
使用项目级 module_design_reviewer，在全新上下文中只读审查：
Feature: <真实 Feature>
Module: <真实 Module>
Implementation Design: <真实绝对路径>
Review Scope: <本次范围>
审查清单: <design-review>/references/review-checklist.md

只允许依据正式事实源、Engineering Rules、Repository Reality 和上述最终版 Design。
不要读取或依赖父 Agent 的历史推理，不修改任何文件，不执行实现，不修复 Finding。
返回固定格式的中文审查报告和最终 Verdict。
```

如果当前运行环境无法选择 Custom Agent，但仍支持独立新 Thread，可以在该 Thread 中显式复述只读约束并记录“未加载项目级 Custom Agent”；如果连独立 Thread 都无法创建，必须返回 `BLOCKED`，不得由主 Agent 自我审查来替代。

主 Agent 只负责传递目标、等待和整合 Reviewer 的结果，不得在同一回合用自己的判断偷偷替代独立 Review。Reviewer 返回异常、超时或证据不足时，按 `BLOCKED` 报告具体原因。

## Fresh Review Context

Reviewer 的允许事实输入只有：

1. 正式 `Architecture`、Feature Spec、Module Spec、Contract 和 Acceptance / Evaluation；
2. `Engineering Rules`、ADR 和当前项目明确的设计标准；
3. 当前 Repository Reality，包括真实代码、测试、依赖、配置、资源、Ports、Contracts 和 Infrastructure；
4. 当前最终版 `Implementation Design`。

不得将以下内容当作事实依据：

- 设计 Agent 的 Chain of Thought 或中间分析；
- 设计 Agent 对自己方案的辩护；
- 未正式确认的聊天意见；
- 历史 Memory 中未经当前事实源重新验证的方案结论；
- “应该没问题”等引导性结论。

所有 Finding 必须可以回溯到实际读取的正式文件、Repository 文件或当前 Implementation Design，并在报告中写出路径或明确的证据位置。

## Review 方法

Reviewer 必须先读取本目录下的 [references/review-checklist.md](references/review-checklist.md)，再按其中的事实源、优先级、检查项、Severity 和报告格式执行。至少覆盖：

- Contract Alignment；
- Architecture Alignment；
- Module Boundary；
- Repository Compatibility；
- Typed Contract 与 Validation Boundary；
- Failure Contract 与 Fail Closed；
- Test / Evaluation Boundary；
- 已提出 Technology Decision；
- Minimality / Overengineering；
- Design 中自报问题的独立判定。

只审查 Design 已提出的 Module-Level Technology Decision，不重新发起全局技术选型。若 Design 与正式 Contract 冲突，Finding 应要求修改 Design；不得为了迁就 Design 自动修改 Contract、Architecture 或 Domain。

发现问题时使用最小修复边界：

```text
Finding
    → 为什么是问题
    → 正式依据
    → 影响
    → 最小 Required Fix
```

不要输出“重新设计一整套模块”的替代方案。若问题无法在当前正式事实下安全消解，使用 `BLOCKED`，要求返回「模块设计」Skill 处理正式冲突或缺失信息。

## 只读约束

Reviewer 和主 Agent 在本 Skill 的 Review 阶段均不得：

- 修改代码、测试、Spec、Architecture、资源或配置；
- 安装依赖、修改数据库、启动或修改外部服务；
- 执行 Implementation、修复 Finding 或自动调用其他实施 Skill；
- Commit、Stage 或清理用户已有工作区修改；
- 把部分审查结果伪装成完整 PASS。

## 输出与人工 Gate

Reviewer 必须按审查清单中的固定结构返回中文报告。最终 Verdict 只允许：

- `PASS`：设计可以进入人工批准；
- `PASS WITH MINOR FIXES`：只有轻微问题，不需要重新完整设计；
- `NEED FIX`：存在 `MAJOR`，返回「模块设计」修正后重新 Review；
- `BLOCKED`：存在 `BLOCKER`，或正式事实本身冲突 / 缺失，暂时不能安全实现。

主 Agent 应原样保留 Findings 的证据、Severity、Required Fix 和 Verdict，并明确：

> 本次 Reviewer 为独立 Read-Only Agent，未修改生产代码或正式文档；最终是否批准由人工决定。

`PASS` 不是开发授权，`NEED FIX` / `BLOCKED` 也不触发自动修复。审查结束后停止，等待人工决定。
