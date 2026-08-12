# Natural Language Query Feature Spec

# 自然语言查询功能规格

> **Document（文档）：** `docs/Technical Design/Natural Language Query/FEATURE_SPEC.md`
> **Feature（功能）：** Natural Language Query（自然语言查询）
> **Version（版本）：** V1
> **Status（状态）：** Feature Specification Baseline（功能规格基线）
> **Architecture Reference（架构引用）：** `ARCHITECTURE.md`
> **Feature Spec Standard Reference（功能规格标准引用）：** `../FEATURE_SPEC_STANDARD.md`

# 1. Purpose（目的）

本文档定义 ChatBI Engine（ChatBI 引擎）中 Natural Language Query（自然语言查询，NLQ）的正式 Feature Specification（功能规格）。

本文档定义：

- Feature Goal（功能目标）；
- Responsibility / Boundary（职责 / 边界）；
- Input / Runtime Context（输入 / 运行时上下文）；
- Feature Outcome（功能结果）；
- Supported Capability（支持能力）；
- Business / Behavioral Rule（业务 / 行为规则）；
- Authorization Rule（权限规则）；
- Result Rule（结果规则）；
- Clarification / Failure Rule（澄清 / 失败规则）；
- Unsupported / Deferred Boundary（不支持 / 延后边界）；
- Feature Invariant（功能不变量）。

本文档不定义：

- Module Contract（模块契约）；
- Class / Function（类 / 函数）；
- Pydantic Model（Pydantic 数据模型）；
- Prompt（提示词）；
- SQL Generation Algorithm（SQL 生成算法）；
- SQL AST Library（SQL 抽象语法树库）；
- Retrieval Algorithm（检索算法）；
- Vector Database（向量数据库）实现；
- Test Case（测试用例）；
- Evaluation Dataset（评估数据集）；
- Acceptance Threshold（验收阈值）。

原则：

> **Feature Spec defines required behavior, not implementation.**
> **功能规格定义必须表现出的行为，不定义具体实现方式。**

# 2. Feature Goal & Success（功能目标与成功）

## 2.1 Feature Goal（功能目标）

Natural Language Query（自然语言查询）的目标是：

> **用户通过自然语言表达业务数据查询需求，系统基于受支持的 Business Domain（业务领域）、Authoritative Business Semantics（权威业务语义）、Authoritative Metric（权威指标）和合法 Data Structure（数据结构），在当前 Authorization Scope（授权范围）内完成查询，并返回可信的 QueryResult（查询结果）。**

NLQ（自然语言查询）的核心职责：

> **把业务事实查清楚。**

NLQ（自然语言查询）不负责：

> **解释业务事实为什么发生，以及应该采取什么行动。**

这些属于 Business Analysis（经营分析）。

## 2.2 Feature Success（功能成功）

NLQ（自然语言查询）成功必须同时满足：

1. Intent Correctness（意图正确性）；
2. Semantic Correctness（业务语义正确性）；
3. Query Correctness（查询正确性）；
4. Result Correctness（结果正确性）。

```
User Intent
（用户意图）
        ↓
Correct Semantic Understanding
（正确语义理解）
        ↓
Correct Business Semantics
（正确业务语义）
        ↓
Correct Query
（正确查询）
        ↓
Correct Business Result
（正确业务结果）
```

SQL（结构化查询语言）成功执行：

> **不等于 Feature（功能）成功。**

只有最终业务结果正确：

> 才能产生 QueryResult（查询结果）。

# 3. Responsibility & Boundary（职责与边界）

## 3.1 Responsibility（职责）

NLQ（自然语言查询）负责完整的 Deterministic Business Fact Query（确定性业务事实查询）。

包括：

- Current Query Understanding（当前查询理解）；
- Continuous Follow-up（连续追问）；
- Metric Resolution（指标解析）；
- Dimension Resolution（维度解析）；
- Time Resolution（时间解析）；
- Filter Resolution（筛选解析）；
- Grouping Resolution（分组解析）；
- Sorting / Ranking（排序 / 排名）；
- Comparison（比较）；
- Schema Linking（结构关联）；
- Relationship Resolution（关系解析）；
- SQL Generation（SQL 生成）；
- SQL Validation & Guard（SQL 校验与防护）；
- Authorization Enforcement（权限强制校验）；
- Query Execution（查询执行）；
- Query Result Assembly（查询结果组装）；
- Detail Query（明细查询）；
- Drill-Through（明细下钻）；
- Clarification（澄清）；
- UnsupportedRequest（不支持请求）。

## 3.2 Feature Boundary（功能边界）

NLQ（自然语言查询）回答：

