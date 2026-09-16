# Online Retrieval V1 统一检索流水线规格

状态：已确认；需求已完成 `grill-with-docs` 和人工确认

## Problem Statement

当前 Online Retrieval（在线检索）同时存在单指标、实体类和多指标的不同处理逻辑，并且历史设计中还包含中间表补入、字段业务规则、公式字段自动补充、静态 Schema fallback（回退）等行为。

这些行为使流程难以理解，也让维护者无法快速判断：

- 哪些内容是用户问题的候选资源；
- 哪些内容是指标和关系图的权威事实；
- 哪些内容可以交给 LLM；
- 哪些失败必须停止；
- 单指标和多指标是否需要两条完整流水线。

当前 ChatBI 项目的主要数据模型是事实表直接连接客户、商品、日期、区域和币种维表的 Star Schema（星型模型）。当前指标也主要来自同一事实表，并使用已经冻结的人民币物理字段。因此，本次需要把 Online Retrieval 收敛为一条清晰的、可拒答的统一流水线，而不是继续叠加检索分支和补充机制。

## Solution

为实体查询、单指标查询和多指标查询提供同一条 Online Retrieval 流程。

```text
同一版本资产快照
→ TABLE 检索 + 可选 METRIC 检索（并行）
→ 在候选表范围内进行 COLUMN 检索
→ 直接 FK-PK Relationship Graph
→ 最小结构化上下文
→ 一次 Prompt 调用
→ 一条 SQL 或 CANNOT_ANSWER
→ SQL Guard
→ 数据库执行
```

单指标和多指标的差异只体现在 `METRIC` 是否存在以及指标数量，不建立两条完整流水线。

V1 的初始检索配置为：

```text
TABLE  Top-K = 5，threshold = 0.30
COLUMN Top-K = 20，threshold = 0.25
METRIC Top-K = 10，threshold = 0.30
```

其中 `COLUMN = 20` 是所有候选表合计最多 20 个列；`METRIC = 10` 是候选数，不是最终输出指标数。V1 一条查询最多明确请求 5 个指标。

## User Stories

1. 作为 ChatBI 用户，我希望用同一种方式查询实体、单个指标或多个指标，从而不需要理解系统内部的检索分支。
2. 作为 ChatBI 用户，我希望多个指标在同一查询范围内完整返回，从而不会得到缺少指标或口径不一致的部分结果。
3. 作为维护者，我希望 LLM 只看到当前查询必要的结构化上下文，从而减少错误 Join、无关 Schema 和敏感元数据暴露。
4. 作为项目负责人，我希望系统在候选不足、关系不确定或安全检查失败时停止，而不是让 LLM 猜测并生成不可验证的 SQL。

## Implementation Decisions

### 1. Architecture（架构）

- 保持 Modular Monolith（模块化单体）。
- 保持现有 `OnlineRetriever.retrieve()` 作为主要可观察 Seam（接缝）。
- 不重新建设完整 DDD 的 `domain`、`application`、`infrastructure` 三层。
- 单指标、实体类和多指标使用同一条编排流程；仅对可选的指标上下文做条件处理。
- 内部实现可以按资源检索、关系解析和上下文组装组织，但不新增公共 Port / Adapter 或新的外部 API。
- 不把 Qdrant、Embedding Model、LLM Provider 或数据库 SDK 提升为 Domain（领域）概念。

### 2. Asset Snapshot（资产快照）

- 一次请求开始时读取一次当前已发布资产版本。
- TABLE、COLUMN、METRIC、Relationship Graph 和 Embedding Model 必须来自同一版本。
- 本次请求中不混用不同版本的表、列、指标公式或关系事实。
- 资产版本不完整、不一致或不可用时，返回 `CONTEXT_ERROR`，不进入 LLM。

### 3. Resource Retrieval（资源检索）

