# Retrieval Index Building Module Spec
# 检索索引构建模块规格

> **Status（状态）：** V1 Module Contract Design Baseline（V1 模块契约设计基线）
> **Version（版本）：** V1
> **Feature（所属功能）：** Offline Pipeline（离线链路）
> **Feature Architecture Reference（功能架构引用）：** `../ARCHITECTURE.md`
> **Feature Spec Reference（功能规格引用）：** `../FEATURE_SPEC.md`
> **Acceptance Reference（验收引用）：** `../ACCEPTANCE_AND_EVALUATION.md`
> **Module Standard Reference（模块标准引用）：** `../../../MODULE_CONTRACT_STANDARD.md`

---

## 1. Responsibility（职责）

本 Module 负责将 `EmbeddedRetrievalRecords` 构建为 Online Retrieval（在线检索）可消费的 `BuiltRetrievalAssets`（已构建检索资产），形成统一的逻辑 Retrieval Space（检索空间），并保留：

- Retrieval Record；
- Retrieval Representation；
- Semantic Payload；
- Physical Mapping Reference；
- Logical Identity；
- Source Trace；
- Build Metadata（构建元数据）。

V1 采用 Full Rebuild（全量重建）：每次构建都形成当前权威输入的完整资产集合。

本 Module 可以通过 `Retrieval Index Capability` 保存或暂存候选资产，但输出的 `BuiltRetrievalAssets` 必须处于未验证状态，不能绕过 Retrieval Asset Validation 直接成为有效 Online Asset。

本 Module 不负责：

- Resource Loading、Retrieval Projection 或 Embedding Generation；
- 定义业务事实、修改 Semantic Payload 或猜测 Relationship；
- Online Ranking、Top-K、Threshold、Schema Linking 或 Metric Resolution；
- 设计物理 Collection、Index Algorithm 或存储产品；
- 在 Validation 之前激活或对外提供未验证资产；
- 增量更新、部分更新、调度器或通用 ETL 平台。

---

## 2. Input Contract（输入契约）

### `EmbeddedRetrievalRecords`

输入必须是 `03_EMBEDDING_GENERATION.md` 定义的完整对象。

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Constraint（约束） |
|---|---|---:|---|
| `records` | `list[EmbeddedRetrievalRecord]` | Yes | 覆盖四类 Record；每个 Record 有且只有一个合法 Representation |
| `source_descriptors` | `list[SourceResourceDescriptor]` | Yes | 恰好五类当前源资源描述；包括 Relationship Catalog |
| `build_context` | `BuildContext` | Yes | `build_mode=FULL_REBUILD`；同批次一致 |

### 2.1 `BuildIdentity` 等逻辑类型

本 Module 使用上游 Build Context 中的以下逻辑类型：

- `BuildIdentity`：本次完整构建的逻辑身份；
- `BuildConfigurationIdentity`：影响构建结果的相关配置身份；
- `RepresentationVersion`：表示契约版本。

这些类型只要求稳定、非空和可追踪，不冻结具体值格式或生成算法。

---

## 3. Preconditions（前置条件）

进入本 Module 前必须满足：

1. 所有 Embedded Record 均通过 Embedding Generation Contract。
2. `records` 内不存在缺失、重复或未知 Record Type；不包含 Relationship。
3. 每条 Record 的 Representation 与 Record Identity、Source Trace 和 Representation Version 一致。
4. `source_descriptors` 完整，且其内容与各 Record 的 Source Trace 相容。
5. `build_context.build_mode=FULL_REBUILD`，并且 Build Identity、Build Configuration Identity 和 Representation Version 完整。
6. `Retrieval Index Capability` 支持构建逻辑统一检索空间，并能区分未验证候选与已验证资产。
7. 本次构建不得依赖上一版 Index 才能产生完整结果；上一版只用于失败保护，不作为新事实来源。

---

## 4. Processing Responsibilities（处理职责）

本 Module 必须完成：

1. 对每个 `EmbeddedRetrievalRecord` 建立一个且只有一个逻辑 Index Entry。
2. 保持 Embedded Record 中的 Record、Representation、Payload、Identity、Physical Mapping Reference 和 Source Trace 的完整关联。
3. 将 Table、Column、Metric、Dimension 四类 Entry 纳入统一逻辑 Retrieval Space；不要求也不暗示某一种物理存储组织。
4. 形成 `IndexMetadata` 与 `BuildMetadata`，记录本次资产的逻辑身份、输入来源、构建身份、配置身份和 Representation Version。
5. 执行 Full Rebuild：当前输入中的所有 Record 必须进入候选资产；不得以已有索引内容补齐本次缺失输入，也不得只构建部分类型后报告完整成功。
6. 通过 `Retrieval Index Capability` 保存或暂存候选资产时，保持候选状态为未验证；不得在 Validation 前使其成为有效在线资产。
7. 新 Build 失败时，不得使已经存在的上一版 Validated Retrieval Asset 自动失效。
8. 不创建 Relationship Entry，不依据 Representation 或相似度生成正式 Join Relationship。
9. 任一 Entry、Metadata、Capability 输出不完整时，整个 Build 失败。