- 是多少；
- 有哪些；
- 哪些最高 / 最低；
- 差多少；
- 增长多少；
- 同比多少；
- 环比多少；
- 哪些业务记录组成这个结果。

核心判断：

> **能够通过确定性查询和确定性计算获得的业务事实，属于 NLQ（自然语言查询）。**

例如：

> “今年比去年销售额少多少？”

属于 NLQ（自然语言查询）。

Business Analysis（经营分析）回答：

- 为什么下降；
- 为什么增长；
- 什么因素导致变化；
- 哪个因素贡献最大；
- 当前经营状态意味着什么；
- 应该采取什么行动。

核心判断：

> **需要 Hypothesis / Diagnosis / Attribution / Reasoning（假设 / 诊断 / 归因 / 推理）的请求，不属于 NLQ（自然语言查询）。**

## 3.3 Internal Query Capability（内部查询能力）

未来 Business Analysis（经营分析）需要业务事实时，应复用 NLQ（自然语言查询）提供的可信 Internal Query Capability（内部查询能力）。

```
Business Analysis
（经营分析）
        ↓
Internal Query Capability
（内部查询能力）
        ↓
Trusted Query Result
（可信查询结果）
        ↓
Diagnosis / Reasoning
（诊断 / 推理）
```

Business Analysis（经营分析）不应重新实现独立的：

- Schema Linking（结构关联）；
- Metric Resolution（指标解析）；
- SQL Generation（SQL 生成）；
- Query Execution（查询执行）。

# 4. Feature Input & Runtime Context（功能输入与运行时上下文）

## 4.1 Business Input（业务输入）

NLQ（自然语言查询）的核心业务输入只有：

> **Current Query（当前查询）。**

Current Query（当前查询）表示：

> 用户当前这一轮明确表达的自然语言业务请求。

# 4.2 Runtime Context（运行时上下文）

Runtime Context（运行时上下文）由 Application Layer（应用层）自动准备，不属于用户业务输入。

概念上包括：

```
Runtime Context
（运行时上下文）

├── Conversation Semantic Context
│   （会话语义上下文）
│
├── Authorization Context
│   （权限上下文）
│
└── Execution Context
    （执行上下文）
```

## 4.2.1 Conversation Semantic Context（会话语义上下文）

表示：

> 前序对话已经确认并仍然有效的 Structured Business Semantic State（结构化业务语义状态）。

可以包含：

- Metric（指标）；
- Dimension（维度）；
- Time（时间）；
- Filter（筛选）；
- Grouping（分组）；
- Sorting（排序）；
- Comparison（比较）；
- Detail Requirement（明细要求）。

默认不使用无限累积的：

> Raw Chat History（原始聊天历史）。

## 4.2.2 Authorization Context（权限上下文）

表示当前 Run（运行）的 Authorized Business Scope（授权业务范围）。

可以约束：

- Domain（领域）；
- Metric（指标）；
- Dimension（维度）；
- Data Scope（数据范围）；
- Row（行）；
- Field（字段）；
- Detail Data（明细数据）。

Authorization Context（权限上下文）由系统建立。

## 4.2.3 Execution Context（执行上下文）

表示当前 Run（运行）所需要的运行环境。

概念上可以包含：

- Run Identity（运行标识）；
- Current Business Date / Time（当前业务日期 / 时间）；
- Business Timezone（业务时区）；
- Locale（本地化信息）；
- Trace Context（链路追踪上下文）。

具体 Typed Schema（类型化结构）不在 Feature Spec（功能规格）定义。

# 5. Feature Outcome（功能结果）

NLQ（自然语言查询）的 Business Outcome（业务结果）只有三类：

```
Feature Outcome
（功能结果）

├── QueryResult
│   （查询结果）
│
├── Clarification
│   （澄清）
│
└── UnsupportedRequest
    （不支持请求）
```

System Failure（系统失败）属于：

> Error Path（错误路径）。

不是 Business Outcome（业务结果）。

Authorization Denied（权限拒绝）属于：

> Authorization / Security Path（权限 / 安全路径）。

不属于 UnsupportedRequest（不支持请求）。

## 5.1 QueryResult（查询结果）

QueryResult（查询结果）表示：

> **用户意图明确、请求属于正式支持范围、权限允许，并且系统成功完成了业务查询。**

因此：

> **QueryResult（查询结果）永远代表成功业务结果。**

它不是：

- Database Response（数据库响应）；
- SQL Response（SQL 响应）；
- API Response（接口响应）；
- UI Model（界面模型）；
- Chart Model（图表模型）。

## 5.2 Clarification（澄清）

Clarification（澄清）表示：

