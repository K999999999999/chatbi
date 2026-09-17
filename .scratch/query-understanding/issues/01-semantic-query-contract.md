# Ticket 01：SemanticQuery Contract 和确定性校验

Status: done

## What to build

在 `online_query` Module 内建立 `SemanticQueryCandidate`、`ValidatedSemanticQuery` 及其确定性校验边界。

实现内容包括：

- `query_type`、`subjects`、`metrics`、`dimensions`、`time` 和 `filters` 的结构 Contract；
- 字段类型、空值、枚举值和字段组合校验；
- 指标数量最多 5 个，不增加 `metric_count`；
- `time.granularity`、`QUERY_TIMEZONE`、日期区间和相对日期规则；
- `filters` 的 `values: string[]`、6 个允许操作符和 `AND` 规则；
- 结构失败与业务语义拒答的错误边界；
- `ValidatedSemanticQuery` 不直接承载物理表、物理字段和 Join Key。

## Blocked by

None (can start immediately)

## Acceptance criteria

- 合法候选可以转换为 `ValidatedSemanticQuery`；
- 非法 JSON 结构、字段类型、枚举值和缺少必要字段可以被确定性拒绝；
- `entity_lookup`、`metric_analysis` 和 `unknown` 的一致性规则生效；
- 指标数量超过 5 个时返回业务拒答；
- 日期和过滤条件规则可以独立进行确定性测试；
- 校验结果不会包含未经授权的物理资源；
- 不调用 LLM、不调用 Retrieval、不修改 SQL Guard 行为。

## Result

已完成 `SemanticQueryCandidate`、`ValidatedSemanticQuery`、日期标准化、过滤条件和确定性校验；相关定向测试及 `tests/online_query` 全量测试通过。

## Comments

本 Ticket 只建立稳定内部 Contract 和程序裁决边界，不选择具体 LLM Provider / SDK，也不决定最终代码文件拆分。
