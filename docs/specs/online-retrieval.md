
# Online Retrieval Module Spec

状态：Online Retrieval V1（实体类、单指标、TABLE/COLUMN/METRIC 检索、确定性关系图和动态上下文）已实现并通过验收。基础 Multi-Metric Retrieval（多指标在线检索）为独立增量规格，见 `docs/specs/multi-metric-retrieval.md`；T1～T4 软件实现与确定性测试已完成，修复后真实在线 RAG 评测为 20/20，正式 Business Acceptance（业务验收）已通过。

## 1. 模块目标

Online Retrieval（在线检索）负责根据用户问题，从已发布的 RAG Offline Build（RAG 离线构建）资产中取得最小、可解释、可用于 SQL 生成的业务上下文。

本模块解决：

~~~
用户问题
→ 应该查询哪些表
→ 应该使用哪些字段
→ 表之间如何合法连接
→ 指标应该按什么口径计算
~~~

本模块不生成 SQL、不执行 SQL、不修改数据库，也不改变已确认的指标口径。

## 2. 设计依据与事实源

### 2.1 优先级

设计和实现遵循以下优先级：

~~~
Architecture / Domain / Existing Contract
→ 本规格
→ 项目参考课程
→ 具体实现
~~~

课程用于确定 V1 的最小处理方法；课程示例与当前项目事实冲突时，以当前项目事实和上层 Contract（契约）为准。

### 2.2 权威事实源

在线模块使用已发布且经过校验的离线资产，不直接重新读取未发布的中间文件：

- TABLE、COLUMN、METRIC 三个逻辑向量集合。
- 已验证的 Relationship Graph（关系图）。
- 资产版本和发布状态。
- 指标事实源 src/semantic/metrics.json 经过离线构建后的对应文档。

当前项目的原始业务事实仍然是：

- src/structure/generated/tables.json
- src/structure/generated/columns.json
- src/structure/generated/relationships.json
- src/semantic/metrics.json

向量和图是派生产物，不反向修改这些事实源。

### 2.3 课程参考

V1 采用以下项目课程中已经验证的主链路：

- 第 13 课：Schema Linking 拆分为表召回、字段匹配和 Join 路径推理。
- 第 14 课：Embedding 和余弦相似度的 Dense Retrieval（稠密向量检索）。
- 第 16 课：先召回表，再在候选表范围内匹配字段，并输出精简 Schema。
- 第 17 课：根据查询意图选择锚表，使用 BFS Shortest Path（BFS 最短路径）计算 Join。
- 第 18 课：把表、字段、Join 组装为 Dynamic Schema（动态 Schema），失败时保留静态 Schema fallback。
- 第 19 课：指标使用独立语义检索；指标文档包含定义、公式、时间口径和依赖信息。
- 第 20 课：Schema Linking 负责“查哪里”，指标 RAG 负责“怎么算”，两路上下文最后一起进入 Prompt。

### 2.4 与基础多指标规格的关系

本文继续作为实体类和单指标基线的主规格。一个问题明确请求多个已登记指标时，由 `docs/specs/multi-metric-retrieval.md` 覆盖本文中关于指标选择、Indicator Context 数量、请求完整性、SQL 后置检查和技术 fallback 的增量规则。

因此，本文中的“最终只选择一个指标”和“技术故障可以回退静态上下文”只适用于实体类或已确定的单指标基线请求；多指标请求必须完整命中全部请求指标，技术故障直接返回 `CONTEXT_ERROR`，不得用静态上下文绕过多指标约束。

## 3. 范围

### 3.1 本模块负责

1. 在单个已发布资产版本上执行一次同步在线检索。
2. 执行 TABLE Dense Retrieval（表级稠密检索）。
3. 根据候选表限制 COLUMN Dense Retrieval（字段级稠密检索）。
4. 独立执行 METRIC Dense Retrieval（指标级稠密检索）。
5. 使用确定性 Relationship Graph 计算 BFS 最短合法 Join 路径。
6. 生成 Dynamic Schema 和 Indicator Context（指标上下文）。
7. 返回独立的路由证据、结构化结果、状态和告警。
8. 为外层 Prompt Builder 提供失败状态；实体类和单指标基线的技术故障可回退到静态上下文，多指标请求遵循多指标规格，不回退。

### 3.2 不负责

- 不生成 SQL。
- 不执行 SQL。
- 不调用 SQL AST Parser 或 SQL Guard；AST 校验位于 LLM 生成 SQL 之后。
- 不修改 PostgreSQL、Qdrant 或任何业务数据。
- 不增加权限系统、租户系统或登录系统。
- 不实现强制包含、强制排除、条件触发规则引擎。
- 不执行指标递归依赖展开。
- 不执行第二次 LLM 调用来选择表、字段或指标。
- V1 不实现 Sparse、Hybrid、Reranker 或 Multi-vector 检索。
- 不支持把不可连通的事实表强行 Join 成一条 SQL。