> 用户业务意图本身无法唯一确定，并且这种不确定会影响查询业务含义。

Clarification（澄清）：

> 是正常 Business Outcome（业务结果），不是 System Failure（系统失败）。

## 5.3 UnsupportedRequest（不支持请求）

UnsupportedRequest（不支持请求）表示：

> 用户业务意图明确，但请求超出 NLQ V1（自然语言查询第一版）正式能力边界。

UnsupportedRequest（不支持请求）不是：

- Clarification（澄清）；
- System Failure（系统失败）；
- Authorization Denied（权限拒绝）。

## 5.4 Empty Result（空结果）

查询语义正确、权限正确、执行成功，但没有符合条件的数据：

> 仍然返回 QueryResult（查询结果）。

原则：

> **No Data（无数据） ≠ Failure（失败）。**

# 6. Supported Capabilities（支持能力）

NLQ V1（自然语言查询第一版）正式支持九类核心查询能力。

## 6.1 Metric Query（指标查询）

Supported（支持）：

- Single Metric（单指标）；
- Multiple Metrics（多指标）；
- Metric Alias（指标别名）；
- 自然语言指标表达。

Rules（规则）：

- 所有 Metric（指标）必须绑定 Authoritative Metric Definition（权威指标定义）；
- LLM（大语言模型）不得创建或修改指标；
- LLM（大语言模型）不得创建指标公式；
- 真实 Metric Ambiguity（指标歧义）进入 Clarification（澄清）；
- 明确请求不存在的指标能力进入 UnsupportedRequest（不支持请求）。

## 6.2 Dimension Grouping（维度分组）

Supported（支持）：

- Single Dimension Grouping（单维度分组）；
- Multiple Dimension Grouping（多维度分组）。

Rules（规则）：

- 多维度分组形成组合 Result Grain（结果粒度）；
- 只有正式 Business Dimension（业务维度）可以用于分组；
- Physical Column（物理字段）存在不代表它是 Business Dimension（业务维度）。

## 6.3 Time Query（时间查询）

Supported（支持）：

- Absolute Time（绝对时间）；
- Relative Time（相对时间）；
- Date Range（日期范围）；
- Multiple Time Period（多个时间区间）；
- Year（年）；
- Quarter（季度）；
- Month（月）；
- Day（日）；
- Time Grouping（时间分组）。

Time（时间）必须区分三个语义：

```
Business Time
（业务时间）

Time Filter
（时间筛选）

Time Grouping
（时间分组）
```

Business Time（业务时间）：

> 使用哪个正式业务时间语义。

Time Filter（时间筛选）：

> 查询哪个时间范围。

Time Grouping（时间分组）：

> 按什么时间粒度产生结果。

Relative Time（相对时间）在进入 SQL Generation（SQL 生成）之前：

> 必须解析为确定 Absolute Time Range（绝对时间范围）。

## 6.4 Filter Query（条件筛选）

Supported（支持）：

- Equality Filter（等值筛选）；
- Set Filter（集合筛选）；
- Exclusion Filter（排除筛选）；
- Range Filter（范围筛选）；
- Multiple AND Filter（多个并且条件）；
- Same-Attribute Multi-Value Filter（同属性多值筛选）。

Range Operator（范围操作符）支持：

- `>`；
- `>=`；
- `<`；
- `<=`；
- Between（区间）。

Rules（规则）：

- Filter（筛选）只能作用于正式 Filterable Business Attribute（可筛选业务属性）；
- Physical Column（物理字段）存在不代表可以直接作为 NLQ Filter（自然语言查询筛选条件）；
- V1（第一版）不支持任意 Cross-Dimension OR（跨维度或者条件）。

## 6.5 Aggregate Filter（聚合筛选）

Aggregate Filter（聚合筛选）：

> 作用于 Aggregation（聚合）完成后的业务结果。

支持：

- `>`；
- `>=`；
- `<`；
- `<=`；
- `=`；
- Between（区间）；
- 简单 Multiple AND Aggregate Conditions（多个并且聚合条件）。

必须保持：

```
Filter
（普通筛选）
→ Aggregation Before
  （聚合之前）

Aggregate Filter
（聚合筛选）
→ Aggregation After
  （聚合之后）
```

复杂 Aggregate OR / Arbitrary Boolean Expression（聚合或者条件 / 任意布尔表达式）V1（第一版）不支持。

## 6.6 Sorting / Top N（排序 / 前 N）

Supported（支持）：

- Ascending Sorting（升序排序）；
- Descending Sorting（降序排序）；
- Global Top N（全局前 N）；
- Global Bottom N（全局后 N）；
- Metric-Based Ranking（基于指标排名）。

