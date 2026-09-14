# ChatBI DDD Architecture Alignment（DDD 架构对齐设计）

## 1. 文档状态

- 阶段：Architecture / Implementation Design（架构与实现设计）
- 状态：独立只读设计审查 PASS；DDD-T1 已实现，确定性测试与静态边界检查通过
- 目标：在不改变当前查询行为的前提下，降低 Online Query（在线查询）代码复杂度
- 本文不改变业务规格，不增加用户功能，不改变数据库、RAG 文档语义或运行配置；为版本隔离可验证性，后续发布流程可只增加 Manifest 的资产完整性字段，不改变文档内容和业务口径

## 2. 背景与问题

ChatBI 当前采用 Modular Monolith（模块化单体），顶层模块边界基本清楚，Online Query、RAG Offline Build、Evaluation、Observability、Query API 和 Streamlit 已经分开。

但 Online Query 内部已经超出“扁平模块”的适用范围。当前 `retrieval.py` 同时包含：

- 单指标、实体和多指标检索流程编排；
- 指标解析、指标兼容性和必需字段规则；
- Relationship Graph（关系图）路径解析和 Join 安全规则；
- Qdrant / Embedding 命中结果转换；
- Dynamic Schema（动态结构）和 Indicator Context（指标上下文）组装；
- Trace（追踪）记录和失败结果构造。

这不是当前功能错误，但会带来三个维护问题：

1. 业务规则和技术实现难以单独理解和测试。
2. 单指标与多指标流程存在重复，后续修改容易出现分支不一致。
3. Domain（领域）代码直接依赖 Qdrant、BGE-M3、OpenTelemetry 等具体技术。

## 3. 事实源与优先级

本设计遵循以下优先级：

```text
正式 Architecture / Feature Spec / Domain / Acceptance
→ Engineering Rules
→ 当前真实代码、测试、依赖和运行事实
→ Implementation Design
→ Legacy / Derived Artifact
```

本次对齐涉及的事实源：

- `docs/architecture.md`
- `docs/specs/online-query.md`
- `docs/specs/online-retrieval.md`
- `docs/specs/multi-metric-retrieval.md`
- `docs/specs/observability.md`
- `docs/designs/online-query.md`
- `docs/designs/online-retrieval.md`
- `docs/designs/multi-metric-retrieval.md`
- `docs/designs/observability.md`
- `src/online_query/`
- `tests/online_query/`

行为规格继续有效。本设计只修正代码内部的职责和依赖方向；如果后续实现发现必须改变行为 Contract（契约），应回到对应 Spec 讨论，不在重构中顺带修改。

状态冲突处理：`docs/specs/online-retrieval.md` 顶部关于“基础 Multi-Metric 尚未实现”的历史状态文字已落后于更具体的 `docs/specs/multi-metric-retrieval.md`、`docs/architecture.md` 和当前实现。涉及多指标行为时，以后两者和多指标专门规格为准；T5B 的文档同步会更新该历史状态文字。这里不把这项文档修正误认为新的业务功能。

验收状态的优先级也必须保持三态分离：当前多指标是 Software Test（软件测试）通过、AI Evaluation（AI 评测）20/20 通过、Business Acceptance（业务验收）仍待用户确认；`online-query.md` 顶部将 C05 写成“业务验收”通过属于历史表述，T5B 统一改为上述三态。本文不把 C05 Evaluation 通过写成 Business Acceptance 已关闭，也不把本 DDD 设计的待审查状态与既有 Online Query Implementation Design 的已确认状态混为一谈。

本文的 T4A/T4B/T4C 是本 DDD 对齐文档内部的重构任务编号，与 `docs/specs/observability.md` 或既有多指标实现设计中的同名验收编号无继承关系；任务验收必须引用本文的目标和测试范围。

## 4. Goal / Non-goal

### 4.1 Goal（目标）

- 保留 `OnlineQueryService.query()` 作为唯一稳定查询入口。
- 将业务规则、应用流程和技术 Adapter（适配器）分开。
- 将单指标、实体和多指标检索合并为一条可读的应用流程。
- 让 Domain 不依赖外部 SDK、数据库、文件和 Observability 实现。
- 保留现有 API、错误码、SQL 安全规则、Trace 名称和评测入口。
- 让每个生产代码文件拥有单一、直观的职责。

### 4.2 Non-goal（不在范围）

- 不增加多轮对话、经营分析、用户权限或租户能力。
- 不增加 LangGraph、Agent、事件总线、微服务或依赖注入框架。
- 不改 RAG 检索规格、指标口径、Relationship Graph 事实或 SQL 业务规则；Manifest 完整性字段属于发布安全边界，不属于新的业务事实。
- 不更换 Qdrant、BGE-M3、LLM、PostgreSQL 或 OpenTelemetry。
- 不为了形式上的 DDD 创建空目录、空接口或每个对象一个 Repository（仓储）。
- 不重写整个仓库；只处理 Online Query 复杂模块及其直接组装入口。

## 5. 目标 Bounded Context（限界上下文）

| Context | 类型 | 职责 | 本次处理 |
|---|---|---|---|
| Online Query | Core Bounded Context（核心限界上下文） | 业务语义约束、检索决策、SQL 生成与安全执行；内部包含 Domain、Application、Infrastructure | 重点对齐 |
| RAG Offline Build | Supporting Capability | 校验事实、构建检索文档、生成向量和关系图、发布资产 | 保持现状，仅稳定公开边界 |
| Evaluation | Quality Support | 使用正式在线链路进行软件评测和 AI 评测 | 保持入口行为 |
| Observability | Generic / Cross-cutting | Trace、阶段耗时、错误类型和安全属性 | 通过 Port 注入 |
| Query API | Interface Adapter | HTTP 请求与查询 Contract 转换 | 保持协议 |
| Streamlit | Interface / POC | 调用 HTTP API 和展示结果 | 保持行为 |

Online Retrieval（在线检索）暂不单独提升为 Bounded Context。它目前没有独立业务生命周期，输出直接服务于 Online Query；其中的业务规则属于 Online Query Domain，Qdrant 和 BGE-M3 接入属于 Online Query Infrastructure。

## 6. 分层规则

```text
Interfaces
    → Application
        → Domain

Application
    → Port / Contract
        ← Infrastructure Adapter
```

### 6.1 Domain Layer（领域层）

只表达 ChatBI 的业务事实和确定性规则，例如：

- 用户请求指标的身份、顺序和去重；
- 多指标的数据源、日期口径和固定条件兼容性；
- 指标公式和必需字段关系；
- 候选表、字段和 Join 范围；
- Anchor Table、最短合法路径和路径歧义；
- 连接基数和事实行放大风险；
- 业务失败与允许回退的语义。

Domain 不得导入或直接调用：

- Qdrant、BGE-M3、LangChain、psycopg、SQLGlot；
- OpenTelemetry 或具体 Trace Recorder；
- `Path`、环境变量、JSON 读取和网络 IO；
- FastAPI、Streamlit 或具体部署平台。

### 6.2 Application Layer（应用层）

负责用例编排：

```text
QueryRequest
→ 请求校验
→ RetrievalRequest / ProvisionalMetricRequest / Final MetricPlan
→ 调用检索 Port
→ 执行 Domain 规则
→ 生成 QueryContext
→ Prompt
→ LLM Port
→ SQL Guard Port
→ Database Port
→ QuerySuccess / QueryFailure
```

Application 只依赖 Port，不创建 Qdrant、LLM、数据库和 Trace 的具体实现。

### 6.3 Infrastructure Layer（基础设施层）

实现 Application 需要的技术能力：

- 已发布 RAG 资产、Qdrant 和 BGE-M3；
- LLM 调用；
- SQLGlot AST（抽象语法树）解析和 SQL Guard；
- PostgreSQL 只读执行；
- 静态 JSON 上下文；
- OpenTelemetry Trace Recorder。

Infrastructure 可以依赖外部 SDK 和文件，但不能把外部技术类型泄露为 Domain Contract。

### 6.4 Interfaces Layer（接口层）

只负责输入输出转换：

- Query API：HTTP JSON 与 `QueryRequest / QueryResult` 转换；
- Streamlit：页面交互和结果展示；
- Evaluation CLI：参数解析、评测运行和报告输出。

它们不能复制查询、检索、Prompt、SQL Guard 或数据库执行逻辑。

## 7. Domain Dictionary（领域词典）

首轮只保留已经有明确 Contract 的对象：

| 对象 | 所属 | 含义 |
|---|---|---|
| `MetricDefinition` | Domain | 由已发布资产转换而来的唯一权威指标事实，不含 Qdrant、SQLGlot 或文件类型 |
| `ProvisionalMetricRequest` / `MetricPlan` | Application / Domain | 前者只绑定 Snapshot 与请求文本；后者是完成确定性解析后的有序指标规划结果 |
| `MetricConstraint` | Compatibility projection | 从 `MetricDefinition` 生成的 Prompt/API 兼容投影，不是业务真相 |
| `MetricRequestPlan` | Compatibility name | 现有类型名，迁移期间映射到 `MetricPlan` |
| `JoinEdge` / `JoinPath` / `JoinResolution` | Domain | 关系事实、最短合法路径和已验证的最终连接解析结果 |
| `JoinConstraint` | Domain | SQL 可使用的连接约束 |
| `QueryContext` | Application Contract | 同时承载本次最终允许使用的表、列、指标和 Join；首轮不再新增 `QueryScope` |
| `FallbackPolicy` | Application Policy | 根据请求形态决定技术故障时是否允许静态回退 |
| `RetrievalEvidence` | Application / Evaluation DTO | 检索、评测和追踪所需证据 |

暂不新增完整 `SemanticQuery`。当前日期、分组和自然语言过滤条件还没有全部形成确定性结构；过早创建它会引入一个无法约束的“大对象”。多轮对话阶段需要共享结构化查询状态时再单独设计。

### 7.1 资产事实到领域视图的转换

`MetricCatalogEntry` 和 `MetricHit` 目前包含发布载荷、检索正文和技术命中信息，不能直接混合作为 Domain 输入。目标边界如下：

