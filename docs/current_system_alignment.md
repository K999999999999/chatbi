# Current System Alignment

> 审计范围：2026-08-11 当前工作树。本文只根据仓库代码、配置和资源文件描述现状，不把架构设计文档当作已实现能力。

## 1. 结论口径与仓库边界

状态标记：✅ 已实现并可被现有脚本调用；🟡 基础设施存在但未接入在线主链路；🔴 不存在 / 未实现。

当前 `src/` 只有 `infrastructure/retrieval`，没有 API、Streamlit、Application、Domain、LLM Client、SQL Generator、SQL Guard 或查询执行模块。标准 `tests/` 目录也不存在，当前验证主要由 `scripts/validate_schema_loaders.py`、`scripts/build_schema_index.py`、`scripts/build_metric_index.py` 和 `scripts/test_bge_m3.py` 完成。

稳定架构边界见 `docs/ARCHITECTURE.md` 与 `docs/ENGINEERING_RULES.md`；这些文件明确说明它们是设计约束，不等同于实现或生产就绪。

当前工作树中已有用户改动 `M resources/schema/relationships.json`，以及未跟踪的 `.idea/`、`pyproject.toml`。本轮未修改它们。

## 2. Current Capability Map

| 能力 | 当前事实 | 证据 |
|---|---|---|
| 用户入口 | ✅ 只有离线 CLI 脚本；没有 HTTP/API/UI 入口 | `scripts/*.py` 的 `main()`；`src/` 无 Web 入口 |
| Text2SQL | 🔴 未实现。没有用户问题接收、Prompt Builder、System Prompt、LLM Client 或 SQL 返回链路 | `src/` 与 `scripts/` 无 LLM/Prompt/SQL Generator 实现 |
| SQL Safety | 🔴 AST、SELECT-only、表/字段白名单、LIMIT、SQL Validator、查询执行器均不存在 | `src/` 无 SQL AST/Guard/Executor 模块 |
| PostgreSQL | ✅ 仅有课程数据库初始化、生成和校验脚本；没有在线 BusinessDataSource 或连接池 | `scripts/init_course_database.py:94-126,332-357`；`scripts/generate_course_demo_data.py:723-790` |
| 数据库权限 | ✅ `chatbi_app` 的只读角色脚本存在 | `database/grants.sql:14-31` |
| BGE-M3 | ✅ 本地 FlagEmbedding Dense + Sparse 编码 | `src/infrastructure/retrieval/bge_m3.py:BGE_M3Encoder` |
| Qdrant | ✅ 原生 `qdrant-client` Store 与离线写入/查询基础能力 | `src/infrastructure/retrieval/qdrant_store.py:17-166` |
| RAG 在线链路 | 🔴 未实现；当前只有离线索引和 smoke query | `scripts/build_schema_index.py:121-149` |

`.env.example` 只声明 Qdrant、BGE-M3 和本地缓存配置（`.env.example:1-9`）；`docker-compose.yml` 还要求 PostgreSQL 的 `POSTGRES_*` 变量（`docker-compose.yml:6-18`）。实际 `.env` 存在，但本审计不读取或输出其敏感值。`.gitignore:1-15` 已忽略 `.env`、模型、Qdrant/PostgreSQL 数据和缓存。

## 3. Semantic Layer：资源、索引与在线使用

| Catalog | Source of Truth | Loader / Indexer | Retriever | 在线使用 |
|---|---|---|---|---|
| Table Catalog | `resources/schema/tables.json` | `load_table_documents()`；`SchemaIndexer.build()` | 🔴 无专用在线 Retriever | 🔴 否 |
| Column Catalog | `resources/schema/columns.json` | `load_column_documents()`；`SchemaIndexer.build()` | 🔴 无专用在线 Retriever | 🔴 否 |
| Relationship Catalog | 当前 `resources/schema/relationships.json` | 🔴 无 Loader / Graph Builder | 🔴 无 Join Resolver | 🔴 否 |
| Metric Catalog | `resources/semantic/sales/metrics.json` | `load_metric_documents()`；`SchemaIndexer.build_collection()` | 🔴 无 Metric Retriever | 🔴 否 |
| Few-shot | 未发现资源、Loader 或索引 | 🔴 不存在 | 🔴 不存在 | 🔴 否 |
| Business Rules | `database/course_baseline/*.sql` 与 `business_scenarios.md` 是课程校验/ground truth，不是在线规则 Loader | 🔴 无在线 Loader | 🔴 不存在 | 🔴 否 |