- TABLE 检索最多保留 5 个候选，低于 `0.30` 的结果不进入有效候选集。
- METRIC 在存在指标意图时执行一次综合检索，最多保留 10 个候选，低于 `0.30` 的结果不进入有效候选集。
- METRIC 路线不按每个指标分别发起检索。
- 无指标意图的实体类查询跳过 METRIC，空的指标上下文不视为技术失败。
- COLUMN 检索必须在 TABLE 候选范围内进行，最多保留所有候选表合计 20 个列，低于 `0.25` 的普通语义结果不进入有效候选集。
- 不增加字段白名单、黑名单、加权或条件匹配规则引擎。
- 允许在候选表范围内恢复指标公式、固定过滤条件和时间关系明确引用的必需字段；允许对用户明确请求的分组维度执行有限字段检索。
- 不通过全库字段扫描、候选表外检索或隐藏业务规则绕过候选范围。
- 不使用中间表补入机制扩大候选表范围。

### 4. Metric（指标）

- V1 一条查询最多明确请求 5 个指标。
- 指标候选数为 10，实际输出指标数为用户明确请求的 1～5 个指标。
- 用户明确请求的每一个指标都必须被当前一次综合 METRIC 检索有效覆盖。
- 任一请求指标未命中、低于阈值或无法确定时，整次返回 `CANNOT_ANSWER`，不只返回其余指标。
- `depends_on` 只表达指标血缘和解释关系，V1 不在线展开、不触发第二次指标检索，也不自动增加输出指标。
- 多指标只有在以下内容兼容时才允许合并为一条 SQL：
  - `data_source` 相同；
  - `time_field` 相同；
  - 固定 `filters` 相同；
  - 用户时间范围、分组维度和查询级过滤条件相同。
- 不兼容的指标组合返回 `CANNOT_ANSWER`，不拆成多条 SQL，不构造条件聚合或子查询。
- 指标的 `definition`、`formula`、固定 `filters`、`time_field` 和 `data_source` 是权威事实。
- LLM 可以使用这些事实，但不能删除、替换、改写或重新解释它们。
- 指标公式、固定过滤条件和时间关系引用的物理字段，可以在已命中的候选表范围内进行受限恢复；如果资产中不存在或恢复失败，返回 `CANNOT_ANSWER`。

### 5. Relationship Graph（关系图）

- Graph 只使用已经认证的直接 Foreign Key（外键）到 Primary Key（主键）关系。
- 不自动补入中间表、桥接表或用户没有直接召回的隐藏表。
- 不支持必须经过中间表的多跳 Join；此类请求返回 `CANNOT_ANSWER`。
- TABLE 候选是候选池，不代表所有候选表都必须 Join。
- Graph 只返回候选表之间允许使用的直接 Join Facts（连接事实）；不自动把候选表全部连接起来。
- Join Key 不占用 COLUMN Top-20；它作为 Graph 的结构事实提供给结构化上下文和 SQL Guard。
- 指标类请求使用指标 `data_source` 对应的事实表作为 `anchor_table`。
- 无指标请求使用被列候选命中且表检索分数最高的表作为主表；无法确定时返回 `CANNOT_ANSWER`。
- 事实表作为主表时，维表统一使用 `LEFT JOIN`。
- 禁止 `RIGHT JOIN`、`FULL JOIN` 和 `CROSS JOIN`。
- 同一表对存在多条直接关系时，指标的 `time_field` 或用户明确的时间语义优先；无法确定时返回 `CANNOT_ANSWER`。
- 只有查询确实需要日期过滤或日期分组时才连接 `dim_date`；普通客户、商品、区域和币种 Join 不需要时间判断。

### 6. Structured Context（结构化上下文）和 Prompt

发送给 LLM 的内容只包含当前查询必要的最小结构化上下文：

- TABLE 候选；
- COLUMN 候选；
- METRIC 候选及其权威定义、公式、固定过滤条件、时间关系和数据来源；
- 候选表之间必要的直接 Join Facts；
- 原始用户问题。

不发送：

- 完整数据库 Schema；
- 完整 `relationships.json`；
- 无关表和列；
- 行数据或样例数据；
- 未授权资源。

LLM 的职责是：

