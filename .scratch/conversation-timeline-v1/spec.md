# Conversation Timeline V1（当前会话查询记录）Feature Spec

Spec status: confirmed

Design review: PASS WITH MINOR FIXES

## Problem Statement

现有 `Multi-Turn Query V1` 已经支持当前会话中的连续追问、状态继承、失败回滚和“新建会话”。但当前 Streamlit 页面只保存并展示最后一次查询结果或最后一次错误，用户无法回看连续查询过程。

在内部销售 / 经营分析场景中，用户需要确认系统是否正确经历了以下分析过程：

```text
2025 年第一季度人民币销售额
→ 按销售区域拆分
→ 改看毛利率
```

如果页面只展示最后一次结果，用户无法理解上下文是否被保留、哪一轮发生了失败，也不利于内部试用和问题反馈。

本 Feature 只解决当前页面的查询过程展示问题，不重新建设会话系统。

## Solution

在现有 Streamlit 页面中增加 `Conversation Timeline V1`：

- 同一页面会话中的每一轮查询按时间顺序追加展示；
- 最新一轮置于时间线顶部并默认展开，较早轮次默认折叠但可只读查看；
- 成功轮次展示用户问题、成功状态、结果表和结果摘要；
- 失败或受控拒绝轮次展示用户问题、失败状态和用户可理解的错误信息；
- SQL、`Request ID`、`Trace ID` 等技术信息放在可展开详情中；
- 历史轮次只读，不恢复旧状态，也不从旧轮次分叉继续查询；
- 复用现有“新建会话”行为，点击后清空页面 Timeline 和当前会话引用；
- 仅保留当前页面会话中的记录，页面刷新、关闭页面或服务重启后不恢复；
- 不修改现有 Query API、`conversation_id`、后端会话状态或授权语义。

### Observable Behavior（可观察行为）

#### 正常场景

用户连续完成三轮查询：

1. `2025 年第一季度的人民币销售额是多少？`
2. `按销售区域拆开`
3. `改看毛利率`

页面按顺序保留三条 Timeline 记录。每条记录都能回看该轮问题和结果；第三轮结果仍由现有 Multi-Turn Query Contract 产生，不由 Timeline 自己重新计算。

#### 失败和拒绝场景

- 查询失败、需要澄清、超出范围或被授权拒绝时，当前轮次作为失败记录追加到 Timeline；
- 失败轮次不改变现有 Multi-Turn 的最后一次成功状态；
- 用户可继续输入问题修正，不因为展示失败记录而创建第二套会话状态；
- 页面继续使用现有的受控错误信息，不展示原始异常、Secret 或未授权数据。

#### 新建会话场景

- “新建会话”继续复用现有页面行为；
- 点击后清空当前页面 Timeline、当前结果和当前错误，并清除页面侧会话引用；
- 下一次查询从新的当前会话开始；
- 不执行历史数据删除，因为本 Feature 不产生持久化历史。

## User Stories

1. 作为内部销售或经营分析人员，我希望看到当前会话中的每一轮问题和结果，以便确认连续分析是否按我的意图推进。
2. 作为内部用户，我希望看到失败或拒绝发生在哪一轮，以便修正问题，而不是只看到最后一个错误。
3. 作为内部用户，我希望历史轮次只能查看，不能意外改变当前查询状态，以便保持现有 Multi-Turn 行为可预测。
4. 作为现有 API 和会话系统的维护者，我希望 Timeline 不改变既有 Query API 和会话 Contract，以便降低回归风险。

## Implementation Decisions

### Scope and Architecture

- 影响范围限定在 Streamlit 页面展示和页面侧会话状态；
- Timeline 记录由 Streamlit 当前页面状态拥有，不新增后端历史存储；
- 继续调用现有 `POST /api/v1/query`，请求仍只提交当前问题和可选的服务端 `conversation_id`；
- 不向 API 提交完整 Timeline、原始对话、结构化状态、SQL 或结果历史；
- 不修改 Query API、Application 会话状态、授权、Online Query、SQL Guard 或数据库执行链路；
- 复用现有成功响应和 `QueryAPIError` 的数据形状，不创建第二套查询或错误链路。

### Timeline Record

每条记录至少包含页面展示所需的以下信息：

- 用户原始问题；
- 成功、失败或受控拒绝状态；
- 成功响应中的现有结果数据和结果摘要；
- 失败响应中的现有受控错误信息；
- 可选展开的现有 SQL、`Request ID` 和 `Trace ID`。

记录顺序以查询完成并写入页面状态的顺序为准。现有 API 的行数上限和 `truncated` 语义保持不变，不在本 Feature 增加新的结果查询或分页 Contract。

