# Ticket 07：时间条件与分组维度的必需表候选保留

- Status: done
- Blocked by: None (can start immediately)

## What to build

修复带时间条件和分组维度的 TABLE Retrieval（表检索）候选竞争问题，保证完整的结构化查询语义能够在现有 `table_top_k=5` 边界内共同参与候选召回。

实现范围：

- 将已验证的 `ValidatedSemanticQuery.time.text` 纳入 TABLE 查询语义；
- 查询存在时间条件时，不再额外执行会挤出日期表的维度单独补充查询；
- 无时间条件的分组查询继续保留现有维度补充召回；
- 不修改公共 API、`RetrievalConfig` 默认 Top-K、Metric 事实、Relationship Graph、SQL Guard 或 Multi-Turn 状态 Contract；
- 不进行全库扫描、候选表外补表、动态阈值或新的重排器建设。

## Acceptance criteria

- “时间条件 + 销售区域维度 + 人民币销售额”在默认 `table_top_k=5` 下能够同时保留事实表、销售区域表和日期表，并返回 `SUCCESS`；
- 既有无时间条件的维度补充召回回归继续通过；
- 必需日期表实际不在 TABLE 候选时仍返回 `PARTIAL_UNREACHABLE`，不进入 SQL 生成；
- 既有 `tests/online_query/test_retrieval.py`、Online Query 和 Multi-Metric 回归不退化；
- 代码、逻辑、集成和运行时验证完成后，重新执行真实三轮 Multi-Turn E2E；
- Retrieval 作为高风险链路，最终 candidate 上重新执行 21 条真实 AI Evaluation，并记录 Commit 与 `git_dirty`。

## Result

TDD Green 已完成：新增确定性回归 `test_time_and_grouping_query_keep_required_date_table_in_top_k`，修复后返回 `SUCCESS`；完整回归为 `357 passed, 6 skipped, 118 subtests passed`。最终 candidate `2a1c262a2fd315bf90fe64899ddf33c8bb345a5a` 上，21 条真实 AI Evaluation 为 `21/21 PASS`、`Execution Accuracy=100.00%`，报告 `git_dirty=false`；真实三轮 HTTP E2E 均返回 `200`，第三轮返回列为 `销售区域`、`毛利率`。

## Comments

- 真实三轮 E2E 的第一轮成功、第二轮 `CANNOT_ANSWER`；只读重放确认默认 `table_top_k=5` 下日期表被分组维度候选挤出。
- 临时将 Top-K 改为 7 可以通过，但不作为最终方案，因为会扩大所有查询的候选范围和 Schema 暴露面。
- 上述问题已由本 Ticket 修复：完整结构化查询包含 `time.text`，存在时间条件时跳过维度单独补充查询；保持 `table_top_k=5`，修复后真实三轮和 21 条 AI Evaluation 均通过。
- 本 Ticket 只修复 Retrieval 候选查询构造，不扩展 Business Analysis、多轮状态或新的查询链路。
