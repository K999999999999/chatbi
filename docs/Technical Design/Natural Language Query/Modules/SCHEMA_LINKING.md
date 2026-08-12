可以。下面就把刚才已经确认的设计整理成正式的 `SCHEMA_LINKING.md（结构关联模块规格）`。

我会顺手把一个容易出问题的边界写严谨：Schema Linking（结构关联）和 Metric Resolution（指标解析）是逻辑并行的，因此 **Schema Linking（结构关联）不能依赖指标解析结果才能成功**。特别是纯指标查询时，结构锚点可能要等 Generation Context Assembly（生成上下文组装）结合指标上下文后才能最终确定，所以这里不会强行让 Schema Linking（结构关联）猜指标对应的事实结构。



# Schema Linking Module Spec

# 结构关联模块规格

> **Module（模块）：** Schema Linking（结构关联）
> **Feature（功能）：** Natural Language Query（自然语言查询）
> **Version（版本）：** V1
> **Status（状态）：** Design Baseline（设计基线）
> **Feature Architecture Reference（功能架构引用）：** `../ARCHITECTURE.md`
> **Feature Spec Reference（功能规格引用）：** `../FEATURE_SPEC.md`
> **Module Standard Reference（模块标准引用）：** `../../MODULE_CONTRACT_STANDARD.md`

# 1. Responsibility（职责）

Schema Linking（结构关联）负责：

> **将已经明确的 Semantic Query Intent（语义查询意图）映射到当前业务领域中合法、可查询、受权限约束的数据结构，并解析完成查询所需要的正式结构关系。**

核心职责可以概括为：

> **确定“用户已经明确的业务语义，在数据结构中对应什么”。**

它承接 Query Semantic Parser（查询语义解析器）输出的业务语义，但不重新理解或修改用户问题。

## 1.1 Responsible For（负责）

本模块负责：

- Schema Grounding（结构语义映射）；
- Candidate Retrieval（候选召回）；
- Authoritative Resolution（权威解析）；
- Authorization Trimming（权限裁剪）；
- Anchor Selection（锚点选择）；
- Dimension Resolution（维度解析）；
- Time Structure Resolution（时间结构解析）；
- Filter Attribute Resolution（筛选属性解析）；
- Detail Attribute Resolution（明细属性解析）；
- Relationship Resolution（关系解析）；
- Join Resolution（连接解析）；
- Structure Compatibility Validation（结构兼容性校验）；
- Resolution Evidence（解析证据）记录。

## 1.2 Not Responsible For（不负责）

本模块明确不负责：

- Current Query Understanding（当前查询理解）；
- Conversation Context Resolution（会话上下文解析）；
- 修改 Semantic Query Intent（语义查询意图）；
- Authoritative Metric Resolution（权威指标解析）；
- Metric Formula Definition（指标公式定义）；
- SQL Generation（SQL 生成）；
- 具体 SQL Join Expression（SQL 连接表达）生成；
- SQL Validation（SQL 校验）；
- Authorization Context（权限上下文）建立；
- Authentication（身份认证）；
- Database Query Execution（数据库查询执行）；
- 创建新的 Schema Relationship（结构关系）；
- 根据字段名称猜测未定义 Relationship（关系）。

核心边界：

> **Schema Linking（结构关联）发现并选择已有合法结构，不创造数据库事实。**

# 2. Input Contract（输入契约）

本模块统一接收：

```
SchemaLinkingInput
（结构关联输入）

├── semantic_query_intent
│   （语义查询意图）
│
└── authorization_context
    （权限上下文）
```

# 2.1 semantic_query_intent（语义查询意图）

**Required（必需）**

来源：

> Query Semantic Parser（查询语义解析器）。

必须是：

> Resolved SemanticQueryIntent（已完成解析的语义查询意图）。

本模块主要消费其中与数据结构有关的业务语义，例如：

- Dimension Intent（维度意图）；
- Grouping Intent（分组意图）；
- Time Intent（时间意图）；
- Filter Intent（筛选意图）；
- Detail Intent（明细意图）；
- Comparison（比较）中涉及的结构语义；
- Sorting / Top N（排序 / 前 N）中涉及的结构语义。

Semantic Query Intent（语义查询意图）中的 Metric Intent（指标意图）可以作为整体查询上下文存在，但：

