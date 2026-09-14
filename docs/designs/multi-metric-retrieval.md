# 基础 Multi-Metric Retrieval（多指标在线检索）实现设计

状态：T1～T5 已完成；修复 M08 分组粒度后真实在线 RAG 评测 20/20 通过，Business Acceptance（业务验收）已通过；当前仍不代表 Production Ready（生产可用）

## 1. 目标

在现有 Online Retrieval（在线检索）V1 上增加基础多指标能力，使下面这类问题能够进入一条可验证的生产链路：

> 按客户类型统计已完成订单数、人民币销售额和毛利率

本次完成后，系统应当：

1. 识别用户明确列出的多个已登记指标；
2. 使用完整用户问题完成一次综合 METRIC Dense Retrieval（指标稠密检索）；
3. 对综合候选逐项检查全部请求指标是否有效覆盖；
4. 确认这些指标可以在同一条 SQL 中安全组合；
5. 合并表、列、关联关系、日期和固定指标过滤条件；
6. 只调用一次 LLM（大语言模型）生成一条 SQL；
7. 在执行前用 Deterministic Guard（确定性校验）确认所有指标均被正确实现；
8. 任一指标缺失、冲突或链路失败时整体失败，不返回部分结果。

## 2. Source of Truth（事实源）

实现必须同时满足：

- `docs/architecture.md`
- `docs/engineering.md`
- `docs/specs/online-query.md`
- `docs/specs/online-retrieval.md`
- `docs/specs/multi-metric-retrieval.md`
- `docs/designs/online-retrieval.md`

优先级仍为 Architecture（架构）→ Engineering（工程规则）→ Spec（规格）→ Design（实现设计）→ Code（代码）。

## 3. 本次范围

### 3.1 In Scope（范围内）

- 一次请求包含 2～5 个去重后的已登记指标；
- 指标名称或别名由当前发布版本的指标资源确定；
- 一次综合指标召回、逐项完整性检查和兼容性检查；
- 多指标所需列的合并检索；
- 从共同事实表到分组维表的安全关联；
- 多指标 Prompt（提示词）约束；
- 多指标 SQL 结构、公式、固定过滤条件和输出完整性校验；
- 多指标失败时禁止 Static Fallback（静态回退）；
- Software Test（软件测试）、AI Evaluation（AI 评测）和 Business Acceptance（业务验收）。

### 3.2 Out of Scope（范围外）

- 新增或修改指标定义；
- 递归展开 `depends_on`；
- 多事实表、跨主题或跨数据源指标组合；
- CTE（公共表表达式）、子查询、窗口函数、集合运算和 HAVING；
- 多轮对话、经营分析、权限系统和生产安全边界；
- 修改公共 Query API（查询接口）请求或响应结构；
- 修改离线文档格式、Manifest（清单）格式或重新构建 RAG（检索增强生成）资源；
- 通用 SQL 代数等价证明。

## 4. 当前实现事实与缺口

T1～T3 已在现有单指标链路旁增加了受限、Fail Closed（失败关闭）的多指标检索分支；T4 已补齐多指标 Prompt、AST SQL Guard（语法树 SQL 安全校验）和 Service（服务层）闭环。T5 首轮真实 LLM、Qdrant、PostgreSQL 评测暴露了 M08 分组粒度波动，补充 Prompt 约束后正式报告达到 20/20；主验收问题 C05 和 M08 通过，正式 Business Acceptance（业务验收）已确认，不能据此直接称为 Production Ready（生产可用）。

## 5. 总体链路

```text
QueryRequest
  → Request Shape Classification（请求形态预判）
  → Published Asset Snapshot（同一发布版本快照）
  → Metric List Resolution（指标列表解析）
  → TABLE Retrieval × 1
  → METRIC Retrieval × 1（完整用户问题）
  → Metric Coverage + Compatibility Check（逐项覆盖与兼容检查）
  → Required Column Merge
  → COLUMN Retrieval × 1（候选表范围内）
  → Join Path + Cardinality Check
  → Structured QueryContext
  → Prompt × 1
  → LLM × 1
  → Existing SQL Scope/Safety Guard
  → Multi-Metric SQL Guard
  → Database × 1
  → QueryResponse
```

其中 METRIC 只执行一次；请求指标数量仍限制为去重后的 2～5 个。一次检索结果必须覆盖全部请求指标，否则整体失败。