关系目录需要特别区分：数据库真实结构只有 2 个 FK，见 `database/course_baseline/001_create_tables.sql:32-50`；当前未提交的 `relationships.json` 还描述了 `sales_orders` 与 `exchange_rates` 的日期+币种语义 Join，但它没有被任何代码读取，不能视为已接入的 Join Resolver。

## 4. RAG Infrastructure 现状

### 4.1 Document Loader

| Loader | 输入 | 输出 | 实现证据 |
|---|---|---|---|
| Table Loader | `tables.json` JSON 数组 | 每个表一个 `langchain_core.documents.Document`；`page_content` 为表名+业务含义，metadata 含 `kind/table_name` | `src/infrastructure/retrieval/table_loader.py:11-37` |
| Column Loader | `columns.json` JSON 数组 | 每个字段一个 `Document`；`page_content` 为表/字段/类型/含义，metadata 含 `kind/table_name/column_name/data_type` | `src/infrastructure/retrieval/column_loader.py:11-51` |
| Metric Loader | `metrics.json` JSON 数组 | 每个指标一个 `Document`；page content 只含名称、别名、业务定义，metadata 保留完整指标对象 | `src/infrastructure/retrieval/metric_loader.py:32-66` |

现有 LangChain 只承担统一 `Document` 数据结构。Loader 不切块、不连接 Qdrant；后续编码和存储是项目自定义实现。

### 4.2 Embedding

`BGE_M3Encoder`（`src/infrastructure/retrieval/bge_m3.py:26-111`）直接加载 `FlagEmbedding.BGEM3FlagModel`，设置离线环境并传入 `local_files_only=True`。输入可以是 `Document`（`encode_documents()`）或文本（`encode_texts()`），输出 `EncodedText`：

- Dense：`list[float]`，维度固定为 1024（`bge_m3.py:15,75-80`）。
- Sparse：转换为 Qdrant `models.SparseVector`（`bge_m3.py:90-108`）。
- 一次编码同时生成 Dense 和 Sparse；明确关闭 ColBERT 向量。
- 这不是 LangChain Embeddings 实现；模型、编码和向量格式由当前 Infrastructure Adapter 负责。

Schema 与 Metric 两个离线构建脚本都复用该编码器（`scripts/build_schema_index.py:14,211-226`；`scripts/build_metric_index.py:14,185-206`）。

### 4.3 Qdrant 与 Point

`QdrantStore.__init__()` 在 `src/infrastructure/retrieval/qdrant_store.py:17-26` 创建原生 `QdrantClient` 并做连接检查。当前代码定义的 Collection 只有：

| Collection | 内容 | Point payload |
|---|---|---|
| `schema_tables` | 5 个表 Document | `page_content` + 表 metadata |
| `schema_columns` | 40 个字段 Document | `page_content` + 字段 metadata |
| `metric_catalog` | 5 个指标 Document | `page_content` + 完整 metric metadata |

`ensure_collection()` 使用 named vectors：`dense` 为 1024 维 Cosine，`sparse` 为稀疏向量（`qdrant_store.py:28-77`）。`SchemaIndexer._build_points()` 将 `page_content` 和 metadata 写入 payload，并使用 UUID5 确定性 ID（`schema_indexer.py:42-46,192-217`）。同一对象重复 upsert 会写入同一 Point ID；`--repeat` 验证了这一幂等意图。

`QdrantStore` 是当前唯一的 Qdrant Store/Repository 边界（`qdrant_store.py:79-166`），没有第二套向量客户端或 LangChain Qdrant 封装。

### 4.4 离线 Indexing Pipeline