Top N（前 N）的业务语义：

> **Sorting + Limit（排序 + 数量限制）。**

Ranking Basis（排名依据）必须能够唯一确定。

真实 Ranking Basis Ambiguity（排名依据歧义）：

> Clarification（澄清）。

Per-Group Top N（组内前 N）：

> V1（第一版）Deferred（延后）。

## 6.7 Comparison Query（比较查询）

Supported（支持）：

- Time Period Comparison（时间区间比较）；
- Dimension Value Comparison（维度值比较）；
- Side-by-Side Comparison（并列比较）；
- Difference（差值）；
- Percentage Change（变化率）；
- YoY（同比）；
- MoM（环比）；
- Multiple Simple Comparison Periods（多个简单比较区间）。

Comparison（比较）回答：

> **差多少、变化多少。**

不回答：

> **为什么变化。**

Comparison（比较）不是新的 Metric（指标）。

Comparison Formula（比较公式）必须来自正式规则。

## 6.8 Continuous Follow-up（连续追问）

Supported（支持）：

- Carry-Forward（继承）；
- Replace（替换）；
- Add（追加）；
- Remove（删除）；
- Reset（重置）；
- Current Turn Override（当前轮覆盖）。

基础连续追问使用：

> Conversation Semantic Context（会话语义上下文）。

V1（第一版）不要求：

- 任意历史轮次定位；
- 任意历史 QueryResult（查询结果）单元格引用；
- 无限回溯 Raw Chat History（原始聊天历史）。

## 6.9 Detail Query / Drill-Through（明细查询 / 明细下钻）

NLQ V1（自然语言查询第一版）支持：

### Direct Detail Query（直接明细查询）

返回：

> 正式允许的 Business Detail Record（业务明细记录）。

不是：

> Raw Database Record（数据库原始记录）。

### Drill-Through（明细下钻）

从 Aggregate Result（聚合结果）进入 Supporting Detail（支撑明细）。

Drill-Through（明细下钻）必须继承原结果的：

- Time Scope（时间范围）；
- Business Scope（业务范围）；
- Business Semantics（业务语义）；
- Authorization Scope（授权范围）。

Detail Query（明细查询）必须受到：

- Authorized Detail Field（授权明细字段）；
- Authorization Scope（授权范围）；
- Result Limit（结果限制）；
- Pagination（分页）；
- Sensitive Data Rule（敏感数据规则）

等约束。

具体限制值不在本 Feature Spec（功能规格）定义。

# 7. Semantic Truth Rules（业务语义事实规则）

核心原则：

> **模型可以理解业务语言，但不能定义业务事实。**

NLQ（自然语言查询）的业务事实必须来自 Authoritative Semantic Asset（权威语义资产）。

## 7.1 Metric Truth（指标事实）

Metric（指标）必须来自：

> Authoritative Metric Catalog（权威指标目录）。

LLM（大语言模型）可以：

- 理解；
- 提取；
- 匹配；
- 提出候选。

不能：

- 定义指标；
- 修改指标；
- 创造指标公式。

## 7.2 Dimension Truth（维度事实）

只有正式 Business Dimension（业务维度）可以进入 NLQ（自然语言查询）。

原则：

> **Physical Column（物理字段）存在，不等于 Business Dimension（业务维度）存在。**

## 7.3 Business Time Truth（业务时间事实）

Business Time（业务时间）必须来自：

> Domain Rule（领域规则）。

LLM（大语言模型）不得从多个日期字段中自行选择业务时间。

## 7.4 Relationship Truth（关系事实）

Relationship / Join Relationship（关系 / 连接关系）必须来自：

> Authoritative Metadata（权威元数据）。

不得根据：

- 字段同名；
- 表名相似；
- 模型猜测；

创建新的正式 Relationship（关系）。

## 7.5 Canonical Business Value（标准业务值）

用户自然语言值需要标准化时：

> 必须映射到正式 Canonical Business Value（标准业务值）。

LLM（大语言模型）不得自行猜测数据库编码。

## 7.6 Retrieval Boundary（检索边界）

Retrieval（检索）的职责：

> **Find Candidate（寻找候选）。**

不是：

> **Create Truth（创造事实）。**

```
Retrieval
（检索）
→ Candidate
  （候选）

Authoritative Asset
（权威资产）
→ Truth
  （事实）
```

Vector Index（向量索引）如果保存完整业务定义：

> 必须是 Authoritative Source（权威来源）产生的有效 Runtime Projection（运行时投影）。

# 8. Query Behavior Rules（查询行为规则）

## 8.1 Default Rule（默认规则）

Default（默认值）只能来自：