> **本模块不得负责将指标表达绑定到正式 Metric Definition（指标定义）。**

该责任属于 Metric Resolution（指标解析）。

# 2.2 authorization_context（权限上下文）

**Required（必需）**

表示：

> 当前 Run（运行）允许访问的数据和业务范围。

概念上可以包含：

- Allowed Domain Scope（允许领域范围）；
- Allowed Dataset Scope（允许数据集范围）；
- Allowed Attribute Scope（允许属性范围）；
- Allowed Detail Scope（允许明细范围）；
- Row / Data Scope（行级 / 数据范围约束）；
- 其他 Domain Authorization（领域权限）约束。

具体 Typed Schema（类型化结构）由后续实现设计确定。

## 2.2.1 Authorization Boundary（权限边界）

Query Semantic Parser（查询语义解析器）负责：

> **用户想查什么。**

Schema Linking（结构关联）开始负责：

> **哪些结构能够合法参与当前查询。**

因此 Authorization Context（权限上下文）必须参与 Schema Linking（结构关联）。

但是：

> **权限只能限制可以访问的结构和数据范围，不允许改变用户业务语义。**

例如：

```
用户请求：
全国销售额

权限：
华东
```

不得解析成：

```
华东销售额
```

如果用户明确请求的业务范围超出权限：

> 应产生 Authorization Violation（权限违规）。

不得进行 Silent Narrowing（静默缩窄）。

# 3. Preconditions（前置条件）

进入 Schema Linking（结构关联）前必须满足以下条件。

## 3.1 Semantic Intent Complete（语义意图完整）

`semantic_query_intent（语义查询意图）` 必须来自：

> Query Semantic Parser（查询语义解析器）的 Resolved（解析完成）结果。

以下结果不得继续进入本模块：

- ClarificationRequired（需要澄清）；
- OutOfScope（超出范围）。

## 3.2 Authorization Context Established（权限上下文已经建立）

Authorization Context（权限上下文）必须在调用本模块前准备完成。

本模块：

> **消费权限上下文，不负责建立用户身份和权限。**

## 3.3 Schema Metadata Available（结构元数据可用）

本模块依赖的正式 Schema Metadata（结构元数据）必须可用。

至少能够表达：

- Table / Dataset Identity（表 / 数据集身份）；
- Column / Attribute Identity（字段 / 属性身份）；
- Business Semantic Mapping（业务语义映射）；
- 数据结构状态；
- 当前结构是否允许参与业务查询。

## 3.4 Relationship Metadata Available（关系元数据可用）

完成多结构查询所需要的 Relationship Metadata（关系元数据）必须存在。

Relationship（关系）必须来源于正式定义。

不得根据：

- 字段同名；
- 字段类型相同；
- 表名相似；
- LLM（大语言模型）推断；

创建未定义的正式 Relationship（关系）。

## 3.5 Retrieval Asset Available When Required（需要检索时检索资产可用）

如果当前解析需要 Semantic Retrieval（语义检索），对应 Retrieval Asset（检索资产）必须是：

- 已构建；
- 当前有效；
- 与权威结构资产一致；
- 可用于 Online Runtime（在线运行）。

# 4. Processing Responsibilities（处理职责）

# 4.1 Schema Grounding（结构语义映射）

本模块首先将业务语义映射到可能的数据结构。

例如：

```
Business Semantic
（业务语义）

“区域”

↓

Schema Candidate
（结构候选）
```

或者：

```
“客户类型”

↓

可能的 Business Attribute
（业务属性）
```

Schema Grounding（结构语义映射）的目标不是立即决定最终结构，而是：

> **建立业务语义与数据结构候选之间的映射关系。**

# 4.2 Candidate Retrieval（候选召回）

当无法通过直接 Machine Identity / Exact Mapping（机器身份 / 精确映射）完成绑定时，本模块可以使用：

> Semantic Retrieval Capability（语义检索能力）

寻找可能的：

- Table Candidate（表候选）；
- Column Candidate（字段候选）；
- Dimension Candidate（维度候选）；
- Filter Attribute Candidate（筛选属性候选）；
- Detail Attribute Candidate（明细属性候选）。

概念链路：

```
Business Semantic
（业务语义）

↓

Semantic Retrieval
（语义检索）

↓

Candidate Set
（候选集合）
```

Retrieval（检索）只负责：

> **提出候选。**

