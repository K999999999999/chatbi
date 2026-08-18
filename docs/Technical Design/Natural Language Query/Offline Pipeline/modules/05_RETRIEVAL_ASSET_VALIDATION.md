# Retrieval Asset Validation Module Spec
# 检索资产验证模块规格

> **Status（状态）：** V1 Module Contract Design Baseline（V1 模块契约设计基线）
> **Version（版本）：** V1
> **Feature（所属功能）：** Offline Pipeline（离线链路）
> **Feature Architecture Reference（功能架构引用）：** `../ARCHITECTURE.md`
> **Feature Spec Reference（功能规格引用）：** `../FEATURE_SPEC.md`
> **Acceptance Reference（验收引用）：** `../ACCEPTANCE_AND_EVALUATION.md`
> **Module Standard Reference（模块标准引用）：** `../../../MODULE_CONTRACT_STANDARD.md`

---

## 1. Responsibility（职责）

本 Module 负责在资产进入 Online Runtime 前，对 `BuiltRetrievalAssets` 执行最终确定性 Contract Validation（契约验证），并在所有硬契约通过后输出 `ValidatedRetrievalAssets`（已验证检索资产）。

本 Module 必须验证：

- Source / Asset Alignment（源与资产对齐）；
- Record Coverage（记录覆盖）；
- One Object → One Logical Record（一对象一逻辑记录）；
- Payload Integrity（载荷完整性）；
- Identity Integrity（标识完整性）；
- Representation Integrity（检索表示完整性）；
- Index Completeness（索引完整性）；
- Source Trace（来源追踪）；
- Relationship Boundary（关系边界）；
- Build Metadata Integrity（构建元数据完整性）；
- Online Retrieval Consumability（在线检索可消费契约）。

本 Module 的职责终点是产生 `ValidatedRetrievalAssets`：将候选资产从 `BUILT_UNVALIDATED` 变为逻辑上的 `VALIDATED + ELIGIBLE`。这是 Validation（验证）成功后的输出，不代表已经完成 Physical Activation（物理激活）。

### Validation Boundary（验证边界）

本 Module 只负责：

```text
BUILT_UNVALIDATED
        ↓
VALIDATED + ELIGIBLE
```

`VALIDATED` 到 `ACTIVE` 的 Physical Activation 属于 Validation 成功后的 Feature / Application Orchestration Boundary（功能 / 应用编排边界）及其对应的 Capability（能力）。它不是本 Module 的内部 Processing Responsibility（处理职责），也不新增第六个 Core Module（核心模块）。

本 Module 不负责：

- 修改上游 Source Resource 或修复业务定义；
- 重新投影 Record、重新生成 Representation 或重建 Index；
- 创造 Relationship 或替换 Authoritative Relationship Catalog；
- 以 Retrieval Quality 平均值掩盖 Hard Contract Failure；
- 直接决定 Online Ranking、Top-K、Threshold 或业务解析结果；
- 在验证失败时将候选资产标记为有效或激活。

---

## 2. Input Contract（输入契约）

### `AssetValidationInput`（资产验证输入）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Semantic Meaning（语义） | Constraint（约束） |
|---|---|---:|---|---|
| `built_assets` | `BuiltRetrievalAssets` | Yes | 待验证的完整候选资产 | `asset_state=BUILT_UNVALIDATED`；不得是已激活或部分资产 |
| `validated_catalogs` | `ValidatedCatalogs` | Yes | 验证资产来源与关系边界的当前权威目录 | 必须由 Resource Loading & Validation 成功产生 |

`validated_catalogs` 不会被并入 Retrieval Index，也不会因为验证而成为新的合并事实源。它只作为 Source / Asset Alignment 和 Relationship Boundary 的权威参照。

---

## 3. Preconditions（前置条件）

进入本 Module 前必须满足：

