# Sales Analytical Model
# 销售分析模型

> **Status（状态）：** Accepted（已接受）
> **Version（版本）：** V1
> **Domain（领域）：** Sales（销售）
> **Document Type（文档类型）：** Analytical Model Specification（分析模型规格）
> **Upstream Source of Truth（上游事实源）：** `DOMAIN_SPEC.md`
> **Target（目标）：** Sales Analytical Data Model（销售分析数据模型）

---

# 1. Purpose（目的）

本文档定义 Sales Domain（销售领域）的 Analytical Data Model（分析数据模型）。

本文档负责定义：

- Analytical Grain（分析粒度）；
- Fact Model（事实模型）；
- Dimension Model（维度模型）；
- Star Schema（星型模型）；
- Historical Dimension Strategy（历史维度策略）；
- Historical Fact Strategy（历史事实策略）；
- Business Time Mapping（业务时间映射）；
- Currency / FX Modeling（币种 / 汇率建模）；
- Measure Storage Rule（度量存储规则）；
- Data Lineage Requirements（数据血缘要求）。

本文档不重新定义 Business Truth（业务事实）。

业务含义以：

> `DOMAIN_SPEC.md`

为唯一上游依据。

稳定关系：

DOMAIN_SPEC
（领域规格）
        ↓
ANALYTICAL_MODEL
（分析模型）
        ↓
Physical Schema / DDL
（物理模型 / 建表）
        ↓
ETL / ELT
（数据加工）
        ↓
Semantic Layer
（语义层）
        ↓
ChatBI

---

# 2. Modeling Principles（建模原则）

Sales Analytical Model V1 遵循：

1. Business Grain First（业务粒度优先）。
2. Star Schema First（星型模型优先）。
3. Preserve Historical Truth（保留历史事实）。
4. Atomic Facts First（原子事实优先）。
5. Derived Metrics Stay Semantic（派生指标留在语义层）。
6. Stable History, Replaceable Pipeline（历史稳定，加工链可替换）。
7. Do Not Overbuild（不过度建设）。

---

# 3. Model Overview（模型总览）

V1 核心模型：

```text
                         dim_customer
                              |
                              |
                         customer_key
                              |
                              |
dim_product ─────── fct_sales_order_line ─────── dim_date
                              |
                              |
                       sales_region_key
                              |
                              |
                      dim_sales_region
                              |
                              |
                         dim_currency
```

辅助汇率模型：

```
dim_date
   |
   |
fct_exchange_rate_daily
   |
   |
dim_currency
```

核心表：

- `fct_sales_order_line`
- `dim_customer`
- `dim_product`
- `dim_date`
- `dim_sales_region`
- `dim_currency`
- `fct_exchange_rate_daily`

------

# 4. Core Fact Grain（核心事实粒度）

核心事实表：

> ```
> fct_sales_order_line
> ```

Grain（粒度）：

> **一行 = 一条 Sales Order Line（销售订单明细）。**

稳定关系：

```
Sales Order
    1
    ↓
    N
Sales Order Line
```

每条事实必须唯一对应：

- 一个 Sales Order（销售订单）；
- 一个 Sales Order Line（销售订单明细）；
- 一个 Customer（客户）；
- 一个 Product（产品）；
- 一个销售事实发生上下文。

任何 Join（连接）或数据加工：

> 不得改变或重复该粒度。

------

# 5. Fact Table（事实表）

## 5.1 `fct_sales_order_line`

职责：

> 保存销售订单明细级历史交易事实。

主要包含以下信息。

### Business Identity（业务标识）

- `order_id`
- `order_no`
- `order_line_id`
- `order_line_no`

其中：

> `order_line_id` 或等价业务组合必须唯一识别销售订单明细。

------

### Dimension References（维度引用）

- `customer_key`
- `product_key`
- `sales_region_key`
- `transaction_currency_key`

所有需要保留历史版本的维度：

> 使用 Surrogate Key（代理键）关联。

------

### Business Time References（业务时间引用）

事实表至少保留：

- `order_date_key`
- `confirmation_date_key`
- `completion_date_key`

V1 默认销售 Business Time（业务时间）：

> ```
> completion_date_key
> ```

------

