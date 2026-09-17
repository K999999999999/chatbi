# Online Retrieval Implementation Design

> 本文是历史 Implementation Design（实现设计）记录，不是当前行为事实源。当前实现以 [Online Retrieval V1 Feature Contract（在线检索 V1 功能契约）](../../.scratch/online-retrieval-v1/spec.md)、代码和测试为准；本文中关于 BFS、技术 fallback（回退）和独立多指标分支的旧设计仅供追溯。

## 1. 状态与目标

- Module Spec（模块规格）：docs/specs/online-retrieval.md
- 当前阶段：Historical Record（历史记录）
- 当前状态：原设计已完成；当前代码以 V1 Feature Contract（V1 功能契约）和确定性测试为准
- Runtime Mode（运行模式）：同步、单请求、无副作用

本文记录的是已经完成的实体类和单指标 Online Retrieval V1 实现设计。基础 Multi-Metric Retrieval（多指标在线检索）的 T1～T4 软件实现记录在 `docs/designs/multi-metric-retrieval.md`；T5 修复分组粒度 Prompt 约束后真实在线 RAG 评测为 20/20，C05 通过，正式业务验收已通过。下文出现“一个最终指标”或技术 fallback 的地方均指单指标基线。

目标是把已经确认的 RAG Offline Build（RAG 离线构建）资产接入现有 Online Query（在线查询）上下文获取阶段，实现：

~~~
用户问题
→ TABLE Dense Retrieval
→ 候选表范围内的 COLUMN Dense Retrieval
→ 独立 METRIC Dense Retrieval
→ 确定性 Relationship Graph Join Resolution
→ Dynamic Schema + Indicator Context
→ 现有 LLM / SQL Guard / Database 链路
~~~

本设计不重新定义业务指标，不修改关系事实，不新增 Agent、权限系统、数据库表或复杂分析能力。

## 2. 设计依据

优先级如下：

~~~
Architecture / Domain / Existing Contract
→ docs/specs/online-retrieval.md
→ 当前真实代码和已发布资产
→ 项目参考课程
~~~

实现必须遵循以下已确认结论：

- 先检索表，再在候选表范围内检索列。
- 指标独立检索，不受表检索结果过滤。
- V1 只使用 Dense Retrieval；BGE-M3 资产中的 Sparse 向量暂不使用。
- 指标不做递归依赖展开。
- Relationship Graph 只来自已验证结构事实。
- 指标 time_field 优先决定指标查询的日期关系。
- 用户月份、日期是过滤值；V1 不增加独立日期检索或复杂日期分类链路。
- Metric 检索使用离线文档的语义 `page_content` 召回，并同时读取同一文档的结构化 metadata；不执行第二次 metadata 向量检索。
- 对单指标基线，METRIC Top-K 只保留为检索证据；最终 Indicator Context 只能使用一个确定指标。规范化名称/别名唯一命中优先，否则只能在阈值以上唯一候选时选择，多候选无法确定时返回 AMBIGUOUS。明确请求多个指标的逐项识别、完整性和后置 SQL 检查以多指标规格为准。
- 指标公式和 `filters` 引用的物理字段使用确定性 Formula Reference Resolver 提取；它只读取已认证事实，不调用 LLM，也不负责生成 SQL 的 AST 安全校验。
- `time_field` 左侧用于匹配 Graph Edge 来源字段，右侧用于日期过滤；实际 Join Key 始终来自 Graph Edge，不把日期过滤字段误当 Join Key。
- 同长度且语义不同的路径无法由已知条件唯一确定时返回 AMBIGUOUS；只有同一 edge_id 的重复结果允许去重。
- 必须表不可连通时返回 CANNOT_ANSWER，不让 LLM 猜 Join。
- 单指标类请求必须完整命中 TABLE、COLUMN、METRIC 和必要 Join；实体类请求不要求命中 METRIC。多指标请求必须完整命中全部请求 METRIC，遵循多指标规格。
- 业务资源零命中直接 CANNOT_ANSWER；只有 Qdrant、Embedding、资产加载等技术失败允许静态 fallback；多指标技术故障不回退。
- Prompt 明确限制 Dynamic Schema，程序使用动态表列白名单进行确定性校验。
- 保留现有静态 Schema 路径作为技术故障 fallback。
- 每次请求只读取一次 `current.json`；Runtime 可以按 `build_id` 缓存不可变快照。`asset_version` 和检索配置不是外部用户可以任意指定的 QueryRequest 字段。