1. `built_assets` 已由 Retrieval Index Building 产生，且其状态为 `BUILT_UNVALIDATED`。
2. `validated_catalogs` 覆盖同一构建所依据的四份当前权威 Source Resource。
3. `built_assets.build_metadata`、`index_metadata`、Entries 和 `validated_catalogs.source_descriptors` 可被显式比较。
4. 输入中不存在需要通过猜测、补写或读取 Legacy Resource 才能验证的字段。
5. `Retrieval Index Capability` 能够提供 Built / Validated Retrieval Asset 的逻辑访问能力，并支持 Asset Validation 所需的 Online Retrieval Consumability Contract 检查或确认；该前置条件不要求本 Module 执行 Physical Activation，也不要求预先冻结具体物理存储机制。
6. 本次验证针对 V1 Full Rebuild；增量、部分资产或多版本并行在线服务不属于当前输入。

---

## 4. Processing Responsibilities（处理职责）

本 Module 必须按以下顺序完成硬契约验证：

1. **Source / Build Metadata Alignment**：比较 `source_descriptors`、Source Version、Source Fingerprint、Build Identity、Build Configuration Identity、Representation Version 和 Asset Identity；发现不一致即失败。
2. **Record Coverage**：将 `validated_catalogs` 中三类当前可检索 Source Object 与资产 Entries 对齐，要求覆盖 100%。
3. **One Object, One Logical Record**：验证每个 Source Object 恰好对应一个 Logical Record，且没有由重复构建产生的逻辑重复。
4. **Identity Integrity**：验证 `record_type`、`logical_record_identity`、`source_object_identity`、Entry 归属和 `asset_identity` 一致。
5. **Payload Integrity**：逐条比较 Entry 中的 Semantic Payload 与对应权威 Source Object，确认 Metric Formula、Column / Field Meaning、Filter Rule、Time Definition、物理字段信息和其他正式语义没有被改变。
6. **Physical Mapping Integrity**：确认 `PhysicalMappingReference` 的所有目标仍存在且与当前权威映射一致；不得出现静默替换。
7. **Representation Integrity**：确认每个 Record 都有合法 Representation，Representation Identity、Source Trace 和 `RepresentationVersion` 与 Build Metadata 一致。
8. **Index Completeness**：确认三类 Record 均存在，Entry Count、Record Type Coverage 和 Index Metadata 一致，不能以部分构建报告完整成功。
9. **Source Trace**：确认每个 Entry 能追踪到当前正式 Source Resource；`Traceability Coverage = 100%`。
10. **Relationship Boundary**：确认 Relationship Catalog 在 `validated_catalogs` 中存在且合法，同时确认资产 Entries 中不存在 Relationship Record，Retrieval 没有创造 Join。
11. **Online Retrieval Consumability**：确认输出包含 Online Retrieval 所需的完整 Record、Representation、Payload、Identity、Trace 和 Index Metadata；必要的 Capability Contract 检查失败时，不能输出 Validated Asset。
12. 所有检查通过后，复制逻辑资产内容形成 `ValidatedRetrievalAssets`，只改变验证状态和验证标记，不修改业务内容。
13. 本 Module 在产生 `ValidatedRetrievalAssets` 后结束；后续 `VALIDATED` 到 `ACTIVE` 的 Physical Activation 由 Feature / Application Orchestration Boundary 通过对应 Capability 负责。
14. 验证失败时不改变 Activation State、不执行 Physical Activation，并保持已有上一版有效资产不受影响。

---

## 5. Output Contract（输出契约）

### 5.1 `ValidationMetadata`（验证元数据）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Semantic Meaning（语义） | Constraint（约束） |
|---|---|---:|---|---|
| `validation_status` | Enum | Yes | 硬契约验证结果 | 成功输出固定为 `VALIDATED` |
| `activation_eligibility` | Enum | Yes | 是否允许进入后续激活边界 | 成功输出固定为 `ELIGIBLE`；不等于已完成物理激活 |