```text
Qdrant / JSON Payload
    → Infrastructure Metric Catalog Adapter
    → MetricDefinition / Snapshot-bound evidence
    → Domain Metric Rules
```

具体规则：

- `MetricCatalogEntry` 属于 Infrastructure 的发布资产读取模型；
- Adapter 校验 `document_id`、名称、来源、`time_field`、公式和 filters，并创建不含第三方类型的 `MetricDefinition`；
- `MetricDefinition` 保持纯 Domain 值对象；进入 Application 的已发布指标必须包在 `SnapshotBoundMetricDefinition` 中，绑定本次 `PublishedRetrievalSnapshot` 的不可伪造身份；
- Adapter 使用 SQLGlot 解析公式和 filters，只输出纯 Python 的字段引用、规范化过滤条件和受控解析错误；
- Domain 不比较 SQLGlot AST，也不接收 SQLGlot 类型；它只使用 `MetricDefinition` 中的中立值；
- 公式或 filters 解析失败转换为 `ASSET_UNAVAILABLE` / `INVALID_ASSET`，不得静默降级或交给 LLM；
- 公式字段引用和 filters 字段引用在转换时提取为完整的 `schema.table.column` 身份，Domain 只负责合并、去重和完整性判断；
- `MetricHit` 保留为检索证据 DTO，不作为业务事实源；最终指标事实只来自同一 `SnapshotBoundMetricDefinition.value`，并且必须先通过 Snapshot 身份校验。

这样既保留当前 SQLGlot 的确定性能力，又避免把 SQLGlot 直接搬进 Domain。

指标事实流转只有一条权威路径：

```text
Published Asset Payload
    → MetricDefinitionAdapter
    → tuple[SnapshotBoundMetricDefinition]  同一 Snapshot 的指标事实视图
    → MetricPlan                       本次请求的有序指标计划
    → QueryContext.metric_definitions  SQL Guard 唯一结构化输入
    → MetricConstraint                 只读兼容展示投影
```

必须满足以下不变量：

- `MetricDefinition` 是不可变对象；唯一键是 `asset_version + document_id`，同一版本同一 `document_id` 只能有一份定义；
- `SnapshotBoundMetricDefinition` 是 Application 侧的不可伪造已验证值对象，包含 `SnapshotBinding` 和一个不可变 `MetricDefinition`；`SnapshotBinding.asset_version` 的规范来源是 `PublishedRetrievalSnapshot.asset_version`，`MetricDefinition.asset_version` 只能作为被核对的目录事实，生产代码不能从普通请求字段直接构造 wrapper；
- `SnapshotBinding.asset_version` 是本次 Application 来源闭包的唯一 canonical version；`MetricPlan.asset_version`、所有 evidence 的 `asset_version` 和 `QueryContext.asset_version` 都只能从该 Binding / Snapshot 复制，不能由调用方另行指定；
- V1 中 `asset_version` 与发布资产的 `build_id` 是同一规范身份，不允许 Domain 同时维护两套版本语义；
- `MetricPlan.ordered_metric_definitions` 必须是来自同一 `snapshot_identity` / `asset_version` 的 `SnapshotBoundMetricDefinition`，并与去重后的 `ordered_mentions` 按顺序和 `document_id` 一一对应；`raw_mentions` 只保留解析证据，不参与 SQL Guard 或业务兼容判断；
- `MetricHit` 只能携带同版本的身份、排名、分数和语义摘要；命中后找不到同版本同 `document_id` 的 `MetricDefinition` 时，属于资产契约错误，返回 `CONTEXT_ERROR`，不能伪装成 `NO_METRIC_HIT`；
- `MetricConstraint` 只能由一个确定性投影函数从当前 `MetricPlan` 的 `SnapshotBoundMetricDefinition` 和本次请求绑定派生，不能独立构造后参与业务规则；公式、filters、time_field、data_source、depends_on 只能来自其 `.value`，`requested_text` 和 `ordinal` 只能来自 `MetricMention` / `MetricPlan`；
- `QueryContext` 构造时检查 `metric_definitions` 与 `metric_constraints` 的版本、身份、顺序和数量一致；
- “同一 `document_id` 但公式不同”“同版本但 Snapshot 身份不同”“命中版本不一致”“兼容投影与定义不一致”“QueryContext 缺少对应定义”都必须是确定性失败测试。

静态 fallback 是另一种上下文来源，不冒充已发布资产：`QueryContext.context_source=STATIC_FALLBACK` 时 `asset_version=None`、不携带 Published Snapshot 的指标定义或检索证据；静态 JSON 中的指标文本只保留当前 fallback 的 Prompt 兼容行为，不能作为新的结构化 SQL Guard 业务真相。只有 `context_source=PUBLISHED` 的 QueryContext 才允许携带 `MetricDefinition`、`MetricConstraint` 和版本绑定检索证据。

最小 Typed Contract（类型契约）如下：

```text
MetricDefinition                         # 纯 Domain 业务事实
  asset_version: str
  document_id: str
  metric_name: str
  aliases: tuple[str, ...]
  semantic_text: str
  data_source: TableRef(schema, table)
  formula: FormulaStructure
  time_field: TimeFieldRef(source_table, source_column, target_table, filter_column)
  filters: tuple[NormalizedFilterCondition, ...]
  depends_on: tuple[str, ...]

SnapshotBinding
  snapshot_identity: OpaqueSnapshotIdentity
  asset_version: str                    # canonical source: PublishedRetrievalSnapshot

SnapshotBoundMetricDefinition             # Application 已验证值对象；只由 Snapshot Factory 创建
  binding: SnapshotBinding
  value: MetricDefinition

TableCatalogEntry                         # Snapshot-owned、已校验的 TABLE 事实
  document_id: str
  table_ref: TableRef
  semantic_text: str

ColumnCatalogEntry                        # Snapshot-owned、已校验的 COLUMN 事实
  document_id: str
  table_ref: TableRef
  column_name: str
  semantic_text: str

SnapshotResourceCatalog
  tables: tuple[TableCatalogEntry, ...]
  columns: tuple[ColumnCatalogEntry, ...]

MetricPlan
  snapshot_identity: OpaqueSnapshotIdentity
  asset_version: str
  request_shape: RequestShape
  ordered_metric_definitions: tuple[SnapshotBoundMetricDefinition, ...]
  raw_mentions: tuple[MetricMention, ...]              # 解析证据，可含别名重复
  ordered_mentions: tuple[MetricMention, ...]          # 规范化、去重后的请求顺序
  status: MetricPlanStatus
  reason: str

ProvisionalMetricRequest              # 检索前的请求计划，不是最终业务事实
  snapshot_identity: OpaqueSnapshotIdentity
  asset_version: str
  request_shape: RequestShape
  ordered_mentions: tuple[MetricMention, ...]
  status: PENDING_RESOLUTION

MetricConstraint
  snapshot_identity: OpaqueSnapshotIdentity
  asset_version: str
  ordinal: int                  # 1..N，来自本次请求顺序
  requested_text: str           # 来自 MetricMention
  document_id: str
  metric_name: str
  formula: FormulaStructure     # 只读展示副本；SQL Guard 不以它为真相
  data_source: TableRef         # 只读展示副本；SQL Guard 不以它为真相
  time_field: TimeFieldRef      # 只读展示副本；SQL Guard 不以它为真相
  filters: tuple[NormalizedFilterCondition, ...]  # 只读展示副本
  depends_on: tuple[str, ...]    # 只读展示副本

ValidatedStaticContext                 # 仅由 StaticContextAdapter / Test-only Fixture 创建
  source_identity: OpaqueStaticContextIdentity
  prompt_context: str
  allowed_tables: frozenset[str]
  allowed_columns: Mapping[str, frozenset[str]]

FormulaStructure
  shape: AGGREGATE | AGGREGATE_RATIO
  aggregates: tuple[AggregateSpec, ...]
  referenced_columns: tuple[ColumnRef, ...]
  zero_division_guard: NULLIF_ZERO | NONE
  canonical_expression: str

TableHit
  snapshot_identity: OpaqueSnapshotIdentity
  asset_version: str
  document_id: str
  table_ref: TableRef
  semantic_excerpt: str

ColumnHit
  snapshot_identity: OpaqueSnapshotIdentity
  asset_version: str
  document_id: str
  table_ref: TableRef
  column_name: str
  semantic_excerpt: str

MetricHit
  snapshot_identity: OpaqueSnapshotIdentity
  asset_version: str
  document_id: str
  rank: int
  score: float
  semantic_excerpt: str

CollectionKind
  TABLE | COLUMN | METRIC

RawRetrievalHit
  snapshot_identity: OpaqueSnapshotIdentity
  asset_version: str
  collection_kind: CollectionKind
  document_id: str
  rank: int
  score: float
  payload: SanitizedPayload
  page_content: str

Version-bound retrieval evidence
  RetrievalEvidence.snapshot_identity: OpaqueSnapshotIdentity
  TableHit.snapshot_identity: OpaqueSnapshotIdentity
  ColumnHit.snapshot_identity: OpaqueSnapshotIdentity
  MetricHit.snapshot_identity: OpaqueSnapshotIdentity
  TableHit.asset_version: str
  ColumnHit.asset_version: str
  MetricHit.asset_version: str
  JoinPath.snapshot_identity: OpaqueSnapshotIdentity
  JoinConstraint.snapshot_identity: OpaqueSnapshotIdentity
  JoinPath.asset_version: str
  RetrievalEvidence.asset_version: str

JoinPath
  snapshot_identity: OpaqueSnapshotIdentity
  asset_version: str
  tables: tuple[str, ...]
  edges: tuple[JoinEdge, ...]

JoinEdge
  edge_id: str
  source_table: str
  source_columns: tuple[str, ...]
  target_table: str
  target_columns: tuple[str, ...]
  constraint_name: str
  direction: FORWARD | REVERSE

JoinConstraint
  snapshot_identity: OpaqueSnapshotIdentity
  asset_version: str
  edge_id: str
  source_table: str
  source_columns: tuple[str, ...]
  target_table: str
  target_columns: tuple[str, ...]
  constraint_name: str
  direction: FORWARD | REVERSE
  cardinality_proof: CardinalityProof | None

CardinalityProof
  snapshot_identity: OpaqueSnapshotIdentity
  asset_version: str
  edge_id: str
  source_table: str
  source_columns: tuple[str, ...]
  target_table: str
  target_columns: tuple[str, ...]
  proof_kind: FOREIGN_KEY_TO_PRIMARY_KEY | FOREIGN_KEY_TO_UNIQUE

JoinResolution
  snapshot_identity: OpaqueSnapshotIdentity
  asset_version: str
  anchor_table: str
  anchor_reason: METRIC_DATA_SOURCE | UNIQUE_TOP_TABLE
  required_tables: frozenset[str]
  optional_tables: frozenset[str]
  unreachable_required_tables: frozenset[str]
  dropped_optional_tables: frozenset[str]
  selected_paths: tuple[JoinPath, ...]
  selected_edges: tuple[JoinEdge, ...]
  join_constraints: tuple[JoinConstraint, ...]
  status: UNIQUE | PARTIAL_UNREACHABLE | AMBIGUOUS
  cardinality_requirement: NOT_REQUIRED | REQUIRED_FOR_AGGREGATION
  cardinality_proof: tuple[CardinalityProof, ...]

RetrievalEvidence
  snapshot_identity: OpaqueSnapshotIdentity
  asset_version: str
  table_hits: tuple[TableHit, ...]
  column_hits: tuple[ColumnHit, ...]
  metric_hits: tuple[MetricHit, ...]
  metric_queries: tuple[MetricRetrievalEvidence, ...]
  join_resolution: JoinResolution | None  # 失败/空命中可无；成功范围必须有 UNIQUE Resolution

MetricRetrievalEvidence
  snapshot_identity: OpaqueSnapshotIdentity
  asset_version: str
  requested_text: str
  target_document_id: str | None       # 实体基线零命中时无逐指标目标
  hits: tuple[MetricHit, ...]
```