不能直接成为最终业务事实。

原则：

> **Retrieval proposes; authoritative metadata decides.**

即：

> **检索提出候选，权威元数据决定是否合法。**

# 4.3 Authoritative Resolution（权威解析）

所有 Retrieval Candidate（检索候选）必须经过 Authoritative Metadata（权威元数据）确认。

基本过程：

```
Candidate
（候选）

↓

Authoritative Validation
（权威校验）

↓

Resolved Structure
（已解析结构）
```

必须确认：

- 结构真实存在；
- 当前结构有效；
- 业务语义允许映射到该结构；
- 当前结构可以用于对应业务行为；
- 未违反业务或架构规则。

因此：

> **Vector Index（向量索引）不是业务事实源。**

即使 Online Runtime（在线运行）直接从索引 Payload（载荷）读取完整元数据：

> 其中的内容仍然必须是由 Authoritative Source（权威来源）构建并发布的有效 Materialized Asset（物化资产）。

# 4.4 Authorization Trimming（权限裁剪）

经过权威校验后的结构候选还必须应用：

> Authorization Context（权限上下文）。

候选可以分为：

```
合法 + 有权限
→ 可以进入 Resolved Schema Context
合法 + 无权限
→ 不允许进入 Resolved Schema Context
```

但是必须保持：

> **Authorization Trimming（权限裁剪）不能改变用户真实语义。**

如果多个结构候选都表达完全相同业务语义，只是其中部分无权限：

> 可以移除无权候选并继续解析。

如果用户明确请求的业务范围本身越权：

> 必须报告 Authorization Violation（权限违规）。

# 4.5 Dimension Resolution（维度解析）

负责将 Business Dimension Intent（业务维度意图）绑定到正式 Business Dimension（业务维度）及其数据结构。

例如：

```
区域
↓
Business Dimension Identity
（业务维度身份）
↓
Physical Binding
（物理绑定）
```

必须保持三个概念分离：

```
User Expression
（用户表达）

↓

Business Semantic Identity
（业务语义身份）

↓

Physical Binding
（物理结构绑定）
```

例如：

```
“区域”

↓

customer_region
（客户区域业务身份）

↓

dim_customers.region
（物理字段绑定）
```

不能把：

> ```
> dim_customers.region
> ```

直接当成整个系统的 Business Semantic Identity（业务语义身份）。

# 4.6 Time Structure Resolution（时间结构解析）

Query Semantic Parser（查询语义解析器）已经负责解析：

> 用户到底表达了什么时间范围和时间粒度。

Schema Linking（结构关联）继续负责：

> **该 Business Time（业务时间）对应什么正式数据结构。**

例如：

```
Semantic Query Intent
（语义查询意图）

2025 年
+
Business Time = 销售完成时间
```

Schema Linking（结构关联）解析：

```
Business Time Identity
（业务时间身份）

↓

Physical Time Binding
（物理时间字段绑定）
```

原则：

> **Parser（解析器）决定时间语义，Schema Linking（结构关联）决定时间结构。**

# 4.7 Filter Attribute Resolution（筛选属性解析）

Query Semantic Parser（查询语义解析器）可能已经得到：

```
Attribute
（属性）
= 区域

Value
（值）
= 华东
```

Schema Linking（结构关联）负责确定：

```
区域
↓

正式 Filterable Business Attribute
（可筛选业务属性）

↓

Physical Binding
（物理结构绑定）
```

本模块主要解决：

> **Attribute（属性）对应什么结构。**

Canonical Business Value（规范业务值）的业务标准化规则如果属于 Domain Semantic Rule（领域语义规则），则应由对应领域规则提供，而不是在 Schema Linking（结构关联）内部重新定义。

# 4.8 Detail Attribute Resolution（明细属性解析）

Detail Query（明细查询）或 Drill-Through（明细下钻）可能要求：

```
订单编号
客户名称
产品名称
销售时间
```

本模块负责把这些 Business Detail Attribute（业务明细属性）映射到：

> Approved Detail Field（允许的明细字段）。

必须保证：

- 字段属于正式业务明细能力；
- 字段允许当前查询使用；
- 字段满足当前权限要求。

不得因为数据库存在某个字段：

> 就自动允许用户查询。

因此：

> **Physical Column Exists（物理字段存在）不等于 Approved Business Detail Field（允许的业务明细字段）。**

