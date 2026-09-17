# Ticket 02：QueryUnderstandingAdapter

Status: done

## What to build

增加独立的 `QueryUnderstandingAdapter`，将用户自然语言转换为单个 `SemanticQueryCandidate`。

实现内容包括：

- 独立的 Query Understanding Prompt；
- Structured Output（结构化输出）或等价的 JSON 对象接收；
- LLM 调用、空响应和响应转换错误处理；
- Query Understanding 专用 Trace 阶段；
- 一次请求最多调用两次；仅 Provider 调用异常或超时允许重试一次，响应内容和 Contract 错误不重试；
- 不与现有 `SQLGenerator` 合并职责。

## Blocked by

Ticket 01：SemanticQuery Contract 和确定性校验

## Acceptance criteria

- LLM 只需要返回一个结构化对象，不接受解释、Markdown 或额外文本；
- 合法结构可以交给 Ticket 01 的确定性校验；
- Provider 调用失败或超时在一次重试后仍失败时映射为 `LLM_ERROR`；空响应、非法 JSON 或响应转换失败不重试并映射为 `LLM_ERROR`；
- 失败时不进入 Retrieval、SQL Generation 或 Database；
- 不输出物理表、物理字段、Metric 公式、`time_field` 或 Join Key；
- Query Understanding Trace 与 SQL Generation Trace 可以区分；
- 使用 Fake / Stub Model 完成确定性测试，不依赖真实 API Key。

## Result

已完成独立 `QueryUnderstandingAdapter`、专用 Prompt、JSON Contract 转换、受控 Provider 重试、`LLM_ERROR` 映射和 `llm.query_understanding` Trace 阶段；定向测试及 `tests/online_query` 全量测试通过。

## Comments

具体 Provider / SDK 只在本 Ticket 的实现阶段选择，不能改变 `SemanticQueryCandidate` Contract。