`FormulaStructure` 只支持当前已冻结且有测试的公式形态：`COUNT(DISTINCT column)`、`SUM(column)`、`SUM(column - column)` 和 `AGGREGATE / NULLIF(AGGREGATE, 0)` ratio。`AggregateSpec` 至少包含 `function`、`distinct`、`argument_columns` 和 `argument_shape`；`NormalizedFilterCondition` 至少包含 `column`、`operator`、类型化常量和规范化条件；`TimeFieldRef` 至少包含 source/target 表、source join column 和 target filter column。超出表达能力的公式在 Adapter 阶段返回 `InvalidAssetError`，不扩展成通用 SQL 数学等价证明。

`RelationshipGraphFacts` 只包含已校验的表、列、关系边和约束事实；`EmbeddingFingerprint` 至少包含 model 标识、向量维度以及 dense/sparse 配置标识。二者都是中立值，不暴露 Qdrant、Embedding Provider 或文件对象。

实体请求虽然保留一次基线 METRIC Search，但没有请求指标目标；因此它可以只记录不带逐指标目标的综合检索证据，或不创建 `MetricRetrievalEvidence` 项，不得伪造 `target_document_id`。单指标和多指标在完成请求身份映射后，`target_document_id` 必须非空且来自同一 Snapshot 的目录。

`JoinResolution` 是 Relationship Graph 的唯一跨层解析结果，不是候选路径列表：`relationship_rules.resolve()` 先根据已确定的 Anchor Table 和目标表集合计算最短合法路径；每个目标的最短路径必须唯一，等长路径歧义或 Anchor 无法确定返回 `AMBIGUOUS`。`anchor_table` 始终属于 `required_tables`；指标事实表和用户明确要求的维度表进入 `required_tables`，实体请求中由 TABLE 唯一最高候选确定的 Anchor 也必须保留；`EXPLICIT_DIMENSION` 不是新的 Anchor 选择规则，明确维度只是 required target。其他命中表进入 `optional_tables`。必需表不可达时返回 `PARTIAL_UNREACHABLE`，记录 `unreachable_required_tables`，不生成可用 Join Constraint；仅可选表不可达时记录 `dropped_optional_tables` 并继续。`CardinalityProof` 是 Offline Relationship Graph 已验证结构事实在在线 Snapshot 中的投影，不为实体/单指标额外增加新的拒答条件；当 `cardinality_requirement=REQUIRED_FOR_AGGREGATION`（首版多指标聚合）时，每条保留边必须有对应 proof，否则 fail closed。只有必需表全部闭合、可选表已丢弃或闭合、且 `status=UNIQUE` 时，Resolver 才按正式 Graph 的 `source/target/constraint_name/direction` 和规范化边顺序生成 `selected_paths`、去重后的 `selected_edges`、`cardinality_proof` 和 `join_constraints`。候选路径只存在于 Domain/Adapter 内部，不进入 `RetrievalEvidence`；`RetrievalEvidence.join_resolution` 在成功范围上必须是该已验证结果，零命中、技术失败或 Join 之前失败可以为 `None`。单表查询也生成无边的 `UNIQUE` Resolution，保持派生过程统一。

`SanitizedPayload` 不是通用 `Mapping[str, Any]`，而是按集合类型区分的不可变 DTO（数据传输对象）：

```text
SanitizedTablePayload
  table_ref: TableRef
  display_name: str
  business_description: str
  labels: tuple[str, ...]

SanitizedColumnPayload
  table_ref: TableRef
  column_name: str
  display_name: str
  business_description: str
  aliases: tuple[str, ...]

SanitizedMetricPayload
  document_id: str
  metric_name: str
  aliases: tuple[str, ...]
  semantic_text: str

SanitizedPayload = SanitizedTablePayload | SanitizedColumnPayload | SanitizedMetricPayload
```

上述字段只允许 `str`、`tuple[str, ...]` 和中立的 `TableRef` 等纯值；不允许任意递归 Mapping。`page_content` 只保留面向业务语义检索的正文，不承载技术配置。禁止物理 collection name、Qdrant/Embedding/SQLGlot/OpenTelemetry 对象、Provider 实例、连接信息、Secret 和原始 SDK Payload。Adapter 必须在构造 `RawRetrievalHit` 前按 `CollectionKind` 完成字段白名单过滤，并针对三种 Payload 分别有泄漏回归测试。

`OpaqueSnapshotIdentity` 是 `load_snapshot()` 为一次不可变 `PublishedRetrievalSnapshot` 创建的不可序列化身份令牌；它只用于 Application 内部的来源闭包校验，不进入 Prompt、API JSON、日志或 Trace。

`SnapshotBoundMetricDefinition`、带 `snapshot_identity` 的 Hit、`JoinResolution` 和 `RawRetrievalHit` 都只能由同一 Snapshot 的 Factory / Adapter 创建。它们的公开构造器不属于 Application Contract；测试如果需要构造它们，必须使用 Test-only Fixture。`from_published()` 除了比较版本号，还要比较不可伪造的 Snapshot identity，并按 `document_id` 与传入 Snapshot 的目录重新核对，不能接受“同版本但外部伪造”的对象。

`MetricConstraint` 的唯一投影入口绑定到请求级 `MetricPlan`，定义为：

```text
project_metric_constraints(plan: MetricPlan)
    -> tuple[MetricConstraint, ...]

project_metric_constraint(                                # 仅为上述批量入口的内部步骤
    plan: MetricPlan,
    definition: SnapshotBoundMetricDefinition,
    mention: MetricMention,
    ordinal: int,
) -> MetricConstraint
```

`project_metric_constraints(plan)` 是唯一对外投影入口：它只使用 `ordered_mentions` 和 `ordered_metric_definitions`，先一次性检查两者长度、顺序、`document_id`、metric name、Snapshot identity、版本和 `1..N` 序号，再调用内部单项步骤。单项步骤必须检查 `definition.snapshot_identity == plan.snapshot_identity`、`definition.asset_version == plan.asset_version`、`definition` 正是 `plan.ordered_metric_definitions[ordinal - 1]`、`mention` 正是 `plan.ordered_mentions[ordinal - 1]`、`mention.document_id == definition.value.document_id`、规范化后的 `mention.metric_name == definition.value.metric_name`。它从 `definition.value` 复制业务口径字段，从 `mention` 复制请求文本和序号，不能从 `MetricHit`、原始 Payload 或 Prompt 文本读取公式和 filters；`MetricConstraint.snapshot_identity` 和 `asset_version` 只能复制自 `plan`。

`canonical_expression` 是解析后受控生成的规范表示，不是未经处理的原始 Payload 字符串；`aggregates`、字段引用和零除保护用于 Domain 兼容性与 SQL Guard 的确定性检查。`MetricHit` 只证明检索命中，不携带公式事实，必须通过 `snapshot_identity + asset_version + document_id` 关联 `SnapshotBoundMetricDefinition.value`。

现有 `MetricConstraint` 在过渡期间只作为 `QueryContext` 的 Prompt/API 兼容投影，供展示必要文本；它不再是领域校验输入。`MetricDefinition` 是公式、filters、time_field、data_source 和 depends_on 的唯一业务真相。已验证投影只提供 `ordinal`、请求文本、规范指标身份和 `definition` 绑定关系，SQL Guard 可以读取这些绑定字段来检查“每个请求指标是否覆盖且顺序/身份正确”，但不得读取投影中可能重复的公式、filters 或物理字段来作规则判断；这些判断只能读取经过 Snapshot 校验后解包的 `QueryContext.metric_definitions`。这样不需要新增第二套业务真相，也不会让原始公式字符串重新成为业务真相。

### 7.2 QueryContext 的目标投影

`QueryContext` 继续是在线链路传给 Prompt 和 SQL Guard 的最终范围 Contract，目标字段为：

```text
QueryContext
  prompt_context: str
  context_source: PUBLISHED | STATIC_FALLBACK
  snapshot_identity: OpaqueSnapshotIdentity | None
  asset_version: str | None
  request_shape: RequestShape
  allowed_tables: frozenset[str]
  allowed_columns: Mapping[str, frozenset[str]]
  metric_definitions: tuple[MetricDefinition, ...]  # 仅由 Factory 解包已验证的 SnapshotBoundMetricDefinition
  metric_constraints: tuple[MetricConstraint, ...]   # 兼容展示 + 已验证覆盖绑定，不是业务真相
  join_constraints: tuple[JoinConstraint, ...]
```

