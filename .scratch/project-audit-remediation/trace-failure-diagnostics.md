# Trace 失败原因分类短 Spec

状态：已确认。用户于 2026-10-17 明确同意开始补充安全错误分类并重跑目标用例。

## 目标

让本地/OTLP Trace 在不采集业务正文的前提下，区分审计复现目标 S02 的 Provider 故障类别，以及 MT-FILTER-REPLACE 的 SQL Guard 拒绝规则类别。

## 范围与行为

- Provider 失败 Span 写固定 `chatbi.provider.error_category`；可安全读取时写 HTTP 状态码，并标记故障类别是否通常可重试。状态码与分类只用于诊断，不改变重试策略。
- Provider 分类从受控异常链中映射为固定枚举，不写异常类名、消息、响应正文、endpoint、Header 或凭据。
- 本地 Evaluation `tools` 容器沿用 OTel exporter 配置，内容采集强制关闭；多轮每轮独立关联 case / turn / trace ID。
- SQL Guard 拒绝 Span 写固定 `chatbi.sql_guard.rejection_code`，定位至候选格式/语法、数据范围、Join、指标约束等确定性规则类别；不记录候选 SQL 或 Guard 原始消息。
- 多轮 Evaluation 为每个请求轮次建立可关联 Root Trace，并在报告中写入 Trace ID 与安全的 case / turn 标识符。
- 保持公开错误码、查询结果、业务执行顺序、Provider 参数和既有重试次数不变。Trace 仍 fail-open，内容采集继续关闭。
- 更新正式 Observability Spec / Design，并增加确定性测试。

## 不在范围

- 修改 Prompt、模型、endpoint、timeout、案例、Seed、评测门槛或 SQL Guard 业务规则。
- 记录完整问题、Prompt、异常文本 / 堆栈、完整 SQL、HTTP Body、Secret。
- 将新的本地复跑报告替换或改写既有正式失败报告。

## Done When

- 受控 Provider 异常链能映射到安全固定类别；无法识别时记录 `UNKNOWN`，不泄漏原始异常。
- SQL Guard 的每个正式拒绝路径得到受控类别；原公开 `SQL_REJECTED` 不变。
- 单元测试验证成功/失败分类、未知异常、状态码范围和敏感文本不进入 Span。
- 定向测试、文档检查、Code Review、Diff 检查通过；在本地候选上分别重跑 S02 和 MT-FILTER-REPLACE，保留新报告及失败证据。

## 授权

用户 2026-10-17 回复“可以 开始”，授权实施上述错误分类并重跑目标用例；继承审计目标既有本地实施、验证、Review 和 Commit 范围，不包含 Push、PR 或 Merge。
