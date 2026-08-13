# Embedding Generation Module Spec
# 检索表示生成模块规格

> **Status（状态）：** V1 Module Contract Design Baseline（V1 模块契约设计基线）
> **Version（版本）：** V1
> **Feature（所属功能）：** Offline Pipeline（离线链路）
> **Feature Architecture Reference（功能架构引用）：** `../ARCHITECTURE.md`
> **Feature Spec Reference（功能规格引用）：** `../FEATURE_SPEC.md`
> **Acceptance Reference（验收引用）：** `../ACCEPTANCE_AND_EVALUATION.md`
> **Module Standard Reference（模块标准引用）：** `../../../MODULE_CONTRACT_STANDARD.md`

---

## 1. Responsibility（职责）

本 Module 负责将每一个 `RetrievalRecord` 转换为满足 `RetrievalRepresentation` Contract（检索表示契约）的 `RetrievalRepresentation`（检索表示），并形成 `EmbeddedRetrievalRecords`（带检索表示的检索记录集合）。该输出作为后续 Retrieval Index Building（检索索引构建）的 Contract Input（契约输入）；本 Module 不通过运行时调用下游 Capability（能力）确认可消费性。

本 Module 必须保证：

- Representation 与 Retrieval Record Identity 保持一一关联；
- Source Trace、Semantic Payload、Physical Mapping Reference 和 Business Meaning 不丢失、不改变；
- 每个 Record 都有完整 Representation，不能以部分成功替代完整构建；
- 在相同 Contract Input、Build Conditions 和 Representation Version 下，结果具有可重复语义。

本 Module 不负责：

- 定义 Business Truth、Metric Definition 或 Dimension Meaning；
- 修改 Retrieval Record；
- 决定 Dense / Sparse / Hybrid 等表示类别；
- 决定 Embedding Model、维度、Tokenizer、设备或批量参数；
- Online Retrieval、Ranking、Schema Linking、Metric Resolution 或 SQL 相关职责；
- 处理 Relationship Retrieval Record。

---

## 2. Input Contract（输入契约）

### 2.1 `RetrievalRecords`（检索表示生成输入）

本 Module 的输入就是 `02_RETRIEVAL_PROJECTION.md` 输出的 `RetrievalRecords`，不再包裹另一层隐式请求对象。它必须包含：

- `records`：四类完整 Retrieval Record；
- `source_descriptors`：五类源资源描述；
- `build_context`：本次完整构建的身份与条件。

每条 Record 必须已有 Source Trace 和 Physical Mapping Reference。

### 2.2 `BuildContext`（构建上下文引用）

`BuildContext` 的正式字段定义位于 `01_RESOURCE_LOADING_AND_VALIDATION.md`。本 Module 只读取其值，并要求 `RetrievalRecords.build_context` 在输出中原样传递到 `EmbeddedRetrievalRecords`。

---

## 3. Preconditions（前置条件）

进入本 Module 前必须满足：

1. `RetrievalRecords` 已通过 Retrieval Projection Contract。
2. 所有 Record 的 `record_type`、`semantic_payload`、`physical_mapping_reference` 和 `source_trace` 已完整。
3. `BuildContext` 的四个字段完整，且 `build_mode=FULL_REBUILD`。
4. 输入 Record 不包含 Relationship，不包含未知对象类型，也不依赖隐藏全局状态。
5. `Embedding Capability` 可以在给定 `RepresentationVersion` 下处理四类 Record 的检索内容，并且其返回结果必须满足 `RetrievalRepresentationValue` Contract。

---

## 4. Processing Responsibilities（处理职责）

本 Module 必须完成：

