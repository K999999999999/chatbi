# R2 实现设计

行为以[Spec](../specs/result-visualization-v1.md)为准；[设计审查](../../.scratch/result-visualization-v1/design-review.md)与[实施规划](../../.scratch/result-visualization-v1/design.md)记录确认过程。

## 后端

`online_query/result_metadata.py`在执行完成后认证实际投影、固定过滤与业务分组；`result_time.py`核实完成日期连接角色、实际半开区间和行对齐的时间键。复用已锁定SQLGlot及Guard的物理解析帮助函数，仅提供显示证据，不新增SQL拒绝。复杂子查询/Window/CTE或无法证明的表达式保留原始结果。

`semantic/result_display.py`校验展示属性引用权威指标、维度与Structure。属性与既有 `metrics.json` 分开，避免无关RAG重建。`ResultMetadata`是冻结JSON快照，序列化得到独立对象；业务Contract不携带AST、ECharts或DB cursor。QuerySuccess及TaskResult新增最后一个可选字段，API显式序列化；报告模型输入仍使用原字段，新增元数据不进入Prompt。Checkpoint类型白名单加入ResultMetadata，旧构造字段默认为None。

## 网页

`resultMetadata.ts`校验公共形状、位置与名称、角色/格式、范围与时间键；损坏列局部降级，未知版本或损坏范围保留原表。`numberFormat.ts`使用十进制字符串和BigInt格式化，保留原返回值。`chartPlan.ts`是确定性计划：只取可信指标/维度、按单位拆分、拒绝重复分组与不安全数值、排序时间并在缺失处插入NULL。

`Chart.tsx`隐藏ECharts生命周期及错误，按需动态加载 `echartsRuntime.ts` 的SVG Line/Bar、Grid/Tooltip/Legend/Aria/DataZoom模块。ResizeObserver随组件销毁断开，图形对象dispose；滚动展示长分类，不删数据。Tooltip使用richText，数值由原值格式化。图表失败独立于表格；ResultView复用于問数和分析任务证据。

`Analysis.tsx`使用既有归因方向、产品分类和因素；CNY格式限于已确认的两个人民币指标，不把其他指标猜成金额。产品选择只改本地状态。

## 回滚与证据

无Migration、业务数据和RAG资产改写；回滚代码与npm锁定依赖，保留已有用户、Checkpoint、卷与模型。纯软件/Chrome默认回归不调用真实模型；`scripts/verify_container_dev.sh real`显式真实验收，独立SQL参考和专用账号由既有工具准备、禁用并撤销Session。正式证据必须绑定clean代码候选，热更新试验单独标记临时源修改，结束恢复并检查工作区。