`QueryContext` 不把原始 Evidence 暴露给 Prompt；它只有两个受控构造入口：

```text
QueryContext.from_published(
    snapshot,
    evidence: RetrievalEvidence,
    metric_plan: MetricPlan,
) -> QueryContext

QueryContext.from_static(
    static_context: ValidatedStaticContext,
    request_shape: RequestShape,
    fallback_policy: FallbackPolicy,
) -> QueryContext
```

`ValidatedStaticContext` 由 `StaticContextAdapter` 从受控、允许的静态资产创建，包含已验证的 `prompt_context`、`allowed_tables` 和 `allowed_columns`，并带有 Test/Production 不可混用的内部来源令牌。Production Application 不能直接传入任意字符串或表列集合；测试使用 Test-only Fixture 生成该值对象。

`from_published()` 是唯一能创建 `context_source=PUBLISHED` 的入口，必须检查 Snapshot、Evidence、MetricPlan、所有命中、`metric_queries` 中的逐项命中、`JoinResolution`、`SnapshotBoundMetricDefinition` 和派生投影的 `snapshot_identity` 与 `asset_version` 全部相同，且指标命中、定义和请求顺序完整。它还必须按 `document_id` 将每个 `SnapshotBoundMetricDefinition` 与传入 Snapshot 的不可变目录重新核对，并确认 `MetricHit` 只能引用该目录中的定义。它从同一份已验证 Evidence 和 `JoinResolution` 确定性派生 `allowed_tables`、`allowed_columns` 和 `join_constraints`，调用方不能传入或扩大这些范围；额外表、列或 Join 注入必须确定性拒绝。任一缺失、错序、错身份、越权范围、Join 歧义、在 `cardinality_requirement=REQUIRED_FOR_AGGREGATION` 时的基数证明缺失或跨版本都 fail closed。`from_static()` 固定创建 `context_source=STATIC_FALLBACK`、`snapshot_identity=None`、`asset_version=None`、`metric_definitions=()`、`metric_constraints=()` 且无 Published Retrieval Evidence，并且只接受 `request_shape=BASELINE` 与 `fallback_policy=ALLOW_STATIC`；`EXPLICIT_MULTI` / `POSSIBLE_MULTI` 必须拒绝。`QueryContext` 不提供绕过这两个 Factory（工厂）的公开构造入口。这样全量版本和范围校验有明确承载点，Prompt 和 SQL Guard 不需要接收原始检索证据。

`from_published()` 还必须按 `document_id` 将每个 `TableHit` 的 `table_ref`、每个 `ColumnHit` 的 `(table_ref, column_name)` 与 `snapshot.resource_catalog` 逐项核对；命中只要不在该目录、正文身份不一致或版本/identity 不一致，就 fail closed。对 `JoinResolution`，必须按 `edge_id` 回查 `snapshot.relationship_graph` 的 `source/target`、方向、`constraint_name` 和复合键条件，并按 `edge_id + source/target columns + proof_kind` 回查每个 `CardinalityProof`；任何外部伪造的 Edge、Proof、required/optional 集合或 selected path 都必须拒绝。

成功创建 `context_source=PUBLISHED` 的 `QueryContext` 时，`evidence.join_resolution` 不能为 `None`，且必须是 `status=UNIQUE` 的已验证结果；`None` 只允许出现在零命中、技术失败或尚未进入范围组装的失败证据中，不能被 Prompt、SQL Guard 或数据库执行路径消费。

范围派生规则固定为：`retained_tables = (valid_table_hits ∪ JoinResolution.selected_paths.tables) - JoinResolution.dropped_optional_tables`；`allowed_tables = retained_tables`；`allowed_columns` 是所属表位于 `retained_tables` 的有效 COLUMN 命中以及 `JoinResolution.selected_edges` 中实际使用的 Join Key 的并集；`join_constraints` 只能由同一 Graph 中已验证的 `selected_edges` 和 `cardinality_proof` 确定性生成。`RetrievalEvidence` 只携带已选定的 `JoinResolution`，不把候选路径交给 `QueryContext` 自行猜选；多条等长可行路径、无法确定 Anchor、任一必需表不可达或在 `cardinality_requirement=REQUIRED_FOR_AGGREGATION` 时任一保留边缺少基数证明，`status` 都不能是 `UNIQUE`，`from_published()` 必须拒绝。`from_published()` 还必须拒绝任何出现在 `dropped_optional_tables` 中的表、列或 Join。任何不在这三个派生集合中的表、列或 Join 都不能进入 QueryContext。

字段使用边界：

- Prompt 使用 `MetricDefinition.semantic_text`、规范公式展示和 `metric_constraints` 兼容投影；
- SQL Guard 使用 `asset_version`、`metric_definitions` 和 `join_constraints` 做确定性检查；
- `metric_constraints` 不能反向覆盖 `metric_definitions`，也不能成为公式、固定过滤、`NULLIF` 或指标覆盖检查的唯一输入；
- `context_source=PUBLISHED` 时，`snapshot_identity` 与 `asset_version` 必须与所有 `SnapshotBoundMetricDefinition`、`MetricConstraint`、`MetricHit`、`TableHit`、`ColumnHit`、`JoinResolution` 和 `RetrievalEvidence` 一致；`QueryContext.metric_definitions` 只能是 Factory 在上述检查后解包的纯 `MetricDefinition`；
- `context_source=STATIC_FALLBACK` 时，`asset_version` 必须为空，结构化指标定义和 Published Retrieval Evidence 必须为空；
- 对外 Query API 的 JSON Body 不增加这些内部字段。

## 8. 目标代码结构

这是职责结构，不要求一次性创建全部文件：

```text
src/online_query/
├─ domain/
│  ├─ models.py                 # 稳定领域值和规则对象
│  ├─ metric_rules.py           # 指标身份、兼容性、必需字段
│  └─ relationship_rules.py     # Anchor、路径、连接安全
│
├─ application/
│  ├─ ports.py                  # LLM、DB、检索、Trace 等最小 Port
│  ├─ retrieval_service.py      # 0/1/N 指标统一检索流程
│  ├─ query_service.py          # 查询用例主流程
│  └─ prompt_builder.py         # Domain Context 到 Prompt 的转换
│
├─ infrastructure/
│  ├─ rag_adapter.py            # 发布资产、Qdrant、BGE-M3
│  ├─ llm_adapter.py            # 具体 LLM 客户端
│  ├─ sqlglot_guard.py          # SQLGlot 和确定性 SQL 检查
│  ├─ postgres_executor.py      # PostgreSQL 只读执行
│  └─ static_context.py         # 静态上下文回退
│
├─ bootstrap.py                 # 统一组装具体 Adapter
└─ __init__.py                  # 稳定公开入口
```

当前已有的 `contracts.py`、`retrieval.py`、`service.py`、`rag_runtime.py`、`llm.py`、`database.py`、`sql_guard.py`、`context.py` 会按职责渐进归位，不进行一次性大搬家。

## 9. 统一检索链路

当前单指标和多指标流程应收敛为一个应用流程：

```text
RetrievalRequest
→ RequestShapeHint（仅做初步形态判断）
→ 一致 AssetSnapshot
→ 基于该 Snapshot 的 ProvisionalMetricRequest（只含请求指标文本）
→ 完整问题 Embedding 一次（TABLE / METRIC 复用）
→ TABLE Retrieval
→ METRIC Retrieval（实体/单指标各一次基线；多指标一次综合）
→ 从同一 Snapshot 的 MetricDefinition 目录确定性解析
→ Final Version-bound MetricPlan
→ COLUMN 组合查询 Embedding 一次
→ 候选表范围内 COLUMN Retrieval
→ 必需资源完整性检查
→ Relationship Graph Resolution
→ QueryContext 的最终范围字段
→ Dynamic Schema + Indicator Context
→ QueryContext
```

不同请求只表现为计划内容不同：

- 实体查询：0 个指标；
- 单指标查询：1 个指标；
- 多指标查询：2～5 个指标。

这不改变已经确认的资源路线：TABLE、COLUMN、METRIC 仍然是不同集合和不同 Contract；“统一”只表示共用编排和错误处理，不表示合并三个集合。

“一次问题 Embedding”只指完整用户问题向量。当前 COLUMN 仍使用包含用户问题、指标语义、公式和 `time_field` 的组合查询文本，因此另外生成一次 COLUMN 组合向量；如果存在分组字段补充，还会按既有规则生成一次分组向量。具体 Search 次数保留当前按候选表过滤和必需字段补充的逻辑，见第 10.2 节。

`RequestShapeHint` 只做不依赖资产的初步判断：`BASELINE` 选择 `ALLOW_STATIC`，明确或可能的多指标形态选择 `FAIL_CLOSED`。快照加载后先创建 `ProvisionalMetricRequest`，它只绑定本次 Snapshot 和 `MetricMention`，不声称已经确定 `document_id` 或公式。完成一次规定的 METRIC Retrieval 后，再由同一版本的 `MetricDefinition` 目录完成最终解析并创建 `MetricPlan`：实体请求创建空计划；单指标的名称/别名目录匹配只用于确认目标 `document_id`，不能替代本次 METRIC 有效命中，最终必须在本次检索结果中达到指标阈值；没有目录精确映射时，才允许从同一 Snapshot 的 `MetricHit` 中选择唯一阈值以上候选，再回目录取得最终定义；多指标必须先按目录确认每个请求身份，再检查同一次综合 METRIC Retrieval 对每个身份都有同一 Snapshot 的有效命中和阈值覆盖，缺失、歧义或不兼容直接 fail closed。`MetricHit` 只证明召回，不能直接成为 `MetricDefinition` 或 `MetricPlan` 的事实来源。如果资产加载失败，不能先使用旧版本目录或静态 `metrics.json` 补齐最终计划；无法建立合法快照时直接按上述技术失败规则处理。实体请求即使最终不需要指标上下文，也保留一次基线 METRIC 检索，以符合既有 Online Retrieval Contract。

