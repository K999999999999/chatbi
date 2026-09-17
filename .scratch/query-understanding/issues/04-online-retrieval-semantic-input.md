# Ticket 04：Online Retrieval 消费 ValidatedSemanticQuery

Status: done

## What to build

调整 `OnlineRetriever` 及其内部 Retrieval 文件，使其消费 `ValidatedSemanticQuery`，移除对原始问题的分散解析。

重点复核：

- `retrieval.py`：保留 Retrieval 子流程编排；
- `resource_retrieval.py`：按结构化 subjects、metrics、dimensions 和 filters 形成检索输入；
- `retrieval_selection.py`：消费已确认的维度、过滤字段和日期语义；
- `multi_metric.py`：收缩为权威 Metric 候选确认、去重和兼容性校验；
- `RetrievalRequest`：以 `ValidatedSemanticQuery` 为主要输入。

## Blocked by

Ticket 01：SemanticQuery Contract 和确定性校验

Ticket 03：OnlineQueryService 主链路接入 Query Understanding

## Acceptance criteria

- TABLE 检索主要消费 `subjects` 和结构化维度语义；
- METRIC 检索消费 `metrics`，每个请求指标都必须唯一映射到权威 Metric；
- COLUMN 检索消费维度和过滤字段语义，并限制在候选表范围内；
- 主表和 Join 继续由程序结合 Relationship Graph 确定；
- 不再使用正则重新判断指标意图、指标数量或分组文本；
- 找不到或歧义的 Metric、Column、主表或 Join 返回 `CANNOT_ANSWER`；
- Retrieval 技术故障仍返回 `CONTEXT_ERROR`；
- Online Retrieval V1 的资产版本、Top-K、阈值和 fail-closed 边界不被削弱；
- 不扩大静态 Schema fallback，也不引入新的候选选择 LLM。

## Result

- `OnlineRetriever.retrieve` 现正式只接收带 `ValidatedSemanticQuery` 的 `RetrievalRequest`，字符串不再是主链路输入。
- TABLE、METRIC、COLUMN 和 Relationship Graph 的输入均来自结构化 `subjects`、`metrics`、`dimensions`、`filters`、`time`；不再从原始问题正则推断指标意图、指标数量、分组文本或日期条件。
- METRIC 按每个请求指标独立检索，并要求名称或 alias 唯一精确匹配；重复 alias 仍按权威 Metric 去重，固定过滤、data_source、time_field 兼容性继续由程序校验。
- `RequestShape` 收缩为 `BASELINE / EXPLICIT_MULTI`，移除无法由结构化 Contract 表达的 `POSSIBLE_MULTI`。
- 保留 Online Retrieval 的资产版本、Top-K、阈值、Relationship Graph 和 fail-closed 边界；未增加候选选择 LLM，也未接入静态 Schema fallback。
- 已迁移相关 Retrieval、Multi-Metric、Trace 和 Evaluation 测试，并增加结构化输入回归测试。
- 验证：`283 passed, 6 skipped, 99 subtests passed`；`compileall` 已通过。

## Comments

现有 `OnlineRetriever.retrieve(str)` 测试和评测迁移在本 Ticket 或 Ticket 06 中完成，但不得保留字符串作为正式主链路输入。