## 4. 核心设计原则

### 4.1 两条检索路线

Schema Linking 和指标 RAG 保持独立：

~~~
Schema Linking：查哪里
TABLE → COLUMN → Dynamic Schema

指标 RAG：怎么算
METRIC → Indicator Context

两路合并
→ 必需资源检查
→ Anchor
→ Relationship Graph Join
→ Dynamic Context
~~~

TABLE 和 METRIC 可以并行执行；COLUMN 必须等待 TABLE 候选表后执行。两条路线在必需资源检查后由在线编排层合并。

### 4.2 表先于列

COLUMN 检索必须使用 TABLE 路线返回的候选表作为范围过滤条件：

~~~
TABLE candidates
→ table_name 范围
→ COLUMN candidates
~~~

不得默认在整个 COLUMN 集合中无约束搜索。

### 4.3 指标不参与候选表过滤

V1 中 METRIC 路线不受 TABLE 结果限制，也不反过来修改 COLUMN 的候选表范围。

指标检索只负责提供：

- 指标定义。
- 完整公式。
- 数据来源。
- 时间字段。
- 过滤条件。
- depends_on 血缘信息。

指标依赖不触发第二轮检索，不递归扩展。

### 4.4 程序负责结构，模型负责组合

程序确定：

- 候选表范围。
- 候选字段范围。
- 合法 Join 路径和 Join 条件。
- 指标的权威公式、时间口径和过滤条件。

LLM 只在这份精简上下文中组合 SQL。LLM 输出仍然是不可信候选，必须经过后续 AST Guard。

## 5. 运行模式

### 5.1 模式

V1 是同步、无副作用、单请求检索：

~~~
一次请求
→ 读取一个不可变资产快照
→ 执行三条逻辑路线和图计算
→ 返回一个结果包
~~~

### 5.2 资产一致性

一次请求中的 TABLE、COLUMN、METRIC、Relationship Graph 和 Embedding Model 必须来自同一个 asset_version。

请求开始时只读取一次当前发布指针，并根据该指针取得或创建一个按 `build_id` 缓存的不可变资产快照。三条检索路线和图计算在本次请求期间都只能使用这份快照，不允许各路线分别重新读取当前指针；发布新资产后无需重启即可在新请求使用新版本。任一资产缺失、版本不一致或 Embedding Model 不匹配时，返回 ASSET_UNAVAILABLE。

不允许出现：

~~~
TABLE 使用 V1
COLUMN 使用 V2
Graph 使用 V1
~~~

资产必须在进入在线请求前处于已发布状态。未完成或半成品资产不得被在线模块读取。

## 6. 处理链路

~~~
用户问题
    │
    ├── TABLE Dense Retrieval
    │       └── COLUMN Dense Retrieval（候选表过滤）
    │
    └── METRIC Dense Retrieval（独立）
            └── 保留命中指标文档

TABLE / COLUMN / METRIC
    ↓
按请求类型检查必需资源
    ↓
Anchor Table Selection
    ↓
BFS Shortest Join Path
    ↓
Dynamic Schema + Indicator Context

Dynamic Schema + Indicator Context + 用户问题
    ↓
LLM 生成 SQL
    ↓
AST Parser / SQL Guard
    ↓
数据库执行
~~~

### 6.1 路由执行顺序

以下是实际执行顺序；6.2 至 6.7 是各节点的职责说明，不再表示 Anchor 必须早于 COLUMN 或 METRIC 执行。

~~~
TABLE
  └→ COLUMN

METRIC（独立）
→ 必需资源检查
→ Anchor
→ JOIN
→ Dynamic Schema + Indicator Context
~~~

其中 TABLE 和 METRIC 可以并行；COLUMN 只在 TABLE 候选范围内执行。

### 6.2 步骤一：TABLE Retrieval

输入：

~~~
query: str
asset_version: str
~~~

执行：

- 只查询 TABLE 逻辑集合。
- V1 使用 Dense 向量。
- 按相似度降序返回 Top-K。
- 应用可配置的表级阈值。

输出：

~~~
table_candidates: list[TableHit]
~~~

每个 TableHit 至少包含：

~~~
document_id
schema_name
table_name
table_role
score
rank
metadata
~~~

### 6.3 步骤二：Anchor Selection

Anchor Table（锚表）只作为 Join 计算的内部输入，不作为独立的外部检索路线。