## 3. 当前仓库真实基础

当前代码已经提供以下可复用能力：

| 现有能力 | 代码位置 | 实现设计中的用法 |
|---|---|---|
| 已发布资产指针、Manifest 和关系图加载 | src/rag_offline/build.py | 一次请求加载一个资产快照 |
| Qdrant 连接和 Dense 检索 | src/rag_offline/qdrant_store.py | 使用 Manifest 中的 TABLE / COLUMN / METRIC 集合 |
| BGE-M3 查询向量 | src/rag_offline/embedding.py | 使用与离线资产一致的 Embedding Model |
| TABLE / COLUMN / METRIC 文档 payload | src/rag_offline/documents.py | 读取 metadata 和 page_content |
| 结构化 Relationship Graph | data/rag/{build_id}/relationship_graph.json | BFS Join Path |
| 静态 QueryContext | src/online_query/context.py | 技术故障 fallback |
| 表列 allowlist | src/online_query/contracts.py | Dynamic Schema 和候选范围校验 |
| PostgreSQL AST SQL Guard | src/online_query/sql_guard/sql_guard.py | 继续作为 SQL 最终安全边界 |
| 现有 SQL 生成、数据库执行和服务编排 | src/online_query/ | 不改变职责，只替换上下文来源 |

当前已发布真实资产：

- asset_version：20260906-bge-m3-v2
- TABLE：7
- COLUMN：69
- METRIC：5
- Foreign Key Join Edge：9
- Embedding：本地 BGE-M3，dense dimension 1024

## 4. 总体实现结论

不新建通用的 `domain`、`application`、`infrastructure` 或 `ports` 分层。代码继续放在 `src/online_query/`，只把已经形成稳定边界的 Retrieval 和 SQL Guard 分别组织为子包，通过在线检索编排对象连接离线资产和现有 Online Query。

建议的最小结构：

~~~
src/online_query/
├─ contracts.py       # 共享 Query、Retrieval 和 SQL Guard 类型
├─ service.py         # 按请求取得上下文，串联 Prompt、LLM、SQL Guard 和数据库
├─ context.py         # 静态上下文加载
├─ prompt.py          # Dynamic Schema 资源限制
├─ database.py        # PostgreSQL 只读执行适配
├─ llm.py             # LLM SQL 生成适配
├─ retrieval/         # OnlineRetriever 和在线检索内部职责
│  ├─ retrieval.py
│  ├─ resource_retrieval.py
│  ├─ retrieval_context.py
│  ├─ retrieval_selection.py
│  ├─ relationship_graph.py
│  ├─ rag_runtime.py
│  └─ multi_metric.py
└─ sql_guard/         # SQL 安全校验内部职责和公共入口
   ├─ sql_guard.py
   ├─ sql_guard_join.py
   └─ sql_guard_multi_metric.py
~~~

不新增 ports、infrastructure、agent、workflow 等目录。Qdrant 和 BGE-M3 适配器直接复用 src/rag_offline/ 已有实现，Online Retrieval 只负责在线编排。

## 5. 在线运行链路

### 5.1 请求级链路

~~~
QueryRequest.question
  ↓
RAG Asset Snapshot Loader
  ↓
TABLE Retrieval
  ├─→ 候选表范围内的 COLUMN Retrieval
  └─→ METRIC Retrieval（与 Schema Linking 独立）
          ↓
      data_source 确认事实表身份（不替代 TABLE 命中）
  ↓
按请求类型检查必需资源
  ↓
Anchor Table Selection
  ↓
Relationship Graph BFS
  ↓
按指标 time_field 绑定日期口径、必须表可达性检查
  ↓
Dynamic QueryContext
  ↓
Prompt
  ↓
LLM SQL
  ↓
Candidate Scope Check + AST SQL Guard
  ↓
Database
~~~

### 5.2 运行顺序

1. 请求开始时读取一次当前发布指针。
2. 加载同一个 asset_version 的 Manifest、三个集合名称、关系图和 Embedding 配置。
3. 生成一次 query embedding。
4. 执行 TABLE 和 METRIC 检索；两路逻辑独立。
5. 根据 TABLE 候选范围执行 COLUMN 检索；指标类请求同时使用已命中 Metric 的语义内容和 formula 作为 COLUMN 查询补充文本。
6. 按请求类型检查 TABLE、COLUMN、METRIC 必需资源；formula 引用的业务列必须出现在 COLUMN 命中结果中。
7. 再根据指标 time_field 和关系图执行 Join Resolution。
8. 组装 Dynamic QueryContext。
9. 把 Dynamic QueryContext 交给现有 Prompt / LLM / SQL Guard 链路。