```text
Table / Column / Metric JSON
        │  Loader：list[Document]
        ▼
Document(page_content, metadata)
        │  BGE_M3Encoder.encode_documents()
        ▼
EncodedText(dense[1024], sparse)
        │  SchemaIndexer._build_points()
        ▼
PointStruct(id=UUID5, vector={dense,sparse}, payload=...)
        │  QdrantStore.ensure_collection() + upsert()
        ▼
schema_tables / schema_columns / metric_catalog
```

具体入口：

- Schema：`scripts/build_schema_index.py:203-239` → 两个 Loader → `SchemaIndexer.build()`（`schema_indexer.py:48-101`）。校验 5 个表、40 个字段、payload、Dense/Sparse smoke query，并可用 `--repeat` 验证重复构建。
- Metric：`scripts/build_metric_index.py:177-234` → `load_metric_documents()` → `SchemaIndexer.build_collection()`（`schema_indexer.py:103-137`）。校验 5 个指标、完整 metadata、确定性 ID、Dense/Sparse 和重复构建。

### 4.5 在线 Retrieval

`QdrantStore.query_dense()` 与 `query_sparse()` 确实存在（`qdrant_store.py:120-160`），但它们只在 `build_schema_index.py:121-149` 中作为离线 smoke test 被调用。`retrieve()` 是按已知 Point ID 读取，不是面向用户 query 的 Retriever。当前不存在 `TableRetriever`、`ColumnRetriever`、`MetricRetriever`、Top-K 结果契约、Hybrid/RRF 融合或在线服务调用。

因此结论是：**索引已存在，但在线检索尚未实现。**

## 5. 当前真实 Online Query Pipeline

仓库中没有从用户问题到数据库结果的真实调用链。当前能执行的实际链路只有以下离线任务：

```text
[CLI script]
   ├─ validate_schema_loaders.py
   │    └─ JSON → Table/Column Loader → Document → count/sample
   ├─ build_schema_index.py
   │    └─ JSON → Document → BGE-M3 → Qdrant upsert → smoke query
   ├─ build_metric_index.py
   │    └─ metrics.json → Metric Document → BGE-M3 → Qdrant upsert → payload/vector validation
   └─ init_course_database.py / generate_course_demo_data.py
        └─ .env → psycopg → PostgreSQL 建库/建表/生成/校验
```

课程目标的在线链路目前在每个节点都没有实现：

```text
User Question [🔴 无入口]
  → Retrieval / Schema Linking / Metric RAG [🔴 无在线调用]
  → Context Merge [🔴]
  → Prompt Builder [🔴]
  → LLM [🔴]
  → SQL [🔴]
  → SQL Validation / Guard [🔴]
  → PostgreSQL Query Executor [🔴]
  → Result Formatter / UI / API [🔴]
```

`init_course_database.py` 使用 `psycopg.connect()` 的迁移/校验连接（`scripts/init_course_database.py:94-126,332-357`），`generate_course_demo_data.py` 使用同一类配置写入确定性课程数据；它们不是在线查询 Adapter，也没有连接池。不能把课程 SQL 校验脚本当作 Text2SQL 执行链路。

## 6. Schema Linking 当前状态

| 阶段 | 状态 | 当前证据与边界 |
|---|---|---|
| Table Retrieval | 🟡 | `schema_tables` 已建，Qdrant dense/sparse 原语可调用；没有 `query: str → candidate_tables` 的在线封装 |
| Anchor Selection | 🔴 | 没有 Query Intent、metric/entity 分类或锚表选择函数 |
| Field Matching | 🟡 | `schema_columns` 已建并可做离线 smoke query；没有在线字段候选输出 |
| Relationship Graph | 🔴 | `relationships.json` 存在但无 Loader、标准化关系对象或有向图构建；当前文件改动也未提交、未被读取 |
| Join Resolver | 🔴 | 没有 Join 路径解析、可达性或 `unreachable` 输出 |
| BFS | 🔴 | 未发现 BFS/图搜索实现 |
| Dynamic Schema | 🔴 | 没有动态 Schema Context，也没有 Prompt 注入点 |

所以现状不是“Schema Linking 已完成”，而是“表/字段离线索引基础存在，在线结构关联未开始”。

## 7. Metric RAG 当前状态

