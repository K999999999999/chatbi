# Multi-Metric Retrieval（多指标在线检索）业务验收记录

验收日期：2026-09-14

对应规格：`docs/specs/multi-metric-retrieval.md`

对应实现设计：`docs/designs/multi-metric-retrieval.md`

对应实现 Commit：`c60e0739ec296593ee179d57af4f2ac90cdfb86d`

## 一、验收结论

结论：PASS（按当前已确认规格）。

Multi-Metric Retrieval 已完成当前规格范围内的软件实现、确定性测试、真实在线 RAG Evaluation（评测）和 Business Acceptance（业务验收）。该结论不代表 Production Ready（生产可用）。

## 二、验收范围

- 2～5 个能够映射到已登记名称或别名的明确指标。
- 共同事实表、共同过滤条件和已确认的确定性关系图。
- 单层 SELECT，以及规格允许的 GROUP BY、ORDER BY、LIMIT。
- C04 四指标组合和 C05 三指标组合。
- 多指标检索或 SQL 校验失败时 Fail Closed（失败关闭），不得回退到不满足新契约的静态上下文。

跨事实表组合、经营分析、多轮澄清、权限平台和 Production Hardening（生产强化）不在本次结论范围内。

## 三、软件与评测证据

1. 全量确定性测试：230 passed、6 skipped、79 subtests。
2. 真实在线 RAG Evaluation：20/20，通过 0 失败、0 无效案例；C05 和 M08 均为 PASS。
3. C05 使用真实 `chatbi_app` 只读执行器，标准 SQL 与系统 SQL 均返回 3 个客户类型，结果逐值一致，未截断：

| 客户类型 | 已完成订单数 | 人民币净销售额 | 毛利率 |
|---|---:|---:|---:|
| Distributor | 539 | 180845212.311687 | 26.8856% |
| Enterprise | 1871 | 634643420.033334 | 26.5661% |
| SMB | 1327 | 470145816.033255 | 26.6333% |

4. C04 使用真实只读执行器，标准 SQL 与系统 SQL 均返回 4 个产品线，销售额、销售成本、毛利和毛利率逐行一致，结果未截断。
5. 评测运行标识：`20260912T145505Z-c60e073`。该次原始 JSON / Markdown 报告按仓库本地策略被 `.gitignore` 忽略；本记录保留其运行标识和验收摘要。

## 四、业务口径核对

### C05：按客户类型统计已完成订单数、人民币销售额和毛利率

- 分组维度为 `dim_customer.customer_type`。
- 已完成订单数使用 `COUNT(DISTINCT f.order_id)`，不会按订单明细行数重复计算。
- 人民币销售额使用事实表冻结字段 `f.net_sales_amount_cny` 汇总，不重新计算汇率。
- 毛利率使用同一过滤范围内的 `SUM(net_sales_amount_cny - sales_cost_amount_cny) / NULLIF(SUM(net_sales_amount_cny), 0)`。
- 三项指标均使用 `f.order_status = 'completed'`。
- 事实表通过 `f.customer_key = c.customer_key` 连接客户维度。
- 返回指标恰好为已完成订单数、人民币净销售额、毛利率，顺序正确。

### C04：按产品线统计销售额、销售成本、毛利和毛利率

- 四项指标均独立出现在结果中。
- 毛利率使用已确认公式和 `NULLIF` 除零保护。
- 产品线维度来自 `dim_product.product_line`。
- 结果与标准 SQL 执行结果一致。

## 五、事实源与证据追溯

- 指标定义、公式、过滤条件和时间字段：`src/semantic/metrics.json`。
- 表字段和数据类型：`src/structure/generated/columns.json`。
- 客户 Join 关系：`src/structure/generated/relationships.json` 中的 `fk_fct_sales_customer`。
- 多指标成功、逐项覆盖、关系唯一性和 Fail Closed 行为：`tests/online_query/test_retrieval.py`。
- 真实结果一致性：评测执行器使用标准 SQL 结果与系统结果逐单元格比较；C04/C05 另行完成真实只读核对。

## 六、历史证据处理

`docs/acceptance/online-retrieval-20260907.md` 是 2026-09-07 的历史 Online Retrieval V1 验收记录，保留当时 C05 尚未支持的原始结论，不改写历史结果。

## 七、后续边界

本次业务验收完成后，Multi-Metric Retrieval 可以作为当前规格范围内的已验收能力使用。以下事项仍需独立立项或单独验收：

- 权限、多租户、审计、限流、性能和部署治理。
- 跨事实表组合、经营分析和更复杂的任务编排。