# 4.9 Anchor Selection（锚点选择）

Anchor（锚点）表示：

> 当前结构查询围绕哪个核心事实结构或主要查询结构建立。

例如销售领域可能形成：

```
Sales Fact
（销售事实）

├── Customer Dimension
│   （客户维度）
│
└── Product Dimension
    （产品维度）
```

Anchor Selection（锚点选择）必须依据：

- Business Structure（业务结构）；
- Schema Metadata（结构元数据）；
- Relationship Metadata（关系元数据）；
- 当前需要解析的结构语义。

不得因为：

> 某个 SQL（结构化查询语言）写起来更简单

就随意改变业务锚点。

## 4.9.1 Parallel Resolution Boundary（并行解析边界）

Schema Linking（结构关联）与 Metric Resolution（指标解析）逻辑并行。

因此：

> **Schema Linking（结构关联）不得依赖 Metric Resolution（指标解析）的输出才能完成自身职责。**

对于包含明确 Dimension / Filter / Detail（维度 / 筛选 / 明细）结构语义的查询：

> 可以在本模块确定 Structural Anchor（结构锚点）。

对于纯 Metric Query（纯指标查询），如果仅凭结构语义无法唯一确定最终事实锚点：

> 本模块不得猜测指标所依赖的事实结构。

此时最终查询锚点可以在：

> Generation Context Assembly（生成上下文组装）

结合：

- Resolved Schema Context（已解析结构上下文）；
- Resolved Metric Context（已解析指标上下文）；

后完成最终一致性确认。

原则：

> **并行模块不得通过隐藏依赖破坏架构边界。**

# 4.10 Relationship Resolution（关系解析）

当查询同时涉及多个数据结构时，本模块负责确定：

> 这些结构之间是否存在正式、合法的 Relationship（关系）。

例如：

```
Sales Fact
（销售事实）

↓

Customer Dimension
（客户维度）
```

以及：

```
Sales Fact
（销售事实）

↓

Product Dimension
（产品维度）
```

Relationship（关系）必须来自：

> Authoritative Relationship Metadata（权威关系元数据）。

# 4.11 Join Resolution（连接解析）

本模块负责：

> **决定结构之间通过什么正式 Relationship Path（关系路径）连接。**

但不负责生成具体：

```
JOIN ...
ON ...
```

SQL（结构化查询语言）。

职责边界：

```
Schema Linking
（结构关联）

决定：
A 与 B 可以连接
使用正式 Relationship R1
```

然后：

```
SQL Generation
（SQL 生成）

决定：
如何把 R1 表达成正确 SQL
```

原则：

> **Schema Linking defines legal joins; SQL Generation expresses legal joins.**

即：

> **结构关联决定哪些连接合法，SQL 生成负责把合法连接表达出来。**

# 4.12 Structure Compatibility Validation（结构兼容性校验）

单个结构分别合法：

> 不代表这些结构组合以后仍然合法。

例如：

```
A 合法
B 合法
C 合法
```

仍必须验证：

```
A + B + C
```

是否存在：

- 合法 Relationship Path（关系路径）；
- 合法查询粒度；
- 无冲突的业务结构；
- 当前权限允许的组合。

如果无法形成合法结构：

> 不允许继续产生成功的 Resolved Schema Context（已解析结构上下文）。

# 5. Parallel Relationship with Metric Resolution（与指标解析的并行关系）

Feature Architecture（功能架构）规定：

```
Semantic Query Intent
（语义查询意图）

        ┌────────────────────────┐
        ↓                        ↓

Schema Linking             Metric Resolution
（结构关联）                （指标解析）

        ↓                        ↓

Resolved Schema            Resolved Metric
Context                    Context
（已解析结构上下文）         （已解析指标上下文）

        └──────────┬─────────────┘
                   ↓

Generation Context Assembly
（生成上下文组装）
```

因此：

> **两个模块不得互相直接调用形成隐藏依赖。**

Schema Linking（结构关联）主要负责：

- Dimension Structure（维度结构）；
- Time Structure（时间结构）；
- Filter Attribute Structure（筛选属性结构）；
- Detail Structure（明细结构）；
- Relationship（关系）；
- Structural Connectivity（结构连通）。

Metric Resolution（指标解析）主要负责：