---

## 5. Output Contract（输出契约）

### 5.1 `AssetIdentity`（资产标识）

`AssetIdentity` 是标识一个完整 Built Retrieval Asset Set 的稳定非空 Machine Value。它不规定具体 ID 算法、物理路径或存储名称。

### 5.2 `AssetState`（资产状态）

本 Module 输出的 `AssetState` 必须为：

- `BUILT_UNVALIDATED`：已完成构建但尚未通过 Retrieval Asset Validation；不可作为有效 Online Asset。

后续 `ValidatedRetrievalAssets` 可以将同一逻辑资产标记为 `VALIDATED`。`ACTIVE` 的具体激活实现不在本 Module Contract 冻结。

### 5.3 `IndexMetadata`（索引元数据）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Semantic Meaning（语义） | Constraint（约束） |
|---|---|---:|---|---|
| `logical_index_identity` | `string` | Yes | 统一逻辑检索空间的身份 | 非空；不等于具体物理 Collection Name |
| `asset_identity` | `AssetIdentity` | Yes | 所属完整资产集合身份 | 与外层资产一致 |
| `indexed_record_types` | `list[enum]` | Yes | 已构建的 Record 类型集合 | 恰好包含 `TABLE`、`COLUMN`、`METRIC`、`DIMENSION` |
| `indexed_record_count` | `integer` | Yes | 已写入逻辑索引的 Record 数量 | 大于等于 0；必须等于 Entry 数量 |
| `representation_version` | `RepresentationVersion` | Yes | 所有 Entry 使用的表示契约版本 | 批次内一致 |
| `asset_state` | Enum | Yes | 当前资产能否进入验证/激活流程 | 输出固定为 `BUILT_UNVALIDATED` |

### 5.4 `BuildMetadata`（构建元数据）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Semantic Meaning（语义） | Constraint（约束） |
|---|---|---:|---|---|
| `asset_identity` | `AssetIdentity` | Yes | 本次构建产物身份 | 与 `IndexMetadata` 一致 |
| `build_identity` | `BuildIdentity` | Yes | 本次完整构建身份 | 非空 |
| `build_configuration_identity` | `BuildConfigurationIdentity` | Yes | 本次构建条件身份 | 非空 |
| `build_mode` | Enum | Yes | 本次构建模式 | 固定为 `FULL_REBUILD` |
| `representation_version` | `RepresentationVersion` | Yes | 资产使用的表示版本 | 与 `IndexMetadata` 和所有 Representation 一致 |
| `source_descriptors` | `list[SourceResourceDescriptor]` | Yes | 资产构建依据的五类源资源 | 恰好五类；每个指纹/版本来自输入，不得现场伪造 |

### 5.5 `BuiltRetrievalAssets`（已构建检索资产）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Semantic Meaning（语义） | Constraint（约束） |
|---|---|---:|---|---|
| `asset_identity` | `AssetIdentity` | Yes | 完整资产集合身份 | 与所有元数据一致 |
| `entries` | `list[EmbeddedRetrievalRecord]` | Yes | 逻辑检索空间中的完整 Record Entry | 每个 Embedded Record 恰好一次；不含 Relationship |
| `index_metadata` | `IndexMetadata` | Yes | 逻辑索引描述 | 必须反映 `entries` 实际内容 |
| `build_metadata` | `BuildMetadata` | Yes | 可追踪构建来源与条件 | 必须完整；不依赖隐藏状态 |

输出成功只表示候选资产已完整构建，不表示它已经通过 Validation 或已经 Active。

---

## 6. Postconditions / Invariants（后置条件 / 不变量）

成功返回 `BuiltRetrievalAssets` 时必须成立：

1. Entry Coverage 与输入 `EmbeddedRetrievalRecords` 完全一致；不存在丢失、重复或额外 Entry。
2. 每个 Entry 保持 Record、Representation、Payload、Identity、Physical Mapping Reference 和 Source Trace 的完整关联。
3. 四类 V1 Record 均可在 `indexed_record_types` 中识别；Relationship 不存在于 Entries。
4. `indexed_record_count`、`asset_identity`、`representation_version` 和 `asset_state` 与实际 Entries 一致。
5. `BuildMetadata` 能够追踪 Source Resource、Build Configuration 和 Representation Version。
6. 资产是由当前输入完整重建的派生产物，不是新的 Business Source of Truth。
7. 输出资产状态为 `BUILT_UNVALIDATED`；未经过 Retrieval Asset Validation 的资产不得进入有效 Online Runtime。
8. 当前 Build 失败时，上一版有效资产的有效性必须保持不变。
9. 无法保持完整性时必须返回失败，不得返回 Partial Build + Full Success。

