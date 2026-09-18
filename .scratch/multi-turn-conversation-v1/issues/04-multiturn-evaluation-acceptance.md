# Ticket 04：多轮 Evaluation 与业务验收证据

- Status: done
- Blocked by: Ticket 02、Ticket 03

## What to build

- 增加多轮语义修订的确定性回归测试。
- 增加会话生命周期、状态提交、用户隔离、TTL、并发冲突的测试。
- 增加 Streamlit 三轮交互验收场景。
- 分别记录 Software Test、AI Evaluation 和 Business Acceptance 证据。
- 真实 LLM / 本地完整 Real E2E 在获得单独授权后执行，并如实记录通过或失败结果。

## Blocked by

Ticket 02、Ticket 03：需要多轮后端行为和 Streamlit 交互均已形成可验收闭环。

## Acceptance criteria

- 既有单轮回归测试全部保持通过。
- 覆盖增加维度、替换指标两类多轮场景。
- 覆盖澄清、越界、下游失败、状态保留、用户隔离、TTL 和并发冲突。
- Streamlit 三轮场景可重复验收。
- 报告明确区分确定性测试、AI Evaluation 和业务验收。
- Real E2E 未通过时，不声称真实多轮业务链路已经验收。
- Real E2E 若执行，报告必须记录测试 Commit、`git_dirty=false` 和实际结果。

## Result

已完成分层验收证据整理与确定性回归补充：

- 补充 Streamlit 会话失效后、用户点击“新建会话”前不得静默调用 API 的回归测试；
- 多轮 API、会话生命周期、状态提交/保留、用户隔离、TTL、并发冲突、授权变化和 Streamlit 三轮交互均有可重复确定性覆盖；
- 关键多轮测试为 `47 passed, 21 subtests passed`，全量回归为 `357 passed, 6 skipped, 118 subtests passed`；
- 新增 `docs/acceptance/multi-turn-query-v1-20260919.md`，明确区分 Software Test、AI Evaluation、Business Acceptance 和 Real E2E 证据；
- 真实 21 条 AI Evaluation 为 `21/21 PASS`、`Execution Accuracy=100.00%`，报告 Commit 为 `2a1c262a2fd315bf90fe64899ddf33c8bb345a5a`，且 `git_dirty=false`；
- Retrieval 修复后真实三轮 HTTP E2E 全部返回 `200`：第一轮创建会话，第二轮增加销售区域分组，第三轮在同一会话中替换为毛利率，返回列为 `销售区域`、`毛利率`；
- 用户已通过真实 Streamlit 页面手动执行上述三轮问题并确认无误，本次三轮场景的 Business Acceptance 通过；
- 原因已定位并由 Ticket 07 修复：完整结构化查询纳入 `time.text`，存在时间条件时跳过会挤出日期表的维度单独补充查询，保持 `table_top_k=5`。

## Comments

- 本 Ticket 只建立验收证据和回归覆盖，不扩大多轮能力范围；真实 Retrieval 失败已由 Ticket 07 在 `2a1c262` 修复。
