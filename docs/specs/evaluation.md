# Evaluation Module Spec

## 目标

使用固定标准测试集调用现有 Online Query（在线查询）系统，比较系统结果与标准结果，建立能力 Baseline（基线），并在后续变更后识别 Regression（能力回退）。

Evaluation（评测）是离线回归评测工具，不参与用户在线请求，也不维护另一套 SQL 生成系统。

## 运行方式

- 离线、批量、顺序执行。
- 每个案例独立运行；单条失败不得中断剩余案例。
- 第一轮建立 Baseline，不设置准确率门槛。
- 后续使用同一测试集和同一比较规则复测，并与上一份有效报告比较。

## 输入

### 标准测试集

默认读取 `src/evaluation/eval_cases.json`。每条案例包含：

```text
id
schema_name
category
question
description
expected_sql
order_sensitive（可选，默认 false）
```

- `question` 必须调用正式 `OnlineQueryService`。
- `expected_sql` 只用于生成标准结果，不得替代系统生成 SQL。
- 标准 SQL 仍须经过现有 SQL Guard（SQL 安全校验），并使用同一个只读数据库执行器。

### 待评测系统

必须复用正式 Online Query 链路：

```text
question
  -> OnlineQueryService
  -> Prompt
  -> LLM
  -> SQL Guard
  -> PostgreSQL
  -> QuerySuccess 或 QueryFailure
```

不得复制或重新实现 Prompt、LLM 调用、SQL Guard、数据库查询和错误转换。

## 单条评测链路

```text
读取测试案例
  -> question 调用 OnlineQueryService
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
各 category 的 Execution Accuracy
相对上一份报告的回退案例和改善案例
```

`Execution Accuracy = PASS 数量 / 有效案例数`。`INVALID_CASE` 不进入分母，但必须在报告中明确列出。

第一份报告作为 Baseline。存在上一份有效报告时：

- 上次 `PASS`、本次 `FAIL`：Regression（能力回退）。
- 上次 `FAIL`、本次 `PASS`：Improvement（能力改善）。
- 其他情况：能力状态未变化。

## 外部调用边界

- Software Test（软件测试）使用假的 SQL Generator 和测试数据库行为，不调用真实外部 LLM。
- 真实 Baseline 和后续能力回归必须调用配置的真实 LLM。
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

- 20 条标准案例能够顺序运行完成，单条失败不影响其余案例。
- 生成一份包含单条结果、总体准确率和分类准确率的 Baseline 报告。
- 后续报告能够识别相对上一份有效报告的回退和改善案例。

### Business Acceptance（业务验收）

- 人工确认报告能够回答：当前系统答对多少、哪些案例失败、修改后是否发生能力回退。

## 实现设计阶段再决定

- 代码文件落位和最小类型定义。
- 报告文件格式、保存路径和命名方式。
- 上一份有效报告的选择方式。
- 测试命令和真实评测运行命令。
