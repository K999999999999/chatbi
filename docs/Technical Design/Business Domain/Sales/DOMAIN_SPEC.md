# Sales Domain Specification
# 销售领域规格

> **Status（状态）：** Accepted（已接受）
> **Version（版本）：** V1
> **Domain（领域）：** Sales（销售）
> **Document Type（文档类型）：** Domain Specification（领域规格）
> **Source of Truth（事实源）：** Sales Business Truth（销售业务事实）

---

# 1. Purpose（目的）

本文档定义 ChatBI Sales Domain（销售领域）的权威业务语义。

本文档是以下内容的 Business Source of Truth（业务事实源）：

- Business Object（业务对象）；
- Business Process（业务流程）；
- Fact Grain（事实粒度）；
- Valid Sales Fact（有效销售事实）；
- Metric（指标）；
- Dimension（维度）；
- Business Time（业务时间）；
- Currency（币种）；
- Cancellation / Return（取消 / 退货）；
- Historical Comparability（历史可比）；
- Business Invariant（业务不变量）。

稳定关系：

Business Requirement
（业务需求）
        ↓
DOMAIN_SPEC
（领域规格）
        ↓
Analytical Data Model
（分析数据模型）
        ↓
Semantic Layer
（语义层）
        ↓
ChatBI

原则：

> **Business First（业务优先）。**

> **Domain Owns Business Truth（领域拥有业务事实）。**

Database Schema（数据库结构）、Semantic Resource（语义资源）、LLM（大语言模型）、Retrieval（检索）和 SQL 不得反向定义业务事实。

---

# 2. Domain Boundary（领域边界）

## 2.1 In Scope（范围内）

Sales Domain V1 包含：

- Sales Order（销售订单）；
- Sales Order Line（销售订单明细）；
- Customer（客户）；
- Product（产品）；
- Sales Region（销售区域）；
- Customer Region（客户区域）；
- Sales Status（销售状态）；
- Sales Quantity（销量）；
- Sales Revenue（销售额）；
- Sales Cost（销售成本）；
- Gross Profit（毛利）；
- Gross Margin（毛利率）；
- Business Time（业务时间）；
- Currency Conversion（币种换算）；
- Cancellation（取消）；
- Return Semantics（退货语义）；
- Historical Comparison（历史比较）。

## 2.2 Out of Scope（范围外）

V1 不包含：

- Accounts Receivable（应收）；
- Collection（回款）；
- Accounting Revenue Recognition（会计收入确认）；
- Expense（期间费用）；
- Inventory（库存）；
- Procurement（采购）；
- Production（生产）；
- Marketing（市场）；
- Tax Accounting（税务核算）。

这些能力属于独立 Business Domain（业务领域）。

> **Sales Revenue（销售额）不自动等同于 Accounting Revenue（会计收入）。**

---

# 3. Core Business Model（核心业务模型）

## 3.1 Sales Order（销售订单）

Sales Order 表示：

> 一次客户销售交易的订单级业务对象。

一张 Sales Order：

> 可以包含一个或多个 Sales Order Line（销售订单明细）。

关系：

Sales Order
    1
    ↓
    N
Sales Order Line

## 3.2 Sales Order Line（销售订单明细）

Sales Order Line 表示：

> 一个订单中的一个产品销售事实单元。

Sales Domain 的核心 Fact Grain（事实粒度）为：

> **Sales Order Line（销售订单明细）。**

每条销售事实必须能够确定：

- Order（订单）；
- Customer（客户）；
- Product（产品）；
- Quantity（数量）；
- Revenue（销售额）；
- Cost（销售成本）；
- Currency（币种）；
- Business Time（业务时间）；
- Sales Status（销售状态）。

不得因数据连接导致同一 Sales Order Line 重复计算。

---

# 4. Sales Lifecycle（销售生命周期）

V1 使用以下核心业务状态语义：

Created / Pending
（创建 / 待处理）
        ↓
Confirmed
（已确认）
        ↓
