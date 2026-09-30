# Evaluation Module Spec

## 目标

使用固定标准测试集调用现有 Online Query（在线查询）系统，比较系统结果与标准结果，建立能力 Baseline（基线），并在后续变更后识别 Regression（能力回退）。

Evaluation（评测）是离线回归评测工具，不参与用户在线请求，也不维护另一套 SQL 生成系统。

## 运行方式

- 离线、批量、顺序执行。
- 单轮案例独立运行；多轮按完整 Conversation（对话场景）运行。
- 单条案例或场景失败不得中断后续案例。
- 第一轮建立 Baseline，不设置准确率门槛。
- 后续使用同一测试集和同一比较规则复测，并与上一份有效报告比较。

Evaluation Module 不设对所有产品版本通用的准确率门槛；当前 MVP 生产准备基线另有明确验收要求：在最终 clean commit 上，必需套件必须各自 `0 FAIL`、`0 INVALID_CASE`。该要求不改写此模块的通用报告与比较 Contract。

面向业务能力的评测集分为三类，分别运行并分别出报告：

| 评测集 | 案例文件 | 运行参数 | 计分单位 |
|---|---|---|---|
| 单轮自然查询 | `evaluation/suites/single_turn/cases.json` | `--single-turn`（默认模式） | 单条问题 |
| 多轮自然查询 | `evaluation/suites/multi_turn/cases.json` | `--multi-turn --online-retrieval` | 完整 Conversation |
| 经营分析 | `evaluation/suites/business_analysis/cases.json` | `--business-analysis --online-retrieval` | 单条经营分析场景 |

实现按 `evaluation/common/` 的共享能力和 `evaluation/suites/<suite>/` 的套件实现分类；每个套件的案例文件与对应代码放在同一目录。确定性软件测试按相同套件边界放在 `tests/evaluation/<suite>/`，公共能力测试放在 `tests/evaluation/common/`。

当前仓库中的集合规模为：单轮 29 个案例、多轮 7 个 Conversation / 15 个轮次、经营分析 10 个案例。`evaluation/suites/query_understanding/cases.json` 有 6 个辅助语义案例；它不替代上述三类业务套件。数量应从相应案例文件读取，不用历史报告数量推断。

经营分析案例使用通用语义任务描述，不在案例中绑定 SQL 或固定数值。成功案例由两个独立的 LLM Judge 分别评估任务拆解覆盖度和总结质量；任一维度失败都不跳过另一维度。澄清与拒绝案例按预期结果类型和错误码确定性评估。结果报告分别给出结果类型、任务拆解、总结质量和端到端准确率。Query Understanding（查询理解）语义集是辅助回归，不是第四类业务评测集。

Query Understanding 语义评测单独运行：

```text
uv run --env-file .env python -m evaluation --query-understanding
```

该模式只调用 Query Understanding Adapter，不连接 PostgreSQL、不执行 SQL，适合快速判断结构化语义和失败原因；它不属于普通 CI，也不替代完整 Online Retrieval Real E2E。

## 输入

### 标准测试集

默认读取 `evaluation/suites/single_turn/cases.json`。每条案例包含：

```text
id
schema_name
category
question
description
expected_sql（`result_match` 必填）
expected_outcome（可选，默认 `result_match`）
expected_error_code（非 `result_match` 必填）
coverage（可选，场景覆盖标签数组）
order_sensitive（可选，默认 false）
```

- `question` 必须通过绑定显式测试身份的正式 `BoundAuthorizedQueryService`，由其调用下游 `OnlineQueryService.execute()`。
- `expected_sql` 只用于生成标准结果，不得替代系统生成 SQL。
- 标准 SQL 仍须经过现有 SQL Guard（SQL 安全校验），并使用同一个只读数据库执行器。
- `result_match` 案例中，原始 `question` 走正式授权查询链路；`expected_sql` 走 PostgreSQL 只读执行器。评测比较两边的执行结果，不比较 SQL 文本。
- `clarification_required`、`cannot_answer` 或 `query_failure` 案例不执行标准 SQL；按 `expected_error_code` 与系统返回的业务错误码精确比较。
- 单轮 `coverage` 用于统计指标、时间、维度、条件过滤、TopN、HAVING、多指标、别名、澄清、拒答和组合场景；`category` 继续表示 `simple / medium / complex` 难度。
- 当前 Online Retrieval V1 的标准 Join 必须使用关系图认证的直接 `LEFT JOIN`；中间表、多跳 Join 和未认证 Join 不属于标准案例。

多轮案例的顶层记录代表一个完整 Conversation，`turns` 按顺序包含 `question`、期望 outcome / 错误码，以及成功轮次的 `expected_sql`。一个 Conversation 使用全新的服务端会话；首轮成功响应给出的 `conversation_id` 用于该场景后续轮次，同一测试集中的其他场景不复用此 ID。评测通过正式 `POST /api/v1/query` Application 入口执行，并使用显式 Evaluation 测试身份及授权策略。