- Authoritative Metric Identity（权威指标身份）；
- Metric Definition（指标定义）；
- Metric Formula（指标公式）；
- Metric Required Structure（指标所需结构）。

最终：

> Generation Context Assembly（生成上下文组装）负责检查两条解析结果是否一致、完整和兼容。

# 6. Output Contract（输出契约）

成功时，本模块输出：

> **ResolvedSchemaContext（已解析结构上下文）**

概念结构：

```
ResolvedSchemaContext
（已解析结构上下文）

├── structural_anchor
│   （结构锚点，可为空）
│
├── resolved_dimensions
│   （已解析维度）
│
├── resolved_time
│   （已解析时间结构）
│
├── resolved_filter_attributes
│   （已解析筛选属性）
│
├── resolved_detail_attributes
│   （已解析明细属性）
│
├── relationship_paths
│   （合法关系路径）
│
└── resolution_evidence
    （解析证据）
```

具体 Pydantic Model（Pydantic 数据模型）由 Implementation（实现）阶段确定，但不得改变上述契约语义。

# 6.1 structural_anchor（结构锚点）

表示：

> 当前结构语义能够确定的主要查询结构。

它不是：

- SQL Alias（SQL 别名）；
- SQL FROM（SQL 来源子句）；
- 用户显示名称。

对于结构信息足够的查询：

> 可以确定正式 Structural Anchor（结构锚点）。

对于纯指标查询，如果必须结合 Metric Definition（指标定义）才能确定：

> 可以为空，由 Generation Context Assembly（生成上下文组装）完成最终一致性处理。

不得为了满足字段必填而猜测 Anchor（锚点）。

# 6.2 resolved_dimensions（已解析维度）

表示已经成功绑定的 Business Dimension（业务维度）。

概念结构：

```
ResolvedDimension
（已解析维度）

├── business_identity
│   （业务身份）
│
├── physical_binding
│   （物理绑定）
│
└── resolution_source
    （解析来源）
```

# 6.3 resolved_time（已解析时间结构）

表示 Business Time（业务时间）到物理结构的正式绑定。

概念上包含：

```
Business Time Identity
（业务时间身份）

Physical Binding
（物理绑定）

Resolution Source
（解析来源）
```

时间范围本身由 Semantic Query Intent（语义查询意图）提供。

# 6.4 resolved_filter_attributes（已解析筛选属性）

表示已经绑定的：

> Filterable Business Attribute（可筛选业务属性）。

概念上包含：

```
Business Attribute Identity
（业务属性身份）

Physical Binding
（物理绑定）

Resolution Source
（解析来源）
```

# 6.5 resolved_detail_attributes（已解析明细属性）

表示经过正式业务规则与权限校验后允许使用的：

> Approved Detail Attribute（允许的明细属性）。

不能包含：

> 任意未批准 Physical Column（物理字段）。

# 6.6 relationship_paths（关系路径）

表示本次查询需要的正式 Relationship Path（关系路径）。

每个 Relationship Path（关系路径）必须能够追溯到：

> Authoritative Relationship Metadata（权威关系元数据）。

不得只返回：

> “系统认为 A 和 B 可以连接。”

必须有稳定 Relationship Identity（关系身份）作为依据。

# 6.7 resolution_evidence（解析证据）

Resolution Evidence（解析证据）用于说明：

> 当前结构为什么被选择。

可以概念上记录：

- Business Semantic Identity（业务语义身份）；
- Authoritative Source（权威来源）；
- Retrieval Evidence（检索证据，如存在）；
- Resolution Method（解析方式）。

主要用于：

- Debugging（调试）；
- Bad Case Analysis（失败案例分析）；
- Evaluation（评估）；
- Traceability（可追溯）。

V1（第一版）不要求建设复杂 Evidence System（证据系统）。

# 7. Postconditions / Invariants（后置条件 / 不变量）

如果本模块成功返回 ResolvedSchemaContext（已解析结构上下文），以下条件必须成立。

## 7.1 Complete Resolution（必要结构解析完整）

当前 Schema Linking（结构关联）职责范围内需要解决的业务结构已经完整解决。

不允许：

> 返回半解析结构继续让 SQL Generation（SQL 生成）猜测。

## 7.2 Authorized Only（仅包含授权结构）

所有进入 Resolved Schema Context（已解析结构上下文）的结构都必须满足当前 Authorization Context（权限上下文）。

