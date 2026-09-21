# Ticket 03：经营分析报告与 Summary LLM

- Status: done
- Owner: Business Analysis Application / Reporting
- Blocked by: Ticket 02
- Canonical Source: `.scratch/business-analysis-v1/spec.md`

## Change Profile

- Lifetime：经营分析 V1 的报告输出 Contract。
- Size：中等；消费 TaskResult，不改变查询执行。
- Risk：高 LLM 报告正确性风险。
- Evidence：报告结构校验、失败行为测试和后续 AI Evaluation。
- Delivery：本地 Feature branch；不新增长期 AnalysisState。

## What to build

- 定义 `BusinessAnalysisReport`。
- 实现 Summary LLM 的结构化输出适配。
- 只使用 `TaskResult` 中已完成 Task 的结构化数据作为事实依据。
- 关联 `evidence_task_ids` 与实际存在的 `completed` Task。
- 由程序根据 Task 状态校验或生成 `incomplete_tasks`。
- 处理失败、跳过、空结果和截断结果。
- 没有任何完成 Task 时返回 `CANNOT_ANSWER`，不生成空成功报告。
- Summary LLM Provider 失败、超时或输出 Contract 校验失败时返回 `LLM_ERROR`。
- 防止 Summary LLM 修改 Task 状态、指标口径或最终数值。
- `action_suggestions` 只能表达建议，不表示系统已执行经营动作。

## Owned paths

- `src/business_analysis/`
- `tests/business_analysis/`

## Acceptance criteria

- 正常完成的 TaskResult 能生成自然语言经营分析报告。
- 报告包含标题、摘要、关键发现、趋势判断、原因、建议、证据 Task 和不完整任务信息。
- `evidence_task_ids` 引用不存在、失败或跳过的 Task 时，报告不能返回成功。
- 失败、跳过、空结果和截断状态会被明确反映在报告中。
- Summary LLM 不能凭空创造指标、口径、数值或 SQL 事实。
- 没有任何完成 Task 时返回 `CANNOT_ANSWER`。
- Summary LLM 失败或非法结构时返回 `LLM_ERROR`，不能包装成成功报告。

## Verification evidence

- `tests/business_analysis/` 中的报告 Schema、证据引用和失败行为测试。
- 使用固定 TaskResult 验证正常报告、部分失败、空结果、截断和全部失败。
- 使用非法 Summary LLM 输出验证不存在的 Task 引用和缺失不完整性标记会被拒绝。
- 后续 Ticket 05 补充报告真实数据引用和业务可读性验收。

## Migration / Rollback

不涉及数据库或会话迁移。回滚时可停止生成自然语言报告，但不影响普通查询和 Task 查询安全边界。

## Done When

- BusinessAnalysisReport 的字段、证据和失败 Contract 固定。
- Summary LLM 的成功、失败和非法输出都有确定性测试。
- 报告不会把部分数据包装成完整经营结论。

## Result

已完成 `BusinessAnalysisReport`、Summary LLM 适配和报告事实校验：

- Summary LLM 只接收原始问题和结构化 `TaskResult`，不接收 SQL，也不参与 Task 状态裁决。
- 程序严格校验报告字段、证据 Task 引用和 `incomplete_tasks`；失败、跳过、空结果和截断结果均由程序记录。
- 没有任何 `completed` Task 时返回 `CANNOT_ANSWER` 且不调用 Summary LLM；Provider 失败和非法结构统一返回 `LLM_ERROR`。
- `BusinessAnalysisReport` 提供面向 API 的自然语言报告序列化结果，建议字段不会表示系统已执行经营动作。

验证：`uv run pytest -q tests/business_analysis` → 20 passed；`uv run python -m compileall -q src/business_analysis tests/business_analysis` → 通过。

## Comments

- Ticket Readiness Review：READY。
- Summary LLM 是不可信候选；程序以实际 TaskResult 和 Task 状态为准。