V1 使用轻量确定性规则：

- 命中指标时，优先选择指标对应的事实表。
- 未命中指标时，选择 TABLE Retrieval 得分最高的表。
- 没有唯一最高候选或无法确定锚表时，返回 AMBIGUOUS，不调用 LLM 猜测。
- 不调用 LLM 选择锚表。

输出必须记录 anchor_table 和 anchor_reason，便于调试、评估和回归。

锚表的作用是确定：

- Join 路径起点。
- 后续 SQL 生成时的主语义表。
- 可能的 FROM 方向。

### 6.4 步骤三：COLUMN Retrieval

输入：

~~~
query
candidate_tables
asset_version
~~~

执行：

- 只查询 COLUMN 逻辑集合。
- 使用 schema_name = mart_sales 等精确元数据过滤。
- 使用 table_name IN candidate_tables 过滤。
- V1 使用 Dense 向量。
- 问题明确要求按某个维度分组时，如果该维度表已被确定为候选表，额外保留该分组语义的最多两个 COLUMN 候选；其余结果仍按全局 column_top_k 合并。
- 应用可配置的字段级阈值和 Top-K。

输出：

~~~
column_candidates: list[ColumnHit]
~~~

每个 ColumnHit 至少包含：

~~~
document_id
schema_name
table_name
column_name
data_type
score
rank
metadata
~~~

字段业务描述和值示例继续来自离线文档。V1 不额外建立业务规则评分器。

必需字段的 V1 定义：

- 指标公式中确定性解析出的物理字段属于必需字段。
- 指标 `filters` 中确定性解析出的物理字段属于必需字段。
- 指标 `time_field` 的来源字段、日期过滤字段属于必需字段。
- Relationship Graph 为 Join 补入的键字段属于结构字段，但不能替代业务字段命中。
- 用户问题召回的其他业务字段属于候选字段，由 LLM 在候选范围内组合；Online Retrieval 不声称逐一解析每个自然语言短语。

公式字段使用 Formula Reference Resolver（公式引用解析器）从离线已认证的 `formula` 中确定性提取，不调用 LLM，也不负责生成 SQL 的安全校验。公式无法解析时返回 `ASSET_UNAVAILABLE`；公式引用字段未被 COLUMN 路线有效命中时返回 `NO_REQUIRED_COLUMN_HIT`。

### 6.5 步骤四：Relationship Graph Join Resolution

输入：

~~~
anchor_table
candidate_tables
relationship_graph
~~~

执行：

1. 从锚表出发，对每个候选目标表执行 BFS。
2. 返回经过表数量最少的合法路径。
3. 合并多个目标表共享的路径。
4. 删除重复 Join Edge，但不合并语义不同的边。
5. 使用图边中已验证的列、方向、Join 类型和复合键条件。
6. 如果最短路径包含确定的中间桥接表，将该表加入路径和 Dynamic Schema。
7. 如果目标表不可达，标记 unreachable_tables，不得强行生成 Join。

必须区分必须表和可选候选表：指标对应的事实表、用户明确要求的维度表属于必须表；其他检索命中的表属于可选候选。必须表不可达时，返回 PARTIAL_UNREACHABLE，由外层 Online Query 映射为 CANNOT_ANSWER，不得进入 LLM SQL 生成。仅可选候选不可达时，丢弃该候选并继续。任何情况下都不得猜测 Join 或通过 Cross Join 强行连接不可达表。

图关系必须保留同一对表之间的全部合法边。BFS 选择路径时不能删除或覆盖多日期等不同语义关系。同长度且语义不同的最短路径，在 `time_field` 等已知条件过滤后仍无法唯一确定时，返回 `AMBIGUOUS`；只有同一 `edge_id` 的重复结果才允许去重。

输出：

~~~
join_path: {
    anchor_table,
    paths,
    joins,
    unreachable_tables
}
~~~

### 6.6 日期处理

多日期不通过额外的日期关键词推理模块解决。

对于指标问题：

~~~
使用匹配指标文档中的 time_field
~~~

当前项目指标统一使用：

~~~
completion_date_key → dim_date.full_date
~~~

用户输入的月份、日期或日期范围只是过滤值，后续 SQL 按指标 `time_field` 生成过滤条件，不触发新的日期检索或日期意图分类。

Relationship Graph 仍保留全部合法日期边，BFS 不得因为表已访问就丢失平行关系边；但 V1 不让 LLM 或额外分类器自行改变指标的 `time_field`，也不新增默认 `order_date_key` 规则。