### Sales Status（销售状态）

保存：

- Pending（待处理）；
- Confirmed（已确认）；
- Completed（已完成）；
- Cancelled（已取消）。

V1 普通销售指标：

> 仅基于 Completed（已完成）事实。

------

### Atomic Measures（原子度量）

事实表保存：

- Sales Quantity（销售数量）；
- Transaction Unit Price（原币单位价格）；
- Transaction Discount Amount（原币折扣金额）；
- Transaction Gross Amount（原币总额）；
- Transaction Net Sales Amount（原币净销售额）；
- Applied FX Rate（实际采用汇率）；
- CNY Net Sales Amount（人民币净销售额）；
- Frozen Unit Cost（冻结单位成本）；
- CNY Sales Cost Amount（人民币销售成本）。

------

# 6. Order Modeling（订单建模）

V1：

> **不建立 `dim_order`。**

Order ID / Order No（订单标识 / 订单号）直接保存在：

> ```
> fct_sales_order_line
> ```

作为：

> Degenerate Dimension（退化维度）。

V1 不建立独立 Order Dimension（订单维度）。

当未来订单拥有大量稳定分析属性时：

> 再重新评估 `dim_order`。

------

# 7. Date Dimension（日期维度）

## 7.1 `dim_date`

Grain：

> 一天一行。

至少包含：

- `date_key`
- `full_date`
- `year`
- `quarter`
- `month`
- `day`

V1 不要求提前建设大量日历属性。

------

## 7.2 Role-Playing Date（角色日期）

只建立一张：

> ```
> dim_date
> ```

通过不同 Foreign Key（外键）承担不同时间角色：

```
                   order_date_key
                         |
dim_date ───── confirmation_date_key
                         |
                   completion_date_key
```

对应：

- Order Date（下单日期）；
- Confirmation Date（确认日期）；
- Completion Date（完成日期）。

不得建立三套重复日期维度。

------

# 8. Customer Dimension（客户维度）

## 8.1 `dim_customer`

职责：

> 保存客户业务属性及其历史版本。

主要属性：

- `customer_key`
- `customer_id`
- `customer_name`
- `customer_type`
- `industry`
- `country`
- `customer_region`
- `valid_from`
- `valid_to`
- `is_current`

------

## 8.2 History Strategy（历史策略）

`dim_customer` 使用：

> **SCD Type 2（缓慢变化维度第二型）。**

Customer Business ID（客户业务 ID）保持不变。

客户属性发生需要保留历史的变化时：

> 新增 Dimension Version（维度版本），不得覆盖旧版本。

事实表必须关联：

> 销售发生时有效的 `customer_key`。

------

# 9. Product Dimension（产品维度）

## 9.1 `dim_product`

职责：

> 保存产品业务属性及其历史版本。

主要属性：

- `product_key`
- `product_id`
- `product_name`
- `product_line`
- `product_category`
- `technology_route`
- `valid_from`
- `valid_to`
- `is_current`

V1 中：

- Product（产品）；
- Product Line（产品线）；
- Product Category（产品类别）；
- Technology Route（技术路线）

均作为独立可分析属性。

V1 不强制建立严格层级。

------

## 9.2 History Strategy（历史策略）

`dim_product` 使用：

> **SCD Type 2（缓慢变化维度第二型）。**

产品分类等历史属性发生变化时：

> 新建版本，不覆盖历史版本。

事实表关联：

> 销售发生时有效的 `product_key`。

------

# 10. Product Cost Boundary（产品成本边界）

Product Standard Cost（产品标准成本）：

> 不作为历史正式 Sales Cost（销售成本）的动态计算来源。

正式 Sales Cost：

> 必须冻结在 `fct_sales_order_line`。

因此：

```
Product Standard Cost
（产品标准成本）
        ≠
Historical Sales Cost
（历史销售成本）
```

如果未来需要：

- Standard Cost Trend（标准成本趋势）；
- Material Cost（材料成本）；
- Labor Cost（人工成本）；
- Actual vs Standard Cost（实际成本与标准成本比较）；

应单独设计 Cost History Model（成本历史模型）。

V1 不提前建设。

------

# 11. Sales Region Dimension（销售区域维度）

## 11.1 `dim_sales_region`