## 7.3 Authoritative Only（仅使用权威结构）

所有正式结构绑定都必须来源于当前有效：

- Schema Metadata（结构元数据）；
- Business Semantic Metadata（业务语义元数据）；
- Relationship Metadata（关系元数据）。

Retrieval Similarity（检索相似度）本身不能成为最终合法性依据。

## 7.4 Relationship Valid（关系合法）

所有 Relationship Path（关系路径）必须：

- 正式存在；
- 当前有效；
- 可用于当前查询结构。

## 7.5 Connected Structure（结构连通）

本次查询中需要组合使用的结构必须形成合法连通关系。

## 7.6 No Invented Relationship（禁止创造关系）

任何：

- LLM（大语言模型）；
- Retriever（检索器）；
- SQL Generator（SQL 生成器）；

都不能创造不存在的 Relationship（关系）。

## 7.7 No Metric Redefinition（禁止重新定义指标）

Schema Linking（结构关联）不得承担 Metric Resolution（指标解析）职责。

## 7.8 No Semantic Mutation（禁止修改业务语义）

如果用户明确请求：

```
产品线
```

而系统无法正确解析：

> 不得偷偷替换成“产品类别”。

必须明确失败。

## 7.9 No Silent Authorization Narrowing（禁止静默权限缩窄）

如果用户明确请求的业务范围超出授权：

> 不得偷偷改成授权范围内的查询。

# 8. Failure Contract（失败契约）

# 8.1 Invalid Input（非法输入）

包括：

- Semantic Query Intent（语义查询意图）非法；
- 输入不是 Resolved（解析完成）状态；
- Authorization Context（权限上下文）缺失或非法；
- 必需结构上下文缺失。

# 8.2 Resolution Failure（解析失败）

表示：

> 用户业务语义已经明确、当前能力理论上支持，但本模块没有成功完成正式 Schema Mapping（结构映射）。

例如：

```
用户明确请求：
客户类型
```

系统正式业务结构中存在客户类型，但本次解析失败：

> 属于 Resolution Failure（解析失败）。

这是：

> System Failure / Bad Case（系统失败 / 失败案例）。

不能要求用户提供数据库字段名。

# 8.3 Relationship Failure（关系失败）

表示：

> 需要的结构分别存在，但无法找到满足当前查询的合法 Relationship Path（关系路径）。

此时不得：

- 猜测 Join（连接）；
- 使用字段同名建立关系；
- 让 SQL Generator（SQL 生成器）自行决定。

# 8.4 Authorization Violation（权限违规）

当用户明确业务请求需要访问未经授权的结构或范围：

> 报告 Authorization Violation（权限违规）。

不得：

> Silent Trim（静默裁剪）后返回成功。

最终权限结果由 Feature / Application（功能 / 应用层）统一处理。

# 8.5 Dependency Failure（依赖失败）

例如：

- Schema Metadata Capability（结构元数据能力）不可用；
- Relationship Metadata Capability（关系元数据能力）不可用；
- Semantic Retrieval Capability（语义检索能力）不可用；
- Retrieval Asset（检索资产）损坏；
- 权威元数据版本不可用。

# 8.6 Unsupported（不支持）

例如用户明确要求：

> Arbitrary Physical Field Access（任意物理字段访问）。

而 Feature Spec（功能规格）明确不支持：

> 应报告 Unsupported（不支持）。

# 8.7 Internal Failure（内部失败）

例如：

模块返回：

> ResolvedSchemaContext（已解析结构上下文）。

但结果中：

- Relationship（关系）不连通；
- 出现未授权结构；
- 出现不存在的 Structure Identity（结构身份）；
- 违反其他本模块 Invariant（不变量）。

属于：

> Internal Failure（内部失败）。

# 9. Clarification Boundary（澄清边界）

Schema Linking（结构关联）：

> **原则上不产生用户 Clarification（澄清）。**

因为进入本模块时：

> 用户业务意图已经由 Query Semantic Parser（查询语义解析器）确认明确。

必须区分：

```
User Semantic Ambiguity
（用户语义歧义）

↓

Query Semantic Parser
（查询语义解析器）

↓

Clarification
（澄清）
```

和：

```
Schema Resolution Ambiguity
（结构解析歧义）

↓

Schema Linking
（结构关联）

↓

Resolution / Failure
（解析 / 失败）
```

例如：