当前 `time_field` 采用 `source_table.source_column -> target_table.filter_column` 表达：左侧用于匹配 Relationship Graph 的来源表和来源列，目标表用于确认日期维度，右侧字段用于生成日期过滤。实际 Join 列必须取自匹配到的 Graph Edge 的 `target_columns`，不能把右侧过滤字段误当成 Join Key。匹配不到关系时返回 `ASSET_UNAVAILABLE`；匹配到多条语义不同关系时返回 `AMBIGUOUS`。

### 6.7 步骤五：METRIC Retrieval

输入：

~~~
query
asset_version
~~~

执行：

- 只查询 METRIC 逻辑集合。
- 不使用 TABLE 结果做过滤。
- V1 使用 Dense 向量。
- 对实体类或单指标基线请求执行一次指标检索；多指标请求按多指标规格使用完整用户问题执行一次综合指标检索，再逐项检查请求指标覆盖。
- 不执行递归依赖展开。
- 不因 depends_on 再发起第二次指标向量检索。

输出：

~~~
metric_candidates: list[MetricHit]
~~~

指标文档必须包含足够完整的：

- 指标名称和别名。
- 业务定义。
- 完整公式。
- 数据来源。
- 时间字段。
- 过滤条件。
- 注意事项。
- depends_on 信息。

当前项目的 depends_on 保留为血缘和解释信息。由于现有指标公式已经直接引用实际字段，V1 不要求在线展开依赖指标。

对实体类或单指标基线请求，METRIC 检索可以保留 Top-K 作为检索证据，但最终 Indicator Context 只能使用一个确定的指标：

- 规范化后的问题命中唯一指标名或别名时，选择该指标。
- 没有精确命中且阈值以上只有一个指标时，选择该指标。
- 没有阈值以上候选时返回 `NO_METRIC_HIT`。
- 有多个阈值以上候选且无法由名称或别名唯一确定时返回 `AMBIGUOUS`，不把多个指标交给 LLM 选择。

### 6.8 步骤六：Dynamic Schema Assembly

Dynamic Schema 由以下内容组成：

~~~
候选表
相关字段
字段简短描述
表角色
Join Path
Join Condition
必要的结构说明
~~~

Dynamic Schema 是一个精简的候选上下文，不是最终 SQL，也不是新的业务事实源。

### 6.9 步骤七：Indicator Context Assembly

Indicator Context 由匹配的指标文档构成：

~~~
指标名称
业务定义
完整公式
数据来源
time_field
filters
notes
~~~

实体类请求没有匹配指标时，Indicator Context 为空，不视为技术失败；指标类请求没有匹配指标时，按必需资源缺失返回 CANNOT_ANSWER。

PARTIAL_UNREACHABLE 和 AMBIGUOUS 不是可忽略告警：如果涉及必须表或安全生成 SQL 所需的关系，外层不得继续进入 LLM SQL 生成。只有可选候选不可达时，才可以丢弃该候选并继续。

### 6.10 步骤八：交给 LLM

外层 Prompt Builder 使用：

~~~
用户问题
+ Dynamic Schema
+ Indicator Context
+ 已有 Prompt 约束和 Few-shot（如启用）
~~~

只进行一次 SQL 生成调用。

Prompt 必须明确要求 LLM 只能使用本次检索输出的 Dynamic Schema 中的表、列和 Join 关系，不得使用全量数据库中未被检索选中的资源。生成 SQL 后，外层 Online Query 在进入 AST Guard 前执行 Candidate Scope Check，检查 SQL 实际引用的表和列是否都属于本次 Dynamic Schema。检查失败时不得继续进入 AST Guard 或数据库执行。

Online Retrieval 不负责：

- 决定最终 SQL 的具体 SELECT 表达式。
- 生成 WHERE 的自然语言解释。
- 生成不存在的指标口径。
- 绕过 Dynamic Schema 使用全量未知字段；Candidate Scope Check 由外层程序强制执行。

### 6.11 步骤九：AST Guard

SQL 生成后进入既有 SQL 安全边界：

~~~
LLM SQL
→ Candidate Scope Check
→ AST Parse
→ SQL Guard
→ 数据库执行
~~~

Online Retrieval 只向下游提供结构、指标上下文和候选资源范围，不代替 Candidate Scope Check 或 SQL Guard。

## 7. 输入契约

### 7.1 请求对象

~~~json
{
  "query": "按销售区域统计已完成订单的毛利率",
  "asset_version": "20260906-bge-m3-v2",
  "config": {
    "table_top_k": 3,
    "column_top_k": 12,
    "metric_top_k": 3,
    "table_score_threshold": 0.30,
    "column_score_threshold": 0.25,
    "metric_score_threshold": 0.30
  }
}
~~~

### 7.2 输入约束

