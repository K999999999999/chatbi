# 自然查询三类评测集 Spec

状态：已确认；`workflow-design-review` 结论为 `PASS WITH MINOR FIXES`

## Problem Statement

当前 Evaluation 有 21 条逐案例独立运行的普通查询案例，案例按 `simple / medium / complex` 标注；经营分析已有独立的 5 条案例和专用 Runner。受控多轮查询已有应用行为和验收证据，但没有按完整 Conversation 运行、共享会话状态并独立统计的标准评测集。

现有结构无法按“单轮自然查询、多轮自然查询、经营分析”三类观察能力，也无法对单轮澄清/拒答 outcome 和多轮失败后状态恢复进行统一、可重复的评测。

## Solution

Evaluation 将自然语言查询能力组织为三个逻辑独立的评测集：

1. **单轮查询测试集**：每条案例独立运行，不携带或继承其他案例上下文。
2. **多轮对话测试集**：每条案例代表一个完整 Conversation；同一场景的轮次复用同一会话状态，场景之间隔离。
3. **经营分析测试集**：沿用已有经营分析案例与分层判定规则。

三类评测集可分别运行和报告；各自统计分母，不合并成一个跨类别准确率。Query Understanding 的语义回归集继续作为辅助评测，不作为第四种面向业务能力的测试集。

### 单轮查询覆盖范围

单轮集合覆盖：

- 指标查询；
- 时间过滤；
- 维度分组；
- 条件过滤；
- 排序 / TopN；
- 阈值 / HAVING；
- 多指标；
- 指标别名；
- 澄清 / 拒答；
- 组合场景。

成功查询案例通过正式授权查询入口运行。期望结果由标准 SQL 生成，并与系统实际执行结果按现有结果比较 Contract 比较。澄清和拒答案例不要求标准 SQL，按案例声明的期望 outcome 判断；意外技术错误或不匹配的业务 outcome 记为失败。

### 多轮对话覆盖范围

多轮集合覆盖：

- 指标替换；
- 时间替换；
- 维度追加；
- 维度替换；
- 失败轮次不污染上下文。

Filter 追加和 Filter 替换暂不纳入当前评测集：原案例依赖尚未确认可稳定检索的客户类型筛选字段。当前不对这两项能力报告覆盖率。

同一 Conversation 按顺序执行，轮次共享服务端会话状态。成功轮次分别与对应的标准结果比较。需要检查失败轮次状态隔离的场景，应在失败后继续发起成功追问，并验证该追问仍基于失败前最后一次成功状态。一个 Conversation 的全部期望轮次及状态检查通过后，该 Conversation 才计为 PASS。

多轮场景遵循已确认的 Multi-Turn Query Contract：只有成功查询更新结构化状态；失败、澄清、范围拒绝和下游错误不更新状态。每轮仍经过当前认证和授权查询入口。

### 经营分析

经营分析仍使用现有独立评测器和黄金案例，保留计划、Task 执行、报告证据和端到端分层判定，不折算为普通 SQL 结果准确率。

## User Stories

- 作为 Evaluation 维护者，我希望单轮、多轮和经营分析有清楚独立的案例集合及报告，以便分别看到各类能力表现。
- 作为模型/查询链路维护者，我希望单轮成功结果按真实执行数据判定、澄清和拒答按期望 outcome 判定，以便业务拒绝不被误判为 SQL 执行失败。
- 作为多轮能力维护者，我希望以完整共享会话的场景评测状态修订和失败恢复，以便验证追问继承与失败隔离。

## Implementation Decisions

- 三类集合是顶层业务评测类别；单轮现有 `simple / medium / complex` 可继续作为单轮集合内部分类。
- 单轮案例互相隔离；不得在单轮案例之间传递 `conversation_id` 或结构化查询状态。
- 多轮案例以 Conversation 为计分单位；单条 Conversation 内按轮次顺序共享会话，同一轮不可被当作另一个独立案例执行。
- 多轮评测通过正式 `POST /api/v1/query` Application 入口执行；每个 Conversation 的首轮不携带 `conversation_id`，后续轮次复用成功响应返回的同一 ID，每个场景使用新的客户端 / 会话 Store。
- 经营分析保持现有专用 Runner；使用既有案例、分层指标和独立报告。
- 成功结果不比较生成 SQL 文本；继续使用 SQL Guard、同一只读数据库执行器和当前确定性结果比较规则。
- 单轮成功查询使用 `result_match` outcome，要求原始问题走正式授权查询链路，标准 SQL 走 PostgreSQL 只读执行器，并且系统执行结果与标准结果一致；澄清使用 `clarification_required` outcome，对应 `QueryFailure.error_code=CLARIFICATION_REQUIRED`；拒答使用 `cannot_answer` outcome，对应 `QueryFailure.error_code=CANNOT_ANSWER`。返回结果不匹配预期 outcome 或结果数据不一致时记为 FAIL。
- `Execution Accuracy` 只统计有效 `result_match` 案例；澄清 / 拒答案例单独统计 `Outcome Accuracy`；需要整体观察时报告 `Case Accuracy`，不把 expected refusal 混入 SQL 执行准确率。
- 任一预期 outcome 出现非预期技术错误时记为 FAIL；标准案例或标准 SQL 本身无效时沿用 `INVALID_CASE`，不计入能力准确率分母。
- 三类分别选择/运行并分别生成报告，不生成跨类别总准确率；各报告只与同一评测集的兼容基线比较。
- 本 Feature 组织三类离线 Evaluation。后续确认的单轮利润口径歧义属于窄范围行为修复：未限定的“利润”返回 `CLARIFICATION_REQUIRED`；其他 Online Query、多轮会话和 Business Analysis Contract 保持不变。

