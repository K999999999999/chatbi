# Query Semantic Parser Module Spec

# 查询语义解析器模块规格

> **Module（模块）：** Query Semantic Parser（查询语义解析器）
> **Feature（功能）：** Natural Language Query（自然语言查询）
> **Version（版本）：** V1
> **Status（状态）：** Design Baseline（设计基线）
> **Feature Architecture Reference（功能架构引用）：** `../ARCHITECTURE.md`
> **Feature Spec Reference（功能规格引用）：** `../FEATURE_SPEC.md`
> **Module Standard Reference（模块标准引用）：** `../../MODULE_CONTRACT_STANDARD.md`

# 1. Responsibility（职责）

Query Semantic Parser（查询语义解析器）负责：

> **将 Current Query（当前查询）与 Conversation Semantic Context（会话语义上下文）解析为明确、结构化、可供后续模块消费的 Semantic Query Intent（语义查询意图）。**

同时负责识别用户业务意图中的：

- Missing Required Semantics（缺失必要语义）；
- Semantic Ambiguity（语义歧义）；
- Context Reference Ambiguity（上下文引用歧义）；
- Out of NLQ Scope（超出自然语言查询范围）。

核心职责可以概括为：

> **理解“用户想查什么”。**

## 1.1 Responsible For（负责）

本模块负责：

- Current Query Understanding（当前查询理解）；
- Conversation Context Resolution（会话上下文解析）；
- Metric Intent Recognition（指标意图识别）；
- Dimension Intent Recognition（维度意图识别）；
- Time Intent Recognition（时间意图识别）；
- Filter Intent Recognition（筛选意图识别）；
- Grouping Intent Recognition（分组意图识别）；
- Aggregate Filter Intent Recognition（聚合筛选意图识别）；
- Sorting / Top N Intent Recognition（排序 / 前 N 意图识别）；
- Comparison Intent Recognition（比较意图识别）；
- Detail Intent Recognition（明细意图识别）；
- Relative Time Resolution（相对时间解析）；
- Context Carry-Forward（上下文继承）；
- Semantic Default Application（语义默认规则应用）；
- Semantic Provenance Tracking（语义来源记录）；
- User Ambiguity Detection（用户歧义识别）；
- NLQ Scope Recognition（自然语言查询范围识别）。

## 1.2 Not Responsible For（不负责）

本模块明确不负责：

- Schema Linking（结构关联）；
- Table Resolution（表解析）；
- Column Resolution（字段解析）；
- Relationship Resolution（关系解析）；
- Join Resolution（连接解析）；
- Authoritative Metric Resolution（权威指标解析）；
- Metric Formula Definition（指标公式定义）；
- SQL Generation（SQL 生成）；
- SQL Validation（SQL 校验）；
- Authorization Decision（权限裁决）；
- Database Query（数据库查询）；
- Query Result Assembly（查询结果组装）；
- Feature Routing（功能路由）。

核心边界：

> **本模块把用户语言转换成业务语义，不把业务语义直接转换成数据库结构或 SQL（结构化查询语言）。**

# 2. Input Contract（输入契约）

本模块接收统一输入对象：

```
QuerySemanticParseInput
（查询语义解析输入）

├── current_query
│   （当前查询）
│
├── conversation_semantic_context
│   （会话语义上下文）
│
└── time_reference_context
    （时间参考上下文）
```

## 2.1 current_query（当前查询）

**Required（必需）**

类型：

```
string
（字符串）
```

语义：

> 用户当前这一轮提交的原始自然语言业务查询。

要求：

- 必须存在；
- 去除首尾空白后不得为空；
- 保留用户原始业务表达；
- 上游不得提前修改其业务含义。

例如：

```
“2025 年华东销售额是多少？”

“那华南呢？”

“按产品线拆一下。”

“不要华东。”

“销售额最高的 5 个区域。”
```

原则：

> **Current Query（当前查询）是本轮最高优先级的用户语义来源。**

## 2.2 conversation_semantic_context（会话语义上下文）

**Optional（可选）**

类型：

> Structured Semantic Context（结构化语义上下文）。

它表示：

> 上一轮或历史有效查询已经确认的 Business Semantic State（业务语义状态）。

概念上可以包含：

