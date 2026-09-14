# 04: 拒答、超时与执行边界

**What to build:**

统一无指标、单指标、多指标和直接 Join 查询的拒答、技术失败和执行限制，确保系统在缺少事实或运行条件不满足时停止，不猜测、不自动补全、不隐式重试。

**Blocked by:**

01, 02, 03

**Status:** open

## Acceptance criteria

- [ ] 缺少必需 TABLE、COLUMN、METRIC 或 Relationship 时返回 `CANNOT_ANSWER`。
- [ ] 指标公式所需物理字段未成为合法 COLUMN 候选时返回 `CANNOT_ANSWER`，不由程序静默补入。
- [ ] 没有合法 Join 路径或 Join 关系不明确时不调用 LLM，直接返回 `CANNOT_ANSWER`。
- [ ] SQL Guard 失败时不执行 SQL、不修复、不重试。
- [ ] LLM 超过 30 秒返回 `LLM_ERROR`，不重试。
- [ ] 数据库超过 10 秒返回 `QUERY_TIMEOUT`，不重试。
- [ ] 数据库返回 0 行属于成功结果，不返回错误。
- [ ] 最多向调用方返回 100 行，最多执行 101 行用于判断是否截断。
- [ ] 不实现分页和自动重试。
- [ ] 检索、Relationship Graph 和结构化上下文只能使用上游提供的权限范围。
- [ ] 不在本 V1 中新增登录、租户或 RBAC 系统。
- [ ] 为资源缺失、Asset Snapshot 错误、Qdrant/Embedding 错误、LLM 超时、数据库超时、空结果和超行数场景补充确定性测试。

## Result

待实现。

## Comments

本 Ticket 固化的是错误状态和停止边界，不新增业务规则引擎或复杂 Agent 行为。