---

## 7. Failure Contract（失败契约）

本 Module 使用 `01_RESOURCE_LOADING_AND_VALIDATION.md` 定义的 `OfflineBuildFailure` 公共结构，`failure_stage` 固定为 `RETRIEVAL_INDEX_BUILDING`。

### `INVALID_INPUT`（非法输入）

用于：Embedded Record 不完整、版本不一致、源资源描述缺失、Build Mode 非 `FULL_REBUILD`、或输入含 Relationship 等情况。

### `RESOLUTION_FAILURE`（解析失败）

用于：无法为 Entry 建立稳定逻辑归属、无法形成一致 Index Metadata、或无法建立完整 Build Metadata 等情况。

### `DEPENDENCY_FAILURE`（依赖失败）

用于：`Retrieval Index Capability` 不可用、拒绝合法输入、返回不完整资产，或无法保持候选资产未验证状态等情况。

### `UNSUPPORTED`（不支持）

用于：要求增量更新、部分更新、Relationship Retrieval、复杂物理路由或其他不属于 V1 Full Rebuild Contract 的行为。

### `INTERNAL_FAILURE`（内部失败）

用于：输入和 Capability 均合法，但模块无法保持 Entry、Payload、Identity、Trace 或 Build Metadata 不变量。

失败不得激活新资产，也不得自动删除或使上一版有效资产失效。

---

## 8. Dependencies（依赖）

本 Module 依赖：

- `EmbeddedRetrievalRecords` Contract：由 Embedding Generation 提供；
- `Retrieval Index Capability`（检索索引能力）：构建、保存或暂存统一逻辑 Retrieval Asset，并支持未验证状态与失败保护；
- `Build / Source Metadata` 逻辑类型：用于形成可追踪的 Build Metadata。

本 Module 不绑定：

- 具体 Vector Database、Physical Collection、Index Algorithm、Distance Metric、Shard 或 Replica；
- 具体 Point ID、Asset Version 或 Fingerprint Algorithm；
- 具体 SDK、Framework、Serialization Library 或 Deployment Platform。

---

## 9. Test / Evaluation（测试 / 评估）

### Deterministic Contract Test（确定性契约测试）

必须证明：

- Full Rebuild 不依赖已有 Index，并能从当前完整输入形成完整资产；
- Entry Coverage、四类 Record Type 和 Entry Count 正确；
- One Embedded Record → One Index Entry；
- Record、Representation、Payload、Identity 和 Source Trace 完整关联且未被修改；
- Relationship 不进入 Index；
- Build Metadata 能追踪 Source Resource、Build Configuration 和 Representation Version；
- 未验证资产不会被当作有效在线资产；
- Build 失败时不会破坏上一版有效资产；
- Index Capability 返回部分结果或非法结果时显式失败。

### Retrieval Evaluation（检索评估）

本 Module 不用“成功写入索引”替代 Retrieval Quality Evaluation。四类资产必须继续按 Acceptance Baseline 观察 Recall@K、MRR 和 Critical Bad Case；具体阈值由 Feature-Level Acceptance 管理。

### Build-to-Retrieve Integration Evaluation（构建到检索集成评估）

必须验证：

```text
ValidatedCatalogs
→ RetrievalRecords
→ EmbeddedRetrievalRecords
→ BuiltRetrievalAssets
→ Retrieval Asset Validation
→ Activate
→ Online Retrieval
→ Expected Candidate
```

重点证明 Online Retrieval 消费的是构建出的有效逻辑资产，而不是隐藏的旧索引或未经验证的部分资产。

---

## 10. Deferred Technical Decisions（延后技术决定）

以下决定留到 `Technology Selection / Implementation Design`：

- Vector Database、Physical Collection 数量/名称/分片/副本和存储布局；
- Index Algorithm、Distance Metric、Index Parameter 和 Ranking 实现；
- Point / Entry ID 的具体算法；
- Asset Version、Build Identity 和 Source Fingerprint 的具体生成策略；
- Candidate Asset 的具体暂存、发布、原子激活和上一版保护机制；
- Asset Serialization、Batch Size、Concurrency、Timeout 和 Retry；
- Online Retrieval Protocol、Top-K、Threshold、Ranking 和部署方式。

---
