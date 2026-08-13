# Resource Loading & Validation Module Spec
# 资源加载与校验模块规格

> **Status（状态）：** V1 Module Contract Design Baseline（V1 模块契约设计基线）
> **Version（版本）：** V1
> **Feature（所属功能）：** Offline Pipeline（离线链路）
> **Feature Architecture Reference（功能架构引用）：** `../ARCHITECTURE.md`
> **Feature Spec Reference（功能规格引用）：** `../FEATURE_SPEC.md`
> **Acceptance Reference（验收引用）：** `../ACCEPTANCE_AND_EVALUATION.md`
> **Module Standard Reference（模块标准引用）：** `../../../MODULE_CONTRACT_STANDARD.md`

---

## 1. Responsibility（职责）

本 Module 负责把 Offline Pipeline V1 所需的五类 Authoritative Resource（权威资源）加载为可验证的逻辑输入，并在进入 Retrieval Projection（检索投影）前完成确定性校验：

- Schema Metadata（结构元数据）：Table Catalog（表目录）、Column Catalog（字段目录）、Relationship Catalog（关系目录）；
- Semantic Resources（语义资源）：Metric Catalog（指标目录）、Dimension Catalog（维度目录）；
- Resource Contract Validation（资源契约校验）；
- Identity Validation（对象标识校验）；
- Cross-Resource Reference Validation（跨资源引用校验）；
- Semantic → Physical Mapping Validation（语义到物理映射校验）；
- Metric Dependency Validation（指标依赖校验）；
- Relationship Reference Validation（关系引用校验）；
- Legacy Resource Isolation（旧资源隔离）。

本 Module 成功后只产生构建过程中的 `ValidatedCatalogs`（已校验目录集合）。它不产生新的权威合并资源，也不改变任何业务定义。

本 Module 不负责：

- Retrieval Projection（检索投影）；
- Retrieval Content（检索内容）生成；
- Retrieval Representation（检索表示）生成；
- Retrieval Index（检索索引）构建、发布或激活；
- Online Retrieval（在线检索）、Schema Linking（结构关联）或 Metric Resolution（指标解析）；
- 自动补齐缺失的 Table、Column、Metric、Dimension 或 Relationship；
- 修改 Metric Formula（指标公式）、Dimension Meaning（维度含义）或 Physical Mapping（物理映射）。

---

## 2. Input Contract（输入契约）

### 2.1 `AuthoritativeResourceSet`（权威资源集合）

输入是由 `Resource Access Capability`（资源访问能力）提供的五类逻辑资源集合。外部序列化形式不属于本 Module Contract；进入本 Module 的数据必须能够映射为下列 Typed Contract（类型化契约）。

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Semantic Meaning（语义） | Constraint（约束） |
|---|---|---:|---|---|
| `build_context` | `BuildContext` | Yes | 本次完整 Offline Build 的逻辑身份与构建条件 | 由调用边界提供；本 Module 只透传，不据此创造业务事实 |
| `tables` | `TableResource` | Yes | 当前构建使用的表目录 | 恰好一个资源；对应 `TABLE_CATALOG` |
| `columns` | `ColumnResource` | Yes | 当前构建使用的字段目录 | 恰好一个资源；对应 `COLUMN_CATALOG` |
| `relationships` | `RelationshipResource` | Yes | 权威物理关系目录 | 恰好一个资源；对应 `RELATIONSHIP_CATALOG` |
| `metrics` | `MetricResource` | Yes | 当前构建使用的指标目录 | 恰好一个资源；对应 `METRIC_CATALOG` |
| `dimensions` | `DimensionResource` | Yes | 当前构建使用的维度目录 | 恰好一个资源；对应 `DIMENSION_CATALOG` |

每个 `*Resource` 都包含：

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Constraint（约束） |
|---|---|---:|---|
| `descriptor` | `SourceResourceDescriptor` | Yes | 描述该资源的来源、版本和当前权威性 |
| `objects` / `entries` | 对应的 Typed List（类型化列表） | Yes | 可以为空，但若当前正式目录按上层 Contract 要求必须有对象，则空集合导致构建失败 |