## 6. 代码落位与职责

### 6.1 contracts.py

新增或补充以下类型：

- RetrievalStatus：SUCCESS、NO_TABLE_HIT、NO_REQUIRED_COLUMN_HIT、NO_METRIC_HIT、PARTIAL_UNREACHABLE、AMBIGUOUS、ASSET_UNAVAILABLE、RETRIEVAL_UNAVAILABLE、EMBEDDING_UNAVAILABLE、FALLBACK_STATIC_SCHEMA。
- TableHit：document_id、schema_name、table_name、table_role、score、rank、metadata。
- ColumnHit：document_id、schema_name、table_name、column_name、data_type、score、rank、metadata。
- MetricHit：document_id、metric_name、score、rank、metadata、page_content。
- JoinEdge / JoinPath：来源表、目标表、来源列、目标列、约束名、方向和路径顺序。
- RetrievalEvidence：三路原始命中和图解析证据。
- OnlineRetrievalResult：status、asset_version、tables、fields、metrics、join_path、dynamic_schema、indicator_context、evidence、warnings。
- RetrievalProvider Protocol：retrieve(question) -> OnlineRetrievalResult。

已有 QueryContext 保留，动态检索结果最终转换成 QueryContext：

~~~
prompt_context      = Dynamic Schema + Indicator Context
allowed_tables      = 本次最终允许使用的物理表
allowed_columns     = 每张表本次最终允许使用的字段
~~~

### 6.2 rag_runtime.py

提供 RAG Runtime（运行时）对象：

- 调用 load_published_asset() 读取 current.json、Manifest 和关系图。
- 根据 Manifest 的集合名称连接 Qdrant。
- 根据 Manifest 的 Embedding 配置创建 BgeM3EmbeddingProvider。
- 校验集合存在、Manifest 状态为 READY、版本和模型配置一致。
- 每个请求开始时只读取一次 current.json；按 build_id 取得或创建不可变 AssetSnapshot，并允许缓存同一 build_id 的快照。
- 不扫描 staging 目录，不重建资产，不修改 current.json。

AssetSnapshot 至少包含：

~~~
asset_version
collection_names
relationship_graph
embedding_provider
qdrant_store
manifest
~~~

### 6.3 Online Retrieval 内部 Module

`OnlineRetriever` 负责业务顺序、失败状态映射和公共 `retrieve()` Seam，不直接依赖 LangChain、psycopg 或数据库。

内部职责按以下 Module 组织：

- `resource_retrieval.py`：TABLE、COLUMN、METRIC 候选检索、指标选择、公式/filters/time_field 必需字段。
- `relationship_graph.py`：Relationship Graph 事实解析、time_field 关系校验、BFS 最短路径和安全 Join 约束。
- `retrieval_context.py`：最终表/字段闭包、关系键补充、Dynamic Schema、Indicator Context、QueryContext 和 allowlist。

这些 Module 只用于内部实现组织，不新增公共 API、Port / Adapter 或完整 DDD 分层。

Qdrant COLUMN 过滤优先复用现有 search()：对每个候选表执行带有 schema_name 和 table_name 的精确过滤检索，再合并、排序和截断。这样不需要把整个 COLUMN 集合加载到内存，也不需要先修改 Qdrant 通用适配器。

## 7. 三路检索实现

### 7.1 TABLE Retrieval

- 使用 TABLE 物理集合。
- 输入用户原问题和 asset_version。
- 使用 BGE-M3 query embedding。
- Dense limit 默认 3，阈值默认 0.30。
- 结果按 score 降序；分数低于阈值的命中不进入候选表。
- 使用 schema_name + table_name 作为表的完整身份。

TABLE Retrieval 是表的语义候选来源，不直接等同于最终表集合。最终表集合还要经过字段命中和关系图闭包处理；指标 data_source 只在 TABLE 命中后确认事实表和 anchor，不掩盖表路线零命中。

### 7.2 METRIC Retrieval