- query 必须是非空字符串。
- asset_version 必须指向已发布资产；未提供时，在请求开始时读取一次当前默认发布版本。
- 配置只能调整 V1 已支持的 Top-K 和阈值。
- 请求不得直接传入任意 Qdrant collection、任意 Schema 或任意数据库表作为过滤条件。

对外 QueryRequest 只暴露 `question` 和可选 `request_id`；`asset_version` 与检索配置由服务内部运行时提供，或仅由受控的测试/评测调用注入。外部调用者不能借此选择任意未发布或未允许的资产。

课程中的 Top-K 和阈值作为 V1 初始值，不代表跨模型、跨资产的绝对正确阈值。真实评测可以调整配置，但必须保留评测记录。

## 8. 输出契约

### 8.1 结果对象

~~~json
{
  "status": "SUCCESS",
  "asset_version": "20260906-bge-m3-v2",
  "tables": [],
  "fields": [],
  "join_path": {
    "anchor_table": null,
    "paths": [],
    "joins": [],
    "unreachable_tables": []
  },
  "metrics": [],
  "dynamic_schema": "",
  "indicator_context": "",
  "retrieval_evidence": {
    "table_hits": [],
    "column_hits": [],
    "metric_hits": []
  },
  "warnings": []
}
~~~

### 8.2 输出语义

- tables、fields、metrics 是精简后的候选资源，不是原始全量资源；tables 和 fields 同时构成下游 Candidate Scope Check 的允许范围。
- join_path 是程序根据确定性图计算出的结构结果。
- dynamic_schema 是给 Prompt 使用的精简 Schema 文本。
- indicator_context 是给 Prompt 使用的指标知识文本。
- retrieval_evidence 用于测试、评估、调试和追踪，不默认完整注入 Prompt。
- 基线请求的 `metrics` 只包含最终确定的指标；其他 Top-K 指标只能保留在 `retrieval_evidence` 中。多指标请求的 `metrics` 必须包含全部去重后的请求指标，具体以多指标规格为准。
- warnings 记录合法但需要下游处理的情况。

### 8.3 状态

| 状态 | 含义 | 下游行为 |
|---|---|---|
| SUCCESS | Dynamic Schema 已成功组装 | 正常进入 Prompt |
| NO_TABLE_HIT | 表路线没有有效候选 | 对需要表的请求返回 CANNOT_ANSWER，不得用静态 Schema 掩盖业务资源缺失 |
| NO_REQUIRED_COLUMN_HIT | 必需列没有有效候选 | 返回 CANNOT_ANSWER，不进入 LLM SQL 生成 |
| NO_METRIC_HIT | 没有有效指标命中 | 指标类请求返回 CANNOT_ANSWER；实体类请求不注入 Indicator Context 并可继续 |
| PARTIAL_UNREACHABLE | 必须表不可连通，或存在需要外层处理的不可达资源 | 映射为 CANNOT_ANSWER 时不得进入 LLM；可选候选不可达时丢弃并继续 |
| AMBIGUOUS | 当前上下文存在无法安全裁决的歧义 | 不进入 LLM SQL 生成，由外层要求澄清或返回无法回答 |
| ASSET_UNAVAILABLE | 资产不存在、未发布或版本不一致 | 进入技术失败处理 |
| RETRIEVAL_UNAVAILABLE | Qdrant 或检索服务不可用 | 实体类或单指标基线按策略 fallback；多指标返回 `CONTEXT_ERROR` |
| EMBEDDING_UNAVAILABLE | 查询向量无法生成 | 实体类或单指标基线按策略 fallback；多指标返回 `CONTEXT_ERROR` |
| FALLBACK_STATIC_SCHEMA | 外层已切换到静态上下文 | 仅适用于实体类或单指标基线 |

NO_METRIC_HIT 仅在实体类请求中是合法业务分支；指标类请求必须命中指标。

## 9. 典型场景

### 9.1 指标查询

~~~text
问题：按销售区域统计已完成订单的毛利率

TABLE：召回事实表、销售区域维度、日期维度
COLUMN：只在这些表内匹配区域字段、完成日期字段和必要 Join 字段
JOIN：BFS 生成事实表到区域维度、日期维度的最短路径
METRIC：召回毛利率定义和完整公式
输出：Dynamic Schema + Indicator Context
~~~

### 9.2 非指标实体查询

~~~text
问题：列出所有客户

TABLE：召回客户维度
COLUMN：只匹配客户相关字段
JOIN：如果不需要订单信息，不主动增加订单表
METRIC：无命中属于正常情况
~~~

### 9.3 独立表

~~~text
问题：对比销售收入和期间费用