### 2.2 `BuildContext`（构建上下文）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Semantic Meaning（语义） | Constraint（约束） |
|---|---|---:|---|---|
| `build_identity` | `BuildIdentity` | Yes | 本次完整构建的逻辑身份 | 非空；具体 ID 策略不在本 Spec 冻结 |
| `build_configuration_identity` | `BuildConfigurationIdentity` | Yes | 影响本次构建结果的相关配置身份 | 非空；不等于具体配置文件格式 |
| `representation_version` | `RepresentationVersion` | Yes | 本次构建使用的检索表示契约版本 | 非空；不等于具体 Model Name 或算法名 |
| `build_mode` | Enum | Yes | 本次构建方式 | V1 固定为 `FULL_REBUILD` |

`BuildIdentity`、`BuildConfigurationIdentity` 和 `RepresentationVersion` 都是稳定、非空的逻辑 Machine Value（机器值）。它们不冻结具体字符串格式、时间规则、哈希算法、UUID 规则或其他 ID 实现。本 Module 只传递并绑定这些值，不定义其来源算法。

### 2.3 `SourceResourceDescriptor`（源资源描述）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Semantic Meaning（语义） | Constraint（约束） |
|---|---|---:|---|---|
| `resource_kind` | Enum | Yes | 资源的正式类别 | `TABLE_CATALOG`、`COLUMN_CATALOG`、`RELATIONSHIP_CATALOG`、`METRIC_CATALOG`、`DIMENSION_CATALOG` |
| `source_identity` | `string` | Yes | 该正式资源的稳定逻辑身份 | 非空；不是由本 Module 生成的物理存储名 |
| `source_version` | `string` | Yes | 本次构建所依据的源版本 | 非空；版本表达方式不在本 Spec 冻结 |
| `source_fingerprint` | `string` | Yes | 用于识别该源版本的稳定、可重复指纹 | 非空、可重复；算法不在本 Spec 冻结 |
| `authority_status` | Enum | Yes | 该资源是否属于当前正式事实源 | `CURRENT_AUTHORITATIVE` 或 `LEGACY`；输出中只能出现前者 |

`source_version`、`source_fingerprint` 和 `source_identity` 共同支持后续 `SourceTrace`（来源追踪）与可重复构建，但不定义具体 Version Strategy（版本策略）或 Fingerprint Algorithm（指纹算法）。

### 2.4 Source Object（源对象）Typed Contract

所有可进入 Retrieval Projection 的 Source Object（源对象）必须携带：

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Constraint（约束） |
|---|---|---:|---|
| `identity` | `SourceObjectIdentity` | Yes | `object_type` 必须与所属资源类别一致；在同类资源内唯一 |
| `payload` | `SourceObjectPayload` 的对应变体 | Yes | 必须完整保留该 Source Object 的正式字段语义 |

#### `SourceObjectIdentity`（源对象标识）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Semantic Meaning（语义） |
|---|---|---:|---|
| `object_type` | Enum | Yes | `TABLE`、`COLUMN`、`METRIC` 或 `DIMENSION` |
| `source_resource_kind` | Enum | Yes | 对象所属的四类可检索源资源之一；不得为 `RELATIONSHIP_CATALOG` |
| `object_key` | `string` | Yes | 在所属权威资源中唯一且稳定的对象键；键的具体格式不在本 Spec 冻结 |

四类 Source Object 的结构均为：

```text
TableSourceObject     = { identity: SourceObjectIdentity, payload: TablePayload }
ColumnSourceObject    = { identity: SourceObjectIdentity, payload: ColumnPayload }
MetricSourceObject    = { identity: SourceObjectIdentity, payload: MetricPayload }
DimensionSourceObject = { identity: SourceObjectIdentity, payload: DimensionPayload }
```

其中 `identity.object_type` 必须分别为 `TABLE`、`COLUMN`、`METRIC`、`DIMENSION`，`identity.source_resource_kind` 必须与对应 Catalog 一致。

#### `TablePayload`（表载荷）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Constraint（约束） |
|---|---|---:|---|
| `schema_name` | `string` | Yes | 非空物理命名空间 |
| `table_name` | `string` | Yes | 非空物理表名 |
| `table_type` | `string` | Yes | 保留源目录给出的表类型，不由本 Module 重新解释 |
| `description` | `nullable string` | Yes | 可以为空；为空不允许被自动补写为业务定义 |

