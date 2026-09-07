# RAG Offline Build Implementation Design

## 1. 状态

- Module Spec（模块规格）：`docs/specs/rag-offline-build.md`
- Runtime Mode（运行模式）：同步 Batch（批处理）
- 当前状态：Metric Document 分层调整已实现、测试通过并已发布新资产，待提交
- 最后更新：2026-09-06

## 2. 变更背景与边界

当前数据库结构、字段、关系和指标已经形成权威 JSON 事实，但 Online Query（在线查询）仍把全部静态上下文直接放入 Prompt。RAG Offline Build 的目标是把这些已确认事实构建成可独立加载的检索资产，为后续 Online Retrieval（在线检索）提供稳定输入。

当前参与者是本地开发者和未来 Online Retrieval 启动器。当前只构建资产，不接入在线查询，不生成或执行 SQL，不修改 PostgreSQL，不建设 Agent、多租户、权限平台或 Hybrid Search（混合检索）。

当前权威事实规模：

- 7 张表。
- 69 个字段。
- 5 个指标。
- 25 条关系事实，其中 9 条 Foreign Key（外键）形成 Join Edge（连接边）。

## 3. 目标链路

```text
加载四个权威事实源
→ fail-closed 交叉校验
→ 生成 TABLE / COLUMN / METRIC RetrievalDocument
→ 仅对 page_content 调用 BGE-M3 Embedding
→ 写入三个隔离的 Qdrant 版本化集合
→ 生成确定性 Relationship Graph
→ 重载三个集合并校验数量与检索
→ 写入版本目录
→ 原子替换 current.json 发布指针
```

整个构建作为一个发布事务处理。向量集合使用新的物理名称，构建期间不覆盖当前集合；`current.json` 只在所有集合和关系图通过验证后更新。

## 4. 核心 Contract（契约）

### 4.1 RetrievalDocument

- `document_id`：稳定、全局唯一。
- `collection`：只允许 `TABLE`、`COLUMN`、`METRIC`。
- `page_content`：唯一进入 Embedding 的内容。
- `metadata`：结构化身份和过滤字段，不参与 Embedding。
- `to_payload()`：在向量库边界转换为可 JSON 序列化对象。

### 4.1.1 Metric Document 字段分层

Metric 的 `page_content` 是 Retrieval Text（检索正文），只包含指标名、别名、指标层级和业务定义等用于识别指标的语义内容，不包含公式、物理数据来源、时间字段、固定过滤条件、依赖指标和注意事项。

Metric 的 `metadata` 必须完整保存规范化事实源中的指标属性：

```text
doc_type、metric_name、aliases、level、definition、formula、
data_source、time_field、filters、depends_on、notes
```

同一字段同时存在于 `page_content` 和 `metadata` 不代表两份业务事实：`page_content` 负责向量语义召回，`metadata` 负责精确识别、程序裁决和下游上下文组装。一次 Metric 检索返回命中文档的两部分，不新增第二个 Metric 向量集合。

### 4.2 EmbeddingProvider

- `embed_documents(texts)`：输入顺序与输出顺序一一对应。
- `embed_query(text)`：只用于 Retrieval Evaluation。
- `dimension` 和 `config`：用于集合兼容检查和构建清单。
- 任意数量、维度、非有限数值或稀疏索引错误均 fail-closed。

V1 使用 `FlagEmbedding 1.4.2` 的 BGE-M3：

- dense 向量维度固定为 1024。
- 同时保存 dense 和 lexical sparse 向量。
- 当前重载校验和评测使用 dense 路由；Hybrid Search 仍不在本模块范围内。
- 本地 `models/bge-m3` 存在时优先加载本地模型，否则使用配置的模型 ID。

### 4.3 QdrantAssetStore

使用 direct `qdrant-client 1.19.0`，不通过 LangChain Adapter。

每次构建创建三个物理集合：

- `chatbi_table__{build_id}`
- `chatbi_column__{build_id}`
- `chatbi_metric__{build_id}`

每个 Point（点）保存：

