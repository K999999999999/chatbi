# 03: 直接 Join 查询与结构化关系上下文

**What to build:**

在统一检索流程中加入直接表关系查询。由 Relationship Graph 提供已验证的直接 FK → PK 关系和 Join Key，程序形成最小关系上下文，LLM 只在给定候选资源和关系事实范围内生成一条 SQL。

**Blocked by:**

01

**Status:** done

## Acceptance criteria

- [x] 支持事实表与维度表之间的直接 FK → PK Join。
- [x] 事实表作为 Join Anchor（连接锚点）。
- [x] Join 类型固定为允许的 `LEFT JOIN`。
- [x] Join Key 只能来自 Relationship Graph 结构化事实，不占用 COLUMN TopK=10 名额。
- [x] LLM 不能猜测 Join Key、修改关系方向或新增 Relationship Graph 中不存在的关系。
- [x] 只支持直接 Join；需要中间表、桥接表或多跳 Join 时返回 `CANNOT_ANSWER`。
- [x] 需要日期过滤或分组时使用指标定义中的 `time_field`。
- [x] 存在多个日期关系且无法根据 `time_field` 或用户语义确定时返回 `CANNOT_ANSWER`。
- [x] Relationship Graph 只检查当前候选表之间的必要关系，不自动把所有候选表连接起来。
- [x] 结构化上下文只发送当前候选 TABLE、COLUMN、METRIC、必要 Join Facts、指标定义和原始问题，不发送完整 Schema、无关表列或行数据。
- [x] 为按客户、产品、日期分组的直接 Join，以及无关系、桥接表、多跳和日期关系歧义场景补充确定性测试。

## Result

已完成。统一在线检索现在只解析候选事实表到维表的直接 FK → PK 关系；关系键由结构化 Relationship Graph 提供并加入 SQL 白名单，不再合成隐藏表或沿反向/多跳路径推断。普通查询不自动连接日期表，只有明确日期语义时才使用指标 `time_field`。SQL Guard 对动态 Join 只接受已认证的 `LEFT JOIN`。

## Comments

示例场景为“查询 2025 年各产品的销售额”。多指标仍沿用 02 的同一条编排流程；本 Ticket 不引入第二条 Join 流水线。