用户明确说：

> “区域”

但系统不知道应该映射哪个数据库字段。

不得问用户：

> “你说的是 `dim_customers.region` 还是 `sales.region`？”

原因：

> **用户负责表达业务意图，系统负责解决内部数据结构。**

# 10. Dependencies（依赖）

本模块依赖以下 Capability（能力）。

# 10.1 Semantic Retrieval Capability（语义检索能力）

用于：

> 从 Schema Semantic Assets（结构语义资产）中召回候选结构。

当前 Infrastructure Implementation（基础设施实现）可以使用：

- BGE-M3；
- Qdrant。

但 Module Contract（模块契约）只依赖：

> Semantic Retrieval Capability（语义检索能力）。

不绑定具体技术。

# 10.2 Schema Metadata Capability（结构元数据能力）

负责提供：

- Table Metadata（表元数据）；
- Column Metadata（字段元数据）；
- Dataset Identity（数据集身份）；
- Business Semantic Mapping（业务语义映射）；
- Schema Status（结构状态）。

它是最终结构合法性的重要权威来源。

# 10.3 Relationship Metadata Capability（关系元数据能力）

负责提供正式：

- Physical Relationship（物理关系）；
- Semantic Relationship（语义关系）；
- Relationship Identity（关系身份）；
- 合法连接方向和约束。

所有 Join Resolution（连接解析）必须基于该能力。

# 10.4 Authorization Context（权限上下文）

Authorization Context（权限上下文）通过 Input Contract（输入契约）传入。

本模块原则上：

> **消费已经建立的权限上下文，不在内部重复调用 Authorization Service（权限服务）。**

# 10.5 Explicit Non-Dependencies（明确不依赖）

V1（第一版）本模块不直接依赖：

- Model Capability（模型能力）；
- LLM（大语言模型）；
- Metric Resolution（指标解析）；
- SQL Generation（SQL 生成）；
- Database Query Capability（数据库查询能力）。

# 11. Model Boundary（模型边界）

V1（第一版）Schema Linking（结构关联）不直接依赖 LLM（大语言模型）。

采用：

```
Semantic Retrieval
（语义检索）

+

Authoritative Metadata
（权威元数据）

+

Deterministic Resolution Rules
（确定性解析规则）
```

基本链路：

```
Business Semantic
（业务语义）

↓

Semantic Retrieval
（语义检索）

↓

Candidate
（候选）

↓

Authoritative Validation
（权威校验）

↓

Deterministic Decision
（确定性裁决）

↓

Resolved Structure
（已解析结构）
```

原则：

> **Retrieval Proposes, Program Decides（检索提出，程序裁决）。**

如果后续 Evaluation（评估）证明该方案无法满足质量要求：

> 可以通过 Architecture / Module Contract Change（架构 / 模块契约变更）重新评估是否引入 LLM Reranking / Reasoning（大语言模型重排 / 推理）。

V1（第一版）不提前增加。

# 12. Test / Evaluation（测试 / 评估）

Schema Linking（结构关联）同时包含：

- Deterministic Rule（确定性规则）；
- Semantic Retrieval（语义检索）。

因此采用：

```
TDD
（测试驱动开发）

+

EDD
（评估驱动开发）
```

# 12.1 Deterministic Test（确定性测试）

重点验证：

### Input Contract（输入契约）

- 非法 Semantic Query Intent（语义查询意图）；
- 缺失 Authorization Context（权限上下文）；
- 非 Resolved（解析完成）输入。

### Authorization Rule（权限规则）

- 未授权结构不得进入结果；
- 显式越权不得静默缩窄。

### Relationship Legality（关系合法性）

- 所有 Relationship（关系）必须正式存在；
- 禁止字段同名推断 Join（连接）；
- 禁止不存在的关系路径。

### Structure Connectivity（结构连通）

需要共同使用的结构必须合法连通。

### Output Contract（输出契约）

Resolved Schema Context（已解析结构上下文）必须完整、合法。

### No Silent Semantic Change（禁止静默修改语义）

结构解析失败不能通过替换业务语义获得成功。

### No Invented Relationship（禁止创造关系）

任何未定义 Relationship（关系）必须被拒绝。

# 12.2 Retrieval / Semantic Evaluation（检索 / 语义评估）

主要验证：

### Dimension Mapping（维度映射）

例如：