失败轮次必须声明期望错误码；失败后继续执行有效追问，以结果比较确认会话保留在失败前最后一次成功状态。失败轮次若意外成功、返回错误码不符，或影响后续结果，该 Conversation 记为失败。

当前标准多轮集合包含 7 个 Conversation、15 个轮次，覆盖指标 / 时间替换、维度追加 / 替换、Filter 追加 / 替换和失败状态隔离。Filter 案例使用已登记的销售区域及华东、华南值，不依赖企业客户筛选字段。

Query Understanding（查询理解）使用独立的语义评测集
`evaluation/suites/query_understanding/cases.json`。该评测集只验证结构化语义，不执行 Retrieval、SQL Guard 或数据库；其中 `time: null` 表示用户没有提出时间过滤条件，不属于案例缺陷。

### 待评测系统

必须复用正式 Online Query 链路：

```text
question
  -> BoundAuthorizedQueryService.query()
  -> OnlineQueryService.execute()
  -> Prompt
  -> LLM
  -> SQL Guard
  -> PostgreSQL
  -> QuerySuccess 或 QueryFailure
```

Query Understanding 语义评测使用独立链路：

```text
question
  -> QueryUnderstandingAdapter
  -> SemanticQueryCandidate
  -> 确定性 Contract 校验
  -> 比较 query_type、metrics、dimensions、time
  -> 记录 PASS 或 FAIL
```

语义评测与 SQL 执行评测必须同时存在：前者回答“意图是否识别正确”，后者回答“最终查询结果是否正确”。不能只根据 SQL 结果通过推断 Query Understanding 一定正确。

真实 AI Evaluation 必须通过 `--online-retrieval` 装配与生产入口一致的 `OnlineRetriever`；Software Test 可以省略该参数并使用静态 `QueryContext`，以保持确定性和离线性。评测工具不得因此复制一套检索、Prompt 或 SQL Guard 逻辑。

多轮评测必须启用 `--online-retrieval`：首轮需要由正式 Query Understanding / Retrieval 链路生成服务端结构化状态，后续轮次由 Query API Application 管理该状态并继续调用 Online Query。

不得复制或重新实现 Prompt、LLM 调用、SQL Guard、数据库查询和错误转换。

## 单条评测链路

```text
读取测试案例
  -> question 调用 BoundAuthorizedQueryService
  -> expected_sql 生成标准结果
  -> 标准化两边结果
  -> 比较行数、列数和数据值
  -> 记录 PASS、FAIL 或 INVALID_CASE
```

- Online Query 返回失败时，该案例记为 `FAIL`，并保留原始 `error_code`。
- 系统结果与标准结果不一致时，该案例记为 `FAIL`。
- 案例格式错误、标准 SQL 被拒绝或标准 SQL 无法执行时，记为 `INVALID_CASE`，不得计入系统能力失败。
- 任一结果被截断时，当前无法证明完整结果一致，案例记为 `INVALID_CASE`。

## 结果比较规则

- 不比较生成 SQL 和标准 SQL 的文本。
- 忽略结果列名和 SQL Alias（别名）。
- 列数必须一致。
- 列顺序保留，对应位置的数据必须一致。
- 行数必须一致，重复行数量也必须一致。
- `order_sensitive` 未提供或为 `false` 时，忽略行顺序，按完整行的多重集合比较。
- `order_sensitive` 为 `true` 时，逐行比较，行顺序必须一致。
- `NULL` 只与 `NULL` 相等。
- 非数值按实际值比较。
- 数值使用绝对误差和相对误差 `1e-6` 比较。

明确要求排名、升降序、前 N 名或时间顺序的案例，应设置 `order_sensitive = true`。普通聚合和分组统计默认忽略行顺序。

## 输出

### 单条结果

```text
case_id
category
status
generated_sql
query_error_code
failure_reason
failure_stage
internal_reason
duration_ms
```

### 汇总结果

```text
总案例数
有效案例数
PASS 数量
FAIL 数量
INVALID_CASE 数量
Execution Accuracy
Outcome Accuracy
Case Accuracy
Conversation Accuracy（多轮）
coverage 标签准确率
各 category 的案例准确率
failure_stage 和 internal_reason 分布
相对上一份报告的回退案例和改善案例
```

单轮评测分开报告以下准确率：

- `Execution Accuracy = result_match 且 PASS 的有效案例数 / 有效 result_match 案例数`。
- `Outcome Accuracy = 期望失败 outcome 命中的有效案例数 / 有效非 result_match 案例数`。
- `Case Accuracy = 所有 PASS 案例数 / 所有有效案例数`。

多轮评测另外报告 `Conversation Accuracy = 完整 PASS 的有效 Conversation 数 / 有效 Conversation 数`。多轮 `Execution Accuracy` 和 `Outcome Accuracy` 按有效轮次分开计算。经营分析准确率继续按经营分析专用口径报告。`INVALID_CASE` 不进入分母，但必须在报告中明确列出。

