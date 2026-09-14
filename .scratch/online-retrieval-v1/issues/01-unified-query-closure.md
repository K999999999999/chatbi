# 01: 无指标与单指标的统一最小闭环

**What to build:**

建立一条统一的 Online Retrieval 主流程，先覆盖无指标查询、单指标查询和单表场景：TABLE → COLUMN → 可选 METRIC → 结构化上下文 → LLM → SQL Guard → 数据库执行。无指标和单指标只允许在同一条编排流程中通过 `metrics=0/1` 表达，不建立两条完整流水线。

**Blocked by:**

None

**Status:** open

## Acceptance criteria

- [ ] `metrics=0` 的实体查询可以跳过 METRIC 检索并继续生成 SQL。
- [ ] `metrics=1` 的单指标查询与无指标查询使用同一条 Online Retrieval 编排流程。
- [ ] 使用统一候选配置：TABLE TopK=5、阈值=0.30；COLUMN TopK=10、阈值=0.25；METRIC TopK=5、阈值=0.30。
- [ ] COLUMN 只在候选表范围内检索，10 个字段是所有候选表合计上限，而不是每张表各 10 个。
- [ ] 不启用字段业务规则引擎，不自动补充未检索到的公式字段。
- [ ] TABLE、COLUMN、METRIC、Relationship Graph 和 Embedding 使用同一个 Asset Snapshot（资源快照）。
- [ ] Asset Snapshot 不可用或版本不一致时返回 `CONTEXT_ERROR`，不调用 LLM。
- [ ] Qdrant 或 Embedding 失败时返回 `CONTEXT_ERROR`，不使用完整静态 Schema 兜底。
- [ ] 结构化上下文只包含当前查询需要的候选资源和原始问题。
- [ ] LLM 只返回一条 SQL 或 `CANNOT_ANSWER`。
- [ ] SQL Guard 失败时不执行 SQL、不调用 LLM 修复、不自动重试。
- [ ] 为无指标、单指标、缺少候选资源和技术失败场景补充确定性测试。

## Result

待实现。

## Comments

这是 V1 的基础用户闭环；不引入新的外部 Issue、PR 或远程工作流。