职责：

> 表达 Sales Region（销售区域）。

主要属性：

- `sales_region_key`
- `sales_region_code`
- `sales_region_name`

Sales Region：

> 独立于 Customer Region（客户所属区域）。

稳定规则：

```
Sales Region
≠
Customer Region
```

Customer Region：

> 保存在 `dim_customer`。

Sales Region：

> 使用独立 `dim_sales_region`。

------

# 12. Currency Dimension（币种维度）

## 12.1 `dim_currency`

职责：

> 表达交易币种。

主要属性：

- `currency_key`
- `currency_code`
- `currency_name`
- `is_analysis_currency`

V1 Analysis Currency（统一分析币种）：

> **CNY（人民币）。**

每日汇率：

> 不存放在 `dim_currency`。

------

# 13. Exchange Rate Fact（汇率事实）

## 13.1 `fct_exchange_rate_daily`

Grain：

> **一个日期 + 一个币种 = 一条汇率事实。**

主要内容：

- `rate_date_key`
- `currency_key`
- `rate_to_cny`

用途：

- 汇率来源；
- ETL / ELT 换算；
- 数据校验；
- 历史重算；
- 数据审计。

------

# 14. FX Freeze Strategy（汇率冻结策略）

V1 汇率日期：

> Completion Date（销售完成日期）。

销售事实生成时：

```
Completion Date
+
Transaction Currency
        ↓
Daily FX Rate
        ↓
Applied FX Rate
        ↓
CNY Sales Amount
```

`fct_sales_order_line` 必须保存：

- 实际采用的 `fx_rate_to_cny`；
- 转换后的 CNY 金额。

因此：

> ChatBI 在线查询不要求再次 Join 每日汇率表才能计算正式销售额。

`fct_exchange_rate_daily`：

> 是参考、加工、审计和重算来源。

`fct_sales_order_line.fx_rate_to_cny`：

> 是该销售事实实际采用的冻结汇率。

------

# 15. Revenue Modeling（销售额建模）

销售事实同时保留：

### Transaction Currency Fact（原币事实）

- Transaction Currency（交易币种）；
- Net Sales Amount Transaction（原币净销售额）。

### Analysis Currency Fact（分析币种事实）

- Applied FX Rate（采用汇率）；
- Net Sales Amount CNY（人民币净销售额）。

正式 V1 Sales Revenue（销售额）：

> 基于 `net_sales_amount_cny` 聚合。

不得在 ChatBI 查询阶段重新定义汇率口径。

------

# 16. Sales Cost Modeling（销售成本建模）

正式销售成本属于：

> Transaction Fact（交易事实）。

必须直接保存在：

> ```
> fct_sales_order_line
> ```

至少表达：

- Frozen Unit Cost CNY（冻结单位成本）；
- Sales Cost Amount CNY（销售成本金额）。

销售成本一旦随销售事实成立：

> 不得因为 Product Dimension（产品维度）中的当前成本变化而重新计算。

------

# 17. Historical Strategy（历史策略）

V1 区分三类历史。

## 17.1 Dimension History（维度历史）

例如：

- Customer Region；
- Customer Type；
- Product Line；
- Product Category。

处理：

> SCD Type 2。

------

## 17.2 Transaction Fact History（交易事实历史）

例如：

- Quantity；
- Revenue；
- Sales Cost；
- Applied FX Rate。

处理：

> 直接冻结在 Fact Table（事实表）。

------

## 17.3 Reference History（参考数据历史）

例如：

- Daily Exchange Rate（每日汇率）。

处理：

> 独立历史事实表。

不得混用三种历史策略。

------

# 18. Measure Storage Rule（度量存储规则）

事实表优先保存：

> Atomic Measure（原子度量）。

V1 物理保存：

- Quantity；
- Revenue；
- Cost；
- Applied FX Rate。

V1 不物理保存：

- Gross Profit（毛利）；
- Gross Margin（毛利率）。

------

# 19. Derived Metrics（派生指标）

Gross Profit：

```
Gross Profit
=
SUM(Net Sales Amount CNY)
-
SUM(Sales Cost Amount CNY)
```

Gross Margin：

```
Gross Margin
=
Gross Profit
/
Sales Revenue
```