- 使用 METRIC 物理集合。
- 不使用 TABLE 结果过滤。
- Dense limit 默认 3，阈值默认 0.30。
- 只执行一次向量检索。
- 命中后同时保留 Metric `page_content` 和完整 metadata：前者作为召回证据，后者提供 formula、data_source、time_field、filters 等权威事实。
- 不根据 depends_on 继续检索，不递归展开指标。

METRIC 的 Top-K 结果只用于证据保留。`select_metric()` 按以下规则确定一个最终指标：规范化问题命中唯一指标名或别名时优先选择；否则只有一个候选超过阈值时选择；没有候选返回 `NO_METRIC_HIT`；多个候选超过阈值且无法唯一确定时返回 `AMBIGUOUS`，不让 LLM 选择业务口径。

指标的 data_source 只在事实表已被 TABLE 路线命中后用于确认事实表身份和必须表闭包，不扩展无关表，也不改变“指标独立检索”的原则。

### 7.3 COLUMN Retrieval

- 只在 TABLE Retrieval 返回的候选表范围内执行；指标 data_source 不能替代 TABLE 命中。
- 使用 COLUMN 物理集合。
- 对每个候选表分别发起带 schema_name、table_name 精确过滤的 Dense 检索。
- 指标类请求的 COLUMN 查询文本由用户问题和已命中 Metric 的语义内容、formula、time_field 组成；仍然只在 TABLE 候选表内检索。
- 每张表的检索结果合并后按 score 排序，再截断到全局 column_top_k，默认 12。
- 阈值默认 0.25。
- 不把所有 COLUMN 文档加载进应用内存。
- 问题明确要求按某个维度分组时，如果该维度表已被确定为候选表，额外保留该分组语义的最多两个 COLUMN 候选；其余结果仍按全局 column_top_k 合并。
- 指标 `filters` 中确定性解析出的物理字段也属于必需 COLUMN；filters 无法解析返回 `ASSET_UNAVAILABLE`，任一公式、filters 或 `time_field` 必需字段未命中返回 `NO_REQUIRED_COLUMN_HIT`。
- formula 引用的业务列必须被 COLUMN 路线有效命中；只补入 Join Key 不能替代业务列命中。

V1 的必需 COLUMN 包括：Formula Reference Resolver 从指标公式解析出的物理字段、`time_field` 的来源字段和日期过滤字段。用户问题召回的其他业务字段只是候选字段，由 LLM 在白名单内组合；Join Key 可以由 Graph 补入但不能替代业务字段。公式无法解析时返回 `ASSET_UNAVAILABLE`，公式引用字段没有被 COLUMN 有效命中时返回 `NO_REQUIRED_COLUMN_HIT`。

字段结果包含：

~~~
schema_name
table_name
column_name
data_type
description
value_examples
score
~~~

如果必需 COLUMN 零命中，返回 NO_REQUIRED_COLUMN_HIT 并映射为 CANNOT_ANSWER；不保留一个没有可回答字段的表继续生成 SQL，也不让 LLM 自行扩展字段。

## 8. Anchor Table 与关系图实现

### 8.1 Anchor Table

实现规则：

1. 指标的 data_source 事实表必须先出现在 TABLE 命中结果中；通过后将其作为 anchor_table。
2. 未命中指标时，使用 TABLE Retrieval 得分最高的表。
3. 没有唯一最高候选或事实表不在已发布关系图节点中时，返回 AMBIGUOUS 或 CANNOT_ANSWER 所需状态，不调用 LLM 猜测。
4. 记录 anchor_table 和 anchor_reason。

### 8.2 Graph Adapter

把 PublishedAsset.relationship_graph 的 foreign_keys 转换为只读的内部 Edge：

~~~
Edge:
  edge_id
  source_table
  source_columns
  target_table
  target_columns
  constraint_name
  direction
~~~

每条 Foreign Key 保留独立 edge_id。关系图同时建立正向和反向邻接，但 Join 条件始终使用原始 source_columns 和 target_columns，不改写业务事实。

### 8.3 BFS Join Resolver

- 从 anchor_table 出发，针对每个必须表和可选候选表寻找最短合法路径。
- BFS 的访问状态不能只用 table_name；平行关系边必须保留。
- 多条同长度、不同语义的路径全部保留为候选路径。
- 路径中的桥接表只加入关系需要的 Join Key 字段，不做额外语义字段扩展。
- 在 `time_field` 等已知条件过滤后仍有多条同长度且语义不同的路径时，返回 `AMBIGUOUS`；只有同一 `edge_id` 的重复结果才去重。
- 必须表不可达：返回 PARTIAL_UNREACHABLE，外层映射为 CANNOT_ANSWER，不进入 LLM。
- 可选候选不可达：丢弃该候选，继续处理。