- Metric Semantics（指标语义）；
- Dimension Semantics（维度语义）；
- Time Semantics（时间语义）；
- Filter Semantics（筛选语义）；
- Grouping Semantics（分组语义）；
- Aggregate Filter Semantics（聚合筛选语义）；
- Sorting Semantics（排序语义）；
- Top N Semantics（前 N 语义）；
- Comparison Semantics（比较语义）；
- Detail Semantics（明细语义）。

它不是：

- Raw Conversation History（原始对话历史）；
- SQL（结构化查询语言）；
- Table Name（表名）；
- Physical Column（物理字段）；
- Join Relationship（连接关系）；
- Raw Query Result（原始查询结果）。

原则：

> **连续追问继承结构化业务语义，不默认重新注入完整原始对话历史。**

## 2.3 time_reference_context（时间参考上下文）

**Required（必需）**

用于解析：

- 今天；
- 昨天；
- 今年；
- 去年；
- 本季度；
- 上季度；
- 本月；
- 上个月；
- 最近若干时间区间。

最小概念结构：

```
TimeReferenceContext
（时间参考上下文）

├── reference_datetime
│   （参考日期时间）
│
└── business_timezone
    （业务时区）
```

例如：

```
reference_datetime
= 2026-08-12 15:55

business_timezone
= Asia/Shanghai
```

本模块必须基于该上下文解析 Relative Time（相对时间），不得依赖 LLM（大语言模型）自行猜测当前日期或时区。

## 2.4 Excluded Context（不进入本模块的上下文）

### Authorization Context（权限上下文）

不进入本模块业务输入。

原因：

```
Query Semantic Parser
（查询语义解析器）
= 用户想查什么

Authorization
（权限）
= 用户能查什么
```

权限不能影响用户原始语义解析。

例如：

```
用户请求：全国销售额
用户权限：华东
```

Parser（解析器）仍然必须解析为：

```
全国销售额
```

不得偷偷改成：

```
华东销售额
```

### Execution Context（执行上下文）

以下内容不进入本模块业务契约：

- Run ID（运行编号）；
- Trace ID（链路追踪编号）；
- Timeout（超时）；
- Request Metadata（请求元数据）。

这些属于 Runtime / Observability（运行时 / 可观测）上下文，不属于业务语义解析输入。

# 3. Preconditions（前置条件）

进入本模块前，上游必须保证：

### 3.1 Current Query Valid（当前查询有效）

`current_query（当前查询）`：

- 已完成基础结构校验；
- 非空；
- 类型合法。

### 3.2 Conversation Context Valid（会话上下文有效）

如果存在 `conversation_semantic_context（会话语义上下文）`：

- 必须满足正式结构；
- 必须来源于系统已接受的历史语义状态；
- 不得直接把未经校验的 LLM Output（大语言模型输出）作为可信上下文。

### 3.3 Time Reference Valid（时间参考有效）

`time_reference_context（时间参考上下文）`：

- Reference DateTime（参考日期时间）有效；
- Business Timezone（业务时区）有效。

### 3.4 External Contract Validation Completed（外部契约校验已完成）

External API Boundary（外部接口边界）的基础 Schema Validation（结构校验）已经完成。

本模块不负责重复处理接口层基础格式错误。

### 3.5 No Database Resolution Required（不要求数据库解析已经完成）

进入本模块前：

不要求上游已经知道：

- Metric Code（指标编码）；
- Table（表）；
- Column（字段）；
- Join（连接）；
- SQL（结构化查询语言）。

这些属于后续模块职责。

# 4. Processing Responsibilities（处理职责）

## 4.1 Current Query Understanding（当前查询理解）

从 Current Query（当前查询）识别用户表达的业务查询语义。

包括：

- Metric Intent（指标意图）；
- Dimension Intent（维度意图）；
- Grouping Intent（分组意图）；
- Time Intent（时间意图）；
- Filter Intent（筛选意图）；
- Aggregate Filter Intent（聚合筛选意图）；
- Sorting Intent（排序意图）；
- Top N Intent（前 N 意图）；
- Comparison Intent（比较意图）；
- Detail Intent（明细意图）。

本阶段识别的是：

> Business Mention / Business Intent（业务表达 / 业务意图）。