Completed
（已完成）

异常终止：

Created / Confirmed
        ↓
Cancelled
（已取消）

销售完成后可以发生：

Completed
        ↓
Return
（退货）

状态语义：

| Status（状态）    | Business Meaning（业务含义） | Normal Sales Metrics（普通销售指标） |
| ----------------- | ---------------------------- | ------------------------------------ |
| Created / Pending | 尚未形成正式销售事实         | 不计入                               |
| Confirmed         | 已确认但尚未完成             | 不计入                               |
| Completed         | 已形成正式销售事实           | 计入                                 |
| Cancelled         | 销售终止                     | 不计入                               |
| Returned          | 已完成销售后的反向业务事件   | 按退货规则处理                       |

因此 V1：

> **Valid Sales Fact = Completed Sales（已完成销售）。**

---

# 5. Business Time（业务时间）

Sales Domain 必须区分：

- Order Date（下单日期）；
- Confirmation Date（确认日期）；
- Completion Date（完成日期）。

V1 默认销售 Business Time（业务时间）：

> **Completion Date（销售完成日期）。**

用户未指定其他时间语义时：

- 年；
- 季度；
- 月；
- 日；

均基于 Completion Date 计算。

Order Date 和 Confirmation Date：

> 可以作为独立业务时间进行分析，但不得与 Completion Date 静默混用。

---

# 6. Metrics（指标）

V1 核心指标：

- Sales Quantity（销量）；
- Sales Revenue（销售额）；
- Sales Cost（销售成本）；
- Gross Profit（毛利）；
- Gross Margin（毛利率）。

所有指标默认：

> 只统计 Valid Sales Fact（有效销售事实）。

即：

> **Completed Sales（已完成销售）。**

---

## 6.1 Sales Quantity（销量）

定义：

> 已完成销售明细的销售数量合计。

业务公式：

Sales Quantity
=
Σ Completed Sales Line Quantity

V1 要求参与聚合的数据具有可比较计量单位。

不得直接聚合不可比较的产品计量单位。

---

## 6.2 Sales Revenue（销售额）

定义：

> 已完成销售产生的不含税净销售金额。

业务公式：

Sales Revenue
=
Σ Net Sales Amount

Sales Revenue：

- 使用 Net Sales Amount（不含税净额）；
- 已包含正式销售折扣影响；
- 不使用含税总额替代；
- 不使用 `Quantity × Unit Price` 替代已有权威净额；
- 不自动等同财务会计收入。

---

## 6.3 Sales Cost（销售成本）

定义：

> 销售事实形成时归属于该销售明细的历史冻结销售成本。

销售成本必须具有 Historical Stability（历史稳定性）。

过去已经形成的 Sales Cost：

> 不得因为当前产品标准成本变化而重新改变。

正式 Sales Cost 应使用：

> **Confirmed / Frozen Sales Cost（确认 / 冻结销售成本）。**

Product Standard Cost（产品标准成本）：

> 可以用于标准成本、预算成本或差异分析，但不得自动替代历史正式销售成本。

---

## 6.4 Gross Profit（毛利）

定义：

Gross Profit
=
Sales Revenue
-
Sales Cost

Sales Revenue 与 Sales Cost 必须保持：

- 相同业务范围；
- 相同 Business Time；
- 相同过滤条件；
- 相同 Currency Basis（币种基础）。

---

## 6.5 Gross Margin（毛利率）

定义：

Gross Margin
=
Gross Profit
/
Sales Revenue

当：

Sales Revenue = 0

则：

Gross Margin = NULL

不得返回：

0%

表示“不可计算”。

---

# 7. Currency Semantics（币种语义）

Sales Domain 允许 Multi-Currency Transaction（多币种交易）。

不同交易币种：

> 不得未经换算直接进行金额聚合。

V1 Analysis Currency（统一分析币种）：

> **CNY（人民币）。**

金额指标进入统一经营分析前必须转换为 CNY。

转换关系：