#### `ColumnPayload`（字段载荷）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Constraint（约束） |
|---|---|---:|---|
| `schema_name` | `string` | Yes | 非空 |
| `table_name` | `string` | Yes | 非空；必须引用已存在的 Table |
| `column_name` | `string` | Yes | 非空；在所属 Table 内唯一 |
| `ordinal_position` | `integer` | Yes | 大于等于 1 |
| `data_type` | `string` | Yes | 保留源目录类型表达，不在本 Spec 重新枚举 |
| `nullable` | `boolean` | Yes | 保留源目录事实 |
| `default_expression` | `nullable string` | Yes | 保留源目录事实；可以为空 |
| `description` | `nullable string` | Yes | 可以为空 |
| `is_primary_key` | `boolean` | Yes | 保留源目录事实 |
| `is_foreign_key` | `boolean` | Yes | 保留源目录事实；不等于把 Relationship 变成 Retrieval Record |
| `is_identity` | `boolean` | Yes | 保留源目录事实 |
| `identity_generation` | `nullable string` | Yes | 可以为空；不由本 Module 推断 |

#### `MetricPayload`（指标载荷）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Constraint（约束） |
|---|---|---:|---|
| `metric_code` | `string` | Yes | 在 Metric Catalog 内唯一 |
| `metric_name` | `string` | Yes | 正式指标名称 |
| `aliases` | `list[string]` | Yes | 可以为空；每项非空且来自正式资源 |
| `business_definition` | `string` | Yes | 正式业务定义；不得由本 Module 创造 |
| `metric_type` | `string` | Yes | 保留正式资源表达 |
| `expression` | `string` | Yes | 正式计算表达；不得被投影或表示生成修改 |
| `filters` | `list[string]` | Yes | 可以为空；保留正式过滤规则 |
| `depends_on` | `list[string]` | Yes | 可以为空；每项必须引用存在的 Metric |
| `default_time_dimension` | `string` | Yes | 正式时间口径；必须能通过语义资源规则校验 |
| `unit` | `string` | Yes | 正式计量单位 |
| `source_table` | `nullable string` | Yes | 直接物理映射的表；无直接表时必须由合法依赖映射支撑 |
| `source_columns` | `list[string]` | Yes | 可以为空；非空时每项必须属于 `source_table` |

#### `DimensionPayload`（维度载荷）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Constraint（约束） |
|---|---|---:|---|
| `dimension_code` | `string` | Yes | 在 Dimension Catalog 内唯一 |
| `dimension_name` | `string` | Yes | 正式维度名称 |
| `aliases` | `list[string]` | Yes | 可以为空；每项非空且来自正式资源 |
| `business_definition` | `string` | Yes | 正式业务定义；不得由本 Module 创造 |
| `dimension_type` | `string` | Yes | 保留正式资源表达 |
| `source_table` | `string` | Yes | 必须引用已存在的 Table |
| `source_column` | `string` | Yes | 必须引用 `source_table` 中已存在的 Column |
| `date_role` | `nullable string` | Yes | 可以为空；保留正式时间角色 |
| `date_dimension_table` | `nullable string` | Yes | 可以为空；若存在必须引用已存在的 Table |
| `date_key_column` | `nullable string` | Yes | 可以为空；若存在必须引用合法物理字段 |
| `is_default_business_time` | `boolean` | Yes | 保留正式领域规则结果 |

`SourceObjectPayload` 是以上四个变体的 tagged union（带类型标记联合结构）。它不是自由字段集合。后续 Module 必须按 `object_type` 使用对应变体。

### 2.5 `RelationshipEntry`（关系条目）

Relationship 只作为权威物理关系目录输入，不属于 `SourceObjectPayload`，也不属于 Retrieval Record。

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Constraint（约束） |
|---|---|---:|---|
| `relationship_key` | `string` | Yes | 在 Relationship Catalog 内唯一 |
| `relationship_type` | Enum | Yes | `PRIMARY_KEY`、`UNIQUE_CONSTRAINT`、`FOREIGN_KEY` 或 `UNIQUE_INDEX` |
| `source_table` | `PhysicalObjectIdentity` | Yes | `object_kind` 必须为 `TABLE` |
| `source_columns` | `list[string]` | Yes | 非空；必须属于 `source_table` |
| `target_table` | `nullable PhysicalObjectIdentity` | Conditional | `FOREIGN_KEY` 必需；其他类型可以为空 |
| `target_columns` | `list[string]` | Conditional | `FOREIGN_KEY` 必需且数量与 `source_columns` 一致；其他类型为空列表 |
| `condition` | `nullable string` | Yes | 保留正式目录条件；不由本 Module 猜测 |