例如：

```
销售额
```

而不是正式：

```
sales_revenue
```

Formal Metric Binding（正式指标绑定）属于 Metric Resolution（指标解析）。

# 4.2 Context Resolution（上下文解析）

本模块负责将 Current Query（当前查询）与有效历史语义状态合并。

支持：

### Carry-Forward（继承）

当前没有重新说明的有效语义可以继承。

### Replace（替换）

当前明确表达覆盖历史语义。

### Add（增加）

当前查询增加新的业务条件。

### Remove（删除）

当前查询明确移除已有语义。

### Reset（重置）

当前查询已经形成新的独立问题时，不继续继承无关历史语义。

优先级：

```
Current Explicit Semantics
（当前明确语义）

>

Conversation Semantic Context
（会话语义上下文）
```

例如：

```
上一轮：
2025 年华东销售额

当前：
“那华南呢？”

↓

Metric
销售额
→ Inherited（继承）

Time
2025
→ Inherited（继承）

Region
华东 → 华南
→ Replaced（替换）
```

# 4.3 Time Resolution（时间解析）

本模块负责解析用户自然语言中的时间语义。

包括：

### Absolute Time（绝对时间）

例如：

```
2025 年
2025 年第一季度
2025 年 1 月
2025-01-01 到 2025-06-30
```

### Relative Time（相对时间）

例如：

```
今年
去年
这个月
上个月
最近三个月
```

Relative Time（相对时间）必须基于 Time Reference Context（时间参考上下文）转换为明确时间语义。

原则：

> **不能把“去年”“上个月”这种未解析时间继续传递给 SQL Generation（SQL 生成）。**

# 4.4 Semantic Default Application（语义默认规则应用）

如果用户缺少某项语义，而 Feature / Domain（功能 / 领域）已经定义正式 Semantic Default Rule（语义默认规则），本模块可以应用该规则。

优先级：

```
Explicit
（当前明确输入）

>

Inherited
（会话继承）

>

Defaulted
（正式默认规则）

>

Clarification
（必要时澄清）
```

原则：

> **Parser（解析器）消费 Default Rule（默认规则），不创造 Default Rule（默认规则）。**

LLM（大语言模型）不得自行决定：

> “这个用户大概想查这个时间、这个指标、这个范围。”

## Current Dependency Status（当前依赖状态）

当前项目已经存在部分 Sales Domain Rules（销售领域规则），但尚未形成完整正式 Domain Spec（领域规格）。

因此：

> **Domain Semantic Rules（领域语义规则）是本模块的正式依赖，但当前对应的完整领域规格资产仍待补齐。**

该事项不改变本模块责任边界。

# 4.5 Semantic Provenance Tracking（语义来源记录）

最终 Semantic Query Intent（语义查询意图）中的必要业务语义，应能够记录其来源。

标准来源包括：

```
Explicit
（当前明确输入）

Inherited
（上下文继承）

Defaulted
（正式默认规则）
```

例如：

```
Metric
= 销售额
Source
= Explicit


Time
= 2025
Source
= Inherited


Business Time
= 销售完成时间
Source
= Defaulted
```

Semantic Provenance（语义来源）用于：

- Debugging（调试）；
- No Silent Change Verification（禁止静默修改验证）；
- Continuous Follow-up（连续追问）；
- Evidence / Traceability（证据 / 可追溯性）。

# 4.6 Ambiguity / Missing Detection（歧义 / 缺失检测）

本模块负责判断：

> 用户业务意图是否已经足够明确，可以进入后续解析与查询链路。

### Missing Required Semantics（缺少必要语义）

如果某项必要语义：

- 用户没有明确表达；
- 上下文无法继承；
- 正式默认规则无法提供；

并且缺失会改变实际查询含义：

> 报告 Clarification Required（需要澄清）。

### Semantic Ambiguity（语义歧义）

例如：

```
“查一下利润”
```

如果当前业务领域存在：

```
毛利
净利润
经营利润
```

并且无法根据上下文唯一确定：

> 报告 Clarification Required（需要澄清）。

### Reference Ambiguity（引用歧义）

例如：

```
“那第二个呢？”
```

但上下文中无法唯一确定“第二个”具体指什么：

> 报告 Clarification Required（需要澄清）。

