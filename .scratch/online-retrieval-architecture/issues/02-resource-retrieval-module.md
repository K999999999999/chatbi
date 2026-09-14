# 02: 候选资源检索 Module 加深

**What to build:**

把 TABLE、COLUMN、METRIC 候选检索以及公式、filters、time_field 的必需字段处理整理到一个内聚的内部 Module 中。

保持既有检索链路：TABLE 先确定候选表范围，COLUMN 只在候选表内检索，METRIC 保持独立检索；不改变任何业务规则或检索配置。

**Blocked by:**

None (can start immediately)

**Status:** done

## Acceptance criteria

- [x] TABLE、COLUMN、METRIC 继续使用各自的既有集合。
- [x] METRIC 不被 TABLE 结果错误过滤。
- [x] COLUMN 仍然只在候选表范围内执行。
- [x] 公式、filters、time_field 所需字段仍然完整校验。
- [x] 单指标、实体类和 Multi-Metric 行为保持不变。
- [x] 现有 `column.search`、`metric.search`、`embedding.query` 调用语义保持不变。
- [x] 现有 Retrieval 测试继续通过。
- [x] 现有检索可观测性测试继续通过。
- [x] 不改变 Retrieval Top-K、阈值、Embedding 或 Qdrant 行为。

## Result

已完成。TABLE、COLUMN、METRIC 候选检索、指标选择、time_field 解析、公式/过滤条件必需字段和字段完整性已移至 `src/online_query/resource_retrieval.py`；`OnlineRetriever` 保留原有公共 Seam、检索参数和失败状态映射。

验证：

- `uv run --with pytest python -m pytest tests/online_query/test_retrieval.py tests/online_query/test_retrieval_observability_t3a.py -q`
- 结果：18 passed。
- 02 阶段 `git diff --check` 通过。

## Comments

- 本 Ticket 只处理候选资源检索及必需字段完整性，不处理 Prompt Token 或运行性能。
- 不删除必需字段的精确检索；结构整理不能降低字段 Contract 的完整性。
