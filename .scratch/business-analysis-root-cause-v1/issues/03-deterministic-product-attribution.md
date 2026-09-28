# 03 实现产品因素确定性归因并交给总结模型

Status: done

## Owner

ChatBI Engine 实施 Agent

## Blocked by

02 用 LangGraph 编排经营分析固定查询 Task

## What to build

- 新增确定性归因计算：由产品、时期的人民币净销售额、数量和人民币销售成本计算实际成交单价、单位成本和因素贡献。
- 毛利按单价、销量、单位成本三因素计算；销售额按单价、销量两因素计算，使用 Spec 中确认的对称分摊公式。
- 首版按 Natural Query 返回的产品名称配对跨期结果，并实现新品 / 退出产品的独立贡献。
- 对照整体指标查询结果校验所有产品贡献和因素贡献；选择整体变化方向上的至多 3 个主要产品。
- 将查询证据与确定性归因结果传入 Summary LLM；数值、方向、产品排序和指标口径由程序控制。

## Acceptance criteria

- 所有显示因素的未舍入贡献相加后与产品指标实际变化一致；所有产品贡献与整体指标变化一致。
- 成本下降对毛利为正贡献、成本上升对毛利为负贡献；销售额归因不包含成本。
- 产品仅在一个时期有销量时，将整项指标变化列为进入 / 退出贡献，不伪造缺失时期的价格或单位成本。
- 必需查询失败、截断、输入无效或任一层对账失败时，停止后续归因并返回未完成原因；不调用 Summary LLM 生成原因结论。
- 名称暂按比较期内稳定处理；改名可能表现为退出和新增，不做 `product_id` 实体识别。

## Change Profile

- Lifetime: 长期业务规则。
- Size: 中。
- Risk: 高；影响归因金额及经营解释。
- Evidence: 固定数据上的确定性公式测试、舍入 / 边界测试、Golden Case 对账及 LLM Judge。
- Delivery: 本地 Feature branch；不改变业务种子数据。

## Canonical Source

`.scratch/business-analysis-root-cause-v1/spec.md`。

## Owned files

- `src/business_analysis/` 归因计算与 Summary 输入
- `tests/business_analysis/`
- `src/evaluation/` 相关评测接入点

## Migration / Rollback

- 不改数据库 Schema 或 Natural Query SQL 执行边界。
- 若归因校验失败，返回明确未完成状态，不退化为 LLM 自行计算。

## Verification evidence

- 对称因素公式、正负方向、产品进入 / 退出、跨期配对、Top 3 和 0.02 元显示累计误差测试。
- SQL 参考结果与 Graph Task 结果对账。
- 报告事实一致性的 LLM Judge 结果。

## Done When

每项成功归因均可确定性复算并通过总额对账；失败或证据不足时不会生成未经支持的原因结论。

## Result

已实现毛利的实际成交单价、销量、单位成本归因，以及净销售额的实际成交单价、销量归因；程序执行期间 / 产品 / 因素对账并确定 Top 3。Summary 收到确定性归因和因素对目标指标的影响方向。最终真实评测 3 个成功案例均通过独立参考 SQL 对账和 Summary Judge。详见 `docs/acceptance/business-analysis-root-cause-v1-20260928.md`。

## Comments

- 名称变更识别是明确暂缓范围；不得在本 Ticket 中加入专用 `product_id` 查询通道。
