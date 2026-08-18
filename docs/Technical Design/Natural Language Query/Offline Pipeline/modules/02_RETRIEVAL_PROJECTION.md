# Retrieval Projection Module Spec
# 检索投影模块规格

> **Status（状态）：** V1 Module Contract Design Baseline（V1 模块契约设计基线）
> **Version（版本）：** V1
> **Feature（所属功能）：** Offline Pipeline（离线链路）
> **Feature Architecture Reference（功能架构引用）：** `../ARCHITECTURE.md`
> **Feature Spec Reference（功能规格引用）：** `../FEATURE_SPEC.md`
> **Acceptance Reference（验收引用）：** `../ACCEPTANCE_AND_EVALUATION.md`
> **Module Standard Reference（模块标准引用）：** `../../../MODULE_CONTRACT_STANDARD.md`

---

## 1. Responsibility（职责）

本 Module 负责将 `ValidatedCatalogs` 中已经通过校验的三类 Source Object（Table、Column、Metric），确定性投影为独立的 `RetrievalRecord`（检索记录）。

本 Module 必须保证：

- 一个 Source Object 对应一个 Logical Retrieval Record；
- Retrieval Record 具有可被后续 Representation Generation 消费的检索内容；
- Source Object Identity、Semantic Payload、Physical Mapping Reference 和 Source Trace 完整保留；
- Projection 可以重组信息，但不得创造或修改业务事实。

本 Module 不负责：

- Resource Loading & Validation；
- 创建或修改 Table、Column 或 Metric；
- 创建、推断或裁决 Relationship；
- Embedding / Retrieval Representation Generation；
- Retrieval Index Building、Activation 或 Online Ranking；
- Schema Linking、Metric Resolution、SQL Generation 或 Query Execution。

---

## 2. Input Contract（输入契约）

### `ValidatedCatalogs`

输入必须是 `01_RESOURCE_LOADING_AND_VALIDATION.md` 定义的 `ValidatedCatalogs`。本 Module 依赖其以下字段：

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Constraint（约束） |
|---|---|---:|---|
| `build_context` | `BuildContext` | Yes | 从 `ValidatedCatalogs` 原样传递；所有输出 Record 共享同一 Context |
| `source_descriptors` | `list[SourceResourceDescriptor]` | Yes | 必须包含四份当前权威资源，包含 Relationship Catalog 描述但不把它作为可检索对象 |
| `tables` | `list[TableSourceObject]` | Yes | 当前 Table Catalog 的完整已校验集合 |
| `columns` | `list[ColumnSourceObject]` | Yes | 当前 Column Catalog 的完整已校验集合 |
| `relationships` | `list[RelationshipEntry]` | Yes | 仅用于保持权威关系边界；不得投影为 Record |
| `metrics` | `list[MetricSourceObject]` | Yes | 当前 Metric Catalog 的完整已校验集合 |

除 `ValidatedCatalogs` 外，本 Module 不接受隐式全局目录、旧索引或未声明资源。

---

## 3. Preconditions（前置条件）

进入本 Module 前必须满足：

1. `ValidatedCatalogs` 已由 Resource Loading & Validation 成功产生。
2. 三类可检索 Source Object 的 Identity、Payload 和正式 Physical Mapping 已经通过上游校验。
3. 所有 Source Resource 均为当前权威资源；不存在 Current / Legacy 混用。
4. Relationship Catalog 已可被上游识别，但本 Module 不需要把 Relationship 转换为 Retrieval Record。
5. 本次投影范围是 Offline Pipeline V1 的三类记录；不要求处理其他对象类型。

---

## 4. Processing Responsibilities（处理职责）

本 Module 必须完成以下行为：

1. 从 Table、Column、Metric 三类集合中逐一读取 Source Object。
2. 为每个 Source Object 生成且仅生成一个 `LogicalRecordIdentity`。
3. 生成非空 `retrieval_content`；内容只能由 Source Object 的正式名称、物理信息、描述、别名、业务定义和其他已验证字段重组而来。
4. 携带 Source Resource 中已存在的 Alias；如需要表达由正式名称直接得到的检索文本，必须标记为源名称派生，不得冒充业务别名。
5. 将 Source Object 的完整 `SourceObjectPayload` 作为 Typed Semantic Payload 传递；不得修改 Metric Formula、Column / Field Meaning、Filter Rule、Time Definition 或其他业务字段。
6. 形成 `PhysicalMappingReference`：
   - Table / Column 使用其自身已验证的物理对象；
   - Metric 使用上游已验证的语义到物理映射；
   - Metric Dependency 仍是语义依赖，不转换为 Relationship；
   - 不通过名称相似、字段同名或其他猜测创建 Join Relationship。