## 10. Port / Adapter Contract（端口与适配器契约）

首轮只保留真正需要替换或隔离的能力：

- `RetrievalAssetPort`：读取同版本资产、生成查询向量并返回原始检索命中；
- `SQLGenerator`：生成 SQL 候选或 `CANNOT_ANSWER`；
- `SQLGuard`：校验候选范围和 AST 安全性；
- `QueryExecutor`：只读执行已校验 SQL；
- `TraceRecorder`：记录请求和内部阶段。

Port 只描述输入、输出、受控失败，不暴露 Qdrant、LangChain、psycopg、SQLGlot 和 OpenTelemetry 类型。

### 10.1 RetrievalAssetPort 的最小边界

`RetrievalAssetPort` 只做技术资源访问，不做业务裁决。其逻辑 Contract 为：

```text
load_snapshot()
    -> PublishedRetrievalSnapshot

embed(snapshot, text)
    -> OpaqueQueryVector

search(snapshot, collection_kind, vector, limit, table_filter?)
    -> tuple[RawRetrievalHit, ...]
```

`PublishedRetrievalSnapshot` 的 Application 可见 Contract 固定为：

```text
PublishedRetrievalSnapshot
  identity: OpaqueSnapshotIdentity
  asset_version: str                 # V1 中等于发布资产 build_id
  available_collection_kinds: frozenset[CollectionKind]
  resource_catalog: SnapshotResourceCatalog
  metric_definitions: tuple[SnapshotBoundMetricDefinition, ...]
  relationship_graph: RelationshipGraphFacts
  embedding_fingerprint: EmbeddingFingerprint
  adapter_private_bindings: opaque   # 物理集合句柄、Qdrant Store、模型实例
```

其中 `adapter_private_bindings` 只能被 Adapter 自己解释；Application 只能把不可变 Snapshot 句柄传回 `embed()` / `search()`，不能通过 Mapping、任意字符串或反射取得物理集合名。

版本隔离的具体 Contract：

- `CollectionKind = TABLE | COLUMN | METRIC` 是 Application 唯一可以传给 `search()` 的集合身份；
- Adapter 从发布 Manifest 取得物理集合名，并验证它等于当前 `OfflineBuildConfig.collection_name(kind, build_id)` 生成的名称；Manifest 的 `build_id`、当前发布指针、集合名称和集合文档数量必须一致；
- 发布端写入和在线 Adapter 校验必须共同调用同一个纯函数 `canonical_collection_name(prefix, collection_kind, build_id)`；禁止构建端和运行端各自维护一份物理命名公式；
- Adapter 同时校验集合存在、文档数量、Embedding model / dimension 和 Relationship Graph 的版本；任一不一致返回 `AssetUnavailableError`，不得跨版本拼接；
- 发布 Manifest 必须提供 `relationship_graph_sha256`；它是 Graph 文件规范化 JSON 的 SHA-256，缺失或不匹配时视为资产契约不完整并返回 `AssetUnavailableError`，不把“路径位于 build 目录内”当作充分证明；
- Graph 文件路径必须是对应 `build_id` 目录内的安全相对路径；规范化算法固定为 `json.dumps(graph, ensure_ascii=False, sort_keys=True, separators=(",", ":"))` 的 UTF-8 字节后计算 SHA-256。这只是发布完整性字段，不改变 Relationship Graph 的业务事实或检索语义；
- `RawRetrievalHit` 以及映射后的 TABLE/COLUMN/METRIC/Graph evidence 均携带 `asset_version`，由 Snapshot 产生，不允许调用方手工填写；
- Application 不接触 `collection_names` 或任何物理集合名；`search(snapshot, collection_kind, ...)` 不能接受任意字符串集合名；
- V1 与 V2 同时存在时，V1 请求只能使用 V1 Snapshot；即使 V1 Manifest 被故意指向 V2 集合、Graph 或 Embedding，也必须 fail closed。

T4A 的双版本隔离测试必须覆盖：V1 current + V2 集合并存、V1 Manifest 指向 V2 集合、V1 Manifest 指向 V2 Graph、V1 Manifest 使用 V2 Embedding model/dimension，以及 Graph 哈希缺失或不匹配；每种情况都返回 `AssetUnavailableError` / `CONTEXT_ERROR`，且不产生跨版本命中。

Adapter 必须保证这些内容来自同一个已发布版本，并负责把技术错误转换为明确的 Adapter Error：

| 技术问题 | Adapter Error | Application 对外处理 |
|---|---|---|
| 已发布资产、Embedding、Qdrant 或 Graph 技术故障 | 对应 Adapter Error | 实体/单指标基线在 `ALLOW_STATIC` 下静态 fallback；多指标 `CONTEXT_ERROR` |
| 静态上下文本身缺失、损坏或无法建立合法上下文 | `StaticContextUnavailableError` | 所有请求 `CONTEXT_ERROR` |
| 必需资源合法检索结果为空 | 无技术异常 | 按请求形态返回 `CANNOT_ANSWER`；实体类 METRIC 空命中合法并继续 |
| 指标公式或 filters 无法确定性解析 | `InvalidAssetError` | 实体/单指标基线按 `ALLOW_STATIC` fallback；多指标 `CONTEXT_ERROR` |

业务资源空命中、`AMBIGUOUS`、`PARTIAL_UNREACHABLE` 和不支持的多指标组合不属于技术故障，不能走静态 fallback。

版本一致性是不变量：

- 最终 `MetricPlan.snapshot_identity` / `asset_version` 必须存在；检索前的 `ProvisionalMetricRequest` 只能处于 `PENDING_RESOLUTION`，不能进入 QueryContext；
- 每个 `SnapshotBoundMetricDefinition`、`MetricHit`、TABLE/COLUMN Hit、`JoinResolution` 和 `MetricConstraint` 必须带同一 `snapshot_identity` / `asset_version`；纯 Domain `MetricDefinition` 只能通过已验证 wrapper 进入 Published Context；
- `MetricPlan`、指标目录、TABLE/COLUMN 命中、`JoinResolution`、Relationship Graph 和 Embedding 配置必须来自同一个 `PublishedRetrievalSnapshot`；
- `RetrievalAssetPort.search()` 只能接收 Snapshot 与逻辑 `CollectionKind`，不接受调用方传入的任意物理集合名；
- Adapter 内部根据 Snapshot 的 Manifest 解析物理集合，并校验物理集合名与 `build_id` / `asset_version` 的绑定；
- Manifest、集合、Graph 或模型版本不一致时返回 `AssetUnavailableError`，不得跨版本拼接；
- 必须有双版本隔离测试：当 V1 为当前发布版本、V2 集合同时存在时，V1 请求不得搜索或返回 V2 集合的命中。

Adapter 不得负责：

- 选择最终指标；
- 判定指标组合是否兼容；
- 把指标 `data_source` 自动补成 TABLE 命中；
- 判定必须列是否完整；
- 选择 Join Path；
- 决定是否静态回退；
- 让 LLM 猜测缺失资源。

这些属于 Application 调度或 Domain 规则。

Adapter Error taxonomy（适配器错误分类）固定为：

| 错误 | 来源 | 实体/单指标 | 多指标 | 对外错误码 | Trace 分类 | 同一请求自动重试 |
|---|---|---|---|---|---|---|
| `AssetUnavailableError` | `PublishedAssetError`、Manifest、集合、Graph 或版本不一致 | `ALLOW_STATIC`；静态上下文失败则 `CONTEXT_ERROR` | `CONTEXT_ERROR` | `CONTEXT_ERROR` | `TECHNICAL_FAILURE` | 否 |
| `InvalidAssetError` | 指标公式或 filters 无法规范化、`RetrievalContractError` | `ALLOW_STATIC`；静态上下文失败则 `CONTEXT_ERROR` | `CONTEXT_ERROR` | `CONTEXT_ERROR` | `TECHNICAL_FAILURE` | 否 |
| `RetrievalUnavailableError` | `QdrantStoreError`、Qdrant/检索服务不可用 | `ALLOW_STATIC` | `CONTEXT_ERROR` | `CONTEXT_ERROR` | `TECHNICAL_FAILURE` | 否 |
| `EmbeddingUnavailableError` | `EmbeddingError`、Embedding 初始化或查询失败 | `ALLOW_STATIC` | `CONTEXT_ERROR` | `CONTEXT_ERROR` | `TECHNICAL_FAILURE` | 否 |
| `StaticContextUnavailableError` | 静态上下文本身缺失或损坏 | `CONTEXT_ERROR` | `CONTEXT_ERROR` | `CONTEXT_ERROR` | `TECHNICAL_FAILURE` | 否 |
| `SQLRejectedError` | AST/候选范围/指标安全校验失败 | 不 fallback | 不 fallback | `SQL_REJECTED` | `BUSINESS_REJECTION` | 否 |

日志和 Trace 只记录上表中的安全错误类型和公开错误码，不记录原始异常文本或堆栈；Trace Adapter 自身失败仍按 Observability Contract fail-open。

### 10.2 统一检索的实际调用基线

首轮统一流程必须保持当前调用语义：

```text
完整问题 Embedding：一次
    ├─ TABLE 基础检索复用
    └─ METRIC 基础/综合检索复用（所有请求形态）

COLUMN 组合查询 Embedding：一次
    └─ 候选表范围内的 COLUMN 搜索复用

分组字段补充 Embedding：保持当前行为；存在分组补充且有目标表时，TABLE 补充一次、COLUMN 补充一次

TABLE Search：基础查询一次；存在分组补充时每个补充查询一次
METRIC Search：实体和单指标各一次基线检索；多指标一次综合检索
COLUMN Search：按候选表过滤逐表检索；必需字段精确补充检索仍按当前规则执行
```

这些是逻辑调用基线，不把同一向量在不同候选表上的多个过滤 Search 错算成一次。T3 必须为实体、单指标和多指标分别记录并断言实际调用次数；如果为性能优化改变调用次数，必须先独立评测，不能借重构名义改变。

