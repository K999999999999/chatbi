# Online Retrieval Module 内部结构加深

状态：Confirmed；01～03 已实现

## Problem Statement

当前 Online Retrieval（在线检索）的业务行为、检索 Contract（契约）和验收结果已经稳定，但实现复杂度集中在一个较大的内部 Implementation（实现）中。

当前实现同时处理候选资源检索、指标必需字段解析、候选表闭包、Relationship Graph（关系图）路径解析、最终字段整理、Dynamic Schema（动态结构）和 Indicator Context（指标上下文）组装，以及检索 Trace（链路记录）。

这使维护者在只修改一个检索阶段时，仍需要跨越多个不同职责的实现区域，降低了代码可读性、可导航性和测试的局部性。

本次工作不改变当前检索行为，只改善 Online Retrieval 内部复杂度的组织方式。

## Solution

保留现有 `OnlineRetriever.retrieve()` 作为唯一稳定的外部 Seam（接缝），在其内部把复杂度整理为少量职责清晰的 Module：

1. 候选资源检索与候选字段完整性处理；
2. 确定性 Relationship Graph 解析与 Join Resolution（连接解析）；
3. 最终资源闭包和 QueryContext（查询上下文）组装。

这些 Module 是内部 Implementation 组织方式，不自动升级为新的公共 API、Port（端口）或完整 DDD 分层。

Online Retriever 继续负责整体顺序、失败状态映射、版本一致性和最终结果返回。Trace 继续作为横切关注点存在，不为了拆文件而建立独立业务层。

## User Stories

1. 作为维护者，我希望修改一个 Retrieval 阶段时只涉及对应的内部 Module，从而不影响无关的 Retrieval 阶段。
2. 作为维护者，我希望现有 Retrieval 测试继续观察同一个公共 Seam，从而不因内部结构调整而依赖实现细节。
3. 作为项目负责人，我希望现有 Online Retrieval 行为和验收证据保持不变，从而避免架构整理演变成 Feature 变更。

## Implementation Decisions

- 保持当前 Modular Monolith（模块化单体）架构，不重新建立完整 `domain/`、`application/`、`infrastructure/` 分层。
- 保持 `OnlineRetriever.retrieve()` 的输入形式、返回类型、成功结果、失败状态、错误边界、资源版本语义和调用顺序不变。
- 保持 `OnlineRetrievalResult`、`QueryContext`、`allowed_tables`、`allowed_columns` 以及现有 Retrieval Contract 不变。
- 保持 TABLE、COLUMN、METRIC 三路检索、必需字段校验、Anchor 选择、BFS Join、time_field 规则和 Dynamic Schema 结果语义不变。
- 保持单指标、实体类和 Multi-Metric（多指标）请求的既有行为；不借结构整理引入新的检索策略、Prompt 优化、Token 优化或业务规则。
- 保持现有 Trace Span 名称、结果状态和可观测性边界；结构整理不能改变已确认的 Trace Contract。
- 内部职责按少量内聚 Module（模块）组织，不按每个函数或每个步骤机械拆分文件。
- 新 Module 的 Interface 仅用于内部组织和测试需要；除非出现两个真实的替换实现，否则不新增 Port / Adapter 抽象。
- 不把 Qdrant、BGE-M3、SQL、数据库或平台 SDK 细节提升为 Domain（领域）概念。
- 不新增领域术语，因此本 Spec 不要求创建或更新 `CONTEXT.md`；本次也不满足创建 ADR 的不可逆决策条件。

## Testing Decisions

### Software Test

以现有 `OnlineRetriever.retrieve()` 公共 Seam 作为主要测试边界，保持现有测试的行为断言，不让测试依赖新的内部文件或私有函数。

至少保持以下行为证据：

- 实体类、单指标和 Multi-Metric 成功检索；
- TABLE、METRIC 独立检索和候选表范围限制；
- COLUMN 必需字段、分组字段和 Join Key 保留；
- Anchor、BFS 最短路径、平行关系边、time_field、不可达和歧义处理；
- Dynamic Schema、Indicator Context、QueryContext 和 allowlist 结果；
- 资产、Embedding、Qdrant、业务零命中和技术 fallback 失败边界；
- Retrieval Span 的名称、数量、顺序和安全证据范围；
- 现有 Online Query、SQL Guard 和 Query API 集成行为不回归。

如果内部拆分产生真正的纯计算 Module，可以增加针对该 Module Interface 的最小测试；不得为了提高覆盖率而暴露实现细节或删除已有公共 Seam 测试。

### AI Evaluation

结构整理后必须复用现有标准评测集，确认检索上下文和 SQL 执行结果不因内部重组发生变化。既有真实在线 RAG Evaluation（评测）结果作为回归基线，不新增 Token 优化目标。

### Business Acceptance

本次属于内部结构改进，不新增业务验收场景。业务验收标准是：支持范围内原有查询口径、Join 关系、字段白名单和不确定时的拒答行为保持一致。

### Completion Evidence

- 相关 Software Test 全部通过；
- 现有 AI Evaluation 不回归；
- 已确认 Business Acceptance 的行为不变；
- `git diff --check` 通过；
- Diff Review 确认没有引入完整 DDD 分层、无关功能或行为变化。

## Out of Scope

- 不修改业务指标、指标公式、指标时间口径或 Relationship Graph 事实；
- 不改变 TABLE、COLUMN、METRIC 的检索策略、Top-K、阈值或 Embedding 行为；
- 不处理 Prompt Token、LLM 成本或首次模型加载耗时；
- 不新增 Sparse、Hybrid、Reranker、第二次 LLM 或 Agent；
- 不新增完整 DDD 分层、通用 Port / Adapter 体系或未来扩展抽象；
- 不修改数据库、Qdrant 资产、离线构建资产或发布流程；
- 不删除测试、历史证据或文件，除非后续有独立的删除证据和明确范围；
- 不创建 GitHub Issue、PR 或外部任务。

## Further Notes

- 当前 Architecture（架构）事实源继续是 `docs/architecture.md`、相关 Online Retrieval Spec / Design 和 `AGENTS.md`。
- 当前实现已按确认范围整理为 `resource_retrieval.py`、`relationship_graph.py` 和 `retrieval_context.py` 三个内部 Module；`retrieval.py` 保留 `OnlineRetriever.retrieve()` 公共 Seam 和整体编排。
- 当前公共调用方和测试主要依赖 `OnlineRetriever.retrieve()`，这是保留现有外部 Seam 的依据；内部 Module 不作为新的公共 API。
- 01～03 已按依赖顺序完成，并通过相关检索测试、全量 Software Test 和现有在线 AI Evaluation；本 Spec 的行为边界保持不变。