- 在已经提供的候选表、列和指标中选择当前查询需要的资源；
- 根据结构化上下文生成最终 SQL。

LLM 不得：

- 创建候选范围外的表、列或指标；
- 修改指标定义、公式、固定过滤条件或时间口径；
- 发明、修改或绕过 Graph 提供的 Join Facts；
- 生成第二条 SQL；
- 绕过 SQL Guard。

不建立单独的候选选择 LLM，也不为表、列、指标分别调用多个 LLM。

### 7. Filter（过滤条件）

- 用户明确提供的过滤值可以作为 SQL 参数使用。
- V1 不在线读取数据库全部 distinct values（去重值）。
- V1 不让 LLM 猜测业务值到数据库编码的映射。
- 用户值不需要额外映射时直接按用户输入过滤。
- 不因为数据库没有匹配行而将合法查询判定为 `CANNOT_ANSWER`。

### 8. LLM、SQL Guard 和执行

- LLM 一次调用只允许返回一条 SQL 或精确的 `CANNOT_ANSWER`。
- SQL Guard 失败时返回 `CANNOT_ANSWER`，不再次调用 LLM，不执行未通过检查的 SQL。
- SQL 只能使用结构化上下文和 Graph 允许的表、列、指标和 Join。
- V1 SQL 形态限制为单层 `SELECT`，一个主表，直接 `LEFT JOIN`，以及可选的 `WHERE`、`GROUP BY`、`ORDER BY` 和 `LIMIT`。
- 不支持 CTE、子查询、窗口函数、UNION、多 SQL、条件聚合和复杂分析。
- LLM 超过 30 秒返回 `LLM_ERROR`，不自动重试。
- 数据库查询超过 10 秒返回 `QUERY_TIMEOUT`，不自动重试。
- 单次查询最多返回 100 行；执行端最多读取 101 行用于判断截断。
- V1 不支持分页和自动重试。
- SQL 合法执行但没有匹配数据时，返回成功的空结果或指标定义允许的 `0` / `NULL`。

### 9. 权限与隐私边界

- 用户权限范围由上游提供，不在本 Spec 内建设登录、租户或权限系统。
- TABLE、COLUMN、METRIC 和 Graph 都必须在上游允许范围内运行。
- 没有用户权限范围时，V1 只能用于可信内部环境，不能宣称支持多租户生产环境。
- 权限过滤必须发生在检索和上下文组装之前，不能先检索全库再最后过滤。
- 不因允许使用 Graph 就自动暴露完整关系图或无关 Schema。

## Testing Decisions

### Software Test

主要使用现有 Online Retrieval 公共 Seam 和 Online Query / SQL Guard 集成边界验证外部行为，不让测试依赖偶然的私有函数或文件拆分。

必须覆盖：

- TABLE Top-5、COLUMN 总 Top-20、METRIC Top-10 和三个阈值；
- 实体类查询跳过 METRIC；
- 单指标和多指标使用同一编排流程；
- 多指标最多 5 个、全部命中、全部返回且顺序正确；超过 5 个时拒答；
- 多指标来源、时间口径、固定条件或用户范围不兼容时拒答；
- 指标公式、固定过滤条件、`time_field` 和 `data_source` 不被修改；
- 指标必需字段可以在候选表范围内受限恢复；候选表外或资产缺失时拒答；
- 候选表范围内的 COLUMN 检索；
- 直接 FK-PK Join、唯一主表、固定 `LEFT JOIN` 和 Join Key 验证；
- 中间表、多跳 Join、不可达表和未认证 Join 被拒绝；
- 多日期直接关系按 `time_field` 或明确用户语义处理，无法确定时拒答；
- 最小结构化上下文不包含完整关系图、无关 Schema 或行数据；
- SQL Guard 拒绝范围外表、列、指标、Join 和危险 Join 类型；
- 业务候选缺失、资产版本不一致、Qdrant / Embedding 故障、LLM 超时和数据库超时的状态边界；
- 无数据的合法查询返回空结果、`0` 或 `NULL`，不误报为检索失败；
- 100 行上限、无分页和无自动重试。