## 6. 请求形态与回退策略

### 6.1 为什么要在读取资源前预判

如果 Qdrant 或发布资源在最开始就不可用，系统仍要知道本次请求能不能静态回退。多指标请求禁止回退，现有单指标和实体查询保留原行为，所以不能等检索失败后才判断。

### 6.2 RequestShape（请求形态）

增加内部枚举：

- `BASELINE`：没有明确的多指标列举结构，继续走现有实体/单指标行为；
- `EXPLICIT_MULTI`：检测到至少两个指标形态短语被明确并列；
- `POSSIBLE_MULTI`：检测到并列指标意图，但无法仅凭句法确认所有项。

`EXPLICIT_MULTI` 和 `POSSIBLE_MULTI` 都使用 `FAIL_CLOSED`；只有 `BASELINE` 可以在技术失败时使用现有静态回退。

### 6.3 V1 支持的明确列举形式

预判只识别有限句法，不推理业务指标：

- 动作词：`统计`、`查询`、`查看`、`比较`、`分析`；
- 分隔符：`、`、`,`、`，`、`和`、`及`、`以及`、`与`；
- 指标形态词尾：`数`、`数量`、`额`、`金额`、`成本`、`利润`、`毛利`、`率`、`占比`、`均价`、`单价`。

预判只决定回退策略，不决定指标业务含义。真正的名称、别名和去重结果仍由发布指标目录裁决。

为避免把“按客户类型和销售区域分组”误判为多指标，预判只检查动作词后的统计对象，不检查动作词前的分组和过滤范围。

## 7. 同版本 Metric Catalog（指标目录）

### 7.1 数据来源

指标目录必须来自本次 `AssetSnapshot` 指向的已发布 `METRIC` 集合，禁止直接读取工作区中的 `metrics.json`，也禁止混用其他 Build（构建版本）的数据。

在 `QdrantAssetStore` 增加只读 Payload 分页读取能力：

- 使用当前 `qdrant-client 1.19.0` 的 `scroll`；
- `with_payload=True`；
- `with_vectors=False`；
- 按游标读取到结束；
- 读取数量必须与 Manifest 记录一致；
- 结果按 `document_id` 确定性排序。

### 7.2 MetricCatalogEntry（指标目录项）

每项至少包含：

- `document_id`
- `metric_name`
- `aliases`
- `formula`
- `data_source`
- `time_field`
- `filters`
- `depends_on`
- `page_content`

目录加载时检查必填字段、重复 `document_id`、重复规范名，以及名称/别名碰撞。任何 Contract Error（契约错误）都使当前快照不可用。

目录随 `AssetSnapshot` 按 Build ID 缓存，不在每次查询时重新全量读取。

## 8. 指标解析与综合召回

### 8.1 Metric List Resolution（指标列表解析）

解析器执行以下确定性规则：

1. 在问题中匹配当前目录里的规范名和别名；
2. 同一位置存在重叠匹配时保留最长项，例如优先匹配“毛利率”而不是“毛利”；
3. 按用户原文中的出现顺序保留结果；
4. 同一 `document_id` 多次出现时按首次出现去重；
5. 2～5 个不同指标进入多指标分支；
6. 超过 5 个直接拒绝，不截断；
7. 明确列举中的任一项不能映射到目录时整体拒绝；
8. 不通过 LLM 补齐、改写或猜测指标。

### 8.2 Combined Metric Retrieval（综合指标召回）

所有已解析指标共享一次 METRIC Dense Retrieval：

- 查询文本直接使用完整用户问题，不为每个指标重新生成向量查询；
- 综合检索的 Top-K 至少覆盖请求指标数，且不低于 V1 的 5 个指标上限；
- 结果必须包含每个请求指标映射出的目标 `document_id`，并满足指标阈值；
- 目录映射负责“用户明确说的是谁”，综合向量召回负责“这些权威文档确实进入在线候选”；
- 任一目标没有进入这一次综合结果即 `NO_METRIC_HIT`，整体失败；
- 不允许用另一个相似指标替换目标，也不允许为了补齐缺失指标再发起逐指标向量检索；
- 保留一个综合检索证据，同时记录每个请求指标的覆盖结果和失败原因。

