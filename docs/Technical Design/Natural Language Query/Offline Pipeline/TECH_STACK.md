# Offline Pipeline V1 Technology Stack
# 离线链路 V1 技术栈

> **Version（版本）：** V1
> **Status（状态）：** Frozen V1
> **Scope（范围）：** Technology Selection（技术选型）

## 1. Purpose（目的）

本文冻结 Offline Pipeline V1 的技术选择及使用边界。

上游事实源：

- `ARCHITECTURE.md`
- `FEATURE_SPEC.md`
- `PIPELINE_CONTRACT.md`
- `ACCEPTANCE_AND_EVALUATION.md`

技术选型不得修改 M1～M4 的职责、输入输出 Contract 或 Post-build Validation / Online Ready Gate 边界。

本文不定义 Class、字段级 Schema、函数、文件结构、测试命令或具体实现步骤。

## 2. Technology Baseline（技术基线）

- Runtime：Python 3.11。
- Dependency Management：uv。
- Execution Model：同步普通 Python Pipeline。
- Logging：Python `logging`。
- Configuration：延续项目已有配置体系。
- Secret：只通过环境变量提供；V1 不冻结 Secret Manager。
- Offline Retrieval Asset Store：Qdrant。
- PostgreSQL：不是 Offline Retrieval Asset Store。

当前链路是固定的 M1 → M2 → M3 → M4，不引入工作流引擎或异步编排。

本轮不修改依赖清单；依赖声明和版本锁定由后续实现任务处理。

## 3. M1 Resource Loading & Validation（资源加载与校验）

**Technology：** `pathlib`、Python `json`、Pydantic、Pure Python Validation。

**Why：** `tables.json`、`columns.json`、`relationships.json`、`metrics.json` 是结构化权威资源，不是普通 RAG Document。标准库负责文件与 JSON 边界，Pydantic 负责 Runtime Schema Validation，确定性 Python 规则负责跨资源正确性。

**Project-Controlled Logic：**

- Resource Completeness 与 Uniqueness
- Cross-resource Reference Validation
- Semantic → Physical Mapping Validation
- Metric Dependency Validation
- Relationship Validation
- Fail Closed

**LangChain Usage：** M1 不使用 LangChain JSONLoader，也不把权威 JSON 提前转换为 `Document`。

**Not Selected：** Pydantic 只用于最小边界模型，不建立大量 Identity、Descriptor、Wrapper 或 Value Object 层级。

## 4. M2 Retrieval Projection（检索投影）

**Technology：** Pure Python Projection + `langchain_core.documents.Document`。

**Why：** 正式术语保持 Retrieval Record；`Document` 复用 `page_content` 与 `metadata` 通用结构，减少自定义容器和后续 VectorStore 适配代码。

**Core Rules：**

- `TABLE`、`COLUMN`、`METRIC` 分别形成独立 `Document`。
- One Source Object → One Retrieval Record / Document。
- Projection 只重组正式事实，并保留 Source Trace。
- Relationship 不转换为 `Document`，不产生 Retrieval Record。

**LangChain Usage：** LangChain 只提供通用容器，不拥有正式语义、覆盖规则或 Relationship Boundary。

## 5. M3 Retrieval Representation Generation（检索表示生成）

**Technology：**

- Model：BGE-M3。
- Runtime Library：FlagEmbedding。
- Dense Representation：启用。
- Sparse Representation：启用。
- Multi-vector / ColBERT：不启用。

**Why：** BGE-M3 原生支持 Dense、Sparse Lexical Weight 和 Multi-vector；V1 只启用 Dense + Sparse，避免提前承担 Multi-vector 的存储和检索复杂度。FlagEmbedding 直接暴露两类结果，控制边界更清晰。

**Core Rules：** 每个 Retrieval Document 生成一组 Dense 与 Sparse Representation，并与原 Record、Object Type 和 Source Trace 保持一一关联；不得修改业务语义、物理映射或 Relationship。

模型参数、Batch Size、Device 和数值精度不在本文冻结。

**LangChain Usage：** 不为统一接口强制增加 LangChain Embeddings Wrapper；BGE-M3 Dense + Sparse 核心生成逻辑由 FlagEmbedding 和项目 Contract 控制。

## 6. M4 Retrieval Asset Building（检索资产构建）

**Technology：** Qdrant + `langchain-qdrant`；可使用 `QdrantVectorStore`。