Sales Revenue = 0 时：

```
Gross Margin = NULL
```

Gross Margin：

> 不得通过 `AVG(Line Gross Margin)` 计算。

Derived Metric（派生指标）：

> 由 Semantic Layer（语义层）负责定义和计算。

------

# 20. Status Rule（状态规则）

`fct_sales_order_line` 可以保存不同业务状态。

但普通销售指标必须统一应用：

```
order_status = completed
```

Confirmed（已确认）：

> 不进入 V1 普通销售指标。

Cancelled（已取消）：

> 不进入普通销售指标。

Return（退货）：

> V1 不建立正式退货事实模型。

------

# 21. Return Boundary（退货边界）

DOMAIN_SPEC 已规定：

```
Cancellation
≠
Return
```

以及：

> Original Sale（原销售事实）必须保留。

由于 V1 Return Metric Treatment（退货指标处理）尚未冻结：

> V1 不建立 `fct_sales_return_line`。

在退货业务规则正式确认前：

> 不得自行设计负销售额、负销量、成本回冲或原期重述逻辑。

------

# 22. Lineage & Audit（血缘与审计）

核心事实和需要追溯的维度至少能够记录：

- `source_system`
- `source_updated_at`
- `loaded_at`

目标：

> 能够确定分析记录来源及进入 Sales Mart（销售数据集市）的时间。

V1 不要求建设独立 Enterprise Data Lineage Platform（企业数据血缘平台）。

------

# 23. Data Quality Constraints（数据质量约束）

分析模型至少满足：

## Grain Integrity（粒度完整性）

同一 Sales Order Line：

> 不得重复存在为多个事实。

## Dimension Integrity（维度完整性）

正式销售事实必须能够关联：

- Customer；
- Product；
- Business Time。

## Completed Fact Completeness（完成事实完整性）

Completed 销售至少必须具备：

- Completion Date；
- Quantity；
- Net Sales Amount；
- Sales Cost；
- Transaction Currency；
- Applicable FX Rate；
- CNY Revenue。

## Currency Integrity（币种完整性）

不同币种：

> 不得未经统一换算直接聚合。

## Historical Integrity（历史完整性）

已经形成的历史销售事实：

> 不得因当前维度属性、成本或汇率变化被静默重写。

------

# 24. Physical Model Boundary（物理模型边界）

本文档冻结：

- 表职责；
- Grain（粒度）；
- 维度关系；
- 历史策略；
- Measure Strategy（度量策略）；
- 数据模型边界。

本文档不冻结：

- PostgreSQL 精确数据类型；
- Index（索引）；
- Check Constraint（检查约束）；
- Foreign Key 名称；
- Sequence / Identity（序列 / 自增键）；
- Partition（分区）；
- Storage Parameter（存储参数）。

这些属于：

> Physical Schema / DDL（物理模型 / 建表实现）。

------

# 25. V1 Non-Goals（V1 非目标）

V1 不建设：

- `dim_order`
- `dim_order_status`
- `fct_sales_return_line`
- Daily Aggregate Fact（每日聚合事实表）
- Monthly Aggregate Fact（月度聚合事实表）
- Materialized Metric Table（物化指标表）
- Product Cost History Model（产品成本历史模型）
- Inventory Fact（库存事实）
- Receivable Fact（应收事实）
- Expense Fact（费用事实）
- Procurement Fact（采购事实）

没有真实需求时：

> 不提前建设。

------

# 26. Downstream Semantic Contract（下游语义契约）

完成 Physical Schema（物理模型）和数据加工后，Semantic Layer（语义层）使用四类机器可读资产：

- `tables.json`：Table Metadata（表元数据）与 Table Retrieval（表检索）；
- `columns.json`：Column Metadata（字段元数据）与 Column / Field Retrieval（字段检索）；
- `metrics.json`：Metric Catalog（指标目录）与 Metric Retrieval（指标检索）；
- `relationships.json`：Relationship Metadata（关系元数据）与确定性 Relationship Catalog → Graph → Join Resolution（关系目录 → 关系图 → 连接解析）。