Transaction Currency
（交易币种）
        ↓
Exchange Rate
（汇率）
        ↓
CNY
（人民币）
        ↓
Sales Metrics
（销售指标）

---

## 7.1 Exchange Rate Date（汇率日期）

V1 汇率日期使用：

> **Completion Date（销售完成日期）。**

即：

Completion Date
+
Transaction Currency
        ↓
Applicable Exchange Rate
（适用汇率）

不得在同一指标中静默混用不同汇率日期规则。

---

# 8. Dimensions（维度）

## 8.1 Time Dimensions（时间维度）

支持：

- Year（年）；
- Quarter（季度）；
- Month（月）；
- Day（日）。

默认基于：

> Completion Date。

---

## 8.2 Customer Dimensions（客户维度）

支持：

- Customer（客户）；
- Customer Type（客户类型）；
- Industry（行业）；
- Country（国家）；
- Customer Region（客户所属区域）。

---

## 8.3 Product Dimensions（产品维度）

支持：

- Product（产品）；
- Product Line（产品线）；
- Product Category（产品类别）；
- Technology Route（技术路线）。

V1：

> 将上述内容定义为独立可分析属性。

V1 不强制定义：

Product Line
→ Category
→ Technology Route
→ Product

这样的严格 Hierarchy（层级）。

正式层级在获得业务依据后单独引入。

---

## 8.4 Region Dimensions（区域维度）

Sales Domain 必须区分：

### Sales Region（销售区域）

表示：

> 销售交易 / 销售组织所属区域。

### Customer Region（客户区域）

表示：

> 客户主体所属区域。

稳定规则：

> **Sales Region ≠ Customer Region。**

不得将两者静默视为同一个业务维度。

---

# 9. Cancellation & Return（取消与退货）

## 9.1 Cancellation（取消）

Cancelled 表示：

> 销售业务未形成最终有效销售事实。

因此：

Cancelled
→ Excluded From Normal Sales Metrics

取消订单不计入：

- Sales Quantity；
- Sales Revenue；
- Sales Cost；
- Gross Profit；
- Gross Margin。

Cancellation 可以作为独立业务事件进行专项分析。

---

## 9.2 Return（退货）

Return 表示：

> 原 Valid Sales Fact 已经成立，之后发生反向业务事件。

稳定规则：

> **Cancellation ≠ Return。**

> **Return 不得删除或覆盖 Original Sale（原销售事实）。**

必须保留：

Original Sale
+
Return Event

V1 暂不冻结具体 Return Metric Treatment（退货指标冲减规则），包括：

- 负销量；
- 收入冲减；
- 成本回冲；
- 毛利调整；
- 原期重述；
- 退货发生期调整。

上述规则：

> **Deferred（延后）。**

在正式引入 Return Analysis（退货分析）前必须新增对应业务规则。

---

# 10. Historical Comparability（历史可比）

跨时间比较必须使用 Comparable Business Semantics（可比业务语义）。

比较双方必须保持一致：

- Valid Sales Rule（有效销售规则）；
- Metric Definition（指标定义）；
- Business Time（业务时间）；
- Currency Rule（币种规则）；
- Cost Rule（成本规则）；
- Dimension Meaning（维度含义）。

业务口径发生重大变化时：

> 必须显式版本化或记录变化。

不得通过修改当前规则：

> 静默改变历史业务事实。

---

# 11. Authorization Semantics（授权语义）

Domain Authorization（领域授权）可以限制：

- Business Domain（业务领域）；
- Metric（指标）；
- Dimension（维度）；
- Customer（客户）；
- Product（产品）；
- Region（区域）；
- Detail Data（明细数据）。

但：

> **Authorization 不得改变 Business Meaning（业务含义）。**

同一 Metric：

> 对不同用户保持相同业务定义。

不同用户仅允许具有不同：

> Authorized Data Scope（授权数据范围）。

---

# 12. Downstream Data Contract（下游数据要求）

Sales Analytical Model（销售分析模型）必须能够表达：