## Clarification Boundary（澄清边界）

只有：

> **用户自己的业务意图不明确**

才能请求 Clarification（澄清）。

以下问题不能要求用户澄清：

- Schema Mapping Failure（结构映射失败）；
- Metric Catalog Resolution Failure（指标目录解析失败）；
- Join Resolution Failure（连接解析失败）；
- SQL Generation Failure（SQL 生成失败）；
- External Dependency Failure（外部依赖失败）。

# 4.7 NLQ Scope Recognition（自然语言查询范围识别）

本模块可以识别：

> 当前明确用户意图是否能够表示为 NLQ Semantic Query Intent（自然语言查询语义查询意图）。

例如：

```
“销售额下降多少？”
→ NLQ（自然语言查询）
“销售额为什么下降？”
→ Cause Analysis（原因分析）
→ Out of NLQ Scope（超出自然语言查询范围）
```

本模块只负责识别：

```
OutOfScope
（超出范围）
```

不负责：

```
Route to Business Analysis
（路由到经营分析）
```

Feature Routing（功能路由）属于系统级 Application Capability（应用能力）。

# 5. Output Contract（输出契约）

本模块统一输出：

```
SemanticParseResult
（语义解析结果）
```

合法结果只有三类：

```
SemanticParseResult
（语义解析结果）

├── Resolved
│   （解析完成）
│
├── ClarificationRequired
│   （需要澄清）
│
└── OutOfScope
    （超出自然语言查询范围）
```

# 5.1 Resolved（解析完成）

成功结果包含：

```
SemanticQueryIntent
（语义查询意图）
```

概念结构：

```
SemanticQueryIntent

├── result_mode
│   （结果模式）
│
├── metrics
│   （指标意图）
│
├── groupings
│   （分组意图）
│
├── time
│   （时间意图）
│
├── filters
│   （普通筛选）
│
├── aggregate_filters
│   （聚合筛选）
│
├── sorting
│   （排序）
│
├── top_n
│   （前 N / 后 N）
│
├── comparison
│   （比较）
│
└── detail
    （明细）
```

具体 Pydantic Model（Pydantic 数据模型）和字段实现由 Implementation（实现）阶段确定，但必须保持本契约语义。

## 5.1.1 result_mode（结果模式）

建议使用 Enum（枚举）：

```
aggregate
（聚合）

detail
（明细）
```

用于区分：

> 用户要汇总查询还是业务明细。

## 5.1.2 metrics（指标意图）

表示用户表达的 Metric Intent（指标意图）。

例如：

```
销售额
销量
毛利
```

它不是正式 Metric Definition（指标定义）。

正式指标绑定属于：

> Metric Resolution（指标解析）。

## 5.1.3 groupings（分组意图）

表示用户希望使用的业务分组。

例如：

```
区域
产品线
月份
客户类型
```

## 5.1.4 time（时间意图）

表达：

- Absolute Time Range（绝对时间范围）；
- Time Granularity（时间粒度）；
- Semantic Provenance（语义来源）。

Relative Time（相对时间）在成功输出前必须已经解析。

## 5.1.5 filters（普通筛选）

表示 Pre-Aggregation Filter（聚合前筛选）。

概念结构：

```
FilterIntent
（筛选意图）

├── attribute
│   （业务属性）
│
├── operator
│   （操作符）
│
├── value
│   （业务值）
│
└── source
    （语义来源）
```

Operator（操作符）概念上包括：

```
eq
（等于）

in
（集合）

not_in
（排除）

gt
（大于）

gte
（大于等于）

lt
（小于）

lte
（小于等于）

between
（范围）
```

## 5.1.6 aggregate_filters（聚合筛选）

用于表达 Post-Aggregation Filter（聚合后筛选）。

例如：

```
“销售额超过 100 万的区域”
```

表示：

```
区域
→ Grouping（分组）

销售额 > 100 万
→ Aggregate Filter（聚合筛选）
```

## 5.1.7 sorting（排序）

表达：

- Sorting Target（排序目标）；
- Sorting Direction（排序方向）。

例如：

```
销售额
descending
（降序）
```

## 5.1.8 top_n（前 N / 后 N）

表达：