这样减少重复向量调用，但不降低完整性要求：LLM 不能从相似指标、公式字段或自己的常识中补齐未命中的指标。

## 9. 多指标兼容性

完成全部指标召回后，程序比较认证 Metadata（元数据）：

1. `data_source` 必须完全一致；
2. `time_field` 必须完全一致；
3. 固定 `filters` 经 SQL AST（抽象语法树）规范化后必须一致；
4. 所有公式引用的字段必须存在于同一事实表或已认证关系路径；
5. `depends_on` 只作为血缘信息返回，不参与递归检索和展开。

不兼容时对外返回现有 `CANNOT_ANSWER`，内部原因记录为 `UNSUPPORTED_METRIC_COMBINATION`。

## 10. 表、列与关系处理

### 10.1 TABLE 和 COLUMN 路由

- TABLE 路由仍以完整用户问题检索一次；
- METRIC 路由以完整用户问题执行一次综合检索，并逐项验证请求指标覆盖；
- 共同 `data_source` 必须在候选表中成立；
- 合并所有指标公式、固定过滤条件、共同日期字段以及用户分组所需字段；
- COLUMN 路由在候选表范围内执行一次组合检索；
- 必需字段通过精确过滤补齐，不受普通 Top-K 截断；
- 任一必需字段缺失时整体失败。

### 10.2 Join Cardinality（关联基数）安全

多指标聚合以共同 `data_source` 作为唯一 Anchor Fact Table（锚点事实表）。从事实表到分组/日期维表的每一段关系必须满足：

- 当前表是 Foreign Key（外键）源端；
- 下一张表是外键目标端；
- 目标列属于目标表的 Primary Key（主键）或无条件 Unique Constraint（唯一约束）；
- 路径上的每一段都是多对一或一对一；
- 不允许反向的一对多遍历；
- 不采用 Partial Unique Index（部分唯一索引）作为 V1 安全证明；
- 多条同等有效路径仍按现有歧义规则拒绝。

这样可以防止维表关联把事实行重复放大，造成 SUM、COUNT 和比率结果错误。

这些限制只应用于新多指标分支，不改变现有单指标和实体查询行为。

## 11. 内部 Contract（契约）变化

公共 Query API 保持不变，只增加内部结构。

### 11.1 RetrievalRequest

包含：

- 原始 `question`；
- `request_shape`；
- `fallback_policy`。

Service（服务层）先构造该请求，再交给 Retrieval Provider（检索提供者）。因此即使 Provider 抛出异常，Service 也知道多指标请求不能回退。

### 11.2 MetricConstraint

每个已确认指标形成一个结构化约束：

- 用户原始短语；
- 用户顺序；
- `document_id` 和规范指标名；
- 公式；
- `data_source`；
- `time_field`；
- 固定过滤条件；
- 必需列集合。

### 11.3 JoinConstraint

每条允许使用的 Join（关联）包含：

- 源表和源列；
- 目标表和目标列；
- 目标唯一性依据；
- 方向。

### 11.4 QueryContext

在现有动态 Schema（模式）文本之外，增加：

- `request_shape`
- `metric_constraints`
- `join_constraints`

这些字段是 SQL Guard 的程序输入，不能只写在 Prompt 文本里。

### 11.5 Retrieval Evidence（检索证据）

保留现有扁平命中证据，同时增加一次综合 METRIC 检索证据及按“用户指标项”展开的覆盖结果，能够回答：

- 用户要求了哪个指标；
- 映射到了哪个规范指标；
- 综合向量召回返回了哪些候选；
- 每个请求指标是否在同一批候选中有效命中；
- 为什么成功或失败。

## 12. Prompt（提示词）变化

Indicator Context（指标上下文）改为带顺序的 `requested_metrics` 数组，每项只包含认证资源中的业务事实。

Prompt 明确要求：

1. 只能使用 Dynamic Schema 中的表和列；
2. 必须输出 `requested_metrics` 中的全部指标；
3. 指标出现顺序必须与用户请求顺序一致；
4. 不得增加未请求的聚合指标；
5. 每个指标必须使用给定公式和固定过滤条件；
6. 所有指标共享同一用户日期、分组和过滤范围；
7. 只能使用给定 Join；
8. 只生成一条 SQL。

Prompt 负责帮助模型生成候选，最终正确性仍由程序校验。