> Authoritative Domain / Product Rule（权威领域 / 产品规则）。

不能由 LLM（大语言模型）现场创造。

语义优先级：

```
Current Explicit Intent
（当前明确意图）
        >
Conversation Semantic Context
（会话语义上下文）
        >
Authoritative Default
（权威默认规则）
        >
Clarification
（澄清）
```

Default（默认值）：

- 只能补充 Missing Semantic（缺失语义）；
- 不能覆盖 Explicit Semantic（明确语义）；
- 不能覆盖有效 Context（上下文）；
- 不能掩盖 System Failure（系统失败）。

最终语义必须能够区分：

- Explicit（明确）；
- Inherited（继承）；
- Defaulted（默认）。

# 8.2 Context Rule（上下文规则）

Conversation Semantic Context（会话语义上下文）支持：

- Carry-Forward（继承）；
- Replace（替换）；
- Add（追加）；
- Remove（删除）；
- Reset（重置）。

规则：

1. Current Turn（当前轮）明确语义优先；
2. 新值覆盖冲突旧值；
3. 明确新增条件应追加；
4. 明确删除条件必须真正删除；
5. 独立新查询不得被无关历史状态污染；
6. 无法唯一解析的历史指代进入 Clarification（澄清）；
7. 默认继承 Structured Semantic State（结构化语义状态），不是无限 Raw Chat History（原始聊天历史）；
8. Context（上下文）不能改变 Feature Boundary（功能边界）。

# 8.3 Query Semantics Rule（查询语义规则）

Query Intent（查询意图）中的主要语义元素必须保持独立职责：

```
Metric
（指标）

+ Dimension / Grouping
（维度 / 分组）

+ Time
（时间）

+ Filter
（筛选）

+ Aggregate Filter
（聚合筛选）

+ Sorting / Top N
（排序 / 前 N）

+ Comparison
（比较）

+ Detail Requirement
（明细要求）
```

其中：

- Metric（指标）决定 **算什么**；
- Dimension / Grouping（维度 / 分组）决定 **按什么粒度看**；
- Filter（筛选）决定 **聚合前保留哪些业务记录**；
- Aggregate Filter（聚合筛选）决定 **聚合后保留哪些业务结果**；
- Business Time（业务时间）决定 **使用哪种正式业务时间**；
- Time Filter（时间筛选）决定 **查询哪个时间范围**；
- Time Grouping（时间分组）决定 **按什么时间粒度展示**；
- Sorting（排序）只改变结果顺序；
- Top N（前 N）是 Sorting + Limit（排序 + 数量限制）；
- Comparison（比较）是在兼容业务语义之间进行比较，不创建新指标；
- Detail Query（明细查询）必须保持明细语义。

# 8.4 No Silent Change Rule（禁止静默修改规则）

核心原则：

> **可以改变表达形式，不能改变业务含义。**

禁止静默修改：

- Metric（指标）；
- Time（时间）；
- Filter（筛选）；
- Grouping（分组）；
- Ranking Basis（排名依据）；
- Comparison（比较）；
- Business Scope（业务范围）；
- Authorization Scope（授权范围）；
- Detail / Aggregate Mode（明细 / 聚合模式）。

如果某个语义无法正确处理：

> 必须明确失败或澄清，不得删除、替换或弱化该语义后继续成功。

允许的 Semantic Transformation（语义转换）：

- Normalization（标准化）；
- Canonical Mapping（标准映射）；
- Relative Time Resolution（相对时间解析）；
- Authoritative Default（权威默认）；
- 保持原 Semantic Intent（语义意图）不变的 Retry（重试）。

Retry（重试）：

> 可以重新尝试完成同一个业务问题。

不得：

> 修改业务问题以换取执行成功。

# 9. Authorization Rules（权限规则）

核心原则：

> **NLQ（自然语言查询）只能在当前 Authorized Business Scope（授权业务范围）内执行。**

> **Authorization Decision（权限裁决）必须是确定性的。**

LLM（大语言模型）不得进行权限裁决。

## 9.1 Authentication vs Authorization（身份认证与授权）

责任边界：

```
Platform
（平台）
→ Authentication
  （身份认证）

ChatBI
→ Domain Authorization
  （领域授权）
```

## 9.2 Authorization Context（权限上下文）

Authorization Context（权限上下文）：

> 是 Runtime Context（运行时上下文），不是用户业务输入。

Schema Linking（结构关联）和 Metric Resolution（指标解析）等需要在授权范围内完成解析。

## 9.3 Final Authorization Enforcement（最终权限强制校验）

Query Execution（查询执行）之前：

> 必须存在 Deterministic Final Authorization Enforcement（确定性最终权限强制校验）。