多指标的 METRIC Search limit 必须为：

```text
max(config.metric_top_k, 5, requested_metric_count)
```

T3 必须同时断言实际 limit，而不仅是调用次数。COLUMN Search 还要分别记录基础候选表检索、分组字段补充检索和必需字段精确补充检索的次数。

实体、单指标和多指标的期望矩阵如下；“按候选表”表示次数由候选表数量和既有必需字段补充规则决定，不得被误读为一次：

| 请求形态 | 完整问题 Embedding | TABLE Search | METRIC Search | COLUMN 组合 Embedding | 分组 Embedding | COLUMN Search |
|---|---:|---:|---:|---:|---:|---:|
| 实体 | 1 | 1 + 可选分组补充 | 1 次基线检索 | 1 | 0 或 TABLE 1 + COLUMN 1 | 按候选表 + 既有补充规则 |
| 单指标 | 1 | 1 + 可选分组补充 | 1 次基线检索 | 1 | 0 或 TABLE 1 + COLUMN 1 | 按候选表 + 既有补充规则 |
| 多指标 | 1 | 1 + 可选分组补充 | 1 次综合检索 | 1 | 0 或 TABLE 1 + COLUMN 1 | 按候选表 + 既有补充规则 |

实体请求的 METRIC 零命中仍是合法业务结果并继续；单指标和多指标的指标有效性仍按各自正式规格检查。

追踪仍然保留现有核心 Span 名称，例如：

```text
query.request
request.validate
retrieval.plan
retrieval.execute
embedding.query
table.search
metric.search
column.search
join.resolve
context.assemble
prompt.build
llm.generate
candidate_scope.validate
sql.guard
database.execute
```

### 10.3 Observability Contract 的归属

`docs/specs/observability.md` 和 `docs/designs/observability.md` 是本设计的事实源之一。重构只改变 Trace Recorder 的注入位置，不改变可观测行为：

- `request_id` 和 `trace_id` 是两个不同标识；Root Trace 必须绑定 `request_id`；
- HTTP Root Trace 在请求体解析前由 API 边界创建或复用，Query Service 只能借用已有 Root Trace；
- 直接 Evaluation 调用和 HTTP 调用都只能有一个 Root Trace 所有者；
- 只有实际执行的节点创建 Span；不存在的分支不能补造 Span；
- Retrieval fallback 必须记录原失败状态、实际采用路径和最终结果；
- Span 只记录安全错误类型和公开错误码，不记录完整问题、Prompt、SQL、结果、Secret、原始异常或堆栈；
- Query API 通过 `X-Trace-ID` 返回 `trace_id`，不改变既有 JSON Body；
- Trace 初始化、记录和导出失败必须 fail-open，不改变业务结果、错误码和调用次数。

因此 Trace Port 属于 Application 可调用的横切 Port，具体 OpenTelemetry 实现属于 Infrastructure；Domain 不创建 Span。

Root Trace 采用“外层优先、无外层兼容创建”的规则，与现有 Observability Design 保持一致：

```text
HTTP / Evaluation Boundary
    必须先调用 query_trace(source, request_id)
    → 成为对应 Root Trace 所有者

OnlineQueryService.query()
    调用同一个 query_trace(source, request_id)
    → 有活动 Root 时只借用
    → 没有活动 Root 时为直接调用创建并关闭唯一 Root

Service、Application 和 Adapter
    只能通过 span(name, attributes) 创建实际执行的子 Span
```

这里不新增第二套必须由调用方掌握的 `begin_root_trace()` / `borrow_current_trace()` API；现有 `query_trace()` 的 `owns_root` 返回值就是所有权 Contract。T4C 必须分别验证：外层 Trace 存在时 Service scope 的 `owns_root == False`；直接调用无外层 Trace 时 Service 只创建一个 `query.request` 并在结束时关闭；两种路径都不能产生第二个 Root。T4B 只验证 HTTP / Evaluation Boundary 持有 Root 和返回 `X-Trace-ID`。

## 11. 行为和不变量

重构前后必须保持：

- `OnlineQueryService.query()` 仍是唯一正式查询入口；
- Query API 的输入输出和公开错误码不变；
- TABLE → COLUMN、独立 METRIC、Relationship Graph 和多指标一次综合召回规则不变；
- 未找到表、列或指标时仍然整次停止，不返回部分结果；
- LLM 仍然只是候选提出者，不能决定指标事实、权限、范围和 SQL 安全；
- SQL 未通过 Candidate Scope Check 或 AST Guard 时不访问数据库；
- 数据库仍使用只读身份、超时和结果行数限制；
- Trace 失败不能阻断业务；
- 日志和 Trace 不记录完整 Prompt、完整异常正文、Secret 或业务敏感数据；
- 既有实体、单指标、多指标、拒答和无数据行为不改变。

## 12. 独立可验证的任务拆分

本文任务的正式 ID 使用 `DDD-` 前缀（下文简称 T1～T5B），避免与 Observability 或其他 Feature Spec 中的同名验收编号混淆。依赖关系固定为：

```text
DDD-T1 → DDD-T2 → DDD-T3
DDD-T1 → DDD-T4A
DDD-T1 → DDD-T4B
DDD-T2 + DDD-T3 + DDD-T4A + DDD-T4B → DDD-T4C
DDD-T1～DDD-T4C → DDD-T5A → DDD-T5B
```

每条箭头表示前置 Contract / 组装证据已经通过；没有前置任务的独立测试不得偷偷承担其职责。

### T1：边界与 Contract 归位

目标：只建立 Domain Value、Application DTO、Port 和 Infrastructure 类型边界，补齐版本字段与兼容 façade；不改查询编排和业务规则。

验证：

- 使用 fake Port 的 Contract 构造测试通过，不依赖 Qdrant、LLM、PostgreSQL 或外部服务；
- 现有公开导入兼容清单通过：`OnlineQueryService`、`OnlineRetriever`、`RagRuntime`、`src.online_query.contracts`、`build_service()`、`run_cli()`；
- Domain / Application import boundary 检查通过：不得导入 Qdrant、SQLGlot、psycopg、OpenTelemetry、文件 IO 或环境变量；
- `MetricDefinition`、`SnapshotBoundMetricDefinition`、`MetricPlan`、`MetricHit` 和 `QueryContext` 的 Snapshot identity / asset version 构造校验通过；
- `PublishedRetrievalSnapshot` 只通过逻辑 `CollectionKind` 暴露检索入口，物理集合名不进入 Application Contract；
- 不改变查询结果和错误码，不改变实体/单指标/多指标的检索调用次数。

### T2：提取纯 Domain Rules

目标：只提取纯 Domain Rules：指标身份、定义唯一性、MetricPlan 版本绑定、兼容性、必需字段、路径和连接安全规则；输入是已经规范化的 `MetricDefinition`，不接收 SQLGlot/Qdrant 类型。

验证：

- 指标规划、定义唯一性、关系图、失败语义和 SQL 约束相关单元测试通过；
- `SnapshotBoundMetricDefinition → MetricConstraint` 只有一个绑定 `MetricPlan` 的投影函数；`QueryContext.from_published()` / `from_static()` 的版本、身份、顺序和数量一致性测试通过；
- 同一 `document_id` 公式冲突、命中版本不一致、缺失定义和不支持公式均确定性失败；
- 投影的错序、错 `document_id`、错 metric name、错 Snapshot identity、错 asset version 和静态上下文携带结构化指标均确定性失败；
- ProvisionalMetricRequest 在指标尚未解析时不能进入 QueryContext；单指标精确命中、唯一阈值候选和多指标逐项目录解析分别有确定性测试；
- JoinResolution 的等长路径歧义、必需表不可达、可选表丢弃按正式语义处理；当 `cardinality_requirement=REQUIRED_FOR_AGGREGATION` 时缺少逐边基数证明确定性失败，普通实体/单指标路径不因新增 proof 字段改变既有行为；QueryContext 额外注入未命中表、列或 Join Key 时确定性拒绝；范围只能由 Evidence/Graph 派生；
- TABLE/COLUMN Hit 必须回查 Snapshot-owned catalog；JoinEdge / CardinalityProof 必须按 edge_id、方向、两端列和 proof_kind 回查同一 RelationshipGraph；
- Domain 仍不依赖外部技术。

### T3：统一 Retrieval Application Service

目标：只实现 Application Retrieval Service 的一条流程覆盖实体、单指标和多指标；通过 Port 编排，不依赖真实 Qdrant；消除当前两个大流程的重复。

验证：

- 使用 fake `RetrievalAssetPort` 的 Application 测试通过，不依赖真实 Qdrant、BGE-M3 或外部服务；
- 实体、单指标、多指标分别按第 10.2 节矩阵断言 Embedding、TABLE Search、METRIC Search、COLUMN Search 次数；
- 分组请求分别断言 TABLE 补充 Embedding 与 COLUMN 补充 Embedding 各一次（无分组或无目标表时为零），不得把两次现有调用误合并为一次；
- 多指标只发生一次综合 METRIC Search；
- 多指标 METRIC Search 的实际 `limit` 等于 `max(config.metric_top_k, 5, requested_metric_count)`；
- Application 只传递同一个 Snapshot 句柄；ProvisionalMetricRequest、最终 MetricPlan、SnapshotBoundMetricDefinition、MetricHit、TABLE/COLUMN/Graph evidence 的 identity / 版本前置条件不一致时 fail closed；
- 单指标先检索后最终确定 MetricPlan；唯一阈值候选只能回查同一 Snapshot 的 MetricDefinition 目录，不能从 MetricHit 复制公式；
- 完整问题向量、COLUMN 组合查询向量和可选分组向量符合第 10.2 节基线；
- 业务零命中、技术故障、实体 METRIC 零命中和多指标 fail-closed 的结果与正式规格一致。

### T4A：Published Snapshot Adapter 归位

目标：只验证发布端 Manifest 与 Infrastructure RAG Adapter 的 Snapshot、CollectionKind 和 fail-closed 版本隔离；不处理 HTTP、Evaluation 或 Trace 组装。发布端只补充 Graph 完整性字段，不改变 RAG 文档和业务事实。