- N；
- Top / Bottom（前 / 后）；
- Ranking Target（排名依据）。

## 5.1.9 comparison（比较）

表达：

- Comparison Type（比较类型）；
- Comparison Scope（比较范围）；
- Difference Requirement（差值要求）；
- Percentage Change Requirement（变化率要求）。

例如：

- YoY（同比）；
- MoM（环比）；
- 两个时间区间比较；
- 两个维度值比较。

## 5.1.10 detail（明细）

表达：

- Direct Detail Query（直接明细查询）；
- Drill-Through（明细下钻）。

只表达 Business Detail Intent（业务明细意图）。

不得表达：

```
SELECT *
```

或者任意物理数据库字段选择。

# 5.2 ClarificationRequired（需要澄清）

当用户业务意图无法唯一确定时，本模块输出：

```
ClarificationNeed
（澄清需要）

├── reason
│   （原因）
│
├── semantic_target
│   （问题语义位置）
│
└── ambiguity_context
    （歧义上下文，可选）
```

Reason（原因）包括：

```
missing
（缺失）

ambiguous
（歧义）

reference_ambiguous
（引用歧义）
```

本模块：

> **不直接生成最终用户问句。**

它只报告业务语义问题。

Feature（功能）负责最终生成：

> Clarification（澄清结果）。

# 5.3 OutOfScope（超出范围）

当用户明确请求不能表示为 NLQ（自然语言查询）能力时，输出：

```
OutOfScope
（超出范围）
```

可以记录概念原因：

- Cause Analysis（原因分析）；
- Recommendation（推荐）；
- Forecasting（预测）；
- Write Operation（写操作）；
- 其他明确超出 NLQ（自然语言查询）的行为。

最终 Feature（功能）负责决定：

> UnsupportedRequest（不支持请求）或由上层 Router（路由器）进入其他 Feature（功能）。

# 6. Postconditions / Invariants（后置条件 / 不变量）

如果本模块返回 `Resolved（解析完成）`，以下条件必须全部成立。

## 6.1 Intent Completeness（意图完整）

下游继续处理所需要的用户业务语义已经足够明确。

## 6.2 Current Query Priority（当前查询优先）

当前明确用户语义必须覆盖冲突的历史上下文。

## 6.3 Semantic Provenance Traceable（语义来源可追溯）

必要语义能够区分：

```
Explicit
Inherited
Defaulted

（明确 / 继承 / 默认）
```

## 6.4 Relative Time Resolved（相对时间已解析）

例如：

```
去年
上个月
昨天
```

不得以未经解析的自然语言时间直接进入后续 SQL Generation（SQL 生成）。

## 6.5 No Database Structure Decision（不进行数据库结构决策）

本模块不得自行决定：

- Table（表）；
- Physical Column（物理字段）；
- Join（连接）；
- SQL（结构化查询语言）。

## 6.6 No Metric Definition（不定义指标）

本模块可以识别：

```
销售额
```

但不得自行创造：

```
销售额 = SUM(...)
```

## 6.7 No Authorization Decision（不进行权限裁决）

本模块不得根据用户权限：

> 修改用户请求的真实业务语义。

## 6.8 No Silent Change（禁止静默修改）

语义变化只能来自：

- Explicit User Input（用户明确输入）；
- Valid Context（有效上下文）；
- Authoritative Default Rule（权威默认规则）。

不得来自：

> LLM（大语言模型）为了让查询成功进行的未经授权猜测。

# 7. Failure Contract（失败契约）

## 7.1 Invalid Input（非法输入）

例如：

- `current_query（当前查询）` 为空；
- 输入结构非法；
- Conversation Semantic Context（会话语义上下文）结构非法；
- Time Reference Context（时间参考上下文）无效。

## 7.2 Resolution Failure（解析失败）

表示：

> 用户问题本身已经足够明确、当前 Feature（功能）也支持，但本模块没有成功形成合法 Semantic Query Intent（语义查询意图）。

例如：

- LLM Output（大语言模型输出）结构非法；
- 解析结果内部冲突；
- 经过合法处理仍无法形成满足 Output Contract（输出契约）的结果。

这种情况属于：

> System Failure / Bad Case（系统失败 / 失败案例）。

不是：

> Clarification（澄清）。

