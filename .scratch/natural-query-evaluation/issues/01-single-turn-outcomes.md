# Ticket 01：补齐单轮自然查询评测集与 outcome 统计

Status: done

## What to build

在现有单轮案例中覆盖指标、时间、分组、条件、TopN、HAVING、多指标、别名、澄清、拒答及组合场景。成功案例的问题走正式授权 Online Query，标准 SQL 走相同 SQL Guard 与 PostgreSQL 只读执行器；报告把 SQL 执行准确率、失败 outcome 命中率和整体案例准确率分开。

经营分析案例及专用评测器继续独立运行，不在本 Ticket 修改判定规则。

## Blocked by

None (can start immediately)

## Acceptance criteria

- 单轮案例覆盖已确认的十类自然查询场景；澄清和拒答不要求 expected SQL。
- `Execution Accuracy` 只计算有效 `result_match` 案例；错误码必须与期望 outcome 匹配。
- 报告记录覆盖标签、错误 outcome、执行准确率和整体案例准确率。
- 单轮问题通过正式授权查询入口执行；黄金 SQL 使用同一个只读 Query Executor。
- Query Understanding 辅助集与经营分析集仍独立。

## Result

已实现。单轮测试集从 21 条扩展到 27 条，包含 25 条执行结果比对案例和 2 条澄清 / 拒答 outcome 案例；报告分别统计 Execution Accuracy、Outcome Accuracy 和 Case Accuracy。

## Comments

- 定向软件测试通过：`105 passed, 1 skipped, 14 subtests passed`；Ruff、格式检查和 `git diff --check` 通过。
- 最终提交 `71586df` 的真实单轮评测：执行准确率 `24/25 = 96%`，Outcome 准确率 `1/2 = 50%`，整体案例准确率 `25/27 = 92.59%`，无 INVALID_CASE。
- 失败案例：`F01` 在 Retrieval 阶段返回 `CANNOT_ANSWER`；`R01` 期望 `CLARIFICATION_REQUIRED`，实际返回 `CANNOT_ANSWER`。
- 报告：`reports/evaluation/20260927T131023Z-71586df.json` 与 `.md`。

## Follow-up repair

2026-09-27：`F01` 已替换为“华东区域”筛选案例，`R01` 收窄为未限定“利润”口径；Online Query 已在 Retrieval 前确定性澄清该表达。上述报告早于本次修复，仍是历史结果，不代表当前案例集准确率。
