# Ticket 05：Prompt 和 SQL Generation 接入已确认语义

Status: done

## What to build

调整 Prompt 组装和 SQL Generation 输入，使 SQL LLM 只接收已经确认的业务语义和最小物理上下文。

实现内容包括：

- Prompt 接收 `ValidatedSemanticQuery`、`QueryContext` 和原始问题；
- 原始问题只作为辅助上下文，不再由 Prompt 重新解析；
- 日期使用程序已经计算出的确定范围；
- 用户过滤条件使用已经校验的字段、操作符和值；
- Metric 继续使用权威定义、公式、固定过滤条件、数据来源和 `time_field`；
- 保持 SQLGenerator 只生成一条 SQL 或精确的 `CANNOT_ANSWER`；
- 保持 SQL Guard 只信任 `QueryContext` 执行物理范围和安全校验。

## Blocked by

Ticket 03：OnlineQueryService 主链路接入 Query Understanding

Ticket 04：Online Retrieval 消费 ValidatedSemanticQuery

## Acceptance criteria

- Prompt 不再从原始问题重新识别指标、日期、维度或过滤条件；
- Prompt 不把 LLM 输出的物理资源直接当作允许范围；
- SQLGenerator 看不到完整静态 Schema 或无关资产；
- 合法查询仍能进入 SQL Guard；
- SQL Guard 拒绝仍返回 `SQL_REJECTED`，不自动修复、不重试、不执行；
- SQL LLM 生成失败仍返回 `LLM_ERROR`；
- 现有多指标公式、固定过滤条件和 Join 安全规则不回归。

## Result

- `build_prompt` 在线调用现接收 `ValidatedSemanticQuery`、`QueryContext` 和原始问题；结构化内容由程序确定性序列化，Prompt 不再从原始问题推断指标、维度、日期或过滤条件。
- Prompt 明确携带已标准化的时间半开区间 `start/end`、过滤操作符和值，以及前序 Retrieval 认证的 Metric Context 和 Dynamic Schema。
- `OnlineQueryService` 在线路径已把确认语义传入 Prompt；静态字符串调用仅保留为待删除静态模式的兼容入口。
- SQLGenerator、SQL Guard 和 Database 的职责及错误码边界保持不变。
- 验证：`221 passed, 6 skipped, 87 subtests passed`（Online Query、Evaluation、Query API 相关测试）；`compileall` 及差异检查待提交前复核。

## Comments

本 Ticket 不重写 SQL Guard，不新增复杂 SQL 能力，不把 Prompt 提升为业务真相来源。
