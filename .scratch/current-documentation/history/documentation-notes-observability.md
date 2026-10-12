# 链路观测与诊断：整理前的过程记录

来源：`docs/specs/observability.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 整理前入口说明

# Observability V1 Module Spec

状态：行为规格已补充 request_id/trace_id 时序和 HTTP 观测边界；T1～T4C 已完成并通过各自测试。T5 的阿里云 OTLP / Trace 验收是历史证据，不代表当前稳定候选仍已接通。R7 的后台执行、导出、安全配置与只读轮询边界见 §14；原有 T1～T5 结果不随该扩展重标。

## 3. 实施前基线（历史事实）

- Query API 和 Online Query 已使用 `request_id` 关联请求，电脑端 Web 在“查看请求信息”中展示该编号与 Header 的 Trace ID。
- Evaluation（评测）只记录一次查询的总耗时，没有节点耗时。
- Online Query 只在部分 Retrieval fallback 场景写入日志，没有完整成功和失败 Trace。
- Online Retrieval 已返回 `asset_version`、状态、候选命中、分数、Join 路径和原始检索证据。
- 当前 LLM Adapter（适配器）只向核心链路返回 SQL 文本，模型返回的 Token 信息未被记录。
- 当前没有 `trace_id`、统一 Span（链路节点）、可观测后端或告警。

## 12. 实现设计阶段再决定

- 具体可观测 SDK、后端和部署方式；
- Span 与代码函数的落位；
- Trace 上下文传播方式和框架集成；
- Token Metadata（元数据）的提取方式；
- 配置项名称和 No-op（空实现）Adapter；
- 测试替身、Exporter（导出器）和验收运行方式；
- 后续采样、保留时间、Dashboard（看板）、告警和系统指标方案。

## 13. 已确认决定

| 编号 | 决定 |
|---|---|
| D1 | 保留 `request_id`，新增独立 `trace_id`，HTTP 通过 `X-Trace-ID` 返回 |
| D2 | 默认不记录完整问题、Prompt、SQL 和结果；本地调试只允许受控开启问题和最终 SQL |
| D3 | Token 为可选观察数据，Provider 未返回时不得失败；V1 不计算费用 |
| D4 | 可观测能力采用 fail-open（记录失败不影响查询）的旁路原则 |
| D5 | V1 覆盖成功、拒绝、技术失败、超时和 Retrieval fallback |
| D6 | 用户、租户、权限、生产告警和具体技术产品不属于本规格 |
| D7 | V1 HTTP 不信任客户端 Trace Context；可信 Gateway 接入后再单独开放上游继承 |
| D8 | OTel/Langfuse 只记录安全错误分类和错误码；原始异常不进入 Trace |