## 13. Multi-Metric SQL Guard（多指标 SQL 校验）

新增独立的多指标校验器。它只在 `metric_constraints` 数量大于等于 2 时执行，现有通用 SQL Guard 行为不变。

执行顺序：

```text
Candidate Scope Guard
  → Existing SQL Safety Guard
  → Multi-Metric SQL Guard
  → Database
```

### 13.1 允许的 SQL 形态

- 单条顶层 `SELECT`；
- 一个共同事实来源；
- 零到多个已认证维表 Join；
- 一个共同 `WHERE`；
- 可选 `GROUP BY`、`ORDER BY`、`LIMIT`。

### 13.2 明确拒绝

- CTE；
- 子查询；
- Window Function（窗口函数）；
- `UNION`、`INTERSECT`、`EXCEPT`；
- `HAVING`；
- 未认证 Join；
- `OR` 绕过固定指标过滤条件；
- 额外聚合指标；
- 指标缺失、重复或顺序错误。

### 13.3 公式校验

使用当前 SQLGlot 解析指标公式和候选 SELECT 表达式：

1. 去除输出 Alias（别名）和无意义括号；
2. 把查询中的表别名解析回认证物理表；
3. 把公式里的列同样规范化为物理表和列；
4. 比较规范化后的 AST 结构；
5. 允许大小写、空白、表别名等无业务意义差异；
6. 不推理交换律、结合律或其他数学等价形式。

当前五个指标公式都属于该有限范围：`COUNT(DISTINCT ...)`、`SUM(...)`、减法和带 `NULLIF` 的除法。

### 13.4 固定过滤条件校验

- 认证固定过滤条件必须作为 `WHERE` 的 AND 子条件存在；
- 用户日期和普通筛选可以作为额外 AND 子条件；
- 多指标 V1 的 `WHERE` 不允许 `OR`；
- 固定过滤条件的列、操作符和值均由 AST 结构比较。

### 13.5 输出完整性

- 非聚合分组列必须出现在 `GROUP BY`；
- 所有聚合表达式必须恰好对应请求指标；
- 指标表达式必须按用户请求顺序出现；
- 输出 Alias 不作为公式正确性的判断依据，但 Prompt 要求使用可读名称。

## 14. 失败语义

| 场景 | 外部结果 | Static Fallback |
|---|---|---|
| 任一指标未登记或未召回 | `CANNOT_ANSWER` | 禁止 |
| 指标超过 5 个 | `CANNOT_ANSWER` | 禁止 |
| 指标来源、日期或固定条件不兼容 | `CANNOT_ANSWER` | 禁止 |
| 必需表、列或安全关系缺失 | `CANNOT_ANSWER` | 禁止 |
| 多指标资源、Embedding 或 Qdrant 技术失败 | `CONTEXT_ERROR` | 禁止 |
| 多指标 SQL 校验失败 | SQL_REJECTED | 禁止执行 SQL |
| 现有实体/单指标技术失败 | 保持现有行为 | 允许 |

多指标链路中的任何失败都必须发生在 Database 执行之前。

## 15. 测试与验收

### 15.1 Software Test（软件测试）

按规格 MM01～MM19 实现确定性测试，至少覆盖：

- 目录分页、同版本缓存、字段缺失和别名碰撞；
- 明确多指标预判与分组字段误判保护；
- 名称/别名匹配、最长匹配、顺序、去重和上限；
- 一次综合 METRIC 召回覆盖全部请求指标，任一项缺失整体失败，且不发起逐指标补检索；
- `data_source`、`time_field`、`filters` 兼容性；
- 多指标所需列合并；
- 安全多对一 Join 和不安全反向 Join；
- 多指标无静态回退；
- Prompt 指标完整性要求；
- SQL 的合法单 SELECT；
- 指标缺失、额外指标、公式错误、固定条件缺失、OR 绕过和不支持结构；
- 现有单指标、实体查询、CTE 基线和静态回退回归不变。

### 15.2 AI Evaluation（AI 评测）

在真实 Online Query（在线查询）链路重跑现有 20 个问题，并重点检查：

- C01、C03、C04：现有行为不回归；
- C05：进入多指标路径，不再走静态回退；
- 生成 SQL 通过新 Guard；
- 不使用检索范围之外的表、列或指标；
- 失败案例不访问数据库。