### Existing Contract Preservation

- 现有 `conversation_id` 仍由服务端生成并由页面复用；
- 现有短期会话、30 分钟 Idle TTL、用户隔离、逐轮授权和失败状态规则保持不变；
- 历史 Timeline 记录不构成授权凭证，也不能恢复或扩大数据权限；
- 单轮 API 调用和既有 Streamlit 查询行为继续兼容。

## Testing Decisions

### Deterministic Software Test（确定性软件测试）

以现有 Streamlit 页面测试替身和 Query API 调用替身为主要测试接缝，验证：

1. 首次成功查询会创建一条成功 Timeline 记录；
2. 连续成功查询按提交顺序追加，旧记录不会被新结果覆盖；
3. 三轮正常场景保留三条记录，并继续复用同一个服务端 `conversation_id`；
4. 失败、澄清、范围拒绝和授权错误会追加失败记录；
5. 失败轮次不替换或破坏此前成功记录和现有会话引用；
6. 成功记录显示结果和摘要，技术详情可按现有方式展开；
7. 失败记录显示受控错误、`Request ID` 和 `Trace ID`（存在时），不显示原始异常或 Secret；
8. “新建会话”清空 Timeline，并继续清除现有页面侧会话引用；
9. 页面刷新或重新初始化时不会从后端恢复 Timeline；
10. API 请求仍只包含问题和可选 `conversation_id`，不包含 Timeline 或完整历史；
11. 现有 Streamlit、Query API 和 Multi-Turn 确定性测试继续通过。
12. 最新轮次默认置顶展开，历史轮次默认折叠；展开历史轮次只查看记录，不恢复状态或重新执行查询。

本 Feature 不改变语义解析、Retrieval、LLM、SQL Guard、数据库执行或后端会话 Contract，因此不以新的 AI Evaluation 或 Real E2E 作为本 Feature 的必要验收证据。若实现阶段影响上述链路，应按实际影响范围重新评估验证级别。

### Business Acceptance（业务验收）

使用现有内部 Streamlit 入口完成三轮确认场景，业务用户能够按顺序看到三轮问题和结果，并能识别失败轮次；点击“新建会话”后页面从空 Timeline 开始。

## Out of Scope

- 修改或重建现有 Multi-Turn Query 会话系统；
- 修改 `POST /api/v1/query` 或新增 Timeline / 历史查询 API；
- 后端持久化、跨页面恢复、跨天恢复或服务重启恢复；
- 多个当前会话并行切换；
- 历史会话搜索、重命名、删除、分享或导出；
- 点击历史轮次后恢复状态、分叉查询或重新执行查询；
- 同比、环比、趋势、原因分析、多查询拆解、结果汇总或 Autonomous Agent；
- 自然语言结果总结、自动 SQL 修复或第二套查询链路；
- 企业 SSO、持久化审计、限流、部署、监控、告警和回滚能力。

## Further Notes

### Change Profile

- 维护寿命：内部产品 V1 的页面体验能力；
- 变更规模：小范围，主要影响 Streamlit 状态管理和渲染；
- 风险：低到中，主要风险是页面状态误污染、历史结果展示错误和用户误以为历史记录可恢复；
- 交付方式：确定性测试、代码 Review 和本地 Commit；不要求因为本 Feature 单独修改生产部署或后端会话存储。

### Decision Record

- 采用当前页面 Timeline，而不是后端持久化历史：因为当前需求是改善内部查询体验，现有会话系统明确只保证短期当前会话；
- 采用只读历史轮次，而不是恢复或分叉：避免改变已确认的 Multi-Turn 状态语义和授权边界；
- 采用最新轮次置顶展开、历史轮次默认折叠：减少多轮查询时的页面滚动，同时保留历史记录的只读回看能力；
- 采用 Streamlit 页面侧实现，而不是修改 Query API：保持既有公共 Contract 和后端会话系统稳定。

### Canonical Source（权威事实源）

- 本文件：`Conversation Timeline V1` 的当前 Feature 行为 Contract；
- `docs/roadmap.md`：产品阶段和路线；
- `docs/adr/0001-multi-turn-query-v1-boundaries.md`：现有会话生命周期与状态边界；
- `docs/specs/query-api.md`：既有 Query API 和 Multi-Turn 公共 Contract；
- `src/streamlit_app.py` 与 `tests/streamlit/test_streamlit_app.py`：实现与确定性测试；
- 后续 Implementation Design：只补充实现结构，不改变本 Spec 的行为范围；
- 后续 Ticket：只在本 Spec 和 Design Review 通过后创建。

本 Spec 尚未授权编写业务代码、测试代码、Ticket、Commit、Push、PR 或生产部署。