7. 根据 `source_descriptors` 与 Source Object Identity 形成 `SourceTrace`。
8. 保留四份源资源描述，确保 Relationship Catalog 的来源仍可追踪，即使 Relationship 不进入 Record。
9. 以独立 Record 集合输出；不得把多个 Source Object 合并为一个超级文档或超级 Record。

---

## 5. Output Contract（输出契约）

### 5.1 `LogicalRecordIdentity`（逻辑记录标识）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Constraint（约束） |
|---|---|---:|---|
| `record_type` | Enum | Yes | `TABLE`、`COLUMN` 或 `METRIC` |
| `record_key` | `string` | Yes | 非空；同一构建内唯一；对同一 Source Object 保持稳定；具体生成算法不在本 Spec 冻结 |

### 5.2 `RetrievalAlias`（检索别名）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Constraint（约束） |
|---|---|---:|---|
| `value` | `string` | Yes | 非空；同一 Record 内不重复 |
| `origin` | Enum | Yes | `AUTHORITATIVE_ALIAS` 或 `SOURCE_NAME_DERIVATION` |

`AUTHORITATIVE_ALIAS` 只能来自正式 Semantic Resource；`SOURCE_NAME_DERIVATION` 只能表达对源名称的确定性重组，不得创造新的业务同义词。

### 5.3 `PhysicalMappingReference`（物理映射引用）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Semantic Meaning（语义） | Constraint（约束） |
|---|---|---:|---|---|
| `physical_targets` | `list[PhysicalObjectIdentity]` | Yes | 该 Record 对应的已验证物理对象 | 至少一个；每个目标必须存在于 Validated Schema Metadata |

此对象只表达正式 Physical Mapping 的引用，不表达 Join Graph。不得包含 Relationship Identity，也不得由本 Module 生成关系。

### 5.4 `SourceTrace`（来源追踪）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Constraint（约束） |
|---|---|---:|---|
| `source_resource` | `SourceResourceDescriptor` | Yes | 必须来自 `ValidatedCatalogs.source_descriptors`，且为当前权威资源 |
| `source_object_identity` | `SourceObjectIdentity` | Yes | 必须与 Record 的 Source Object 一致 |

### 5.5 `RetrievalRecord`（检索记录）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Semantic Meaning（语义） | Constraint（约束） |
|---|---|---:|---|---|
| `logical_record_identity` | `LogicalRecordIdentity` | Yes | Runtime Projection 的逻辑记录身份 | `record_type` 与 Source Object 类型一致 |
| `record_type` | Enum | Yes | 当前 Record 的对象类型 | 只允许三类 V1 类型 |
| `source_object_identity` | `SourceObjectIdentity` | Yes | 被投影的权威源对象 | 与 `source_trace.source_object_identity` 一致 |
| `retrieval_content` | `string` | Yes | 供后续 Retrieval Representation 使用的检索内容 | 非空；只能由源事实重组 |
| `aliases` | `list[RetrievalAlias]` | Yes | 可用于候选发现的源别名或源名称派生表达 | 可以为空；不得包含未经授权的业务同义词 |
| `semantic_payload` | 对应的 `SourceObjectPayload` 变体 | Yes | Online Runtime 可消费的源语义/物理载荷 | 类型必须与 `record_type` 一致；不得改写源事实 |
| `physical_mapping_reference` | `PhysicalMappingReference` | Yes | 语义对象到物理结构的正式映射引用 | 非空且全部已验证 |
| `source_trace` | `SourceTrace` | Yes | Record 到正式 Source Resource 的追踪关系 | 100% 可解析；不得引用 Legacy Resource |

### 5.6 `RetrievalRecords`（检索记录集合）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Constraint（约束） |
|---|---|---:|---|
| `records` | `list[RetrievalRecord]` | Yes | 必须覆盖当前三类可检索 Source Object 的完整集合；不得有 Relationship Record |
| `source_descriptors` | `list[SourceResourceDescriptor]` | Yes | 从 `ValidatedCatalogs` 传递四份源资源描述；恰好四种且不改变其语义 |
| `build_context` | `BuildContext` | Yes | 本次完整构建的身份与条件 | 从 `ValidatedCatalogs` 原样传递；不得由 Projection 修改 |

`RetrievalRecords` 是下游 Embedding Generation 的完整逻辑输入；列表顺序不是业务事实，不能成为 Record Identity 或业务语义的一部分。

---

## 6. Postconditions / Invariants（后置条件 / 不变量）

成功返回 `RetrievalRecords` 时必须始终成立：

