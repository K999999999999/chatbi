# 04: 拒答、超时与执行边界

**What to build:**

统一无指标、单指标、多指标和直接 Join 查询的拒答、技术失败和执行限制，确保系统在缺少事实或运行条件不满足时停止，不猜测、不自动补全、不隐式重试。

**Blocked by:**

01, 02, 03

**Status:** done

## Acceptance criteria

- [x] 缺少必需 TABLE、COLUMN、METRIC 或 Relationship 时返回 `CANNOT_ANSWER`。
- [x] 指标公式所需物理字段未成为合法 COLUMN 候选时返回 `CANNOT_ANSWER`，不由程序静默补入。
- [x] 没有合法 Join 路径或 Join 关系不明确时不调用 LLM，直接返回 `CANNOT_ANSWER`。
- [x] SQL Guard 失败时不执行 SQL、不修复、不重试。
- [x] LLM 超过 30 秒返回 `LLM_ERROR`，不重试。
- [x] 数据库超过 10 秒返回 `QUERY_TIMEOUT`，不重试。
- [x] 数据库返回 0 行属于成功结果，不返回错误。
- [x] 最多向调用方返回 100 行，最多执行 101 行用于判断是否截断。
- [x] 不实现分页和自动重试。
- [x] 检索、Relationship Graph 和结构化上下文只能使用上游提供的权限范围。
- [x] 不在本 V1 中新增登录、租户或 RBAC 系统。
- [x] 为资源缺失、Asset Snapshot 错误、Qdrant/Embedding 错误、LLM 超时、数据库超时、空结果和超行数场景补充确定性测试。

## Result

已完成。业务候选缺失和关系不可达统一在服务层转为 `CANNOT_ANSWER`，技术故障保持 `CONTEXT_ERROR`、`LLM_ERROR`、`DATABASE_ERROR` 或 `QUERY_TIMEOUT`；LLM 最长 30 秒且关闭自动重试，数据库固定 10 秒超时并读取 101 行后最多返回 100 行。SQL Guard、检索失败和数据库执行均没有隐式修复或重试路径。

## Comments

本 Ticket 固化的是错误状态和停止边界，不新增业务规则引擎或复杂 Agent 行为。
