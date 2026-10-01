# 仓库外与本机状态断言的证据边界

Status: confirmed

## Goal

明确要求 Agent 在描述 Skill Plugin 等仓库外状态或本机配置时，根据可核实的配置和文件陈述；证据不足时，不能依据对话记忆或局部线索断言其存在、不存在或可用。

## Scope

- 保留当前 `AGENTS.md` 已采用的 `Skill Plugin` 示例及可核实事实源要求。
- 明确证据不足时不做存在、不存在或可用性断言。
- 不改变其他工作流、产品行为、外部状态或 Plugin 配置。

## Acceptance

- 继续要求检查能够证明状态的配置和文件。
- 证据不足时要求标明未确认，并覆盖存在、不存在、可用三类断言。
- 只修改 `AGENTS.md` 对应规则行；工作项记录留在本 Spec 中。

## Verification

- Review 文案与原规则保持一致，只补明确性。
- 运行 `git diff --check`。
- 不运行软件测试；本改动只调整 Agent 指令文案。

## Authorization

用户于 2026-10-01 确认了“保留该措辞调整并单独 Review”的处理方案；授权范围为此文案调整的本地 Review 和 Commit。Push / PR 未授权。