销售事实表与费用事实表不可连通
→ 不强行 Join
→ 返回 PARTIAL_UNREACHABLE
→ 外层映射为 CANNOT_ANSWER，不进入 LLM SQL 生成
~~~

### 9.4 日期过滤

~~~text
指标：已完成订单数
time_field：completion_date_key → dim_date.full_date
→ 直接使用指标时间口径
~~~

“3 月”“4 月”或具体日期按上述指标 `time_field` 作为过滤值处理，不单独检索日期字段，也不因日期值本身返回 `AMBIGUOUS`。

## 10. 失败和恢复

### 10.1 业务资源零命中

- 指标类请求要求 TABLE、COLUMN、METRIC 以及必要 Join 资源全部有效命中；任一资源零命中，返回对应状态并映射为 CANNOT_ANSWER。
- 实体类请求要求 TABLE、COLUMN 以及必要 Join 资源全部有效命中；METRIC 零命中属于正常情况。
- 必需 COLUMN 零命中返回 NO_REQUIRED_COLUMN_HIT，不保留一个没有可回答字段的表继续生成 SQL，也不允许 LLM 自行补字段。
- 业务资源零命中不是技术故障，不得回退到静态 Schema。

### 10.2 技术失败

以下情况不是零命中：

- 资产未发布。
- 资产版本不一致。
- Qdrant 不可用。
- Embedding 模型不可用。
- 返回文档无法反序列化。
- Relationship Graph 校验失败。

这些情况必须返回明确技术状态，不得伪装成空结果。

### 10.3 静态 Schema fallback

为了保持现有 Online Query 可用：

~~~text
Online Retrieval 成功
→ 使用 Dynamic Schema

Online Retrieval 发生业务资源零命中
→ 返回 CANNOT_ANSWER，不回退为可生成 SQL 的静态上下文

Online Retrieval 发生技术失败
→ 外层按状态回退当前静态结构和指标上下文

PARTIAL_UNREACHABLE 或 AMBIGUOUS
→ 不回退为可继续生成 SQL 的确定上下文
→ 外层返回 CANNOT_ANSWER 或要求用户澄清
~~~

### 10.4 日期处理简化

- 指标类请求直接使用匹配指标文档中的 `time_field` 选择日期字段和关系。
- 用户输入的“3 月”“4 月”或具体日期只是过滤值，交给后续 SQL 生成阶段按该 `time_field` 形成过滤条件。
- V1 不增加独立的日期检索、日期意图分类器或复杂多日期推理链路。
- 用户日期值本身不会触发 `AMBIGUOUS`；只有确实无法确定业务资源或已验证关系时，才按相应错误规则停止。

fallback 必须记录实际状态和原因，不允许静默吞掉异常。

## 11. 验收标准

### 11.1 软件测试

至少覆盖：

1. TABLE 只查询 TABLE 集合。
2. COLUMN 只查询候选表范围。
3. METRIC 不受候选表范围限制。
4. METRIC 不触发递归依赖检索。
5. 指标 time_field 能进入 Indicator Context。
6. 关系图使用所有已验证关系边。
7. BFS 返回最短合法路径。
8. 多个目标表共享路径时 Join 边去重。
9. 复合键生成完整 Join 条件。
10. 不可连通表不被强行 Join。
11. 多日期关系边不因表访问去重而丢失。
12. TABLE、COLUMN、METRIC 使用同一资产版本。
13. 业务资源零命中与技术失败状态区分正确。
14. fallback 由外层触发且保留失败原因。
15. Online Retrieval 不生成 SQL、不执行数据库操作。

16. Anchor Selection 按 V1 规则输出唯一 anchor_table 和 anchor_reason，无法确定时返回 AMBIGUOUS。
17. Prompt 明确限制 Dynamic Schema，Candidate Scope Check 能拒绝范围外的表和列。
18. PARTIAL_UNREACHABLE 和 AMBIGUOUS 不进入 LLM SQL 生成。

### 11.2 AI Evaluation

使用独立评测验证：

- Table Recall。
- Column Recall。
- Metric Recall。
- Candidate Table Filter Correctness。
- Join Path Accuracy。
- Unreachable Table Detection。
- Dynamic Schema Completeness。
- Indicator Context Completeness。
- 多日期关系保留正确性。
- Dense-only 与后续 Hybrid 的效果差异。

现有离线检索评测必须继续通过。Online Retrieval 接入后，使用现有 20 条标准问题与静态上下文基线进行前后对比，至少记录：

- SQL Execution Accuracy。
- 业务结果正确性。
- Schema 召回失败率。
- fallback 触发率。
- 平均和 P95 延迟。

### 11.3 Business Acceptance

