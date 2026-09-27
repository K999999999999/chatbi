# Ticket 02：新增完整 Conversation 多轮评测 Runner

Status: done

## What to build

新增按完整 Conversation 执行和计分的多轮案例集，覆盖指标 / 时间替换、Filter 追加 / 替换、维度追加 / 替换，以及失败轮次不污染上下文。每个场景使用隔离会话；场景内所有请求通过正式 Query API/Application 入口顺序执行并复用同一 `conversation_id`。报告保留 Conversation 结论和轮次级结果。

## Blocked by

None (can start immediately)

## Acceptance criteria

- 每个 Conversation 至少两轮，首轮成功建立结构化查询状态。
- 成功轮次执行 expected SQL 并按结果比较 Contract 判定；失败轮次有明确 expected outcome / error code。
- 每个场景从不带 `conversation_id` 的新会话开始；同场景后续成功请求复用首轮返回 ID。
- 失败轮次后继续成功追问，以可区分的结果确认状态仍是失败前最后一次成功状态。
- `Conversation Accuracy` 按完整场景计算；轮次执行准确率与 outcome 准确率分开统计。
- 多轮评测使用正式认证、授权、Query API 会话、Online Query、SQL Guard、Retrieval 和只读 PostgreSQL 链路。
- 经营分析仍按其现有专用评测器独立运行。

## Result

已实现。新增 7 个完整 Conversation 场景（共 15 轮），通过正式 Query API/Application 入口执行；同场景复用会话，不同场景隔离，并分别统计 Conversation、Execution 和 Outcome 准确率。

## Comments

- 定向软件测试通过：`105 passed, 1 skipped, 14 subtests passed`；Ruff、格式检查和 `git diff --check` 通过。测试使用假的 LLM / Retrieval / Database 边界。
- 最终提交 `71586df` 的真实多轮评测：Conversation 准确率 `4/7 = 57.14%`，成功结果轮次准确率 `9/14 = 64.29%`，Outcome 准确率 `0/1 = 0%`，无 INVALID_CASE。
- 失败场景：`MT-FILTER-APPEND`、`MT-FILTER-REPLACE` 和 `MT-FAILURE-ISOLATION`；前两个的企业客户过滤被 Retrieval 拒答，后者首轮组合查询被拒答，未能到达失败隔离轮次。
- 多轮通过 Query API JSON 返回时 PostgreSQL `Decimal` 被编码为字符串；实现已按标准结果数值列做定向归一化，并补充回归测试后重跑真实评测。
- 报告：`reports/evaluation/20260927T131348Z-71586df-multi-turn.json` 与 `.md`。

## Follow-up scope update

2026-09-27：按用户确认暂时移除 Filter 追加 / 替换场景，集合曾调整为 5 个 Conversation、11 轮。

2026-09-28：按后续确认补回两个独立 Filter Conversation，使用已登记的销售区域值华东 / 华南，不使用企业客户字段。当前集合恢复为 7 个 Conversation、15 轮；此前报告仍是历史证据，不能代表当前集合准确率。