### Business Grain

- Sales Order；
- Sales Order Line；
- Order 1:N Order Line。

### Core Context

- Customer；
- Product；
- Sales Region；
- Customer Region。

### Business Time

- Order Date；
- Confirmation Date；
- Completion Date。

### Sales Fact

- Sales Status；
- Quantity；
- Net Sales Amount；
- Historical Frozen Sales Cost；
- Transaction Currency；
- Applicable Exchange Rate；
- Analysis Currency。

如果现有数据无法满足上述业务事实：

> 记录为 Data Gap（数据缺口）。

不得通过修改 Domain Rule（领域规则）迁就现有数据库。

本文档：

> 不规定 Fact Table（事实表）、Dimension Table（维度表）、Star Schema（星型模型）或 ETL / ELT 的具体实现。

---

# 13. Semantic Layer Contract（语义层要求）

完成 Analytical Data Model（分析数据模型）后，下游 Semantic Layer（语义层）至少应建立：

- Metric Catalog（指标目录）；
- Dimension Metadata（维度元数据）；
- Relationship Metadata（关系元数据）；
- Business Alias（业务别名）；
- Authorization Metadata（授权元数据）。

关系必须保持：

DOMAIN_SPEC
（业务事实）
        ↓
Analytical Data Model
（分析数据模型）
        ↓
Semantic Layer
（语义层）
        ↓
ChatBI Runtime
（ChatBI 运行链路）

Metric Catalog：

> 是领域指标的机器可读表达。

Database Metadata：

> 是当前分析数据模型的机器可读表达。

两者均不得成为：

> Business Truth（业务事实）的上游。

---

# 14. Domain Invariants（领域不变量）

以下规则为 Sales Domain V1 正式业务基线：

1. Sales Order 可以包含多个 Sales Order Line。
2. Sales Order Line 是核心销售事实粒度。
3. Completed 是 V1 唯一普通销售指标有效状态。
4. Confirmed 不进入 V1 普通销售指标。
5. Cancelled 不进入普通销售指标。
6. Default Business Time = Completion Date。
7. Sales Revenue = 不含税净销售额。
8. Sales Revenue 不自动等同会计收入。
9. Sales Cost 使用历史冻结销售成本。
10. 当前产品 Standard Cost 不得重算历史销售成本。
11. Gross Profit = Sales Revenue - Sales Cost。
12. Gross Margin = Gross Profit / Sales Revenue。
13. Sales Revenue = 0 时 Gross Margin = NULL。
14. 多币种金额必须统一转换后才能聚合。
15. V1 Analysis Currency = CNY。
16. V1 Exchange Rate Date = Completion Date。
17. Sales Region ≠ Customer Region。
18. Product Line / Category / Technology Route / Product 在 V1 中不强制组成严格层级。
19. Cancellation ≠ Return。
20. Return 必须保留 Original Sale。
21. V1 暂不定义具体退货冲减规则。
22. Authorization 不得改变业务定义。
23. 历史比较必须使用可比业务口径。
24. 重大业务口径变化必须显式治理。
25. Database / Model / Retrieval / SQL 不得反向定义业务事实。

---

# 15. V1 Domain Baseline（V1 领域基线）

Sales Domain V1：

Sales Order
1:N
Sales Order Line

Fact Grain
=
Sales Order Line

Valid Sales
=
Completed Only

Default Business Time
=
Completion Date

Sales Quantity
=
Completed Sales Quantity

Sales Revenue
=
Net Ex-Tax Sales Amount

Sales Cost
=
Historical Frozen Sales Cost

Gross Profit
=
Revenue - Cost

Gross Margin
=
Gross Profit / Revenue

Revenue = 0
→ Gross Margin = NULL

Analysis Currency
=
CNY

Exchange Rate Date
=
Completion Date

Sales Region
≠
Customer Region

Cancellation
≠
Return

Return
=
Preserve Original Sale

Return Adjustment Rules
=
Deferred