# Ticket 02：多轮语义修订与单条查询执行闭环

- Status: done
- Blocked by: Ticket 01

## What to build

- 基于上一轮已确认的结构化查询状态和本轮新问题生成下一轮查询。
- 支持同一语义槽位替换，例如替换指标。
- 支持不同语义槽位追加，例如增加维度。
- 对无法确定的修订返回澄清。
- 对不支持的分析返回明确错误。
- 继续复用现有授权、语义解析、查询执行和 SQL Guard 链路。
- 每一轮最多执行一条最终查询。
- 仅在下游成功后提交新状态。

## Blocked by

Ticket 01：必须先具备可用且受控的会话状态生命周期。

## Acceptance criteria

- 支持“先按时间看销售额，再增加地区维度，再替换为毛利率”的连续三轮场景。
- 语义存在歧义时返回 `CLARIFICATION_REQUIRED`，HTTP 422。
- 超出产品能力边界时返回 `UNSUPPORTED_ANALYSIS`，HTTP 422。
- 澄清、越界或失败请求不修改已有会话状态。
- 每一轮都重新执行当前用户授权校验。
- 用户权限变化后不能继续使用不再允许的数据范围。
- 现有单轮查询行为保持不变。
- 不把原始对话历史、原始 SQL 或查询结果直接作为客户端状态。

## Result

- 已实现 Application 层结构化语义修订：上一轮成功的 `ValidatedSemanticQuery` 由服务端会话状态持有，当前追问通过 `QueryRevisionAdapter` 生成 delta，再由确定性槽位规则合并并重新校验。
- 已实现同槽位替换（metric / subject / time / 同 field filter）和不同 filter、dimension 追加；每轮最多进入一次 `OnlineQueryService.execute()`。
- 已实现 `CLARIFICATION_REQUIRED`、`UNSUPPORTED_ANALYSIS`、失败不提交状态，以及每轮重新授权；已通过 API-level deterministic tests 覆盖三轮场景、澄清、越界、下游失败和权限变化。
- 已将真实 `LangChainQueryUnderstanding` 扩展为 revision prompt；`QuerySuccess` 回传已确认语义，首轮成功创建会话时保存该状态，后续成功才替换状态。
- 未修改 Streamlit；未执行真实 LLM / Qdrant / PostgreSQL 多轮 E2E，留待单独授权的 AI Evaluation / Business Acceptance。

## Comments

- 模型只提出语义修订候选；最终状态、授权、SQL 安全和状态提交由 Contract 与确定性代码裁决。