`RelationshipResource` 的逻辑结构为：

```text
RelationshipResource = {
  descriptor: SourceResourceDescriptor,
  entries: list[RelationshipEntry]
}
```

`RelationshipEntry` 只能留在 `ValidatedCatalogs.relationships` 中供权威关系校验和后续 Schema Linking 使用；它永远不是 `SourceObject`、`RetrievalRecord` 或 `Index Entry`。

#### `RelationshipIdentity`（关系标识）

`RelationshipIdentity` 只用于在公共 Failure Contract（失败契约）中稳定定位 Relationship，不把 Relationship 变成 Source Object：

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Semantic Meaning（语义） | Constraint（约束） |
|---|---|---:|---|---|
| `entity_type` | Enum | Yes | 关联实体的类型标记 | 固定为 `RELATIONSHIP` |
| `relationship_key` | `string` | Yes | Relationship Catalog 中的稳定关系键 | 非空；必须能在对应 Relationship Catalog 内唯一定位 |

`RelatedEntityIdentity`（关联实体标识）是公共 Failure Contract 使用的 Tagged Union（带类型标记联合结构）：

```text
RelatedEntityIdentity = SourceObjectIdentity | RelationshipIdentity
```

其中 `SourceObjectIdentity` 继续使用既有的 `object_type`、`source_resource_kind` 和 `object_key` 定位 Table、Column、Metric 或 Dimension；`RelationshipIdentity` 使用 `entity_type=RELATIONSHIP` 与 `relationship_key` 定位 Relationship。两种 Identity 只是失败定位的不同变体，Relationship 仍然不是 `SourceObject`、`RetrievalRecord` 或 `Index Entry`。

`PhysicalObjectIdentity` 的逻辑字段为：

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Constraint（约束） |
|---|---|---:|---|
| `object_kind` | Enum | Yes | `TABLE` 或 `COLUMN` |
| `schema_name` | `string` | Yes | 非空 |
| `table_name` | `string` | Yes | 非空 |
| `column_name` | `nullable string` | Yes | `object_kind=TABLE` 时为空；`object_kind=COLUMN` 时非空 |

---

## 3. Preconditions（前置条件）

进入本 Module 前必须满足：

1. `Resource Access Capability` 可读取五类当前 Offline Pipeline V1 资源。
2. 输入已经能够映射到本节定义的 Typed Contract；缺字段、错误类型和无法解析的数据仍视为非法输入。
3. 资源来源身份、源版本和源指纹可被获取；否则无法建立后续 `SourceTrace`，不得继续构建。
4. 本次构建范围只包含 V1 支持的四类可检索对象以及一个权威 Relationship Catalog。
5. 本 Module 不需要也不得依赖已有 Retrieval Index 或上一版派生资产才能成功。

---

## 4. Processing Responsibilities（处理职责）

本 Module 必须按以下规则处理：

1. 确认五类资源各自独立存在，且没有用合并文件替代原始 Source Resource。
2. 严格验证每个 `SourceResourceDescriptor`：资源类别、来源身份、源版本、源指纹和 `authority_status` 均合法；发现 `LEGACY` 资源或 Current / Legacy 混用时失败。
3. 验证四类可检索 Source Object 的类型与对象键唯一性；同一对象不能以不同键重复出现。
4. 验证 Table / Column 的物理引用、Metric 的直接或依赖映射、Dimension 的物理映射均能解析到当前结构目录。
5. 验证 Metric `depends_on` 只引用存在的 Metric，并且依赖图不存在无法解析的引用。
6. 验证 RelationshipEntry 的源端、目标端、列数量和引用对象均来自当前 Schema Metadata。
7. 保留 Relationship Catalog 的独立边界；只验证其合法性，不把其转换为可检索 Source Object。
8. 所有校验通过后，按原资源边界形成 `ValidatedCatalogs`；不得修改 Source Object 的业务语义或物理映射。
9. 任一关键校验失败时，停止当前构建并返回显式 `OfflineBuildFailure`；不得猜测、修补或静默降级。