原则：

> 前面尽量不产生越权查询，最终执行边界绝不能执行越权查询。

## 9.4 Requested Scope vs Authorized Scope（请求范围与授权范围）

LLM（大语言模型）可以理解：

> Requested Scope（用户请求范围）。

不能决定：

> Authorized Scope（授权范围）。

用户未明确指定范围时：

> 可以在当前 Authorization Scope（授权范围）内查询。

用户明确请求超出权限范围时：

> Authorization Denied（权限拒绝）。

不得进行：

> Silent Narrowing（静默缩窄）。

## 9.5 Aggregate vs Detail Authorization（汇总与明细权限）

Aggregate Authorization（汇总权限）和 Detail Authorization（明细权限）可以不同。

拥有汇总权限：

> 不代表自动拥有底层全部明细权限。

## 9.6 Authorization Does Not Change Metric Meaning（权限不改变指标含义）

权限可以改变：

> Data Scope（数据范围）。

权限不能改变：

> Metric Definition（指标定义）。

同一个 Metric（指标）对不同用户：

> 必须保持同一个正式业务定义。

## 9.7 Defense in Depth（纵深防御）

除 Application Layer（应用层）权限控制外，Data Layer（数据层）应尽可能提供额外安全防护，例如：

- Read-Only Account（只读账号）；
- Restricted View（受限视图）；
- Row-Level Security（行级安全，如需要）。

具体实现不在本 Feature Spec（功能规格）定义。

# 10. Result Rules（结果规则）

## 10.1 QueryResult Means Success（查询结果代表成功）

QueryResult（查询结果）只能表达：

> **成功业务查询。**

失败不得混入 QueryResult（查询结果）。

## 10.2 Empty Result Is Success（空结果也是成功）

查询正确执行但没有数据：

> 仍然属于 QueryResult（查询结果）。

## 10.3 Business Semantics Must Be Preserved（必须保留业务语义）

QueryResult（查询结果）必须能够表达必要的：

- Metric（指标）；
- Time（时间）；
- Dimension / Grain（维度 / 粒度）；
- Unit（单位，如适用）；
- Query Scope（查询范围）。

不能只返回无法解释业务含义的数值。

## 10.4 Business Semantic Identity（业务语义身份）

结果中的业务身份必须与 Physical Field（物理字段）和 Display Label（展示名称）分离：

```
Physical Field
（物理字段）
        ↓
Business Semantic Identity
（业务语义身份）
        ↓
Display Label
（展示名称）
```

Display Label（展示名称）：

> 不作为唯一业务身份。

## 10.5 Result Grain Integrity（结果粒度完整性）

Aggregate Result（聚合结果）的 Result Grain（结果粒度）：

> 必须与 Query Intent（查询意图）一致。

不得静默增加或删除 Grouping Dimension（分组维度）。

## 10.6 Detail Result Integrity（明细结果完整性）

Detail Result（明细结果）必须返回：

> 受控 Business Detail（业务明细）。

不得退化为：

> Raw Database Dump（数据库原始数据倾倒）。

## 10.7 Drill-Through Integrity（明细下钻一致性）

Drill-Through Result（明细下钻结果）必须与原 Aggregate Result（聚合结果）保持一致的：

- Time Scope（时间范围）；
- Business Scope（业务范围）；
- Business Semantics（业务语义）；
- Authorization Scope（授权范围）。

## 10.8 Comparison Result Integrity（比较结果完整性）

Comparison Result（比较结果）根据请求应能够表达必要的：

- Metric（指标）；
- Current Period（当前区间）；
- Comparison Period（比较区间）；
- Difference（差值）；
- Percentage Change（变化率）。

## 10.9 Semantic Provenance（语义来源）

系统应能够区分最终业务语义来源：

- Explicit（用户明确）；
- Inherited（上下文继承）；
- Defaulted（默认补充）。

## 10.10 Presentation Boundary（展示边界）

QueryResult（查询结果）不是：

- Table UI（表格界面）；
- Chart（图表）；
- Dashboard（仪表盘）；
- Markdown Presentation（Markdown 展示）。

Presentation（展示）属于：

> Platform / Presentation Layer（平台 / 展示层）。

# 11. Clarification & Failure Rules（澄清与失败规则）

## 11.1 Clarification Rule（澄清规则）

只有同时满足以下条件才允许 Clarification（澄清）：

1. 用户业务意图无法唯一确定；
2. 缺失或歧义会影响查询正确性；
3. 无法通过有效 Conversation Semantic Context（会话语义上下文）解决；
4. 无法通过正式 Default Rule（默认规则）解决。

典型情况：