每次运行同时生成两份同名报告；报告只作为本地评测产物，不作为 GitHub Issue / PR 或远程交付内容：

- JSON 数据报告：保留机器可读的运行元数据、汇总、单条结果和可选基线比较。
- Markdown 总结报告：明确展示总体结论、成功/失败/无效数量、总体与分类准确率、失败阶段、内部原因、失败案例及原因、基线比较状态和必要运行信息。

数据库型评测复用日常开发数据库 `chatbi_mvp`。expected SQL 与模型 SQL 使用同一 `chatbi_app` 只读账号、数据库配置和查询执行器；不创建独立评测数据库。Query Understanding 语义评测不访问数据库，因此不记录 Sales Mart 数据指纹。

Query 与 Business Analysis 的数据库型报告必须记录当前开发 Seed 版本、Sales Mart 行数 / 日期范围摘要、数据 Hash 和 Hash 算法。数据 Hash 从评测连接实际读取稳定键排序的 Sales Mart 业务表行值计算，报告不包含业务明细行、Secret 或连接地址。

未指定 Baseline 时，Markdown 必须明确写明“本次未执行自动基线比较”，不得暗示能力没有回退。

第一份报告作为 Baseline。存在上一份报告时，仅在以下信息可验证且一致时进行回退 / 改善比较：

- 标准测试集 Hash。
- 实际 Sales Mart 数据 Hash、Hash 算法和数据摘要。
- 标准 SQL 结果 Hash。

缺少必要指纹，或实际 Sales Mart 数据 Hash / 算法 / 摘要不同，必须把比较状态标为 `NOT_COMPARABLE`（不可直接比较），说明原因且不报告回退 / 改善。历史报告缺少数据指纹时按不可比较处理。Seed 版本不同但数据 Hash 一致时可以比较，同时在比较结果中标明 Seed 版本已变化。

可比较时：

- 上次 `PASS`、本次 `FAIL`：Regression（能力回退）。
- 上次 `FAIL`、本次 `PASS`：Improvement（能力改善）。
- 其他情况：能力状态未变化。

## 外部调用边界

- Software Test（软件测试）使用假的 SQL Generator 和测试数据库行为，不调用真实外部 LLM。
- 真实 Baseline 和后续能力回归必须调用配置的真实 LLM，并启用 `--online-retrieval` 验证在线 RAG 链路。
- 调用真实外部 LLM 前，需要明确允许发送测试问题、数据库结构和指标上下文。
- 评测过程不得记录 API Key、数据库密码或其他 Secret。

## 不负责

- 不修改 Online Query 的 Prompt、模型配置和业务逻辑。
- 不新增 RAG、Schema Linking、自动修复、重试或多模型投票。
- 不提供 API、UI、网关、定时任务和在线流量能力。
- 不并发执行案例。
- 不根据第一轮结果自动优化系统。
- 不把评测通过等同于生产可用。

## 验收标准

### Software Test（软件测试）

- 标准测试集加载、案例隔离、结果标准化、行顺序规则、列顺序规则、数值误差、错误记录和汇总统计测试通过。
- 使用假的 `OnlineQueryService` 证明每个问题调用现有公开查询入口，不存在第二套 SQL 生成链路。

### AI Evaluation（AI 评测）

- 使用 `uv run --env-file .env python -m evaluation --single-turn --online-retrieval`，单轮案例能够顺序运行完成；成功查询与标准 SQL 结果比对，澄清/拒答按期望错误码判定。
- 使用 `uv run --env-file .env python -m evaluation --multi-turn --online-retrieval`，完整 Conversation 按顺序运行；首轮创建会话，后续轮次复用同一 `conversation_id`，场景之间隔离。
- 使用 `uv run --env-file .env python -m evaluation --business-analysis --online-retrieval`，运行现有经营分析黄金测试集。
- 使用 `uv run --env-file .env python -m evaluation --query-understanding`，独立验证 `query_type`、`metrics`、`dimensions` 和 `time`，其中没有时间条件的案例必须明确期望 `time = null`。
- 生成包含单条结果的 JSON 数据报告，以及包含总体结论、准确率和失败摘要的 Markdown 总结报告。
- 后续报告能够识别相对上一份有效报告的回退和改善案例。
- 单轮报告展示执行准确率、outcome 命中率和场景覆盖；多轮报告展示 Conversation 结论和轮次级诊断；三类报告不生成跨类别总准确率。

### Business Acceptance（业务验收）

- 人工确认报告能够回答：当前系统答对多少、哪些案例失败、修改后是否发生能力回退。

## 实现设计阶段再决定

- 代码文件落位和最小类型定义。
- 报告文件格式、保存路径和命名方式。
- 上一份有效报告的选择方式。
- 测试命令和真实评测运行命令。