### 8.4 日期处理

- 指标问题直接使用匹配指标文档的 time_field。
- 用户输入的月份、日期只是过滤值，不触发新的日期关系检索。
- V1 不增加日期意图分类器或复杂多日期推理；指标日期字段由 time_field 固定。
- 不把指标日期口径交给 LLM。

当前 `time_field` 采用 `source_table.source_column -> target_table.filter_column` 表达。解析后，左侧匹配 Graph Edge 的来源表和来源列，目标表确认日期维度，右侧字段只用于生成日期过滤；实际 Join 列必须取匹配 Graph Edge 的 `target_columns`。匹配不到关系时返回 `ASSET_UNAVAILABLE`，匹配到多条语义不同关系时返回 `AMBIGUOUS`。

## 9. Dynamic Context 组装

### 9.1 最终资源闭包

最终允许资源由程序确定：

~~~
最终表：
  TABLE 命中表
  + 指标 data_source 的事实表
  + Join Path 中必要的桥接表

最终字段：
  COLUMN 命中字段
  + 指标 formula 已命中的业务字段
  + 所有 Join Edge 的 source_columns
  + 所有 Join Edge 的 target_columns

最终指标：
  一次 METRIC Retrieval 最终确定的指标文档 page_content + metadata
~~~

不把未命中的全量表和字段注入 Dynamic Schema。

### 9.2 Dynamic QueryContext

Dynamic QueryContext 使用现有 QueryContext 类型：

- prompt_context：只包含最终表、字段、Join、字段值示例、指标定义和公式。
- allowed_tables：最终表的完整物理身份集合。
- allowed_columns：按完整物理表身份分组的最终字段集合。

Candidate Scope Check 直接使用 allowed_tables 和 allowed_columns，避免再建立一套资源白名单。

### 9.3 Prompt

在现有 Prompt 规则中增加：

~~~
只能使用 Dynamic Schema 中列出的表、字段和 Join 关系。
不得使用数据库中没有列出的其他表或字段。
不得自行发明 Join 条件、日期口径或指标公式。
如果上下文无法确定答案，只返回 CANNOT_ANSWER。
~~~

Prompt 是模型约束；allowed_tables、allowed_columns 和 SQL Guard 是程序约束。

## 10. Online Query 集成

### 10.1 Service 依赖

OnlineQueryService 增加可选 RetrievalProvider：

~~~
OnlineQueryService(
    sql_generator,
    query_executor,
    context_loader=load_query_context,
    retrieval_provider=None,
)
~~~

- retrieval_provider 为 None：保持现有静态链路和现有测试行为。
- retrieval_provider 存在：每次有效 query 调用一次在线检索，获得动态 QueryContext。
- service 不直接依赖 Qdrant、BGE-M3 或关系图实现。
- 对外 QueryRequest 仍只接收 question 和 request_id；asset_version 与检索配置由服务内部运行时决定，或由受控测试/评测注入。

### 10.2 SQL Guard 接入

在线检索成功后，把动态 QueryContext 传给现有 validate_sql(candidate, context)。现有 SQL Guard 已根据 QueryContext 校验物理表和字段，因此实现上复用同一 allowlist：

~~~
Dynamic QueryContext
→ Prompt
→ LLM SQL
→ 使用动态 allowlist 的 Candidate Scope Check
→ 现有 AST SQL Guard
→ Database
~~~

如果需要在代码层显式区分两个阶段，Candidate Scope Check 和 AST Parse 可以共享一次 SQLGlot 解析结果，避免重复解析；不新增独立安全模块。

### 10.3 状态映射