## 7.3 Dependency Failure（依赖失败）

例如：

- Model Capability（模型能力）不可用；
- Model Capability（模型能力）超时；
- Domain Semantic Rules（领域语义规则）读取失败；
- 外部依赖返回非法结果。

## 7.4 Unsupported（不支持）

用户意图明确，但超出当前 NLQ（自然语言查询）正式能力边界。

由 Feature（功能）转换为：

> UnsupportedRequest（不支持请求）。

## 7.5 Internal Failure（内部失败）

例如：

> 模块报告 `Resolved（解析完成）`，但结果违反本模块 Invariant（不变量）。

属于内部程序错误。

## 7.6 Clarification vs Failure（澄清与失败）

必须保持：

```
用户业务意图真的不明确
↓
ClarificationRequired
（需要澄清）
用户已经说清楚
但系统没有解析成功
↓
Resolution Failure
（解析失败）
```

不得互相替代。

# 8. Dependencies（依赖）

本模块依赖以下 Capability（能力）。

## 8.1 Model Capability（模型能力）

用于：

- Natural Language Understanding（自然语言理解）；
- Semantic Intent Extraction（语义意图提取）；
- Contextual Understanding（上下文理解）；
- Structured Semantic Generation（结构化语义生成）。

Feature / Module（功能 / 模块）依赖：

> Model Capability（模型能力）。

不直接绑定：

- DeepSeek；
- OpenAI；
- LangChain；
- 其他具体 Provider / Framework（供应商 / 框架）。

## 8.2 Domain Semantic Rules（领域语义规则）

用于提供正式：

- Business Time Rule（业务时间规则）；
- Semantic Default Rule（语义默认规则）；
- 其他必须在语义阶段应用的领域规则。

原则：

> **Parser（解析器）消费规则，不定义规则。**

### Current Status（当前状态）

Sales Domain（销售领域）已经存在部分正式业务事实，但完整 Domain Spec（领域规格）尚待补齐。

因此该依赖当前标记为：

> **Pending Formalization（待正式规格化）。**

## 8.3 Explicit Non-Dependencies（明确不依赖）

本模块不直接依赖：

- Authorization Service（权限服务）；
- Schema Retrieval（结构检索）；
- Metric Retrieval（指标检索）；
- Vector Database（向量数据库）；
- Database（数据库）；
- SQL Parser（SQL 解析器）。

Conversation Context Capability（会话上下文能力）也不是本模块直接依赖。

Application Layer（应用层）应在调用模块前准备好：

> Conversation Semantic Context（会话语义上下文）。

# 9. Test / Evaluation（测试 / 评估）

本模块同时存在：

- Deterministic Logic（确定性逻辑）；
- AI / LLM Capability（人工智能 / 大语言模型能力）。

因此采用：

```
TDD
（测试驱动开发）

+

EDD
（评估驱动开发）
```

## 9.1 Deterministic Test（确定性测试）

重点验证：

### Input Contract（输入契约）

- 必需字段；
- 非法输入；
- 时间参考上下文合法性。

### Context Rules（上下文规则）

- Current Query（当前查询）优先；
- Carry-Forward（继承）；
- Replace（替换）；
- Add（增加）；
- Remove（删除）；
- Reset（重置）。

### Time Resolution（时间解析）

- Relative Time（相对时间）解析；
- Business Timezone（业务时区）；
- 边界日期。

### Semantic Provenance（语义来源）

正确标记：

- Explicit（明确）；
- Inherited（继承）；
- Defaulted（默认）。

### Output Contract（输出契约）

只允许：

- Resolved（解析完成）；
- ClarificationRequired（需要澄清）；
- OutOfScope（超出范围）。

### No Silent Change（禁止静默修改）

任何未经允许的业务语义改变都必须失败。

# 9.2 AI Evaluation（人工智能评估）

主要验证：

- Metric Query（指标查询）；
- Dimension Grouping（维度分组）；
- Time Query（时间查询）；
- Filter Query（筛选查询）；
- Sorting / Top N（排序 / 前 N）；
- Aggregate Filter（聚合筛选）；
- Comparison Query（比较查询）；
- Continuous Follow-up（连续追问）；
- Detail / Drill-Through（明细 / 明细下钻）。