- Metric Ambiguity（指标歧义）；
- Ranking Basis Ambiguity（排名依据歧义）；
- Comparison Basis Ambiguity（比较基准歧义）；
- Reference Ambiguity（指代歧义）；
- Missing Required Semantic（必要语义缺失）。

## 11.2 Clarification Boundary（澄清边界）

用户负责澄清：

> Business Intent（业务意图）。

系统负责解决：

> Technical Structure（技术结构）。

不得要求用户提供：

- Table Name（表名）；
- Physical Column（物理字段）；
- Join Relationship（连接关系）；
- 数据库内部编码。

Clarification（澄清）必须只询问：

> **当前阻塞查询的最小必要业务信息。**

## 11.3 System Failure Rule（系统失败规则）

如果：

- 用户意图明确；
- 请求属于正式支持能力；
- 权限允许；
- 但系统没有完成；

则属于：

> **System Failure（系统失败）。**

不是：

- Clarification（澄清）；
- UnsupportedRequest（不支持请求）。

## 11.4 Failure Classification（失败分类）

Feature-Level Failure（功能级失败）可以包括：

- Resolution Failure（解析失败）；
- Generation Failure（生成失败）；
- Validation Failure（校验失败）；
- Authorization Failure（权限处理失败）；
- Dependency Failure（依赖失败）；
- Execution Failure（执行失败）；
- Internal Failure（内部失败）。

具体 Error Code（错误码）由 Module Spec（模块规格）或 Integration Contract（集成契约）定义。

## 11.5 Retry Rule（重试规则）

Retry（重试）可以恢复：

> Execution（执行）。

不得改变：

> Semantic Intent（语义意图）。

## 11.6 Failure Observability（失败可观测）

System Failure（系统失败）必须进入 Observability（可观测）体系。

至少应能够关联：

- Run Identity（运行标识）；
- Failure Stage（失败阶段）；
- Failure Type（失败类型）；
- Duration（耗时）；
- Dependency（依赖）；
- 必要 Error Context（错误上下文）。

不是所有 Failure（失败）都必须进入 Bad Case（失败案例）。

具有：

- 分析价值；
- 可复现价值；
- 回归价值；

的 Failure（失败）进入正式 Bad Case Loop（失败案例闭环）。

# 12. Unsupported / Deferred Boundary（不支持 / 延后边界）

用户意图明确，但请求超出正式能力范围：

> UnsupportedRequest（不支持请求）。

LLM（大语言模型）不得临时扩大 Feature Capability（功能能力）。

## 12.1 Deferred Capability（延后能力）

以下能力仍可能属于未来 NLQ（自然语言查询），但 V1（第一版）暂不实现：

- Complex Cross-Dimension OR / Boolean Expression（复杂跨维度或者 / 布尔表达式）；
- Per-Group Top N（组内前 N）；
- Complex Comparison Matrix（复杂比较矩阵）；
- Complex Historical Reference（复杂历史引用）。

## 12.2 Explicitly Unsupported in V1（第一版明确不支持）

V1（第一版）不支持：

- Ad-Hoc Metric Definition（临时指标定义）；
- Arbitrary Physical Field Query（任意物理字段查询）；
- Undefined Arbitrary Cross-Metric Calculation（未正式定义的任意跨指标运算）；
- Raw Data Dump（原始数据倾倒）。

Metric（指标）、Dimension（维度）、Filterable Attribute（可筛选属性）、Detail Field（明细字段）必须经过正式业务定义后才能进入 NLQ（自然语言查询）。

## 12.3 Out of Scope（范围外）

以下能力原则上不属于 NLQ（自然语言查询）的责任：

### Business Diagnosis（经营诊断）

- Cause Analysis（原因分析）；
- Diagnosis（诊断）；
- Attribution（归因）；
- Driver Analysis（驱动因素分析）。

属于 Business Analysis（经营分析）。

### Recommendation（经营建议）

- Recommendation（建议）；
- Decision Support（决策支持）；
- Action Suggestion（行动建议）。

属于 Business Analysis（经营分析）。

### Automatic Multi-Level Analysis（自动多层分析）

系统自动：

- 下钻；
- 寻找异常；
- 判断驱动因素；
- 自动归因；

属于 Business Analysis（经营分析）。

### Data Write（数据写入）

NLQ V1（自然语言查询第一版）是：

> Read-Only Query Capability（只读查询能力）。

不支持：

- INSERT（插入）；
- UPDATE（更新）；
- DELETE（删除）；
- DDL（数据定义操作）；
- 其他数据库写操作。

### Visualization Rendering（可视化渲染）

NLQ（自然语言查询）产生 QueryResult（查询结果）。