### 5.2 `ValidatedRetrievalAssets`（已验证检索资产）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Semantic Meaning（语义） | Constraint（约束） |
|---|---|---:|---|---|
| `asset_identity` | `AssetIdentity` | Yes | 已验证资产集合身份 | 与输入 `built_assets` 一致 |
| `entries` | `list[EmbeddedRetrievalRecord]` | Yes | 可供 Online Retrieval 消费的完整逻辑 Entry | 与输入资产语义等价；三类完整；无 Relationship |
| `index_metadata` | `IndexMetadata` | Yes | 已验证逻辑检索空间描述 | `asset_state=VALIDATED`；计数和类型覆盖正确 |
| `build_metadata` | `BuildMetadata` | Yes | 已验证构建来源与条件 | 与输入及 `validated_catalogs` 一致 |
| `validation_metadata` | `ValidationMetadata` | Yes | 资产通过硬契约并具备激活资格 | 只有全部验证通过才可存在 |

成功语义：

- `entries`、Payload、Representation、Identity、Source Trace 和 Build Metadata 与 `BuiltRetrievalAssets` 保持语义等价；
- 资产状态从 `BUILT_UNVALIDATED` 进入逻辑 `VALIDATED`；
- 只有该输出可以被后续 Activation Capability 接受；接受输出与执行 Physical Activation 属于 Feature / Application Orchestration Boundary，不属于本 Module 内部处理；
- `Relationship Catalog` 仍由 `validated_catalogs` 独立维护，不被复制成 Retrieval Record。

### 5.3 Failure Output（失败输出）

验证失败时输出 `OfflineBuildFailure`，不输出 `ValidatedRetrievalAssets`。失败对象使用 `01_RESOURCE_LOADING_AND_VALIDATION.md` 的公共结构，`failure_stage` 固定为 `RETRIEVAL_ASSET_VALIDATION`。

---

## 6. Postconditions / Invariants（后置条件 / 不变量）

成功返回时必须始终成立：

1. Hard Contract Gate 全部通过；所有确定性硬契约为 100% Pass。
2. Record Coverage、Traceability Coverage、Identity Integrity 和 Payload Integrity 均为 100%。
3. 每个正式 Table、Column、Metric 恰好对应一个逻辑 Record；不存在逻辑重复或虚构对象。
4. 每个 Representation 与 Record Identity、Source Trace、Representation Version 保持完整关联。
5. `IndexMetadata`、`BuildMetadata`、`AssetIdentity` 与实际资产内容一致。
6. Relationship Catalog 保持权威且独立；资产中不存在 Relationship Retrieval Record，也不由 Retrieval 裁决 Join。
7. 没有任何 Source Truth Violation、Legacy Resource 覆盖或静默 Semantic Change。
8. `validation_status=VALIDATED` 且 `activation_eligibility=ELIGIBLE`；未通过验证的资产不可获得该状态。
9. 输出资产可被 Online Retrieval Capability 消费；Online Retrieval 的质量门槛仍由 Feature Acceptance / Retrieval Evaluation 定义。
10. 验证失败不会破坏上一版 Validated Asset，也不会将新候选报告为成功。

---

## 7. Failure Contract（失败契约）

### `INVALID_INPUT`（非法输入）

用于：输入不是未验证的完整候选资产、目录不完整、资产状态错误、Build Metadata 缺失或验证输入无法比较等情况。

### `RESOLUTION_FAILURE`（解析失败）

用于：Source / Asset 无法对齐、Record Coverage 不足、One Object → One Record 违反、Payload 或 Physical Mapping 不一致、Source Trace 缺失、Representation 不完整、Index Metadata 不一致或 Relationship Boundary 违反等情况。

### `DEPENDENCY_FAILURE`（依赖失败）

用于：`Retrieval Index Capability` 无法提供逻辑资产访问能力、无法支持 Online Retrieval Consumability Contract 检查，或无法提供后续 Activation 所需的 Capability Boundary 等情况；这不表示本 Module 负责执行 Activation。

### `UNSUPPORTED`（不支持）