---

## 5. Output Contract（输出契约）

### 5.1 `ValidatedCatalogs`（已校验目录集合）

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Semantic Meaning（语义） | Constraint（约束） |
|---|---|---:|---|---|
| `build_context` | `BuildContext` | Yes | 本次构建的身份与构建条件 | 原样传递；不得由本 Module 修改 |
| `source_descriptors` | `list[SourceResourceDescriptor]` | Yes | 本次验证实际依据的五类源资源描述 | 恰好包含五种 `resource_kind`；全部为 `CURRENT_AUTHORITATIVE` |
| `tables` | `list[TableSourceObject]` | Yes | 已通过校验的表对象 | 对应当前 Table Catalog 的完整对象集合 |
| `columns` | `list[ColumnSourceObject]` | Yes | 已通过校验的字段对象 | 对应当前 Column Catalog 的完整对象集合 |
| `relationships` | `list[RelationshipEntry]` | Yes | 已通过校验的权威物理关系 | 保持独立；不成为 Retrieval Record |
| `metrics` | `list[MetricSourceObject]` | Yes | 已通过校验的指标对象 | 对应当前 Metric Catalog 的完整对象集合 |
| `dimensions` | `list[DimensionSourceObject]` | Yes | 已通过校验的维度对象 | 对应当前 Dimension Catalog 的完整对象集合 |

`ValidatedCatalogs` 是 Module 间的逻辑数据对象：

- 它表示“输入已经通过本 Module Contract”；
- 它不是新的 `merged` Source of Truth；
- 它不是要求持久化的新资源文件；
- 它不能被下游修改后作为权威资源继续使用。

### 5.2 `OfflineBuildFailure`（离线构建失败）

本 Module 失败时只返回显式失败，不返回部分 `ValidatedCatalogs`。公共失败对象包含：

| Field（字段） | Logical Type（逻辑类型） | Required（必需） | Constraint（约束） |
|---|---|---:|---|
| `failure_category` | Enum | Yes | `INVALID_INPUT`、`RESOLUTION_FAILURE`、`DEPENDENCY_FAILURE`、`UNSUPPORTED` 或 `INTERNAL_FAILURE` |
| `failure_stage` | Enum | Yes | 固定为 `RESOURCE_LOADING_AND_VALIDATION` |
| `reason` | `string` | Yes | 非空诊断原因；不得把失败描述为成功 |
| `related_resource_kind` | `nullable enum` | Yes | 失败关联的正式资源类别 | 可以是五类 Resource Catalog 之一；Relationship Failure 使用 `RELATIONSHIP_CATALOG`；无法归属资源时为空 |
| `related_entity_identity` | `nullable RelatedEntityIdentity` | Yes | 失败关联的机器实体标识 | Source Object Failure 使用 `SourceObjectIdentity`；Relationship Failure 使用 `RelationshipIdentity`；无法归属具体实体时为空 |

`related_entity_identity` 是独立于诊断文本的 Machine Identity（机器标识）：

- Source Object Failure → `SourceObjectIdentity`；
- Relationship Failure → `RelationshipIdentity`，至少可以通过 `relationship_key` 稳定定位；
- 无法归属具体实体 → `null`。

`reason` 只用于 Human Diagnostic Information（人类诊断信息），不替代机器可判断的 `failure_category`、`related_resource_kind` 或 `related_entity_identity`。

因此，公共 Failure Contract 可以稳定表达：资源级失败使用 `related_resource_kind` 与空的 `related_entity_identity`；Source Object Failure 使用对应资源类别与 `SourceObjectIdentity`；Relationship Failure 使用 `related_resource_kind=RELATIONSHIP_CATALOG` 与 `RelationshipIdentity`；Dependency Failure 与 Internal Failure 使用对应的 `failure_category`，关联实体按是否可归属填写或为空。

---

## 6. Postconditions / Invariants（后置条件 / 不变量）

只有以下条件全部成立时，才允许返回 `ValidatedCatalogs`：