重点 Bad Case（失败案例）：

- 指标理解错误；
- 时间理解错误；
- 筛选理解错误；
- 普通 Filter（筛选）与 Aggregate Filter（聚合筛选）混淆；
- Comparison（比较）理解错误；
- 连续追问错误继承；
- 当前输入没有覆盖历史上下文；
- 无歧义却错误要求澄清；
- 真正歧义却擅自猜测；
- NLQ（自然语言查询）范围识别错误。

## 9.3 Primary Evaluation Metrics（主要评估指标）

优先复用 Feature-Level Metric（功能级指标）：

### Semantic Intent Accuracy（语义意图准确率）

衡量 Semantic Query Intent（语义查询意图）是否正确。

### Outcome Accuracy（结果类型准确率）

衡量系统是否正确区分：

- Resolved（解析完成）；
- ClarificationRequired（需要澄清）；
- OutOfScope（超出范围）；
- Failure（失败）。

不为本模块额外制造大量正式指标。

# 10. Architecture / Contract Decisions（架构 / 契约决定）

当前 V1（第一版）冻结以下决定：

### Decision 1

Query Semantic Parser（查询语义解析器）负责 Relative Time Resolution（相对时间解析）。

因此正式输入包含：

> Time Reference Context（时间参考上下文）。

### Decision 2

Query Semantic Parser（查询语义解析器）可以应用正式 Semantic Default Rule（语义默认规则）。

但：

> **只能消费 Feature / Domain（功能 / 领域）定义的规则，不允许自行创造默认规则。**

### Decision 3

Query Semantic Parser（查询语义解析器）可以识别 Out of NLQ Scope（超出自然语言查询范围）。

但：

> **不负责跨 Feature Routing（功能路由）。**

### Decision 4

Authorization Context（权限上下文）不参与用户业务意图解析。

原则：

> **先忠实理解用户想查什么，再由权限系统决定用户能查什么。**

### Decision 5

Conversation Semantic Context（会话语义上下文）使用结构化业务语义状态。

默认不把完整 Raw Conversation History（原始对话历史）作为稳定模块契约。

# 11. Pending Dependency（待补依赖）

当前唯一需要后续补齐的正式设计资产：

> **Sales Domain Spec / Domain Semantic Rules（销售领域规格 / 领域语义规则）。**

至少需要正式提供：

- Business Time Rules（业务时间规则）；
- Semantic Default Rules（语义默认规则）；
- 其他由 Parser（解析器）消费的领域级语义规则。

该事项属于：

> Domain Design（领域设计）。

不在本 Module（模块）内部定义。

# 12. Module Invariants Summary（模块不变量总结）

Query Semantic Parser（查询语义解析器）长期必须保持：

> **Understand user intent, not database structure.
> 理解用户意图，不解析数据库结构。**

> **Current explicit intent overrides historical context.
> 当前明确意图优先于历史上下文。**

> **Relative time must become deterministic time semantics.
> 相对时间必须转换为确定时间语义。**

> **Defaults come from authoritative rules, not model guesses.
> 默认值来自权威规则，而不是模型猜测。**

> **User ambiguity leads to clarification; system failure does not.
> 用户歧义进入澄清，系统失败不得伪装成澄清。**

> **Authorization must not rewrite user intent.
> 权限不得改写用户意图。**

> **No Silent Change（禁止静默修改）。**

> **Model Proposes, Program Decides（模型提出，程序裁决）。**

# 13. Freeze Status（冻结状态）

当前 Query Semantic Parser（查询语义解析器）的：

- Responsibility（职责）；
- Input Contract（输入契约）；
- Preconditions（前置条件）；
- Processing Responsibilities（处理职责）；
- Output Contract（输出契约）；
- Postconditions / Invariants（后置条件 / 不变量）；
- Failure Contract（失败契约）；
- Dependencies（依赖）；
- Test / Evaluation（测试 / 评估）；

已经形成 V1 Design Baseline（第一版设计基线）。

唯一 Pending Item（待办项）：

> **正式补齐 Sales Domain Semantic Rules（销售领域语义规则）。**

在不改变上述模块边界的前提下：

> **Query Semantic Parser Module Spec（查询语义解析器模块规格）可以进入 Freeze（冻结）。**