1. 对 `RetrievalRecords.records` 中每一条 Record 单独请求一个 `RetrievalRepresentation`。
2. 保留 Record 的 `LogicalRecordIdentity`、`SourceObjectIdentity`、`SourceTrace`、`SemanticPayload`、`PhysicalMappingReference` 和 `retrieval_content`；表示生成过程不得写回或重写这些字段。
3. 将 `representation_version` 与每个 Representation 绑定，并确保同一批次中版本一致。
4. 验证 `Embedding Capability` 返回的 Representation Value 合法、非空、满足 `RetrievalRepresentationValue` Contract、与输入 Record Identity 一一关联，并使用当前 `RepresentationVersion`。
5. 在单个 Record 失败、Capability 返回非法结果或版本不兼容时，停止当前完整构建；不得返回混有未表示 Record 的部分集合。
6. 在相同 Source Projection、Build Configuration 和 Representation Version 下，保持语义可重复；不要求任何基础设施内部二进制表示逐字节相同。
7. 不依据表示结果反向修改 Source Object、Metric Formula、Dimension Meaning、Physical Mapping 或 Relationship。

---

## 5. Output Contract（输出契约）

### 5.1 `RetrievalRepresentationValue`（检索表示值）

`RetrievalRepresentationValue` 是由 `Embedding Capability` 提供的逻辑 Typed Value（类型化逻辑值）：

- 必须合法、非空并满足当前 `RetrievalRepresentationValue` Contract；
- 不是自由 `dict`、自由 JSON 或隐式字段集合；
- 内部形式、变体和存储表达不在本 Module Spec 冻结；
- 不得携带或改写 Business Truth；
- 必须能在同一 `RepresentationVersion` 下作为后续 Retrieval Index Building 的 Contract Input；该要求通过本 Module 的类型、字段、非空和版本约束表达，不通过运行时调用下游 Capability 确认。

该抽象边界用于保留 Dense / Sparse / Hybrid 等技术决定的延后空间，不代表允许未定义的任意数据。

### 5.2 `RetrievalRepresentation`（检索表示）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Semantic Meaning（语义） | Constraint（约束） |
|---|---|---:|---|---|
| `record_identity` | `LogicalRecordIdentity` | Yes | 该表示对应的 Retrieval Record | 必须与输入 Record 完全一致 |
| `source_trace` | `SourceTrace` | Yes | 表示所依据的源追踪 | 必须与输入 Record 的 `source_trace` 一致；不得丢失 |
| `representation_version` | `RepresentationVersion` | Yes | 表示契约版本 | 必须等于 `BuildContext.representation_version` |
| `value` | `RetrievalRepresentationValue` | Yes | 后续 Index Building 可消费的检索表示 | 非空；必须满足 `RetrievalRepresentationValue` Contract |

### 5.3 `EmbeddedRetrievalRecord`（带表示的检索记录）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Constraint（约束） |
|---|---|---:|---|
| `record` | `RetrievalRecord` | Yes | 必须完整保留输入 Record，不得只保留表示值 |
| `representation` | `RetrievalRepresentation` | Yes | 必须与 `record.logical_record_identity` 一致 |

### 5.4 `EmbeddedRetrievalRecords`（带表示的检索记录集合）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Constraint（约束） |
|---|---|---:|---|
| `records` | `list[EmbeddedRetrievalRecord]` | Yes | 数量与输入 `RetrievalRecords.records` 完全一致；不允许缺失或重复 |
| `source_descriptors` | `list[SourceResourceDescriptor]` | Yes | 原样保留五类源资源描述，包括 Relationship Catalog 描述 |
| `build_context` | `BuildContext` | Yes | 原样保留本次表示生成的构建上下文 |

`EmbeddedRetrievalRecords` 是 Retrieval Index Building 的完整逻辑输入，不需要下游读取隐藏状态或回查上游临时变量。

---

## 6. Postconditions / Invariants（后置条件 / 不变量）

成功返回时必须始终成立：

1. `Embedding Coverage = 100%`：每个 Retrieval Record 都有且只有一个 Embedded Representation。
2. 每个 Representation 的 `record_identity` 与其 Record 一致，且 `source_trace` 未丢失。
3. Record 的 Semantic Payload、Physical Mapping Reference、Business Meaning 和 Source Trace 在嵌入前后保持一致。
4. 所有 Representation 使用同一个 `RepresentationVersion` 和同一个 `BuildContext`。
5. Representation 满足后续 Retrieval Index Building 的逻辑输入契约。
6. Relationship 不会因为表示生成而成为 Retrieval Record 或 Index Entry。
7. 相同 Contract Input、Build Configuration 和 Representation Version 应产生语义等价的表示集合。
8. 任一 Record 无法生成合法 Representation 时，整个 Module 失败，不返回部分成功集合。