```
区域
→ 正确正式业务维度
```

### Time Structure Mapping（时间结构映射）

例如：

```
销售完成时间
→ 正确时间结构
```

### Filter Attribute Mapping（筛选属性映射）

例如：

```
客户类型
→ 正确可筛选业务属性
```

### Detail Attribute Mapping（明细属性映射）

例如：

```
订单编号
→ 正确允许明细字段
```

### Relationship Resolution（关系解析）

多结构查询能否找到：

> 正确、合法、完整的 Relationship Path（关系路径）。

# 12.3 Diagnostic Metric（诊断指标）

本模块可以使用：

> Schema Linking Accuracy（结构关联准确率）。

它主要用于：

- 模块质量诊断；
- Bad Case Analysis（失败案例分析）；
- Regression（回归）。

Feature-Level Acceptance（功能级验收）仍然以：

- Semantic Intent Accuracy（语义意图准确率）；
- Query Execution Correctness（查询执行正确率）；
- End-to-End Business Correctness（端到端业务正确率）；

等正式功能指标为最终判断依据。

# 13. Architecture / Contract Decisions（架构 / 契约决定）

当前 V1（第一版）冻结以下决定。

## Decision 1

Schema Linking（结构关联）与 Metric Resolution（指标解析）保持逻辑并行。

> **Schema Linking（结构关联）不得直接依赖 Metric Resolution（指标解析）的输出。**

两者最终在：

> Generation Context Assembly（生成上下文组装）

汇合。

## Decision 2

V1（第一版）Schema Linking（结构关联）不直接依赖 LLM（大语言模型）。

采用：

> Semantic Retrieval + Authoritative Metadata + Deterministic Rules（语义检索 + 权威元数据 + 确定性规则）。

## Decision 3

Join Resolution（连接解析）属于 Schema Linking（结构关联）的责任。

但这里只负责：

> **确定合法 Relationship / Join Path（关系 / 连接路径）。**

不负责：

> 生成具体 SQL Join Expression（SQL 连接表达）。

## Decision 4

Authorization Context（权限上下文）参与 Schema Linking（结构关联）。

但：

> **权限只能约束合法数据结构范围，不能修改用户业务语义。**

## Decision 5

Retrieval Asset（检索资产）可以包含完整、已验证的 Authoritative Metadata Materialization（权威元数据物化副本）。

因此 Online Runtime（在线运行）不要求每次 Retrieval（检索）之后重新读取原始 Catalog（目录）。

但：

> **Authoritative Source（权威来源）仍然是业务事实源，Retrieval Index（检索索引）只是 Derived Runtime Asset（派生运行资产）。**

# 14. Module Invariants Summary（模块不变量总结）

Schema Linking（结构关联）长期必须保持：

> **Business semantics are mapped to structure; they are not rewritten by structure.
> 业务语义映射到结构，而不是被结构反向修改。**

> **Retrieval proposes; authoritative metadata decides.
> 检索提出候选，权威元数据裁决。**

> **Relationships must be authoritative.
> 关系必须来自权威定义。**

> **No Invented Join（禁止创造连接）。**

> **Authorization constrains access, not meaning.
> 权限约束访问范围，不改变业务含义。**

> **Schema Linking defines legal relationships; SQL Generation expresses them.
> 结构关联决定合法关系，SQL 生成负责表达这些关系。**

> **Schema Linking and Metric Resolution remain independently resolvable.
> 结构关联和指标解析保持可独立解析。**

> **No Silent Change（禁止静默修改）。**

# 15. Freeze Status（冻结状态）

当前 Schema Linking（结构关联）的：

- Responsibility（职责）；
- Input Contract（输入契约）；
- Preconditions（前置条件）；
- Processing Responsibilities（处理职责）；
- Output Contract（输出契约）；
- Postconditions / Invariants（后置条件 / 不变量）；
- Failure Contract（失败契约）；
- Dependencies（依赖）；
- Test / Evaluation（测试 / 评估）；
- Model Boundary（模型边界）；
- Parallel Resolution Boundary（并行解析边界）；

已经形成：

> **V1 Design Baseline（第一版设计基线）。**

当前没有阻止该 Module Spec（模块规格）冻结的 Open Question（开放问题）。

因此：

> **Schema Linking Module Spec（结构关联模块规格）可以进入 Freeze（冻结）。**