验证：

- 构建端写入规范化 Graph JSON 的 `relationship_graph_sha256`，发布加载器读取并校验；
- Adapter 的确定性测试验证 `asset_version == build_id`、Manifest/物理集合绑定、Graph SHA-256、文档数量、Embedding model/dimension 和双版本隔离；
- `SearchHit`、物理集合常量、`EmbeddingError`、`QdrantStoreError` 不穿过 Application；Application 只使用 `RawRetrievalHit`、`CollectionKind` 和受控 Adapter Error；
- 同一 Snapshot 产生的 TABLE/COLUMN/METRIC/Graph evidence 版本一致；
- 不依赖 HTTP、Evaluation、真实 LLM 或数据库。

T4A 可用 fake Qdrant/Embedding 与临时 Manifest 独立验证，不依赖 T4B/T4C。

### T4B：Bootstrap 与 Boundary Trace 归位

目标：只验证 Infrastructure Adapter 的统一组装、Query API / Evaluation 入口和 Boundary Root Trace 传播；使用稳定 fake Query Service / fake Application Port，不依赖 T4C 的真实 OnlineQueryService 链路，也不重新实现 Snapshot 隔离。

验证：

- Bootstrap、API 和 Evaluation 的组装测试分别通过；Query API、数据库集成和 Streamlit 只验证现有入口没有断裂，不在此 Task 新增功能；
- 使用 fake Query Service 的真实 `create_app()` / HTTP Boundary 组装路径验证 Boundary Root Trace、`X-Trace-ID` 和响应序列化；真实 `OnlineQueryService` 的 Root 所有权与完整链路验证归入 T4C；
- Boundary Observability 测试确认 `request_id` / `trace_id`、实际 Span、fallback 属性、脱敏和 fail-open；Service 借用/直接创建 Root 的测试不在 T4B 重复；
- Trace 失败不改变原查询结果、错误码和调用次数。

T4B 可用 fake Query Service、fake Application Port 和真实 HTTP/Evaluation Boundary 独立验证，不依赖 T4C 的真实查询用例。

### T4C：Query Use Case Integration 归位

目标：只把 `OnlineQueryService` 的完整查询用例迁移到 Application Port；接入 Prompt Builder、LLM、SQL Guard 和 Database Adapter，不新增查询功能。

验证：

- `OnlineQueryService` 不直接依赖具体 LLM、PostgreSQL、SQLGlot 或文件读取实现；具体实现只在 Bootstrap/Infrastructure 组装；
- 使用 fake Port 验证 Retrieval → `QueryContext` → Prompt → LLM → SQL Guard → Database 的顺序、错误映射和数据库调用前置条件；
- 使用真实 `OnlineQueryService` + fake Application Ports 验证外层 Trace 存在时 Service 借用 Root、无外层 Trace 时只创建并关闭一个 Root，且两种路径都不产生第二个 `query.request`；
- SQL Guard 只从 `QueryContext.metric_definitions` 读取结构化公式/filters/物理字段；它可以读取 `metric_constraints` 的已验证 ordinal、requested_text、document_id 和 metric_name 做请求覆盖检查，但不得读取其展示副本作为业务真相；
- STATIC fallback 保持 `asset_version=None` 和空结构化指标定义，不把静态 Prompt 文本转换成 Published MetricDefinition；
- API、Evaluation 和直接 Service 调用的公开结果、错误码、Trace 行为不变。

T4C 在 T1～T3 Contract 已通过后，以 fake LLM/SQL Guard/Database Port 独立验证完整用例；不要求外部服务在线。

### T5A：最终验收与证据门

目标：只做最终验证，不删除兼容 façade、不改文档事实源。

验证：

- Software Test、AI Evaluation、Business Acceptance 分开报告；
- C05 的已知 Software Test / AI Evaluation 结果、SQL、错误码和 Trace 链路不退化；Business Acceptance 状态保持独立，不在 T5A 自动关闭；
- 生产代码不因目录搬迁而膨胀；`retrieval.py` 不再同时承担完整编排、Domain 规则、技术适配和 Trace 实现；
- 执行生产代码 import / 旧入口引用扫描并保存结果；发现未登记 Symbol 时停止，不自行扩张范围。

### T5B：兼容 façade 清理与文档同步

目标：仅在 T5A 通过后，删除无调用旧 façade 并同步历史状态文档；不承担新的结构实现或业务行为修改。

验证：

- 删除无调用旧导出后，完整入口和回归测试仍通过；
- 同步全部已登记的状态事实源：`docs/specs/online-retrieval.md`、`docs/specs/online-query.md`、`docs/runbook.md`、`docs/development-process.md`、相关 `docs/designs/*` 和本迁移表；统一 Software Test / AI Evaluation / Business Acceptance 三态；
- `online-retrieval.md` 的历史实现状态、多指标专门规格、Architecture、迁移表和实际引用扫描一致；
- 文档同步失败或旧实现删除失败时，可以独立回滚 T5B，不影响 T5A 的验收证据。

每个 Task 都按“实现一个行为 → 独立测试 → Review Diff → 单独 Commit”完成，不按任意文件数量拆分。

## 13. 设计验收标准

### Architecture

- Domain 不依赖具体技术和 IO。
- Application 只依赖 Domain 与 Port。
- Infrastructure 实现 Port，不反向定义业务事实。
- Query API、Evaluation 和 Streamlit 不复制核心链路。
- 依赖图无循环。
- Domain 不直接接收 `MetricCatalogEntry`、`MetricHit`、SQLGlot AST 或 Qdrant 命中类型。
- 公式和 filters 的 SQLGlot 解析只在 Infrastructure Adapter / Normalizer 完成，失败必须转换为受控资产错误。

### Maintainability（可维护性）

- 单指标、多指标不再维护两套完整检索主流程。
- 每个主要文件有单一职责，打开文件可以直接判断它负责业务规则、流程编排还是技术接入。
- 不新增没有独立验证价值的抽象。
- 生产代码总量不因纯目录移动而膨胀；重复逻辑应实际减少。
- `QueryContext` 是首轮唯一最终范围 Contract，不新增未定义的 `QueryScope`。

### Behavior

- 现有确定性测试全部通过。
- 真实在线评测结果不下降。
- C05 的已知 Software Test / AI Evaluation 证据保持一致；Business Acceptance 仍由用户单独确认。
- 追踪节点、错误码、回退边界和安全边界保持一致。
- Embedding、Search 和 Span 调用符合第 10.2 节基线；未经单独评测不得改变调用次数。

## 14. 影响、风险与回滚

影响范围：

- 主要影响 `src/online_query/`；
- 直接调用方为 `src/query_api/main.py`、`src/evaluation/__main__.py` 和相关测试；
- 不修改数据库、RAG 已发布资产、环境变量和外部监控平台。

主要风险：

- 只移动文件但没有统一流程，代码数量反而增加；
- 为保持兼容而留下过久的旧入口；
- Trace Span 名称或属性变化导致现有链路分析断裂；
- SQL Guard 的领域规则和 AST 技术规则拆分错误，形成安全绕过。

控制措施：

- 先保留兼容导出，再逐步删除无调用旧实现；
- 每一步保持现有测试和真实评测证据；
- Span 名称作为稳定 Contract 保留；
- SQL Guard 仍只有一个最终公开安全入口，不能出现旁路。

回滚方式：每个 Task 单独 Commit；若某一步验证失败，只回滚该 Task 的 Commit，不回退数据库、RAG 资产或用户已有工作区修改。

## 15. 公共入口兼容清单

重构期间以下 Symbol（符号）按表处理；T1～T4C 期间保留兼容 façade 或同步迁移调用方，T5A 通过后由 T5B 才能删除无调用旧实现：