### AI Evaluation

- 复用现有 Online Retrieval 和 Multi-Metric 的标准评测集作为回归基线。
- 评测检索覆盖、候选资源完整性、指标完整性、Join 正确性、SQL 执行结果、拒答准确性和调用次数。
- 增加以下 Bad Case（坏例）回归：
  - 必要表或列不在候选中；
  - 指标候选相似但不是用户请求指标；
  - 多指标只命中部分；
  - 多指标来源、时间或固定条件不兼容；
  - 中间表或不可达表；
  - 多日期关系歧义；
  - SQL Guard 范围外引用；
  - 无数据但查询合法。
- 不把 Token 数、首个 Embedding 加载时间或模型 Provider 更换作为本 Spec 的验收目标。

### Business Acceptance

正向场景：

1. 查询销售额；
2. 查询销售额和已完成订单数；
3. 按客户类型统计销售额；
4. 2025 年按商品统计销售额；
5. 列出客户名称（无指标查询）。

负向场景：

1. 没有必要表、列或指标；
2. 必须使用中间表才能连接；
3. 日期关系无法确定；
4. 多指标来源、时间或固定条件不兼容；
5. SQL Guard 拒绝 SQL。

验收必须观察：

- 正向场景生成并执行一条合法 SQL；
- 多指标没有缺项、替换或额外指标；
- Join 只使用认证的直接关系；
- 业务资源缺失时不调用 LLM；SQL Guard 失败时不执行或重试不安全 SQL；
- 空结果被正确识别为合法执行结果；
- 结果和人工审核的业务口径一致。

## Out of Scope

- 不使用中间表、桥接表或多跳 Join。
- 不建设完整 DDD 分层、权限系统、租户系统、登录系统或多租户生产治理。
- 不建设字段白名单、黑名单、加权或条件业务规则引擎。
- 不从候选表外自动补充公式字段、时间字段或业务字段；只允许当前请求明确依赖字段和明确分组字段的受限恢复。
- 不在线展开 `depends_on`，不做递归指标编译。
- 不做按指标分别检索、第二次 LLM、LLM 修复重试或多 Agent / Plan-and-Execute。
- 不做静态全量 Schema fallback。
- 不做 Sparse、Hybrid、Reranker、动态阈值或额外语义重排。
- 不做数据库 distinct value 查询、业务编码自动映射或 Schema Alias（别名）系统。
- 不支持多 SQL、CTE、子查询、窗口函数、UNION、条件聚合、同比环比、原因分析、What-if 分析或自动分析报告。
- 不修改数据库数据、Qdrant 资产、离线构建流程或外部 Issue tracker。
- 不创建 GitHub Issue、GitLab Issue、PR 或外部任务。
- 本阶段不实现代码、不编写测试代码、不删除旧文档，也不自动进入 `to-tickets` 或 `implement`。

## Further Notes

- 课程提供的是通用 Schema Linking、指标 RAG 和 Graph Join 方法；本 Spec 按当前 ChatBI 数据模型和“简单、低暴露、可拒答”的目标做了收敛。
- 课程示例中出现过表 Top-3、字段 Top-10 / Top-12、指标 Top-3 和依赖展开；ChatBI V1 当前采用 TABLE=5、COLUMN=20、METRIC=10，最多请求 5 个指标，并关闭依赖展开。
- 当前仓库已有的 Online Retrieval Spec、Multi-Metric Spec、实现和验收记录仍可能包含中间表、字段补充、静态 fallback 或旧的单独多指标行为。它们与本 Spec 冲突的部分必须在后续交付前统一处理，不能静默以旧代码覆盖本 Spec。
- 当前项目的 `CONTEXT.md` / ADR 不在本 Spec 阶段新增；本 Spec 先作为 Feature Contract（功能契约）等待确认。若后续设计审查发现需要记录不可逆的架构决策，再单独创建 ADR。
- 本 Spec 已确认，并已使用 `to-tickets` 按可独立验证行为拆分任务；实现按本地 Ticket 顺序推进。
