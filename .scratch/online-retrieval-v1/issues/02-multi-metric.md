# 02: 多指标共用同一条检索流水线

**What to build:**

在 01 的统一流程上增加多指标查询能力。多指标只是同一条流水线中 `metrics=N` 的一种输入，不新增第二条完整流水线，不为每个指标单独执行一套表、列、指标检索和 SQL 生成。

**Blocked by:**

01

**Status:** done

## Acceptance criteria

- [x] V1 最多支持用户明确请求的 3 个指标。
- [x] METRIC 对整条用户问题执行一次合并检索，不针对每个指标分别调用一次。
- [x] `METRIC TopK=5` 表示候选池上限，不表示最终输出只能保留 5 个指标。
- [x] 所有明确请求的指标都必须被合法候选覆盖；任一必需指标缺失时返回 `CANNOT_ANSWER`，不生成部分结果。
- [x] 多指标只生成一条 SQL，不拆成多个 SQL。
- [x] 所有指标必须兼容相同的 `data_source`、`time_field`、固定过滤条件、用户时间范围、分组和查询级过滤条件。
- [x] 指标不兼容时返回 `CANNOT_ANSWER`。
- [x] 不展开 `depends_on`，不额外检索指标依赖，也不自动补充公式字段。
- [x] 不使用 condition aggregation、子查询、窗口函数、CTE、UNION 或其他复杂分析逻辑。
- [x] 用户提供的过滤值直接作为 SQL 参数使用，不执行实时枚举值查询或隐式代码映射。
- [x] 为 2 个指标、3 个指标、超过 3 个指标、指标缺失和指标不兼容场景补充确定性测试与评估样例。

## Result

已完成。多指标在同一条 `_retrieve_request` 流程中执行一次 TABLE、一次综合 METRIC、一次候选范围内 COLUMN 检索，并从本次 METRIC 命中直接构造指标约束；不再加载 Metric Catalog 或执行指标 ID 二次查询。相关 Online Query 测试通过。

## Comments

本 Ticket 只扩展指标数量和兼容性，不改变 01 已确定的检索顺序、候选范围和 SQL 安全边界。