业务验收重点不是“检索到了多少文档”，而是：

- SQL 只使用与问题相关的表和字段。
- 指标公式和时间口径没有被模型改写。
- Join 条件来自真实关系事实。
- 无法确定时不会生成看似正确但口径错误的 SQL。
- 检索故障不会破坏现有可用链路。

## 12. 后续优化，不进入 V1

以下能力保留为评测驱动的后续演进，不进入当前实现：

- Sparse / Hybrid Retrieval。
- RRF 或其他融合策略。
- Reranker。
- 指标递归依赖展开。
- 指标依赖参与候选表范围扩展。
- 针对具体 Bad Case 的定向业务规则。
- 复杂多日期自然语言角色识别。
- 多轮 LLM Schema Resolution。
- 多 SQL 复杂分析和 Plan-and-Execute Agent。

## 13. 实现前置条件与开发顺序

基线已按以下顺序实现并验收；该顺序保留作实现记录。基础多指标不在此处追加实现步骤，按 `docs/specs/multi-metric-retrieval.md` 独立推进：

1. 设计 Online Retrieval 的领域结果对象和状态对象。
2. 设计 Qdrant 适配器和资产快照加载接口。
3. 实现 TABLE 检索及候选表过滤。
4. 实现 COLUMN 检索。
5. 实现 METRIC 独立检索。
6. 实现 Anchor 和 BFS Join Resolver。
7. 实现 Dynamic Schema 与 Indicator Context 组装。
8. 编写确定性软件测试。
9. 执行 Retrieval Evaluation。
10. 进行独立设计审查和 Diff 审查。
11. 通过后再接入 Online Query Prompt Builder。
12. 最后执行完整 SQL 回归、AI Evaluation 和业务验收。

后续多指标实现设计和验收完成前，不改变已经验收的实体类、单指标基线及其技术故障 fallback 行为。

## 14. 设计审查补充约束（V1 最终版）

本节对前文的宽泛描述作最终约束；实现、测试和下游集成均以本节为准。本节不新增检索路线，只明确继续、停止和校验条件。

### 14.1 必须表与不可达表

- 指标对应的事实表、用户明确要求的维度表属于必须表。
- 其他检索命中的表属于可选候选。
- 必须表无法通过已验证关系连接时，返回 PARTIAL_UNREACHABLE，由外层 Online Query 映射为 CANNOT_ANSWER，不得进入 LLM SQL 生成。
- 仅可选候选不可达时，丢弃该候选并继续。
- 任何情况下都不得猜测 Join，也不得通过 Cross Join 强行连接不可达表。

### 14.2 日期处理（简化版）

V1 不增加独立的日期检索、日期意图分类器或复杂多日期推理链路。

- 指标文档中的 `time_field` 是指标问题的权威日期字段和关系。
- 用户输入的“3 月”“4 月”或具体日期只是过滤值，后续 SQL 只能基于该 `time_field` 生成过滤条件。
- 用户日期值本身不会触发 `AMBIGUOUS`，也不会改变指标的 `time_field`。
- Relationship Graph 离线保留全部合法日期边；在线 BFS 不得因为表已访问就丢弃语义不同的平行边。

### 14.3 Anchor Table

命中指标时，使用指标文档中的 `data_source` 确认事实表，并将该事实表作为必须表和 `anchor_table`。但 `data_source` 不能替代 TABLE Retrieval：事实表必须先被 TABLE 路线有效命中，否则指标类请求返回 CANNOT_ANSWER。通过 TABLE 命中后，`data_source` 才用于确认事实表身份，不触发递归指标检索，也不扩展无关表。

- 命中指标时，使用指标对应的事实表作为 anchor_table。
- 未命中指标时，使用 TABLE Retrieval 得分最高的表。
- 没有唯一最高候选或无法确定锚表时，返回 AMBIGUOUS，不调用 LLM 猜测。
- Anchor Selection 必须输出 anchor_table 和 anchor_reason。

### 14.4 Dynamic Schema 与 Prompt 约束

Prompt 必须明确要求 LLM 只能使用本次检索输出的 Dynamic Schema 中的表、列和 Join 关系，不得使用全量数据库中未被检索选中的资源。

Dynamic Schema 中的 tables 和 fields 同时构成下游 Candidate Scope Check 的允许范围。该检查由外层 Online Query 在 AST Guard 之前执行：

~~~
LLM SQL
→ Candidate Scope Check
→ AST Parse / SQL Guard
→ 数据库执行
~~~

Candidate Scope Check 只检查 SQL 实际引用的表和列是否属于本次 Dynamic Schema，不新增权限系统，也不替代 AST SQL Guard。检查失败时不得进入 AST Guard 或数据库执行。