| 阶段 | 状态 | 证据 |
|---|---|---|
| `metrics.json` Source of Truth | ✅ | `resources/semantic/sales/metrics.json`；`metric_loader.py:35-46` 强制 JSON 数组、5 条指标、唯一 code |
| Metric Loader | ✅ | `load_metric_documents()`；校验 atomic/derived 依赖与 filters，输出 5 个 Document（`metric_loader.py:48-107`） |
| BGE-M3 编码 | ✅ | 复用 `BGE_M3Encoder`，没有 Metric 专用模型 |
| `metric_catalog` | ✅ | `SchemaIndexer.build_collection()` 与 `scripts/build_metric_index.py:198-216` |
| 在线 Metric Retriever | 🔴 | 没有 query-facing 函数或 Retriever 类 |
| Query 查询 `metric_catalog` | 🔴 | 当前 query 只出现在 Schema 离线 smoke test，Metric 构建脚本没有在线 query |
| Top-K → Prompt | 🔴 | 没有 Context Merge、Prompt Builder 或 LLM Client |
| LLM 使用 Metric RAG | 🔴 | 仓库没有 LLM 调用实现 |

## 8. Input / Output Contract Map

| 模块 | 目标输入 → 输出 | 当前状态 / 实现位置 |
|---|---|---|
| Table Loader | `path` → `list[Document]`（5 个） | ✅ `table_loader.py:11-37` |
| Column Loader | `path` → `list[Document]`（40 个） | ✅ `column_loader.py:11-51` |
| Metric Loader | `path` → `list[Document]`（5 个，metadata 为完整指标） | ✅ `metric_loader.py:32-66` |
| Embedding | `Document[]` 或 `str[]` → `EncodedText[]` | ✅ `BGE_M3Encoder.encode_documents/encode_texts()`，`bge_m3.py:50-111` |
| Offline Indexer | `Document[] + collection_name` → Qdrant Points | ✅ `SchemaIndexer.build/build_collection()` |
| Table Retrieval | `query: str` → `candidate_tables` | 🔴 未实现；底层 `query_dense/query_sparse` 只返回 `ScoredPoint[]` |
| Anchor Selection | `query + candidate_tables` → `anchor_table` | 🔴 未实现 |
| Field Matching | `query + candidate_tables` → `matched_fields` | 🔴 未实现 |
| Join Resolver | `anchor + candidate_tables` → `{anchor, joins, unreachable}` | 🔴 未实现 |
| Metric Retrieval | `query: str` → `matched_metrics / metric_context` | 🔴 未实现 |
| Context Merge | schema context + metric context + intent/rules → LLM context | 🔴 未实现 |
| Prompt Builder | query + context → system/user prompt | 🔴 未实现 |
| LLM SQL Generation | prompt → SQL / structured response | 🔴 未实现 |
| SQL Validation | sql → validated_sql / error | 🔴 未实现 |
| SQL Execution | validated_sql → query_result | 🔴 未实现；课程脚本的 psycopg 连接不提供此接口 |

## 9. Current vs Target Gap Analysis

**已完成：** Course Baseline V1 的五表 SQL、数据生成/校验脚本、只读角色权限脚本；Table/Column/Metric Catalog 资源；LangChain Document Loader；本地 BGE-M3 Dense + Sparse；三个 Qdrant Collection 的离线构建和幂等校验。

**可以直接复用：** 现有 Loader 的 `Document` 契约、`BGE_M3Encoder`、`QdrantStore`、Collection 名称、`SchemaIndexer` 的确定性 ID 与 `build_collection()`、`.env` 中 Qdrant/BGE 配置、Course Baseline 的只读权限边界。

**只缺在线接线的部分：** Collection 查询的底层原语已经有，但还需要面向 query 的 Retriever 契约、结果标准化和调用方；这不是重新建设模型或向量库。

**尚未实现：** 用户入口、意图/锚表、在线表/字段/指标召回、关系图与 Join Resolver、动态 Schema、Metric Context、Context Merge、Prompt、LLM、SQL Guard、只读查询执行和结果格式化。

