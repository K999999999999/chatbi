```
# Sales Domain（销售业务领域）

> **Status（状态）**：Design Baseline（设计基线）  
> **Scope（范围）**：ChatBI 销售经营领域  
> **Document Type（文档类型）**：Business Domain Specification（业务领域规格）

---

## 1. 领域定位

Sales Domain（销售业务领域）定义 ChatBI 销售经营场景中的统一业务语义。

它为以下产品能力提供业务事实、业务概念和业务规则：

- Natural Language Query（自然语言查询）
- Business Analysis（经营分析）

Sales Domain 负责回答：

- 销售业务中有哪些核心业务对象
- 哪些业务事实是可信的
- 指标分别代表什么
- 可以按照哪些业务维度观察
- 哪些业务规则必须保持一致
- 当前销售领域的业务边界在哪里

Sales Domain 不定义：

- 数据库表和字段如何组织
- 数据之间如何 Join（关联）
- SQL 如何生成
- Retrieval / RAG（检索 / 检索增强）如何实现
- LLM（大语言模型）如何调用
- Workflow / Agent（工作流 / 智能体）如何编排
- AI Platform（AI 平台）如何接入

以上内容属于后续 Architecture（架构）、Feature Spec（功能规格）、Module Spec（模块规格）和 Implementation（实现）。

---

## 2. 业务范围

当前 Sales Domain 描述企业销售经营活动中的以下业务：

- 销售订单
- 客户
- 产品
- 销售数量
- 销售收入
- 销售成本
- 销售毛利
- 销售毛利率
- 销售相关经营维度

Sales Domain 是 ChatBI 当前第一个 Business Domain（业务领域）。

---

## 3. 核心业务对象

### 3.1 Sales Order（销售订单）

Sales Order（销售订单）表示一次销售业务交易。

销售订单是当前销售经营事实的主要载体。

销售订单可以包含：

- 客户
- 产品
- 销售日期
- 销售区域
- 销售状态
- 销售数量
- 销售金额
- 交易币种

---

### 3.2 Customer（客户）

Customer（客户）表示发生销售业务关系的客户主体。

客户可以具有：

- 客户名称
- 客户类型
- 所属行业
- 国家
- 客户所属区域

这些属性可以作为销售经营查询和分析维度。

---

### 3.3 Product（产品）

Product（产品）表示销售活动中的商品或产品。

产品可以具有：

- 产品名称
- 产品线
- 产品类别
- 技术路线
- 产品成本信息

这些属性可以作为销售经营查询和分析维度。

---

### 3.4 Exchange Rate（汇率）

Exchange Rate（汇率）用于处理多币种销售业务中的金额统一。

当销售订单使用不同交易币种时，需要按照规定的汇率口径转换为统一报告币种。

当前 Sales Domain 的统一报告币种为：

> **CNY（人民币）**

---

## 4. 核心业务事实与规则

### 4.1 有效销售

当前正式销售经营指标只统计：

> **已完成的销售订单。**

未完成或已取消的销售订单不计入正式销售指标。

该规则适用于：

- 销量
- 销售额
- 销售成本
- 毛利
- 毛利率

---

### 4.2 销售时间

当前销售经营指标的时间归属统一按照：

> **销售订单日期。**

支持的时间粒度包括：

- 年
- 季度
- 月
- 日

除非具体业务规则另有定义，否则销售相关指标均按照销售订单日期进行时间归属。

---

### 4.3 销售收入

当前销售收入采用：

> **已完成销售订单产生的不含税销售收入。**

销售收入不采用含税销售总额作为当前标准经营口径。

对于外币销售：

> 按照订单日期对应汇率转换为人民币后进行汇总。

因此当前销售额的业务含义为：

> **已完成销售产生的不含税销售收入，并按照订单日期对应汇率统一折算为人民币。**

---

### 4.4 销售成本

当前销售成本采用：

> **已完成销售对应产品的标准成本 × 实际销售数量。**

当前产品标准成本按照人民币口径使用。

---

### 4.5 毛利

当前毛利定义为：

> **销售额 - 销售成本。**

毛利表示销售经营活动自身产生的基础利润。

毛利：

> **不等于企业完整净利润。**

期间费用、税费及其他企业级财务项目不直接包含在当前毛利口径中。

---

### 4.6 毛利率

当前毛利率定义为：

> **毛利 ÷ 销售额。**

当销售额为零时：

> **毛利率不计算。**

不得将销售额为零的情况解释为正常比例指标。

---

### 4.7 多币种

销售业务允许存在不同交易币种。

涉及金额汇总、比较和分析时：

> 必须先按照业务规定的汇率口径转换为统一报告币种。

当前统一报告币种为：

> **CNY（人民币）**

---

### 4.8 区域语义

当前 Sales Domain 中存在两个不同的区域概念：

- Customer Region（客户所属区域）
- Sales Region（销售区域）

两者业务含义不同。

#### Customer Region（客户所属区域）

表示：

> 客户自身所属的业务区域。

#### Sales Region（销售区域）

表示：

> 销售业务发生或归属的销售区域。

必须保持：

```text
Customer Region
≠
Sales Region
```

查询和分析必须根据用户实际业务语义选择正确的区域概念。

不得默认混用。

当无法唯一确定用户指的是哪一种区域时，应进入 Clarification（澄清），而不是自动猜测。

------

## 5. 核心指标

当前 Sales Domain 定义五个核心销售经营指标。

### 5.1 Sales Quantity（销量）

业务含义：

> **已完成销售订单的商品销售数量合计。**

单位：

> 件

------

### 5.2 Sales Revenue（销售额）

业务含义：

> **已完成销售订单产生的不含税销售收入，并按照订单日期对应汇率统一折算为人民币。**

单位：

> CNY（人民币）

------

### 5.3 Sales Cost（销售成本）

业务含义：

> **已完成销售订单对应产品的标准成本 × 实际销售数量。**

当前标准成本按照人民币口径使用。

单位：

> CNY（人民币）

------

### 5.4 Gross Profit（毛利）

业务含义：

> **销售额 - 销售成本。**

单位：

> CNY（人民币）

------

### 5.5 Gross Margin（毛利率）

业务含义：

> **毛利 ÷ 销售额。**

销售额为零时不计算。

单位：

> Percent（百分比）

------

## 6. Metric Catalog（指标目录）

指标的详细机器可读定义统一由：

```
resources/semantic/sales/metrics.json
```

维护。

Metric Catalog（指标目录）负责维护：

- Metric Code（指标编码）
- Metric Name（指标名称）
- Alias（别名）
- Business Definition（业务定义）
- Metric Dependency（指标依赖）
- Calculation Definition（计算定义）
- Filter Rule（过滤规则）
- Time Definition（时间口径）
- Unit（单位）

当前 Sales Domain 定义业务意义。

`metrics.json` 定义指标的机器可读详细规格。

不得在多个位置重复维护同一套指标计算事实。

------

## 7. 核心分析维度

### 7.1 时间

支持：

- 年
- 季度
- 月
- 日

默认按照：

> 销售订单日期

进行时间归属。

------

### 7.2 客户

支持：

- 客户
- 客户类型
- 客户所属行业
- 国家
- Customer Region（客户所属区域）

------

### 7.3 产品

支持：

- 产品
- 产品线
- 产品类别
- 技术路线

------

### 7.4 销售区域

支持：

- Sales Region（销售区域）

Sales Region 与 Customer Region 是两个独立业务维度。

不得默认等价。

------

## 8. 支持的业务问题范围

基于当前 Sales Domain，可以回答：

### 指标查询

例如：

- 某段时间销售额是多少
- 某段时间销量是多少
- 某段时间销售成本是多少
- 某段时间毛利是多少
- 某段时间毛利率是多少

### 维度查询

可以按照：

- 时间
- 客户
- 客户类型
- 行业
- 国家
- 客户所属区域
- 销售区域
- 产品
- 产品线
- 产品类别
- 技术路线

进行查询和比较。

### 经营分析

可以基于当前销售事实进行：

- 趋势分析
- 对比分析
- 维度拆解
- 下钻分析
- 原因验证

例如：

- 2025 年销售额是多少
- 各产品线销售额是多少
- 各客户类型毛利率是多少
- 华东销售区域销售额趋势如何
- 华东客户区域销售额趋势如何
- 哪个产品线毛利下降最多
- 不同客户类型的销售表现有什么差异

------

## 9. 领域边界

当前 Sales Domain 负责：

- 销售订单事实
- 客户销售分析
- 产品销售分析
- 销量
- 销售收入
- 销售成本
- 毛利
- 毛利率
- 与上述销售事实直接相关的经营分析

当前 Sales Domain 不负责完整定义：

- 企业净利润
- 应收账款
- 回款
- 库存
- 采购
- 生产
- 完整财务核算
- 企业预算
- 企业资金管理

如果未来这些业务成为正式 ChatBI 能力：

> 应建立对应 Business Domain（业务领域）或明确 Cross-Domain Analysis（跨领域分析）关系。

不得直接修改 Sales Domain 已经稳定的业务含义来容纳其他领域。

------

## 10. Period Expense Boundary（期间费用边界）

当前数据范围中存在 Period Expense（期间费用），例如：

- 研发费用
- 销售费用
- 管理费用
- 财务费用
- 市场费用
- 物流费用
- 质保费用

这些费用：

> **不属于当前五个 Sales Metric（销售指标）的组成部分。**

因此：

> 当前销售额、销售成本、毛利和毛利率均不直接包含期间费用。

如果未来需要分析：

- 销售利润与期间费用的关系
- 研发费用变化
- 管理费用变化
- 费用对整体利润的影响

应建立：

- Finance Domain（财务领域）

或：

- Cross-Domain Analysis（跨领域分析）

而不是改变当前 Sales Metric 的稳定业务含义。

------

## 11. Domain 与数据实现边界

Sales Domain 定义：

> **Business Meaning（业务含义）。**

例如：

> 销售额 = 已完成销售产生的不含税销售收入，并按照订单日期对应汇率统一折算为人民币。

这是稳定 Business Truth（业务事实）。

至于该指标通过：

- 哪张数据库表
- 哪些数据库字段
- 哪些 Join（关联）
- 哪条 SQL
- 哪种 Semantic Layer（语义层）
- 哪种 Retrieval（检索）
- 哪种数据库产品

实现：

> 不属于 Sales Domain。

必须保持：

```
Business Meaning
（业务含义）
        │
        ▼