**Qdrant Collection Strategy：** V1 冻结三个 Physical Collection：

1. `table_retrieval`
2. `column_retrieval`
3. `metric_retrieval`

每个 Collection 同时保存 Dense Representation、Sparse Representation、必要 Metadata / Payload 和 Source Trace；不拆分为六个 Collection。

**Why：** Qdrant 支持同一 Point 保存 Dense 与 Sparse 表示，符合三类 Retrieval Object 分离且每类两种表示共存的 V1 边界。`langchain-qdrant` 减少通用 VectorStore、Document、Metadata / Payload 和后续 Retriever 集成代码。

**LangChain Usage Boundary：** `QdrantVectorStore` 用于适合其 Contract 的 Collection 访问、Document / Metadata 适配和后续 Retriever 集成。M4 不得通过其写入路径再次生成或替换 M3 已生成的表示；预计算表示的写入接缝在实现阶段验证，不得造成重复生成。

**Project-Controlled Logic：**

- 三类 Retrieval Object 到 Collection 的确定性映射
- Full Rebuild、完整覆盖、Source Trace 和 Fail Closed
- 构建失败时保护上一版有效资产
- Relationship 不进入任何 Qdrant Retrieval Collection

不建立无独立职责的 Table / Column / Metric Repository 或 Insert / Search Service 包装层。

Relationship 保持独立链路：`relationships.json → M1 Validation → Validated Relationship Catalog → Online Join Resolver → Deterministic Graph → BFS / Join Resolution`，不经过 BGE-M3 或 Qdrant Vector Retrieval。

## 7. Pipeline Orchestration（链路编排）

Offline Pipeline V1 使用同步普通 Python 调用顺序：`M1 → M2 → M3 → M4`。

LangGraph = NOT SELECTED FOR V1。

当前没有 HITL、动态路由、复杂状态机、长任务状态持久化或独立节点恢复需求。只有真实出现断点恢复、复杂 Retry、动态 Branch、多阶段并行、HITL 或独立任务恢复需求时，才重新评估 LangGraph。

## 8. LangChain Usage Boundary（LangChain 使用边界）

LangChain 的定位：

> **减少通用胶水代码，不拥有业务事实和核心契约。**

优先使用：Document、VectorStore、Qdrant Integration，以及仅供 Online Reserved 的 Retriever。

不得替代：

- Business Validation 与 Cross-resource Validation
- Metric Dependency Validation 与 Relationship Validation
- Business Truth
- BGE-M3 Dense + Sparse 核心生成逻辑
- Full Rebuild、Fail Closed 和资产完整性裁决

原则：Framework handles plumbing. Domain / Contract owns correctness.

## 9. Online Reserved & Deferred Technology（在线预留与延后技术）

Online Retrieval 不属于本次 Offline Pipeline 实现范围。

仅预留 `QdrantVectorStore → LangChain Retriever`；Table、Column、Metric 分别拥有自己的 Retriever。

未来可以评估 Dense Search + Sparse Search → Fusion / RRF → Top-K，但本轮不冻结参数。

V1 明确延后：

- Multi-vector / ColBERT、LangGraph
- Incremental Index Update、Distributed Build、Background Scheduler
- Multi-version Online Serving、Complex Collection Routing
- Reranker、固定 Top-K、固定 Threshold、Online Fusion 参数
- Atomic Publish 的复杂平台化方案

测试沿用项目当前体系；Deterministic Test、Retrieval Evaluation、Feature Acceptance 保持不同证据边界。Post-build Validation / Online Ready Gate 继续由 `ACCEPTANCE_AND_EVALUATION.md` 定义。

## 10. Final Stack Summary（最终技术栈摘要）

| Technology / Decision | V1 Status |
|---|---|
| Python 3.11 | SELECTED |
| uv | SELECTED |
| Pydantic | SELECTED |
| Python `json` / `pathlib` | SELECTED |
| LangChain Document | SELECTED |
| BGE-M3 | SELECTED |
| FlagEmbedding | SELECTED |
| Dense Representation | SELECTED |
| Sparse Representation | SELECTED |
| Multi-vector / ColBERT | DEFERRED |
| Qdrant | SELECTED |
| 3 Physical Collections | SELECTED |
| `langchain-qdrant` | SELECTED |
| LangChain Retriever | ONLINE RESERVED |
| LangGraph | NOT SELECTED FOR V1 |