### 15.3 Business Acceptance（业务验收）

对 C05 验收：

- 返回维度是客户类型；
- 返回指标恰好为已完成订单数、人民币净销售额、毛利率；
- 指标顺序正确；
- 所有指标使用同一日期和已完成订单条件；
- SQL 执行值与数据库认证查询一致；
- 证据能够追溯到指标文档、列和关系。

## 16. 实现任务

任务按 Independently Verifiable Behavior（可独立验证的行为）拆分，不按文件、类或函数拆分。每个编码任务必须同时交付边界清楚的可观察结果、成功和失败行为、对应确定性测试、相关回归测试、Diff Review（差异审查）和独立 Commit（提交）。

如果一个任务只能证明“增加了一个字段、类或函数”，却不能证明完整行为正确，则任务过细，必须与它服务的行为合并。这里的“可独立验证”不表示每个任务完成后整个多指标功能都已可交付；它表示该任务承诺的行为已经形成输入、输出、失败和测试闭环。完整用户链路在 T4 闭环，并在 T5 做真实评测和业务验收。

### T1：同版本指标目录基础能力

修改 Qdrant Payload 分页读取、目录校验和 `AssetSnapshot` 缓存。

Done When：目录在真实发布集合和测试替身上都能完整、确定性地加载；不改变当前查询行为。

### T2：确定性多指标请求与规划

实现请求形态预判、指标列表解析、目录映射、顺序/去重/上限、兼容性规划和结构化内部 Contract。

Done When：纯程序测试可以对合法、未知、歧义、重复、超限和不兼容请求给出确定结果；尚不调用 LLM。

### T3：完整在线检索分支

接入一次综合指标召回、逐项覆盖检查、表列合并、关系基数校验、结构化 Context 和证据；实现多指标 Fail Closed。

Done When：多指标检索能成功产出完整 `QueryContext`，任何一路失败都在 LLM 前停止；现有实体和单指标回归通过。

### T4：Prompt、SQL Guard 与 Service 闭环

实现一次 LLM、一次 SQL、公式/过滤/输出完整性校验，并在数据库前拦截所有违规候选。

Done When：合法 SQL 可执行，MM 规格中的所有违规 SQL 都被确定性拒绝，且不存在多指标静态回退。

当前状态：已完成；全量确定性测试、真实评测和业务验收均已完成。

### T5：真实评测与业务验收（已完成）

已重跑 20 个真实问题，完成 C04/C05 数据值核对、证据核对和验收记录。

完成条件已满足：Software Test、AI Evaluation、Business Acceptance 三类证据分别记录，规格状态已更新为已实现且已验收。

## 17. 影响与回滚

### 17.1 影响文件

预计涉及：

- `src/rag_offline/qdrant_store.py`
- `src/online_query/contracts.py`
- `src/online_query/rag_runtime.py`
- `src/online_query/retrieval.py`
- 新增纯规则模块 `src/online_query/multi_metric.py`
- `src/online_query/prompt.py`
- `src/online_query/sql_guard.py`
- `src/online_query/service.py`
- 对应 `tests/online_query/` 测试
- 实现完成后的规格、Runbook 和验收记录

### 17.2 不受影响

- 公共 API Contract；
- PostgreSQL 数据结构和数据；
- 离线指标文档和发布 Manifest；
- 当前已发布 Qdrant Collection；
- 单指标/实体查询的 SQL 允许范围。

### 17.3 回滚

代码回滚即可恢复原有单指标行为，不需要回滚数据库、离线资源或发布指针。实现期间每个 Task 独立验证和提交，不混入权限、多轮对话或经营分析能力。

## 18. 编码前确认点

本设计没有新增业务选择，只把已确认规格转换成可编码方案。以下四点已于 2026-09-10 完成人工确认：

1. V1 只支持“明确列出 2～5 个已登记指标”，不使用 LLM 猜测隐含指标；
2. 多指标请求在资源尚未读取成功时，先用有限句法决定“禁止回退”，避免错误落入静态 Schema；
3. 新 SQL 限制只约束多指标分支，现有单指标和实体查询保持不变；
4. 本次不修改指标库、不重建离线资源，直接消费当前发布版本的完整 METRIC Payload。

按 T1 → T5 编码、测试和验收；任何超出本设计的能力停止扩张。
