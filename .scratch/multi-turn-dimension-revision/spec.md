# 多轮查询显式维度替换

Status: confirmed
Confirmed: 2026-09-29，用户确认“明确说改成某维度时只保留新维度；说再加一个维度时追加”。

## Problem Statement

当前多轮修订会把新的分组维度追加到已有维度。用户先按销售区域查询，再说“分组维度改成产品线”时，SQL 同时按销售区域和产品线分组。已确认的 Multi-Turn Query V1 规格只定义维度追加；后续确认的 Evaluation Spec 和 Golden Set 又明确要求维度替换。真实 Evaluation 已暴露该冲突，导致 dimension replacement 场景失败。

## Solution

统一 Multi-Turn Query Contract：用户明确要求“改成 / 换成 / 替换为”某分组维度时，将已有分组维度整体替换为本轮明确提出的维度；用户明确要求“再加 / 增加”分组维度时，保留已有维度并追加新维度。只说新的分组维度、没有明确替换意图时，继续沿用当前追加行为。替换和追加意图同时出现、替换表达被否定，或本轮无法唯一确定新维度时，返回 `CLARIFICATION_REQUIRED`，不执行查询、不改变会话状态。

维度操作只影响 `dimensions`。没有被本轮修改的指标、时间、过滤条件和其他结构化语义保持不变。只有下游查询成功后才提交修订状态；澄清、拒答和执行失败均保留最后一次成功状态。

## User Stories

- 作为业务用户，我可以先按销售区域分析，再明确要求改成产品线，并只看到产品线分组结果。
- 作为业务用户，我可以要求再增加产品线分组，并同时看到已有区域和新增产品线。
- 作为维护者，我能从确定性测试和真实 Multi-Turn Evaluation 中验证替换、追加和失败状态保留行为。

## Implementation Decisions

- Multi-Turn Application 仍由程序合并上一轮状态；LLM 只提出本轮候选维度，不得决定是否覆盖历史状态。
- 应用按当前用户问题中的明确替换语义确定维度操作；无替换表达时维持追加兼容行为。
- 公开 Query API 请求 / 响应结构、身份授权、SQL Guard 和单轮查询 Contract 不变。
- 本 Spec 对 `.scratch/multi-turn-conversation-v1/spec.md` 的维度合并规则作局部补充；其余状态、生命周期和安全 Contract 保持不变。
- `src/evaluation/multi_turn_eval_cases.json` 中 `MT-DIMENSION-REPLACE` 是替换行为的验收案例，不修改其期望 SQL。

## Testing Decisions

- 在 Query API/Application 可观察边界验证：明确替换后只保留新维度；显式追加后原、新维度同时存在。
- 验证两种修订都保留原有指标、时间和过滤条件。
- 验证维度替换后的执行失败不会提交新状态，下一轮仍基于上次成功状态。
- 更新 Query Revision Prompt 规则，令 LLM 返回本轮新维度候选；替换/追加的最终裁决由程序完成。
- 在当前稳定 HEAD 上重跑 Multi-Turn Evaluation；修复该场景后仍须按失败报告要求重跑三套必需 Evaluation。

## Out of Scope

- 任意删除一个已有维度或把多个维度逐一编辑的自由形式操作。
- 修改 Metrics、Filter、时间范围、授权、会话 TTL、Qdrant 资产或 Business Analysis Contract。
- 修改 Golden Set 的期望结果以规避当前失败。
- 引入新 API 字段、数据库状态字段或第二条查询执行链路。

## Further Notes

- 评测证据：`reports/evaluation/20260929T145624Z-050416b-multi-turn.json`；失败轮次为 `MT-DIMENSION-REPLACE-T2`，本轮 SQL 同时保留销售区域和产品线。
- 当前失败基线及单轮、经营分析、Query Understanding 报告由 `.scratch/production-baseline-consistency/issues/04-current-head-evaluation-baseline.md` 记录。
- 确认行为的事实源是本 Spec；Multi-Turn V1 Spec、Query Revision Prompt、Evaluation Spec 和 Golden Set 的对应陈述按本 Spec 对齐。