| 当前路径与 Symbol | 当前调用方 | 目标位置 | 处理方式 | 删除条件 |
|---|---|---|---|---|
| `online_query.OnlineQueryService`、`QueryRequest`、`QueryResult` | API、Evaluation、测试 | Application / `online_query.__init__` | 保留公开导出 | 无替代公开入口，不删除 |
| `online_query.contracts.QuerySuccess`、`QueryFailure`、`QueryErrorCode`、`QueryData`、`ValidatedSQL` | API、Evaluation、Service、Database/LLM/SQL Guard tests | Application / Interface Contract | 保持原路径导出；内部逐步迁移到分层 Contract | 对外查询协议没有变化；不删除稳定公开类型 |
| `online_query.contracts.QueryContext` | Service、Prompt、SQL Guard、Retrieval、相关 tests | Application Final Context | 原路径 façade；增加 `context_source`、可空 `asset_version` 和结构化指标投影 | T2 QueryContext 构造不变量与 T3/T4B 回归通过 |
| `online_query.contracts.RetrievalRequest`、`RequestShape`、`FallbackPolicy`、`RetrievalStatus` | Retrieval、Service、Multi-Metric、Retrieval tests | Application Contract | 原路径 façade；内部调用方同步迁移 | T3 fake Port 回归及引用扫描通过 |
| `online_query.contracts.RetrievalConfig`、`OnlineRetrievalResult` | Retrieval、Retrieval Service、Retrieval tests | Application Retrieval Contract | 原路径 façade；统一流程使用新的 Application DTO | T3 调用矩阵、错误语义和结果回归通过 |
| `online_query.contracts.RetrievalProvider`、`SQLGenerator`、`QueryExecutor` | API、Evaluation、Service、集成测试 | Application Port | 保持 Protocol（协议）语义；具体实现迁移到 Infrastructure | T4B 组装测试和入口回归通过 |
| `online_query.contracts.MetricMention`、`MetricPlanStatus`、`MetricRequestPlan`、`MetricConstraint` | Multi-Metric、Retrieval、SQL Guard、相关 tests | Domain Metric Planner + Application projection | `MetricRequestPlan` 保留为兼容别名；`MetricConstraint` 只能由 `SnapshotBoundMetricDefinition + MetricMention + ordinal` 投影生成 | T2 版本/身份/投影测试通过，T5B 无业务逻辑旧引用 |
| `SnapshotBinding`、`SnapshotBoundMetricDefinition`、`TableCatalogEntry`、`ColumnCatalogEntry`、`SnapshotResourceCatalog` | Published Snapshot Adapter、Metric Planner、QueryContext | Application Snapshot Contract | 由 Snapshot Factory 创建；MetricDefinition 保持纯 Domain 值对象；TABLE/COLUMN/Metric 都必须回查同一 Snapshot 目录 | T1/T2/T4A 来源闭包与 catalog 回归通过 |
| `online_query.contracts.TableHit`、`ColumnHit`、`MetricHit`、`MetricRetrievalEvidence`、`RetrievalEvidence` | Retrieval、Evaluation、Retrieval tests | Application Retrieval Evidence | 保留兼容字段；新增版本绑定并由 Port 产生 | T3 证据版本一致性回归通过 |
| `online_query.contracts.JoinEdge`、`JoinConstraint`、`JoinPath`、`JoinResolution` | Retrieval、SQL Guard、Retrieval tests | Domain Relationship Rules + Application DTO | Domain 规则迁移；原路径导出过渡 | T2 图规则与 T3 QueryContext 回归通过 |
| `online_query.retrieval.OnlineRetriever` | Query API、Evaluation、Retrieval tests | Application Retrieval Service + Infrastructure Adapter | 原路径 façade | T5A 引用扫描通过，T5B 删除后完整回归通过 |
| `src.rag_offline.documents.TABLE_COLLECTION`、`COLUMN_COLLECTION`、`METRIC_COLLECTION`；`src.rag_offline.qdrant_store.SearchHit`、`QdrantStoreError`；`src.rag_offline.embedding.EmbeddedText`、`EmbeddingError` | 当前 `OnlineRetriever` 内部 | Infrastructure RAG Adapter | `CollectionKind`、`RawRetrievalHit` 和 Adapter Error 替代；这些技术 Symbol 不得穿过 Application | T4A 通过且 Application 层不再导入 `src.rag_offline.*` |
| `src.rag_offline.build.COLLECTIONS`、`PublishedAsset`、`PublishedAssetError`、`load_published_asset`；`src.rag_offline.config.OfflineBuildConfig` | `RagRuntime`、RAG Runtime tests | Infrastructure Published Asset Loader | 只在 Offline/Infrastructure 内部使用；Application 只接收不可变 Snapshot 句柄 | T4A Loader/Manifest 回归通过，Application 无这些导入 |
| `src.rag_offline.build._physical_collection_name`、`OfflineBuildConfig.collection_name` | Offline Build、RAG Runtime | Shared Infrastructure Asset Contract | 合并为 `canonical_collection_name()`，发布端写入与在线校验共用 | T4A 命名一致性和双版本测试通过 |
| `src.rag_offline.embedding.BgeM3EmbeddingProvider`、`EmbeddingProvider`；`src.rag_offline.qdrant_store.QdrantAssetStore` | `RagRuntime`、Qdrant/Embedding tests | Infrastructure RAG Adapter | 具体实现留在 Adapter；Port 只暴露 `embed()` / `search()` | T4A Adapter fake/真实边界测试通过 |
| `sqlglot.exp`、`sqlglot.parse_one`、`sqlglot.parse`、`sqlglot.qualify`、`sqlglot.traverse_scope`、`SqlglotError` | `multi_metric`、`sql_guard`、SQL Guard tests | Infrastructure Formula Normalizer / SQL Guard | 原路径测试可暂留；Domain/Application 不得导入 SQLGlot | T2 Domain import 检查和 T4C SQL Guard 回归通过 |
| `online_query.application.ports.RetrievalAssetPort`、`SQLGuard`、`TraceRecorder` | 新 Application Service、Bootstrap | Application Port | 只保留中立输入/输出和受控错误；具体 Adapter 在 T4A/T4B/T4C 组装 | T1 Port Contract、T3/T4A/T4B/T4C 回归通过 |
| `src.observability.tracing.create_trace_recorder`、`src.observability.contracts.TraceRecorder`、在线 Retrieval 的 `_safe_*` Trace helper | API、Service、Retrieval、Evaluation | Infrastructure Observability Adapter + Application Trace Port | 具体 Recorder factory/helper 留在 Infrastructure；Application 只调用 Trace Port | T4B Root Trace/Span/fail-open 回归通过 |
| `src.observability.tracing.create_in_memory_recorder`、`SafeTraceRecorder` | Observability / API / Evaluation tests | Test-only Observability Fixture | 仅保留测试入口，不进入 Application 生产 Contract；生产代码不导入 in-memory fixture | T4B 测试边界扫描通过 |
| `tests.evaluation.test_evaluator` 的 `sqlglot.parse_one` | Evaluation test helper | Test-only SQL expected-result parser | 明确为测试保留入口，不代表生产 Domain/Application 依赖 SQLGlot | T5A 生产代码 import 扫描与评测回归通过 |
| `online_query.retrieval.RetrievalContractError` | 当前 Retrieval 内部、Retrieval tests | Infrastructure Adapter Error Mapping | 映射为受控 `InvalidAssetError` / `AssetUnavailableError`，不穿过 Application | T3/T4A 错误矩阵和安全日志回归通过 |
| `online_query.rag_runtime.RagRuntime`、`AssetSnapshot`、`MetricCatalog`、`MetricCatalogEntry`、`AssetUnavailableError`、`RetrievalUnavailableError`、`EmbeddingUnavailableError` | API、Evaluation、Retrieval、RAG Runtime、Multi-Metric tests | Infrastructure RAG Adapter；`PublishedRetrievalSnapshot` 和 `MetricDefinition` 进入 Port/Domain | 原路径 façade；测试迁移；物理集合名不再进入 Application | T4A Snapshot/Collection 隔离通过，T5B 无旧实现引用 |
| `InvalidAssetError`、`StaticContextUnavailableError`、`SQLRejectedError`、`AdapterError` | 新 Adapter、Static Context、SQL Guard | Infrastructure Error Mapping + Application Error Contract | 内部错误分类按 10.1 taxonomy 映射；不把原始异常泄露到 API/Trace | T2/T4A/T4C 错误矩阵与安全回归通过 |
| `online_query.service.OnlineQueryService` | Service tests、入口组装 | Application Query Service | 原路径 façade | 所有调用方迁移且公开入口保持 |
| `online_query.context.load_query_context`、`ContextLoadError`、`DEFAULT_*` | Service、Evaluation、Context、SQL Guard tests | Infrastructure Static Context | 原路径 façade；明确 `STATIC_FALLBACK` 来源 | Static Context 适配和 fallback 回归通过 |
| `online_query.prompt.build_prompt` | Service、Prompt tests | Application Prompt Builder | 原路径 façade | 全部调用迁移 |
| `online_query.multi_metric.classify_request_shape`、`build_retrieval_request` | Service、Retrieval、Multi-Metric、Retrieval Observability tests | Application Request Planner | 原路径 façade | T1/T2 迁移和回归通过 |
| `online_query.multi_metric.plan_multi_metric_request` | Retrieval、Multi-Metric tests | Domain Metric Planner | 原路径 façade | Version-bound MetricPlan 测试通过 |
| `online_query.sql_guard.validate_sql`、`validate_candidate_scope`、`SQLRejectedError` | Service、SQL Guard tests、Evaluation、Service Integration tests | Infrastructure SQL Guard + Domain Rule input | 原路径保留唯一安全入口；SQL Guard 只读取结构化 `MetricDefinition` | 新 QueryContext 投影和安全回归通过 |
| `online_query.llm.LangChainSQLGenerator`、`LLMError` | API、Evaluation、LLM、Service tests | Infrastructure LLM Adapter | 原路径 façade | Adapter 组装和测试迁移完成 |
| `online_query.database.PsycopgQueryExecutor`、`DatabaseError`、`DatabaseQueryTimeout` | API、Evaluation、Database、Service tests | Infrastructure PostgreSQL Adapter | 原路径 façade | 只读集成测试和组装迁移完成 |
| `query_api.main.build_service`、`evaluation.__main__.run_cli` | API / Evaluation 正式入口 | Bootstrap / Interface | 保持函数入口，内部改为统一 Bootstrap | API、Evaluation 完整回归通过 |

兼容 façade 只能转发到新实现，不能保留第二套业务逻辑。T5A 必须执行 `rg` 引用扫描、公开导入检查和 Application 层无 `src.rag_offline.*` 技术导入检查；T5B 在此证据通过后再删除无调用旧实现并运行完整回归，确认不会破坏测试、Evaluation 或运行入口。

这张表覆盖当前 `src/`、`tests/`、`src/evaluation/` 和 `src/query_api/` 中的跨模块直接导入。T1 开始前先执行一次直接导入清单扫描；如果扫描发现表外 Symbol，必须先补入本表并归属到一个 Task，不能把未登记的迁移留到 T5A/T5B 才处理。

## 16. 待审查事项

以下事项是实现前需要由设计审查确认的边界，不是当前编码问题：

1. `Online Retrieval` 是否继续作为 Online Query 内部能力：本设计建议继续保留。
2. `rag_offline` 与在线 Adapter 的公开边界：本设计建议先不重命名离线模块，只收紧在线调用入口。
3. 旧模块导入路径是否保留过渡兼容：本设计建议保留到 T5A，T5A 通过后再由 T5B 按实际调用删除。
4. SQL Guard 是否分离内部 AST 解析实现：本设计建议可以分离内部实现，但对外只保留一个安全入口。
5. 是否引入完整 `SemanticQuery`：本设计建议暂缓，等日期、维度、过滤条件形成稳定 Contract 后再设计。

## 17. 当前结论

本设计采用 DDD-lite 的增量方案：按业务模块保留顶层结构，只对 Online Query 内部进行 Domain / Application / Infrastructure 对齐；不引入复杂框架，不改变现有行为，不把文件数量本身当作成功标准。

下一步：DDD-T1 保留兼容 façade；后续进入 `DDD-T2` 前，继续按本文 Contract 做独立审查与回归验证。
