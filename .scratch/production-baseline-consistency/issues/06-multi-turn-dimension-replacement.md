# 多轮查询支持明确的分组维度替换

Status: in-progress
Owner: ChatBI 仓库维护者
Backup Owner: None
Blocked by: None (can start immediately)

## Change Profile

- Lifetime: Multi-Turn Query V1 长期行为 Contract。
- Size: M，涉及 Application 状态合并、Query Revision Prompt、Contract 文档和确定性测试。
- Risk: 高；改变已确认的多轮结构化查询状态修订行为，并影响真实 AI Evaluation。
- Evidence: Query API/Application 状态测试、Prompt 合同测试、三套真实 Evaluation 报告。
- Delivery: 当前生产基线工作分支上的独立纵向切片；只本地 Commit。真实 Evaluation 在新 clean candidate 上按仓库门禁再次授权。

## Canonical Source

- 用户确认的行为：`.scratch/multi-turn-dimension-revision/spec.md`。
- Query API 公共 Contract：`docs/specs/query-api.md`。
- 语义合并实现：`src/query_api/semantic_revision.py`。
- 评测案例：`src/evaluation/multi_turn_eval_cases.json`，不修改其期望 SQL。

## What to build

- 明确“改成 / 换成 / 替换为”某分组维度时，程序将已有维度整体替换为本轮候选维度。
- 明确“再加 / 增加”维度时追加并保留现有维度；没有明确替换表达时保持现有追加兼容行为。
- 替换和追加意图冲突、替换被否定或目标维度不明确时返回 `CLARIFICATION_REQUIRED`，不执行查询、不修改会话状态。
- 更新 Query Revision Prompt，使 LLM 只提出当前轮新维度；替换 / 追加方式由 Application 根据用户明确表达确定。
- 对齐 Multi-Turn V1 Spec 与 Query API 文档；不修改 Golden Set 期望结果。

## Acceptance criteria

- 从销售区域开始后问“分组维度改成产品线”，下一次下游查询只包含产品线分组。
- 从销售区域开始后问“再增加产品线”，下一次下游查询同时包含销售区域和产品线分组。
- 替换 / 追加均保留未修改的指标、时间范围和过滤条件。
- 意图冲突或无法唯一确定目标维度时返回 `CLARIFICATION_REQUIRED`，下游调用次数不增加，会话继续使用最后一次成功状态。
- 替换后的下游查询失败时，不提交新维度状态。
- Query Revision Prompt、Multi-Turn V1 Spec、Query API 文档和 Evaluation Spec 对明确替换 / 追加的定义一致。
- 原 `MT-DIMENSION-REPLACE` Golden Case 保持不变并通过后续真实 Evaluation。

## Owned files

- `src/query_api/semantic_revision.py`
- `src/online_query/query_understanding_llm.py`
- `tests/query_api/test_multi_turn_revision.py`
- `tests/online_query/test_query_understanding_llm.py`
- `.scratch/multi-turn-conversation-v1/spec.md`
- `docs/specs/query-api.md`
- 必要时同步 `docs/specs/evaluation.md`
- 本 Ticket Result / Comments
- `.scratch/production-baseline-consistency/issues/04-current-head-evaluation-baseline.md`：更新依赖和后续报告状态

## Validation evidence

- 行为变化按 Red-Green-Refactor 增加并运行 Query API/Application 定向测试、Query Revision Prompt 测试。
- 运行相关 Multi-Turn Evaluation Runner 单元测试及目标子系统测试。
- 实现后完成当前上下文 Code Review、`ruff`、格式和 `git diff --check`。
- 新 clean candidate 获得最终验收授权后，重跑 29 单轮、7 Multi-Turn、10 Business Analysis；要求三个必需套件各自 `0 FAIL`、`0 INVALID_CASE`，并运行 6 个 Query Understanding 辅助案例。

## Migration / Rollback

- 不涉及会话持久化格式变化；会话是短期内存状态，服务重启后失效。
- 若 Evaluation 暴露其他越界行为，保留报告为失败证据，不修改 Golden Set 规避失败；回到 Contract / 实现 Ticket 处理后，在稳定 candidate 重跑所有必需套件。

## Done When

明确替换只保留新维度、明确追加保留旧维度，歧义和失败不改变状态；Contract / Prompt / 文档一致，确定性测试通过，且后续当前 candidate 的三套必需 Evaluation 全部为零失败、零无效案例。

## Result

实现和确定性验证已完成，等待新 candidate 上授权后的真实 Evaluation：

- 用户明确表达维度替换时，Application 清除旧维度并采用本轮候选；默认和明确追加仍按追加处理。
- 替换目标缺失、替换与追加意图冲突或替换被否定时返回 `CLARIFICATION_REQUIRED`，不执行下游查询、不更新会话状态。
- Prompt 已明确 LLM 只返回本轮候选维度，由程序按用户措辞裁定替换或追加；Multi-Turn V1 Spec 与 Query API Contract 已同步。
- 查询失败后旧成功状态保留；替换同时保留指标、时间和过滤条件。
- 定向 Query API / Prompt 测试：27 passed，3 个子测试通过；相关 Query API 与 Multi-Turn Evaluation 测试：90 passed，17 个子测试通过。
- `ruff` 针对变更文件通过（排除仓库既有的 BLE001、RUF100、TRY004、TRY201、UP035 诊断）；格式检查与 `git diff --check` 通过。
- Code Review：PASS。变更限于 Ticket owned files；没有 Golden Set 修改。
- 按仓库候选验收规则，新 candidate 上的真实模型 Evaluation 尚未运行，需在提交候选后取得用户授权。

## Comments

- Ticket Readiness Review：READY。行为、失败边界、代码与测试 seam、文档来源和后续 Evaluation 门禁均明确。
- Design Review：`.scratch/multi-turn-dimension-revision/spec.md`，Verdict `PASS WITH MINOR FIXES`；最小条件是在本 Ticket 中将旧 Spec 的维度追加规则标记为已更新。
- 真实失败证据：`reports/evaluation/20260929T145624Z-050416b-multi-turn.json`，失败轮次为 `MT-DIMENSION-REPLACE-T2`。
- 2026-09-29 实现 Code Review：PASS；实现遵循已确认 Contract，没有需要返工的发现。
