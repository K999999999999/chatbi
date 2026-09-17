# 01: 确定性 Relationship Graph 解析 Module 加深

**What to build:**

把 Relationship Graph 的解析、路径搜索、time_field 校验、Anchor 连接和 Join Resolution 整理到一个职责清晰的内部 Module 中。

保留 `OnlineRetriever.retrieve()` 作为外部 Seam，只调整内部 Implementation 组织方式，不改变检索结果和失败行为。

**Blocked by:**

None (can start immediately)

**Status:** done

## Acceptance criteria

- [x] BFS 最短路径行为保持不变。
- [x] 平行 Foreign Key 边行为保持不变。
- [x] time_field 与 Join Key 的区分行为保持不变。
- [x] 不可达路径和歧义路径行为保持不变。
- [x] `JoinResolution` 输出保持兼容。
- [x] 内部 Module 不引入 Qdrant、Embedding、LLM 或数据库依赖。
- [x] 现有 Retrieval 测试继续通过。
- [x] 不引入完整 DDD 分层、通用 Port / Adapter 体系或未来抽象。

## Result

已完成。Relationship Graph 解析、time_field 校验、BFS 路径解析和多指标 Join 约束已移至 `src/online_query/relationship_graph.py`；`OnlineRetriever.retrieve()` 保留原有公共 Seam 和状态映射。

验证：

- `uv run --with pytest python -m pytest tests/online_query/test_retrieval.py tests/online_query/test_retrieval_observability_t3a.py -q`
- 结果：18 passed。
- 01 阶段 `git diff --check` 通过。

## Comments

- 本 Ticket 只处理确定性关系图逻辑，不改变 Relationship Graph 事实。
- 主要测试边界仍然是 `OnlineRetriever.retrieve()`；只有确实形成独立纯计算 Module 时，才增加最小内部测试。