1. `Record Coverage = 100%`：每个正式 Table、Column、Metric 都有且只有一个 Logical Retrieval Record。
2. `One Source Object → One Logical Retrieval Record`：不合并多个 Source Object，也不因重复构建产生逻辑重复 Record。
3. 每个 Record 的 `record_type`、`source_object_identity`、`logical_record_identity` 和 `source_trace` 相互一致。
4. 每个 Record 的 `semantic_payload` 与源对象语义等价；不改变 Metric Formula、Column / Field Meaning、Physical Mapping 或 Filter Rule。
5. 每个 Record 至少有一个已验证的 Physical Mapping Target；映射引用不包含猜测出的 Relationship。
6. 每个 Record 的 `source_trace` 可回溯到当前权威 Source Resource；`Traceability Coverage = 100%`。
7. Relationship Catalog 仍保持独立，不产生 Relationship Retrieval Record。
8. `RetrievalRecords` 可以从 `ValidatedCatalogs` 重新生成，不成为新的 Business Source of Truth。
9. 无法保持上述不变量时必须返回失败，不得返回部分成功集合。

---

## 7. Failure Contract（失败契约）

本 Module 使用 `01_RESOURCE_LOADING_AND_VALIDATION.md` 定义的 `OfflineBuildFailure` 公共结构，`failure_stage` 固定为 `RETRIEVAL_PROJECTION`。

### `INVALID_INPUT`（非法输入）

用于：输入不是已校验目录、三类对象集合缺失、对象类型与 Payload 不匹配、源描述无法关联等情况。

### `RESOLUTION_FAILURE`（解析失败）

用于：无法为 Source Object 建立唯一 Record Identity、无法形成非空且可追踪的 Retrieval Content、无法建立合法 Physical Mapping Reference 或 Source Trace 等情况。

### `UNSUPPORTED`（不支持）

用于：要求投影 Relationship、未知 Source Object 类型、合并成超级 Record、或处理超出 V1 范围的资源对象等情况。

### `INTERNAL_FAILURE`（内部失败）

用于：输入合法但模块无法保持 One-to-One、Payload Integrity 或其他自身 Invariant 的情况。

本 Module 没有 User Clarification（用户澄清）责任；投影失败属于系统内部失败，不得要求用户重新定义已经确认的业务意图。

---

## 8. Dependencies（依赖）

本 Module 依赖：

- `ValidatedCatalogs` Contract：由 Resource Loading & Validation 提供；
- `Physical Mapping` 的已验证逻辑引用：通过 `ValidatedCatalogs` 传递，不直接访问外部存储；
- `Source Trace` 的逻辑类型：使用上游源资源描述和对象标识。

本 Module 不直接依赖外部技术 Capability，不直接依赖 Online Retrieval，也不依赖任何 Vendor / Framework / SDK。

---

## 9. Test / Evaluation（测试 / 评估）

### Deterministic Contract Test（确定性契约测试）

必须证明：

- 三类 Source Object 的 Record Coverage 为 100%；
- One Object → One Logical Record，且重复投影不产生逻辑重复；
- Record Identity、Source Object Identity、Record Type 和 Source Trace 始终一致；
- Semantic Payload、Physical Mapping Reference 和 Alias 不被修改或凭空创造；
- Retrieval Content 由源事实重组且非空；
- Relationship 不进入 Retrieval Record；
- Legacy Resource 不进入输出；
- 任一关键字段无法建立时显式失败，不产生部分结果。

### Retrieval Evaluation（检索评估）

本 Module 的投影结果必须进入 Feature-Level Retrieval Evaluation，覆盖 Table、Column、Metric 三类对象；业务 Dimension 场景通过 Column / Field Retrieval 评估，不形成独立维度检索记录。Recall@K、MRR 及其 Release Threshold 由 Feature Acceptance Baseline 管理，本 Module 不重复冻结数值。

### Build-to-Retrieve Integration Evaluation（构建到检索集成评估）

必须证明真实 `RetrievalRecords` 可以继续被 Embedding Generation、Retrieval Index Building 和 Retrieval Asset Validation 消费，并最终返回预期候选；只证明 Record 被创建，不等于证明 Online Retrieval 质量通过。

---

## 10. Deferred Technical Decisions（延后技术决定）

以下决定留到 `Technology Selection / Implementation Design`：

- Retrieval Content 的具体文本拼接、排序、格式化和规范化算法；
- Alias 标准化、分词、同义词扩展和多语言处理策略；
- `LogicalRecordIdentity.record_key` 的具体生成算法；
- Record 与 Payload 的具体序列化格式；
- 批量投影、并发、超时和重试策略；
- Retrieval Representation、Index Storage、Ranking 和 Online Query 的具体技术实现；
- 任何具体数据库、向量存储、Embedding Model、SDK 或 Framework。