Chart / Dashboard / Layout（图表 / 仪表盘 / 布局）属于 Platform / Presentation Layer（平台 / 展示层）。

### Forecasting / Prediction（预测）

NLQ V1（自然语言查询第一版）不负责：

- Forecasting（预测）；
- Statistical Modeling（统计建模）；
- Machine Learning Prediction（机器学习预测）。

# 13. Feature Invariants（功能不变量）

以下 Invariant（不变量）在任何实现方案下都必须成立。

### Invariant 1

> **Model Proposes, Program Decides（模型提出，程序裁决）。**

LLM（大语言模型）可以提供候选理解和候选查询。

确定性业务规则、安全规则和权限规则必须由程序裁决。

### Invariant 2

> **Domain Owns Business Truth（领域拥有业务事实）。**

Metric（指标）、Dimension（维度）、Business Time（业务时间）、Relationship（关系）和 Business Value（业务值）不得由模型创造。

### Invariant 3

> **Trusted Data Before Analysis（可信数据先于分析）。**

Business Analysis（经营分析）必须建立在可信 QueryResult（查询结果）之上。

### Invariant 4

> **Clarification Is for User Ambiguity（澄清只解决用户歧义）。**

系统内部失败不得推给用户澄清。

### Invariant 5

> **No Silent Degradation（禁止静默降级）。**

系统不得为了获得成功结果而修改用户真实业务意图。

### Invariant 6

> **Authorization Is Deterministic（权限裁决必须确定性）。**

LLM（大语言模型）不得决定权限。

### Invariant 7

> **QueryResult Means Successful Business Result（查询结果代表成功业务结果）。**

System Failure（系统失败）不得混入 QueryResult（查询结果）。

### Invariant 8

> **Empty Is a Valid Result（空结果是合法结果）。**

没有数据不是失败。

### Invariant 9

> **Detail Is Business Detail, Not Raw Database Data（明细是业务明细，不是数据库原始数据）。**

### Invariant 10

> **Feature Boundary Must Be Preserved（必须保持功能边界）。**

NLQ（自然语言查询）负责确定性业务事实查询。

Business Analysis（经营分析）负责解释、诊断、归因和推理。

# 14. Acceptance Boundary（验收边界）

本 Feature Spec（功能规格）定义：

> **NLQ（自然语言查询）必须做到什么。**

如何证明这些规则已经满足，由：

> ```
> ACCEPTANCE_AND_EVALUATION.md
> ```

定义。

具体：

- Test Case（测试用例）；
- Evaluation Case（评估案例）；
- Evaluation Dataset（评估数据集）；
- Metric（评估指标）；
- Acceptance Threshold（验收阈值）；
- Release Gate（发布门禁）

不在本 Feature Spec（功能规格）重复维护。

# 15. Specification Baseline（规格基线）

NLQ V1（自然语言查询第一版）长期保持以下核心关系：

```
Business Input
（业务输入）
└── Current Query
    （当前查询）


Runtime Context
（运行时上下文）
├── Conversation Semantic Context
│   （会话语义上下文）
├── Authorization Context
│   （权限上下文）
└── Execution Context
    （执行上下文）


Supported Capability
（支持能力）
├── Metric Query
│   （指标查询）
├── Dimension Grouping
│   （维度分组）
├── Time Query
│   （时间查询）
├── Filter Query
│   （筛选查询）
├── Aggregate Filter
│   （聚合筛选）
├── Sorting / Top N
│   （排序 / 前 N）
├── Comparison Query
│   （比较查询）
├── Continuous Follow-up
│   （连续追问）
└── Detail Query / Drill-Through
    （明细查询 / 明细下钻）


Business Outcome
（业务结果）
├── QueryResult
│   （查询结果）
├── Clarification
│   （澄清）
└── UnsupportedRequest
    （不支持请求）


Error Path
（错误路径）
└── System Failure
    （系统失败）
```

最终原则：

> **用户负责表达业务问题，系统负责解决技术结构。**

> **模型负责理解和提出候选，程序负责规则与裁决。**

> **业务事实来自权威语义资产，而不是模型猜测。**

> **当前明确语义优先于上下文，上下文优先于正式默认规则。**

> **只有用户真实业务意图存在歧义时才进入澄清。**

> **权限决定用户能看什么，但不能改变业务事实是什么。**

> **可以改变表达形式，不能改变业务含义。**

> **系统设计上能做但没有做成，就是 System Failure（系统失败）。**

> **QueryResult（查询结果）只代表成功业务结果。**

> **NLQ（自然语言查询）负责把事实查清楚，Business Analysis（经营分析）负责解释这些事实为什么发生。**