| Retrieval 状态 | Online Query 行为 |
|---|---|
| SUCCESS | 使用 Dynamic QueryContext |
| NO_METRIC_HIT | 指标类请求返回 CANNOT_ANSWER；实体类请求指标上下文为空并可继续 |
| NO_REQUIRED_COLUMN_HIT | 返回 CANNOT_ANSWER，不调用 LLM |
| NO_TABLE_HIT | 需要表的请求返回 CANNOT_ANSWER，不使用静态上下文掩盖业务资源缺失 |
| PARTIAL_UNREACHABLE | 必须表不可达时返回 CANNOT_ANSWER，不调用 LLM |
| AMBIGUOUS | 返回 CANNOT_ANSWER 或要求用户澄清，不调用 LLM |
| ASSET_UNAVAILABLE | 单指标/实体基线进入静态 fallback；静态上下文也失败才返回 CONTEXT_ERROR；多指标返回 CONTEXT_ERROR |
| RETRIEVAL_UNAVAILABLE | 单指标/实体基线进入静态 fallback；多指标返回 CONTEXT_ERROR |
| EMBEDDING_UNAVAILABLE | 单指标/实体基线进入静态 fallback；多指标返回 CONTEXT_ERROR |

PARTIAL_UNREACHABLE 和 AMBIGUOUS 不允许通过静态 fallback 伪装成确定的 Dynamic Schema。

## 11. Runtime 配置

优先复用 src/rag_offline/config.py 的环境配置：

- RAG_OUTPUT_DIR：已发布资产目录。
- RAG_QDRANT_URL 或 RAG_QDRANT_PATH：Qdrant 地址或本地目录。
- RAG_QDRANT_API_KEY：仅从本地环境读取，不写入代码和日志。
- RAG_MODEL_DIR / RAG_MODEL_NAME_OR_PATH：Embedding Model。
- RAG_COLLECTION_PREFIX：集合前缀。

新增一个在线接入开关：

~~~
RAG_ONLINE_RETRIEVAL_ENABLED=true
~~~

默认值为 true，真实 Online Query 默认走 RAG：

- 单指标/实体基线的 RAG 技术故障时按规格 fallback 到静态上下文；多指标按独立规格停止并返回 CONTEXT_ERROR。
- 业务资源零命中、必须表不可达或歧义时直接返回 CANNOT_ANSWER，不 fallback 为可生成 SQL 的上下文。
- 单元测试仍可以不注入 RetrievalProvider，以隔离测试现有静态 Online Query。

这只是接入保护开关，不改变模块职责和在线检索行为。

## 12. 失败、资源释放和可观测性

### 12.1 失败处理

- 发布指针、Manifest、关系图或集合校验失败：ASSET_UNAVAILABLE。
- 查询 Embedding 失败：EMBEDDING_UNAVAILABLE。
- Qdrant 检索失败：RETRIEVAL_UNAVAILABLE。
- 业务资源零命中不视为技术故障；它按请求类型映射为 CANNOT_ANSWER。
- 必须表不可达、Anchor 无法确定或关系无法安全裁决：不调用 LLM，返回 CANNOT_ANSWER 所需状态。
- 技术失败时由 Online Query 决定是否使用静态上下文。

### 12.2 资源生命周期

- Qdrant client 和 Embedding Model 在 Runtime 创建时初始化或延迟初始化，生命周期由服务持有。
- 每次请求只创建轻量的查询结果，不重新加载 Manifest 和关系图。
- 服务关闭时调用 Qdrant client close；不删除已发布集合。

### 12.3 日志与证据

只记录不含 Secret 的检索证据：

- request_id。
- asset_version。
- 三路命中 document_id、score、rank。
- anchor_table 和 anchor_reason。
- Join Path 和最终状态。
- fallback 原因。

不记录 API Key、数据库密码、完整 Prompt 中可能包含的敏感内容或用户 Secret。

## 13. Task Split（任务拆分）

实现设计确认后，按依赖顺序连续执行以下任务：

