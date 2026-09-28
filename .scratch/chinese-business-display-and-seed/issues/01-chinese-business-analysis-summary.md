# 01 经营分析总结使用简体中文

- Status: in-progress
- Owner: ChatBI Agent
- Blocked by: None (can start immediately)
- Change Profile: 小范围；Prompt / AI 行为；确定性测试加真实 Business Analysis Evaluation；本地交付

## What to build

要求 Business Analysis Summary 的用户可见报告字段使用简体中文，包括标题、摘要、趋势判断、关键发现、原因分析和行动建议。保留现有 JSON 字段、证据归因、Task ID、不完整任务结构及数值事实，不改 API Contract，也不要求翻译作为证据的权威专有名称。

## Scope

- 修改 Summary Prompt 中的语言要求。
- 增加确定性测试，覆盖中文输出要求且不改变报告字段 Contract。
- 按仓库流程运行针对性测试和真实 Business Analysis Evaluation，记录结果；不静默覆盖旧 Evaluation 报告。

## Out of Scope

- 修改 Summary 字段、API Schema、评测案例数值或归因规则。
- 翻译 SQL、Task ID、错误码、状态码或其他机器可读内容。

## Acceptance criteria

- Prompt 明确要求所有面向用户的报告自然语言字段以简体中文生成。
- 现有报告结构、程序裁决的证据引用及数值事实保持不变。
- 针对性测试通过；真实 Evaluation 报告可检查，任何失败均明确记录，不宣称未通过的行为已验收。

## Owned files

- `src/business_analysis/reporting.py`
- `tests/business_analysis/test_reporting.py`
- 必要时更新与该行为直接相关的 `tests/evaluation/` 测试或评测记录；不得修改旧报告作为基线。

## 验证证据

- `tests/business_analysis/test_reporting.py` 针对性测试。
- 按仓库高风险规则，在确认 candidate 后运行真实 Business Analysis Evaluation，并保留新报告及结果。

## Migration / Rollback

不涉及数据迁移或运行时部署。若真实 Evaluation 暴露报告质量回退，修复 Prompt 后重新验证；保留既有报告作为历史证据。

## Done When

Prompt 和回归测试体现中文 Contract，针对性测试及要求的真实 Evaluation 均有可检查结果，且无未解释的 Contract 或证据回归。

## Result

Prompt 已要求用户可见自然语言字段使用简体中文，并保留 Task ID、状态码和证据原值。Reporting 定向测试和全仓确定性测试通过（全仓 536 passed、14 skipped、124 subtests）；真实 Business Analysis Evaluation 仍须在最终 candidate 验收阶段运行。

## Comments

- Canonical Source: `.scratch/chinese-business-display-and-seed/spec.md`。