## Testing Decisions

### Software Test

- 单轮 Runner 证明每条案例只调用一次公开授权查询入口，不继承其他案例的上下文。
- Outcome 案例验证预期澄清/拒答通过、错误 outcome 失败、技术错误不会被算作预期拒答。
- 单轮未限定的“利润”必须在 Query Understanding / Retrieval 前返回 `CLARIFICATION_REQUIRED`；不支持的问题（如员工人数）继续返回 `CANNOT_ANSWER`。
- 多轮 Runner 验证同一 Conversation 的请求使用同一会话状态，多个 Conversation 之间状态隔离。
- 多轮每轮结果按既有结果比较规则计分；失败轮次之后的有效追问证明状态未污染。
- 若任一轮或最终状态检查不符合预期，则该 Conversation 为 FAIL，并在报告保留轮次级诊断。
- 经营分析保持现有专用评测测试和验收，不改变判定规则。
- 测试使用假的 LLM / Query / Database 边界；Software Test 不调用真实外部 LLM。

### AI Evaluation

- 单轮评测仍通过现有正式 Online Query 链路；成功案例比较执行结果，outcome 案例比较业务结果。
- 多轮评测使用与正式入口一致的认证、授权、会话 Application、Online Query、Retrieval、SQL Guard 和只读数据库链路。
- 多轮每个 Conversation 顺序执行并作为一个计分单位；报告提供会话结论及轮次级结果。
- 真实 LLM 评测需遵循仓库外部调用授权要求；不得在未获授权时发送测试问题和结构上下文。
- Evaluation cases 属于仓库认定的高风险改动；形成 candidate 后按仓库门禁运行本地完整 Real E2E，并如实区分 Software Test、AI Evaluation、Business Acceptance 和 Real E2E 证据。

### Business Acceptance

- 人工确认三类集合边界、报告分类以及单轮 outcome 案例判定符合预期。
- 人工确认多轮的追加、替换和失败恢复场景确实表现为同一 Conversation 的状态变化。

## Out of Scope

- 除单轮已确认的利润口径澄清外，不修改 Online Query、Query Understanding、SQL 生成、Retrieval、授权或会话业务行为。
- 增加 UI、API、调度服务或在线 Evaluation 能力。
- 把 Query Understanding 语义评测合并为第四类业务测试集。
- 重新定义 Business Analysis 计划、Task 或报告的准确率口径。
- 自动改写案例、模型自修复、LLM Judge 或跨类别总分。
- 未经授权运行真实 LLM Evaluation。

## Further Notes

- 实施前普通查询集有 21 条 `simple / medium / complex` 案例；本次补充后为 27 条，其中 25 条结果比对、2 条澄清 / 拒答 outcome 案例。
- 当前经营分析集为 `src/evaluation/business_analysis_cases.json` 中的 5 条案例，已具备专用 Runner 和分层报告。
- 初始多轮评测集新增 7 个 Conversation 场景，覆盖指标/时间替换、Filter 追加/替换、维度追加/替换和失败状态隔离。
- 当前多轮规格和验收已固定失败不提交状态等 Contract；新的工作补充的是 Evaluation Dataset / Runner / Report 证据，不重开多轮业务决策。
- 当前 Query Understanding 辅助集有 6 条案例，不纳入三个顶层能力集。
- 2026-09-27 首次确认的评测集调整：F01 移除企业客户筛选；多轮 Filter 追加 / 替换案例暂时移除；失败状态隔离场景保留并移除企业客户条件。当前多轮集合为 5 个 Conversation、11 轮，暂不声称覆盖 Filter 追加 / 替换。
- 2026-09-27 后续修复确认：F01 改为已登记的华东销售区域筛选，避免与 T01 重复；R01 只测试未限定“利润”的指标歧义，并继续期望 `CLARIFICATION_REQUIRED`。在线查询在语义入口确定性识别该歧义；其他不支持问题仍返回 `CANNOT_ANSWER`。旧评测报告对应调整前的案例，不能作为当前集合的准确率。
- 新建多轮标准案例的数量、文件布局、CLI 参数、独立报告文件形状和 expected outcome 的字段编码留给 Implementation Design；不得改变本 Spec 的行为边界。
- 事实来源：`docs/specs/evaluation.md`、`docs/specs/query-api.md`、`.scratch/multi-turn-conversation-v1/spec.md`、`.scratch/business-analysis-v1/spec.md` 及对应验收记录。