| Task | 目标 | 主要文件 | 完成标准 | 依赖 |
|---|---|---|---|---|
| T1 运行时资产快照 | 加载 current、Manifest、Graph、集合和 Embedding 配置 | src/online_query/retrieval/rag_runtime.py、contracts.py | 同一 asset_version 快照可创建；版本、集合、模型不一致受控失败 | 无 |
| T2 TABLE / METRIC Retrieval | 实现两路独立 Dense 检索、阈值处理和最终指标选择 | src/online_query/retrieval/resource_retrieval.py、src/online_query/retrieval/retrieval.py | TABLE、METRIC 只访问对应集合；指标多候选时不交给 LLM 选择 | T1 |
| T3 COLUMN Retrieval | 在候选表内做精确过滤检索，并校验公式/日期必需字段 | src/online_query/retrieval/resource_retrieval.py、src/online_query/retrieval/retrieval.py | 不查询候选范围外字段；必需公式字段缺失时停止；结果合并排序稳定 | T1、T2 |
| T4 Graph Join Resolver | 实现 Anchor、BFS、平行边、多日期和不可达处理 | src/online_query/retrieval/relationship_graph.py、src/online_query/retrieval/retrieval.py | 最短合法路径、Join Key、time_field 映射、不可达和歧义测试通过 | T2、T3 |
| T5 Dynamic Context | 组装 Dynamic Schema、Indicator Context 和 QueryContext | src/online_query/retrieval/retrieval_context.py、src/online_query/retrieval/retrieval.py、contracts.py | 只输出最终资源；allowlist 完整；指标公式和 time_field 保留 | T3、T4 |
| T6 Prompt / Service 接入 | 增加 Prompt 资源限制、检索依赖和静态 fallback | src/online_query/prompt.py、service.py、query_api/main.py | 真实 API 默认走 RAG；技术失败 fallback；静态单元测试路径不回归 | T5 |
| T7 软件测试 | 覆盖契约、路由、图、状态和 SQL 范围校验 | tests/online_query/ | 新增测试和全仓回归通过 | T1-T6 |
| T8 真实资产验证 | 使用当前 BGE-M3、Qdrant 和标准问题验证 | tests 或 scripts/evaluation | 资产可加载、真实 Dense 检索可运行、评测证据可复现 | T7 |

每个 Task 都必须包含对应确定性测试；不在任务中加入 Sparse、Hybrid、Reranker、指标递归展开或数据库结构变化。

## 14. 测试与验收设计

### 14.1 Software Test

至少新增：

- 资产快照只读取一次 current 指针。
- Manifest、集合、关系图和 Embedding Model 版本不一致时 fail-closed。
- TABLE 只查 TABLE 集合。
- METRIC 不受 TABLE 结果过滤。
- COLUMN 每次检索都带候选表的精确过滤。
- 单指标基线的多个 METRIC 候选不能被直接交给 LLM 选择；无法唯一确定时返回 AMBIGUOUS。多指标请求按用户明确列举项逐项确定，不能交给 LLM 补选或删项。
- 公式引用字段和 time_field 必需字段缺失时返回 NO_REQUIRED_COLUMN_HIT。
- 指标 filters 引用字段缺失时同样返回 NO_REQUIRED_COLUMN_HIT。
- QueryContext 的动态 allowlist 拒绝范围外表和字段。
- 指标 data_source 事实表只有在 TABLE 命中后才能参与 Anchor。
- 指标 time_field 能选择完成日期边，并区分 Graph Join Key 与日期过滤字段。
- 指标日期字段始终来自 time_field；月份或具体日期值不会触发额外日期歧义。
- 必须表不可达时不调用 LLM。
- 可选候选不可达时可以继续。
- 平行 Foreign Key 边不会被 table-only visited 集合丢失。
- 同长度语义不同路径无法唯一裁决时返回 AMBIGUOUS。
- Dynamic Schema 只包含最终闭包和 Join Key。
- 技术失败 fallback 与业务资源零命中区分。
- 每个请求只读取一次 current.json，同一 build_id 可复用不可变快照。
- 原有 Online Query 静态测试全部继续通过。

### 14.2 AI Evaluation

使用现有标准问题增加在线检索证据：

- Table Recall。
- Column Recall。
- Metric Recall。
- Candidate Table Filter Correctness。
- Anchor Accuracy。
- Join Path Accuracy。
- Metric time_field Accuracy。
- Unreachable Detection。
- Dynamic Schema Completeness。
- SQL Execution Accuracy。
- 静态上下文与 Dynamic Schema 的结果差异。

### 14.3 Business Acceptance

- 指标公式仍来自指标事实，模型不能改写。
- 指标时间口径仍使用 time_field。
- SQL 不使用 Dynamic Schema 之外的表和列。
- Join 条件来自 Relationship Graph。
- 不确定时不生成看似正确的 SQL。
- RAG 技术故障时现有静态链路仍可用。

## 15. Out of Scope（不在本实现范围）