**重复能力风险：** 后续若再次创建 Embedding Client、Qdrant Client、Metric JSON、Schema JSON、LangChain QdrantVectorStore 或第二套离线 Indexer，都会绕开当前稳定边界。当前不存在可复用的 PostgreSQL Runtime Adapter、LLM Client 或 SQL Guard，不能把它们写入“必须复用”清单，也不能假设它们已经存在。

## 10. Infrastructure Reuse Rules

### MUST REUSE

- `resources/schema/tables.json`、`columns.json` 和 `resources/semantic/sales/metrics.json` 作为唯一业务资源来源。
- `load_table_documents()`、`load_column_documents()`、`load_metric_documents()` 的 `Document` 与 metadata 契约。
- `BGE_M3Encoder` 的本地离线加载、Dense 1024 和 Sparse 输出。
- `QdrantStore`、`schema_tables`、`schema_columns`、`metric_catalog` 及 named vector 命名。
- `SchemaIndexer.deterministic_point_id()` 与 `build_collection()` 的离线幂等策略。
- `database/course_baseline` 与 `database/grants.sql` 的五表和只读权限边界；它们是数据库基线/脚本，不是在线查询层。

### DO NOT DUPLICATE

- 第二套 BGE/Embedding Client、Sparse 转换逻辑或模型加载逻辑。
- 第二套 Qdrant Client、Collection 名称或 Point payload 规则。
- 第二份 Schema/Metric 业务定义或手工维护的向量索引事实源。
- 在本阶段引入 `langchain_qdrant`、`QdrantVectorStore`、LangChain Retriever 来替换现有原生实现。
- 把课程校验 SQL、指标公式或关系语义直接复制成另一套不受 Source of Truth 管理的配置。

## 11. Architecture Snapshot

```text
【Offline / Build Time】

Semantic Resources [✅]
  ├─ tables.json / columns.json / metrics.json
  └─ relationships.json [🟡 存在但未被读取]
        ↓
Loader → LangChain Document [✅]
        ↓
BGE_M3Encoder / FlagEmbedding [✅]
        ↓
QdrantStore / native qdrant-client [✅]
        ↓
schema_tables / schema_columns / metric_catalog [✅ 离线索引]

【Online / Query Time】

User Query [🔴 无 API/CLI 查询入口]
        ↓
Table / Column / Metric Retriever [🔴]
        ↓
Schema Linking / Join Resolver / Metric Context [🔴]
        ↓
Context Merge / Prompt Builder [🔴]
        ↓
LLM → SQL [🔴]
        ↓
SQL Guard → Read-only BusinessDataSource [🔴]
        ↓
Result / UI / API [🔴]
```

## 12. 下一阶段建议（只建议，不实施）

### Step 1：先建立最小在线 Retrieval 契约

- **目标：** 让已有 `BGE_M3Encoder` + `QdrantStore.query_dense/query_sparse` 能由一个明确的 query-facing 调用方读取三类 Collection。
- **输入：** `query: str`、collection/kind、Top-K 配置。
- **输出：** 统一候选对象，至少包含 `kind`、稳定身份、payload、score；暂不进入 Prompt。
- **依赖：** 复用现有 Loader metadata、BGE-M3、QdrantStore 和 Collection 名称。
- **完成标准：** Table、Column、Metric 各有最小只读 smoke test；明确 Dense/Sparse 结果如何合并；不引入第二套客户端。

### Step 2：确认并加载 Relationship Catalog

先确认当前 `relationships.json` 是确定性 PK/FK 关系还是包含日期+币种的语义 Join；然后实现最小关系对象/图读取，保持数据库真实 2 FK 与课程语义 Join 的边界可追溯。

### Step 3：最小 Schema Linking

在已有候选输出之上实现 Table Retrieval → Anchor Selection → Field Matching → Join Resolver → Dynamic Schema，并为不可达关系提供确定性拒绝/澄清结果。

### Step 4：Metric Context 与统一上下文

让 Metric Retrieval 使用 `metric_catalog`，再把完整 metric metadata 与 Schema Linking 结果合并为可测试的 Context；最后才进入 Prompt Builder/LLM/SQL Guard 设计。

本轮到此停止，不执行上述 Step，也不把架构设计中的目标链路描述成当前实现。