用于：输入是增量/部分构建、包含 Relationship Retrieval、要求多版本并行在线服务或要求本 Module 处理 V1 未冻结能力等情况。

### `INTERNAL_FAILURE`（内部失败）

用于：所有输入和外部能力均满足 Contract，但模块自身无法维持验证结果或状态不变量。

任何失败都必须 Fail Closed：不得通过删除问题 Entry、猜测来源、修改 Payload 或忽略失败来生成 `ValidatedRetrievalAssets`。

本 Module 不产生 User Clarification；它报告的是系统资产契约失败。

---

## 8. Dependencies（依赖）

本 Module 依赖：

- `BuiltRetrievalAssets` Contract：由 Retrieval Index Building 提供；
- `ValidatedCatalogs` Contract：由 Resource Loading & Validation 提供；
- `Retrieval Index Capability`（检索索引能力）：提供 Built / Validated Retrieval Asset 的逻辑访问能力，支持 Asset Validation 所需的可检查状态，并提供后续 Activation 所需的 Capability Boundary；它不使 Physical Activation 成为本 Module 的处理职责；
- Feature Acceptance 中定义的 Hard Contract 与 Build Safety 规则。

本 Module 不绑定具体存储、激活、发布、验证库、SDK、Framework 或 Deployment Platform。物理激活是 Capability Boundary，不新增独立 Core Module。

---

## 9. Test / Evaluation（测试 / 评估）

### Deterministic Contract Test（确定性契约测试）

必须证明并全部通过：

- Source / Asset Alignment；
- Source Integrity、Record Coverage、One Object → One Logical Record；
- Source Trace、Identity Integrity、Payload Integrity、Physical Mapping Integrity；
- Representation Integrity、Index Completeness、Build Metadata Integrity；
- Relationship Boundary 与 Relationship Vectorization Prohibition；
- No Invented Truth、Legacy Resource Isolation；
- Validation Before Activation；
- Failed Build Protection 与上一版有效资产保护；
- 任一硬契约失败时不输出 `ValidatedRetrievalAssets`。

### Retrieval Evaluation（检索评估）

本 Module 不以结构验证代替语义检索质量验证。Validated Asset 必须进入 Feature-Level Retrieval Evaluation，按 Table、Column、Metric 分别观察 Recall@K 与 MRR；业务 Dimension 场景通过 Column / Field Retrieval 评估，并纳入 Canonical Name、Alias、Natural Language、Similar Object 和 Similar Metric 场景；具体数据集与 Release Threshold 由 Acceptance Baseline 管理。

### Build-to-Retrieve Integration Evaluation（构建到检索集成评估）

必须从正式 Schema Metadata 与 Semantic Resources 重新构建，经过本 Module 验证后，由 Feature / Application Orchestration Boundary 通过对应 Capability 执行后续 Physical Activation，再由 Online Retrieval 返回预期 Candidate。该验证必须证明：

- Online 消费的是本次通过验证的资产；
- 资产删除派生结果后可以 Full Rebuild；
- 相同 Source + Build Contract + Relevant Configuration 产生语义等价资产；
- 失败的新 Build 不破坏上一版有效资产；
- Critical Bad Case 不能被总体 Recall / MRR 掩盖。

---

## 10. Deferred Technical Decisions（延后技术决定）

以下决定留到 `Technology Selection / Implementation Design`：

- Asset Validation 的具体 Schema Comparison、Serialization 和校验库；
- Online Retrieval Consumability 的具体探测、接口或协议；
- `VALIDATED` 到 Physical `ACTIVE` 的具体发布、原子切换、别名或指针机制；
- 失败构建保护上一版资产的具体存储与回滚机制；
- Asset Identity、Version、Fingerprint 和 Validation Identity 的具体算法；
- Retrieval Ranking、Top-K、Threshold、Quality Threshold 和 Online Serving 策略；
- 事务、并发、超时、重试、部署和运维实现。