- 新的业务指标和指标口径。
- 修改 tables.json、columns.json、relationships.json、metrics.json。
- 修改 PostgreSQL 表、数据和权限。
- Sparse / Hybrid Retrieval。
- Reranker。
- 指标递归依赖展开。
- 第二次 LLM Schema Resolution。
- 多 SQL 经营分析。
- 新权限系统、租户系统、认证、限流、审计。
- 生产级缓存、分布式部署和在线资产自动切换。

## 16. 已确认规则与实现取值

以下内容不会改变总体架构。业务规则已经确认，工程实现取值如下。

### Q1：Online Retrieval 默认是否开启？

已确认：默认开启，Online Query 默认走 RAG Online Retrieval 路线。

实现要求：

- 默认使用 RAG 检索上下文。
- RAG 技术故障时，按已确认规则回退静态 Schema。
- RAG 返回 AMBIGUOUS 或必须表不可达时，不回退为可生成 SQL 的上下文，直接返回 CANNOT_ANSWER 或要求澄清。

### Q2：指标 data_source 未被 TABLE 检索命中时怎么办？

已确认：不能用指标 data_source 直接掩盖 TABLE 零命中。指标类请求的 TABLE 路线必须有有效命中；否则返回 CANNOT_ANSWER。命中通过后，才使用 data_source 确认事实表和 anchor，不重新做表语义检索，也不扩展无关表。

这样既保持 METRIC 独立检索，又保证三类业务资源都是真实检索得到的。

### Q3：日期是否需要单独处理？

已确认：不增加独立日期检索和复杂日期意图分类。指标使用 `time_field`；用户的月份、日期只作为过滤值。

### Q4：Candidate Scope Check 的实现取值

工程决定：不新增独立安全模块。复用现有 QueryContext.allowed_tables / allowed_columns 和 SQL Guard 的 SQLGlot 解析；代码上可以拆一个内部检查函数，逻辑上仍保持“候选范围检查先于 AST 安全检查”。

### Q5：Qdrant 和模型的加载取值

工程决定：运行时对象启动时加载 Manifest，Qdrant 和模型允许延迟初始化；第一次查询失败时返回明确技术状态并按策略 fallback。

这样可以避免 API 启动时因本地模型暂时不可用而完全无法启动。

### Q6：COLUMN 零命中时是否继续生成 SQL？

已确认：不能继续。指标类请求缺少必需 COLUMN，或实体类请求缺少必需 COLUMN，均返回 CANNOT_ANSWER；不能用静态 fallback，也不能让 LLM 自行补字段。Join Key 只能补充关系字段，不能替代业务字段命中。

### Q7：如何区分指标类请求和实体类请求？

工程取值：问题经过统一规范化后，命中已发布 Metric 的名称或别名，或出现明确的指标 / 聚合表达时按指标类处理；未命中这些条件时按实体类处理。不增加 LLM 意图分类器。这个规则与“指标类必须命中 METRIC、实体类不要求 METRIC”配套。

## 17. Done When（完成标准）

实现设计确认后，整个 Online Retrieval 任务满足以下条件才算完成：

- 所有已确认 Task 完成。
- TABLE、COLUMN、METRIC 三路真实检索可运行。
- Relationship Graph BFS、平行边保留和 time_field 规则通过确定性测试。
- Dynamic QueryContext 和候选范围校验生效。
- Prompt 已明确限制 Dynamic Schema。
- 必须表不可达和必需资源缺失不会调用 LLM；月份或具体日期值不单独触发歧义。
- 技术失败 fallback 行为有测试证据。
- 现有 Online Query 软件测试不回归。
- 真实发布资产可以被加载和检索。
- AI Evaluation、SQL 回归和 Business Acceptance 分别有结果。
- Diff 审查、Secret 检查和 git diff --check 通过。
- 当前设计与代码、测试和运行状态一致。

## 18. 当前设计状态

Implementation Design（实现设计）已获确认，当前代码已完成 Online Retrieval V1 的实现和确定性测试。

当前已完成：

- RAG Asset Snapshot、TABLE / COLUMN / METRIC Dense Retrieval、Formula Reference Resolver 和 Relationship Graph Join Resolver。
- Dynamic Schema、Indicator Context、Candidate Scope Check、Prompt 限制和 Online Query Service 接入。
- v2 已发布资产的加载与真实 Dense 检索基础验证。

Online Retrieval V1 已完成真实 AI Evaluation、完整 SQL 回归和 Business Acceptance。支持范围内通过率为 100%；多指标复杂组合按 V1 边界返回 CANNOT_ANSWER。