Stable
（稳定）


Physical Data Mapping
（物理数据映射）
        │
        ▼
Replaceable
（可演进）
```

数据库结构发生变化：

> 不应该直接改变销售业务本身的含义。

------

## 12. Source of Truth（事实源）

### 12.1 `SALES_DOMAIN.md`

负责维护：

- Sales Domain 范围
- 核心业务对象
- 稳定业务事实
- 业务规则
- 指标业务意义
- 维度业务意义
- 领域边界

------

### 12.2 `resources/semantic/sales/metrics.json`

负责维护：

- Metric Code
- Metric Name
- Alias
- Business Definition
- Metric Dependency
- Calculation Definition
- Filter Rule
- Time Definition
- Unit

------

### 12.3 Schema / Catalog Resources（结构 / 目录资源）

负责维护：

- 数据表
- 数据字段
- 数据类型
- 数据关系
- Physical Schema（物理数据结构）

Sales Domain 不重复维护完整 Physical Schema。

Physical Schema 也不能反向决定业务指标和业务规则。

------

## 13. Domain Invariants（领域不变量）

以下规则必须长期保持：

### 13.1 Business Truth First（业务事实优先）

```
Business Truth
        ↓
Metric / Dimension / Rule
        ↓
Technical Implementation
```

技术实现服务于业务事实。

不得由技术实现反向定义业务事实。

------

### 13.2 Completed Sales Only（只统计已完成销售）

正式销售指标：

> 只统计已完成销售订单。

------

### 13.3 Unified Time Semantics（统一时间语义）

当前销售指标：

> 默认按照销售订单日期归属。

------

### 13.4 Unified Currency（统一报告币种）

金额指标：

> 必须统一转换为人民币后进行汇总和比较。

------

### 13.5 Region Semantics Must Remain Distinct（区域语义必须区分）

```
Customer Region
≠
Sales Region
```

不得默认混用。

------

### 13.6 Gross Profit Is Not Net Profit（毛利不是净利润）

```
Gross Profit
≠
Enterprise Net Profit
```

当前毛利不包含完整期间费用及其他企业财务项目。

------

## 14. Final Definition（最终定义）

Sales Domain 的职责是：

> **定义销售业务到底是什么意思。**

不是：

> 定义程序应该如何实现销售业务。

必须保持：

```
Business Facts
        ↓
Metrics / Dimensions / Rules
        ↓
Stable


Technical Implementation
        ↓
Replaceable
```

ChatBI 的 Natural Language Query（自然语言查询）和 Business Analysis（经营分析）必须在 Sales Domain 定义的业务语义和业务边界内运行。
\```