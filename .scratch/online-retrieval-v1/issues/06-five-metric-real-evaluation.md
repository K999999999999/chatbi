# 06: 扩展五指标检索并完成真实评测

**What to build:**

根据真实评测失败证据，扩展 Online Retrieval V1 的多指标上限和候选预算，并恢复候选表范围内的必需字段、显式分组字段受限检索；评测集保留四指标案例并增加五指标正向案例。

**Blocked by:**

05

**Status:** done

## Acceptance criteria

- [x] 用户明确请求的指标上限为 5 个，超过 5 个时 Fail Closed（失败关闭）。
- [x] `TABLE Top-K = 5`、`COLUMN Top-K = 20`、`METRIC Top-K = 10` 与代码和测试一致。
- [x] 指标公式、固定过滤条件和时间关系引用的字段可在候选表范围内受限恢复。
- [x] 用户明确请求的分组字段可在已命中的维度候选表内受限恢复。
- [x] `C04` 四指标案例和新增 `C06` 五指标案例进入标准评测集。
- [x] 完整确定性测试通过，包含 5 指标成功和超过 5 指标拒答边界。
- [x] 当前本地 PostgreSQL、Qdrant、BGE-M3 和真实 LLM 的 21 条 E2E Evaluation 全部通过。
- [x] 未修改数据库数据，未将 `.env` 或 Secret 写入代码、文档或报告。

## Result

已完成。真实评测报告为 `reports/evaluation/20260916T225032Z-65c6cab.json`，结果为 `21/21 PASS`、`FAIL=0`、`INVALID_CASE=0`，Execution Accuracy（执行准确率）为 `100%`；其中 `C04` 和 `C06` 均通过。

软件测试为 `251 passed, 6 skipped, 85 subtests passed`。当前实现仍保持单条统一检索流程、候选表范围限制、认证直接 FK-PK Join、`LEFT JOIN` 和一次 LLM 调用。

## Comments

本 Ticket 由真实 RAG / LLM / PostgreSQL 评测失败案例驱动；报告运行时工作树包含本 Ticket 的未提交修改，提交后如需可复核的 clean Git metadata，应在提交后的固定版本上重新生成报告。