---

## 7. Failure Contract（失败契约）

本 Module 使用 `01_RESOURCE_LOADING_AND_VALIDATION.md` 定义的 `OfflineBuildFailure` 公共结构，`failure_stage` 固定为 `EMBEDDING_GENERATION`。

### `INVALID_INPUT`（非法输入）

用于：Retrieval Record 不完整、Build Context 缺失、Record Identity 与 Source Trace 不一致、版本为空或输入含 Relationship 等情况。

### `DEPENDENCY_FAILURE`（依赖失败）

用于：`Embedding Capability` 不可用、超出其 Contract、返回空值、违反 `RetrievalRepresentationValue` Contract，或无法证明返回值属于请求的 Representation Version。

### `UNSUPPORTED`（不支持）

用于：请求当前 Module Contract 未支持的 Representation 类型、未知 Record Type、增量/部分表示等 V1 未冻结行为。

### `INTERNAL_FAILURE`（内部失败）

用于：输入合法且 Capability 合法返回，但模块无法维持一一关联、Payload Integrity 或完整性不变量。

失败不得被转化为“忽略该条 Record 后继续成功”。本 Module 不产生 User Clarification。

---

## 8. Dependencies（依赖）

本 Module 依赖：

- `RetrievalRecords` Contract：由 Retrieval Projection 提供；
- `Embedding Capability`（检索表示能力）：把 Record 转换为 `RetrievalRepresentationValue`；
- `RetrievalRepresentation` / `EmbeddedRetrievalRecords` Contract：规定本 Module 的类型化输出，并作为后续 Retrieval Index Building 的输入契约。

本 Module 只依赖 Capability / Contract，不绑定具体 Model Provider、Embedding Library、SDK、Framework、设备或运行平台。

---

## 9. Test / Evaluation（测试 / 评估）

### Deterministic Contract Test（确定性契约测试）

必须证明：

- 每个 Retrieval Record 都生成一个且只有一个 Representation；
- Record Identity、Source Trace、Semantic Payload 和 Physical Mapping Reference 在输出中保持一致；
- `RepresentationVersion` 与 Build Context 一致；
- 缺失、空值、非法版本或非法 Capability 输出会显式失败；
- 任一单条失败都不会产生部分成功的 `EmbeddedRetrievalRecords`；
- Relationship 不会进入表示集合；
- 相同输入和构建条件下，结果满足语义可重复要求。

### Retrieval Evaluation（检索评估）

Representation 的业务价值必须通过 Feature-Level Retrieval Evaluation 验证：四类 Record 均需观察 Candidate Retrieval Quality、Recall@K 和 MRR。测试 Representation Value 本身“存在”不能替代“正确候选能够被召回”的评估；具体阈值由 Acceptance Baseline 管理。

### Build-to-Retrieve Integration Evaluation（构建到检索集成评估）

必须使用真实 `EmbeddedRetrievalRecords` 继续构建、验证并消费最终 Retrieval Asset，证明表示、Payload、Identity 和 Source Trace 在完整链路中仍然关联。

---

## 10. Deferred Technical Decisions（延后技术决定）

以下决定留到 `Technology Selection / Implementation Design`：

- Embedding Model、Embedding Algorithm 及 Provider；
- Dense / Sparse / Hybrid Representation 的具体类别与内部字段；
- Representation Dimension、Tokenizer、Batch Size、Device、GPU / CPU；
- 生成调用的并发、超时、重试、缓存和成本策略；
- `RetrievalRepresentationValue` 的具体序列化和传输格式；
- Representation Version 的具体生成与发布策略；
- 任何具体 SDK、Framework、Runtime 或部署方案。