1. 五类独立 Source Resource 均已识别、读取和验证。
2. 所有输出对象的 Source Object Identity 在所属资源内唯一且稳定。
3. 所有跨资源引用、Semantic → Physical Mapping、Metric Dependency 和 Relationship Reference 均已确定性验证。
4. 输出中的对象集合与当前正式资源集合覆盖一致；不存在静默丢失、重复或新增对象。
5. 所有输出资源都属于当前权威资源；不得包含 Legacy Resource。
6. Relationship Catalog 仍是独立的权威物理关系目录，不形成 Retrieval Record。
7. 任何业务定义、Metric Formula、Dimension Meaning 和 Physical Mapping 均与输入语义一致。
8. `ValidatedCatalogs` 不取代任何上游 Business Source of Truth。
9. 无法确认正确性时必须失败（Fail Closed）。

---

## 7. Failure Contract（失败契约）

### `INVALID_INPUT`（非法输入）

用于：资源缺失、输入无法解析、Typed Contract 字段缺失或类型非法、对象标识重复、源资源描述不完整等情况。

### `RESOLUTION_FAILURE`（解析失败）

用于：跨资源引用不存在、Semantic → Physical Mapping 无法唯一确认、Metric Dependency 无法解析、RelationshipEntry 引用不合法等情况。

### `DEPENDENCY_FAILURE`（依赖失败）

用于：`Resource Access Capability` 不可用、返回不完整资源，或返回的数据无法满足其 Capability Contract 的情况。

### `UNSUPPORTED`（不支持）

用于：输入要求处理 V1 未支持的 Source Object 类型、未冻结的其他资源类别，或要求本 Module 承担 Projection / Embedding / Index / Online 责任的情况。

### `INTERNAL_FAILURE`（内部失败）

用于：模块在输入合法且能力可用时仍无法维持自身 Contract / Invariant 的情况。

本 Module 不产生 User Clarification（用户澄清）。资源内部问题必须由系统显式失败并进入后续 Bad Case（失败案例）处理，不能转化为要求用户修改业务意图。

---

## 8. Dependencies（依赖）

本 Module 只依赖：

- `Resource Access Capability`（资源访问能力）：读取五类正式 Source Resource，并提供来源身份、版本、指纹和当前权威性信息。

本 Module 通过 Capability / Contract 协作，不依赖：

- 具体文件格式或序列化实现；
- 具体校验库、框架或 SDK；
- Retrieval Index、Embedding 或 Online Retrieval 的内部实现；
- 任何 Legacy Resource 作为补偿来源。

---

## 9. Test / Evaluation（测试 / 评估）

本 Module 以确定性契约验证为主，必须证明：

- 缺失、非法、重复或无法解析的资源会显式失败；
- 五类资源均被验证，且 Current / Legacy 混用被拒绝；
- Object Identity 唯一性、跨资源引用、Semantic → Physical Mapping、Metric Dependency 和 Relationship Reference 均满足 Contract；
- `ValidatedCatalogs` 的五类对象覆盖完整，Relationship Catalog 保持独立；
- 输出为明确 Typed Contract，不包含隐藏字段或未声明事实；
- 不会创建不存在的 Table、Column、Metric、Dimension 或 Relationship；
- 不会改变 Metric Formula、Dimension Meaning 或 Physical Mapping；
- 失败不会产生部分成功的 `ValidatedCatalogs`。

与 Feature Acceptance 的对齐：

- 对应 `Deterministic Contract Test` 中的 Source Integrity、Identity、Cross-Resource Reference、Mapping、Relationship Reference 和 Legacy Resource Isolation；
- 本 Module 不单独冻结 Recall@K、MRR 或质量阈值；这些属于 Feature-Level `Retrieval Evaluation`；
- `Build-to-Retrieve Integration Evaluation` 必须使用本 Module 的真实 `ValidatedCatalogs`，证明后续完整链路消费的是经过校验的正式资源。

---

## 10. Deferred Technical Decisions（延后技术决定）

以下决定明确留到 `Technology Selection / Implementation Design`：

- 外部资源的具体文件、传输和序列化方式；
- 解析、Schema Validation 和数据模型的具体库或框架；
- `SourceFingerprint` 的具体算法；
- `SourceVersion`、`SourceObjectIdentity.object_key` 的具体生成策略；
- Current / Legacy 资源发现与隔离的具体实现方式；
- 错误记录、日志和诊断信息的具体存储方式；
- 构建触发、批量处理、并发、超时和重试策略；
- 部署形态与运行环境。