### 14.5 资产快照一致性

- 请求开始时只读取一次当前发布指针。
- TABLE、COLUMN、METRIC、Relationship Graph 和 Embedding Model 必须来自同一个 asset_version。
- 本次请求期间三条检索路线和图计算固定使用这份不可变快照，不允许各路线分别重新读取当前指针。
- 任一资产缺失、版本不一致或 Embedding Model 不匹配时，返回 ASSET_UNAVAILABLE。

### 14.6 最终 V1 链路

~~~
加载一致的 RAG 资产快照
→ Table Retrieval
→ 候选表内的 Column Retrieval
→ 独立 Metric Retrieval
→ 按请求类型检查必需资源是否完整
→ Anchor Selection
→ 确定性 Graph Join Resolution
→ 按指标 time_field 绑定日期口径与不可达检查
→ Dynamic Schema + Indicator Context
→ 一次 LLM 生成 SQL
→ Candidate Scope Check
→ AST SQL Guard
→ 执行 SQL
~~~

### 14.7 请求类型与必需资源

基线 V1 用确定性的最小规则区分两类请求：问题经过统一规范化后，命中已发布 Metric 的名称或别名，或出现明确的指标 / 聚合表达时，按单指标类请求处理；未命中这些条件时按实体类请求处理。不增加 LLM 意图分类器。明确列举多个已登记指标的请求，转由基础多指标规格处理。

明确的指标 / 聚合表达包括“金额、数量、总额、平均值、占比、率、统计”等有限业务表达。该规则只用于决定 METRIC 是否为必需资源，不负责选择具体指标；具体指标仍必须由 METRIC Retrieval 命中。

| 请求类型 | 必须有效命中的资源 | METRIC 零命中 | 失败行为 |
|---|---|---|---|
| 指标类 | TABLE、COLUMN、METRIC、必要 Join | 错误 | 任一必需资源缺失，直接 CANNOT_ANSWER，不调用 LLM，不静态 fallback |
| 实体类 | TABLE、COLUMN、必要 Join | 正常 | 任一必需资源缺失，直接 CANNOT_ANSWER，不调用 LLM；不需要指标上下文 |
| 基础多指标 | TABLE、COLUMN、全部请求 METRIC、必要 Join | 任一指标错误 | 按多指标规格处理；任一必需资源缺失直接停止，技术故障返回 `CONTEXT_ERROR`，不静态 fallback |

这里的“必须有效命中”指对应检索路线确实返回合法候选；Join Key 可以由已验证 Relationship Graph 补入，但不能替代业务 COLUMN 命中。只有 Qdrant、Embedding、资产加载等技术失败才允许回退静态 Schema，且多指标请求受多指标规格的禁止回退规则约束。

### 14.8 指标选择与公式字段

- 对单指标基线，METRIC 的 Top-K 结果只作为检索证据；最终 Indicator Context 只能包含一个确定指标。规范化问题命中唯一指标名或别名时优先选择该指标；没有精确命中时，只有一个候选超过阈值才选择；多个候选超过阈值且不能唯一确定时返回 `AMBIGUOUS`。
- 对明确列举多个指标的请求，逐项识别、逐项召回并完整组装全部 Indicator Context；名称映射、上限、同表/同日期/同固定条件和 SQL 覆盖检查以多指标规格为准。
- 指标公式和 `filters` 引用的物理字段，以及 `time_field` 字段，属于必需 COLUMN；引用由确定性 Formula Reference Resolver 提取，不调用 LLM。
- 公式或 `filters` 无法解析时返回 `ASSET_UNAVAILABLE`；任一必需字段未被 COLUMN 路线命中时返回 `NO_REQUIRED_COLUMN_HIT`。

### 14.9 日期关系与多路径

- `time_field` 的左侧用于匹配 Graph Edge 的来源表和来源列，右侧字段用于日期过滤；实际 Join Key 必须来自 Graph Edge 的 `target_columns`。
- 匹配不到时间关系时返回 `ASSET_UNAVAILABLE`；匹配到多条语义不同关系，或存在无法由已知条件唯一确定的同长度路径时返回 `AMBIGUOUS`。
- 只有同一 `edge_id` 的重复结果可以去重；语义不同的平行边必须保留。

### 14.10 Asset Snapshot 生命周期

- 每个请求只读取一次 `current.json`。
- Runtime 可以按 `build_id` 缓存不可变快照；同一请求的 TABLE、COLUMN、METRIC、Relationship Graph 和 Embedding Model 必须来自同一快照。
- `asset_version` 和检索配置不是外部用户可任意指定的 QueryRequest 字段。