- 稳定 UUIDv5 Point ID。
- 命名 dense / sparse 向量。
- `document_id`、`page_content`、完整 `metadata`。
- 用于候选表过滤的顶层 `schema_name`、`table_name` 等索引字段。

发布前必须重新连接集合、核对精确数量并至少完成一次 dense 检索。

### 4.4 Relationship Graph

- 只来源于 `relationships.json`。
- Primary Key、Unique Constraint 和 Unique Index 用于端点校验。
- Foreign Key 形成连接边。
- 关系记录使用完整身份排序，输出不依赖源文件顺序。
- 同一表上的重复约束身份失败；不同约束名的多日期连接全部保留。
- 关系图不向量化。

### 4.5 BuildSummary 与发布资产

`BuildSummary` 明确返回状态、三类文档数量、关系边数量、集合重载结果、发布状态和失败分类。

文件产物：

```text
data/rag/
├─ current.json
└─ {build_id}/
   ├─ manifest.json
   └─ relationship_graph.json
```

`load_published_asset()` 只按 `current.json` 加载已发布版本，不扫描临时目录，也不猜测集合名称。

## 5. 失败与恢复

- Source、Embedding、Vector Store、Validation 或 Filesystem 任一步失败，`published=false`。
- 失败构建创建的新集合会被清理，旧 `current.json` 保持不变。
- 版本目录先完整生成，再更新当前指针。
- 已成功发布的旧版本集合不自动删除，便于回滚；清理策略留给后续 Maintenance（维护）任务。
- Qdrant 本地 Compose 强制非空 API Key，只绑定 `127.0.0.1:6333/6334`。真实密钥仅保存在被 Git 忽略的 `.env`。

## 6. 任务清单

| Task | 内容 | 状态 |
|---|---|---|
| T1 | 冻结 Module Spec、三逻辑集合和产物契约 | 已完成 |
| T2 | 加载和校验表、字段、关系、指标事实 | 已完成并复核 |
| T3 | 生成三类 RetrievalDocument，并分离 Metric 检索正文与结构化事实 | 已完成并通过离线文档测试 |
| T4 | 生成确定性 Relationship Graph | 已完成并补强排序、重复关系、多日期边测试 |
| T5 | BGE-M3 dense + sparse Embedding Adapter | 已完成 |
| T6 | Qdrant 三集合创建、批量写入、过滤与重载检索 | 已完成 |
| T7 | 版本化目录、BuildSummary、失败保护和原子发布指针 | 已完成 |
| T8 | 固定 Retrieval Evaluation：表、字段、字段值、指标依赖 | 已完成 |
| T9 | 配置、Compose、依赖锁定、文档状态和最终回归 | 已完成 |

## 7. 验收证据

Software Test（软件测试）、AI Evaluation（AI 评测）和 Business Acceptance（业务验收）分别记录：

- Software Test：RAG Offline 33 项确定性测试通过；全仓回归为 148 passed、6 skipped、42 subtests passed。
- Dependency Check（依赖检查）：`uv lock --check` 和 `python -m compileall -q src` 通过。
- Real Integration（真实集成）：正式构建 `20260906-bge-m3-v2` 已发布；Qdrant 三个集合重新连接、精确计数和检索通过，数量为 TABLE=7、COLUMN=69、METRIC=5，关系边=9。v1 旧资产保留，不覆盖。
- AI Evaluation：BGE-M3 固定 5 案例当前为 5/5；字段案例使用候选表过滤，毛利率案例要求同时召回两个直接依赖。
- Metric Document 契约：Metric 检索正文只保留识别语义；公式、data_source、time_field、filters、depends_on 和 notes 在 metadata 中完整保留。
- Business Acceptance：构建成功摘要为 `PUBLISHED`，三个集合重载均为 true；PostgreSQL 仍为 7 张表和原始行数，`chatbi_app` 保持 7 表 SELECT、0 表写权限。

## 8. 后续边界

进入 Online Retrieval 前仍需单独设计：

- 在线三路检索编排和失败回退。
- Schema Linking（模式链接）与精简 Schema 组装。
- Relationship Graph 的在线路径查找。
- 与现有 Online Query Prompt 的可切换接入。

这些能力不因离线集合存在而自动视为已实现。