Customer、Product、Time、Region 等 Dimension（维度）继续由本 Analytical Model 和上游 DOMAIN_SPEC 定义；不建立独立 Dimension Metadata、Dimension Catalog、`dimensions.json` 或 Dimension Retrieval。维度语义通过现有 Column Metadata 的名称与描述供 Schema Linking（结构关联）执行 Field Matching（字段匹配）。

Metric Alias（指标别名）继续保留在 metrics.json。业务 Dimension 的中文名称、别名和字段角色由 Schema Linking 的 Field Matching 处理；Table / Column Retrieval 仍只使用现有 Column name + description，不新增独立 Alias Resource（别名资源）或 Retrieval Object（检索对象）。Authorization Metadata（授权元数据）属于独立的访问控制边界，不属于 Offline Retrieval Asset（离线检索资产）。

Relationship 不进入 Retrieval Record、Embedding 或 Vector Index，只作为确定性 Relationship Catalog → Relationship Graph → Join Resolution 的输入。

`metrics.json` 只能表达本 DOMAIN_SPEC 与本 Analytical Model 已冻结的指标定义、公式、依赖、过滤、时间和物理映射，不得自行扩展业务口径。

核心指标映射目标：

| Metric（指标）          | Analytical Fact（分析事实） |
| ----------------------- | --------------------------- |
| Sales Quantity（销量）  | `fct_sales_order_line.quantity` |
| Sales Revenue（销售额） | `fct_sales_order_line.net_sales_amount_cny` |
| Sales Cost（销售成本）  | `fct_sales_order_line.sales_cost_amount_cny` |
| Gross Profit（毛利）    | Sales Revenue - Sales Cost |
| Gross Margin（毛利率）  | Gross Profit / Sales Revenue |

所有普通销售指标默认：

```
Status = Completed

Business Time = Completion Date
```

------

# 27. Analytical Model Invariants（分析模型不变量）

Sales Analytical Model V1 必须满足：

1. `fct_sales_order_line` 是核心销售事实表。
2. 一行事实对应一条 Sales Order Line。
3. Sales Order 与 Sales Order Line 为 1:N。
4. Order 使用 Degenerate Dimension（退化维度）。
5. V1 不建立 `dim_order`。
6. Customer 使用 SCD Type 2。
7. Product 使用 SCD Type 2。
8. Customer / Product 事实关联必须保留历史版本。
9. Sales Region 与 Customer Region 独立建模。
10. 日期统一使用 `dim_date` Role-Playing Dimension（角色日期维度）。
11. Default Business Time = Completion Date。
12. Completed 是普通销售指标唯一有效状态。
13. Revenue / Cost / Quantity 为核心原子事实。
14. Sales Cost 冻结在销售事实中。
15. Product Standard Cost 不得重算历史销售成本。
16. Analysis Currency = CNY。
17. FX Date = Completion Date。
18. 实际采用汇率冻结在销售事实中。
19. 原币事实与 CNY 分析事实同时保留。
20. Gross Profit 不要求物理存储。
21. Gross Margin 不要求物理存储。
22. Gross Margin 不得使用行级毛利率平均计算。
23. Daily FX 使用独立汇率事实模型。
24. Return V1 不建立正式事实模型。
25. 历史事实不得被当前属性变化静默改写。

------

# 28. V1 Analytical Model Baseline（V1 分析模型基线）

```
Core Fact
=
fct_sales_order_line


Grain
=
One Sales Order Line


Dimensions
=
dim_customer
dim_product
dim_date
dim_sales_region
dim_currency


Reference Fact
=
fct_exchange_rate_daily


Order
=
Degenerate Dimension


Customer History
=
SCD Type 2


Product History
=
SCD Type 2


Business Time
=
Completion Date


Revenue
=
Frozen CNY Net Sales Amount


Sales Cost
=
Frozen Historical Sales Cost


FX
=
Completion-Date Rate
+
Frozen Applied Rate


Gross Profit / Gross Margin
=
Semantic Derived Metrics


Return Fact
=
Deferred
```

最终数据链：

```
DOMAIN_SPEC
        ↓
ANALYTICAL_MODEL
        ↓
Physical Schema / DDL
        ↓
ETL / ELT
        ↓
Sales Mart
        ↓
Semantic Layer
        ↓
ChatBI

```
