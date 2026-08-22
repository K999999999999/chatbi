# ChatBI 当前模块与分层映射 v0.1

状态：Proposed（分层设计草案；当前仅完成源码目录扁平化，模块分层尚未开始）
依赖文档：[平台接入通用契约 v0.1](./platform-integration-contract-v0.1.md)

## 1. 目标

把当前可运行的 Text2SQL POC 映射到 Modular Monolith（模块化单体）的模块和分层中，先确定边界，再进行最小代码改造。

本阶段不做：

- 微服务拆分。
- HiMarket / Higress 安装或接入。
- HTTP API 实现。
- 数据库结构或数据修改。
- 重新设计 LLM 生成链。

## 2. 当前事实

当前主链路为：

```text
CLI
→ QueryParser
→ PromptBuilder
→ OpenAI-Compatible LLM
→ SQL Guard
→ chatbi_app 只读 PostgreSQL
→ 结构化结果
```

当前 POC 已经具备：

- `mart_sales` 结构目录和关系目录。
- 指标文件 `metrics.json`。
- 直接 LLM 生成 SQL。
- SQL 只读、安全词和 Schema 白名单检查。
- `chatbi_app` 只读账号、Statement Timeout 和最大结果行数。
- CLI 入口和真实执行验收。

## 3. 目标依赖方向

```text
Interfaces / Adapters
          ↓
Application
          ↓
Domain + Ports
          ↑
Infrastructure Adapters
```

约束：

- Domain 不依赖 OpenAI、PostgreSQL、HiMarket、Higress 或 HTTP。
- Application 不依赖具体 Provider SDK。
- Infrastructure 实现 Ports，不定义业务真相。
- CLI、未来 HTTP 和未来公司中台只负责进入 Application。
- 平台适配器不进入 Query、Semantic 或 SQL Safety 核心模块。

## 4. 当前文件映射

| 当前路径 | 当前职责 | 目标模块 / 分层 | 处理意见 |
|---|---|---|---|
| `src/cli.py` | CLI 参数、依赖组装、JSON 输出 | `interfaces/cli` + `bootstrap` | 保留入口；后续拆出组装和响应映射 |
| `src/__main__.py` | CLI 启动转发 | `interfaces/cli` | 保留 |
| `src/pipeline.py` | 查询链编排、POC 响应结构 | `application/query` | 目标改成 `QueryService`，暂不改变行为 |
| `src/query_parser.py` | 非空输入校验 | `application/query` | 保留最小职责，不增加规则解析 |
| `src/prompt_builder.py` | Schema、指标、规则、Few-shot 组装 | `application/query/prompting` | 暂时保留；不把 Prompt 文本当作平台能力 |
| `src/semantic/catalog.py` | 指标定义、指标匹配、指标校验 | `domain/semantic` | 后续拆模型与文件加载 |
| `src/semantic/metrics.json` | 指标事实文件 | `infrastructure/metadata` 输入 | 保留为外部事实源 |
| `src/structure/catalog.py` | 表、字段、关系模型和 JSON 读取 | `domain/structure` + `infrastructure/metadata` | 模型与加载器后续拆开 |
| `src/structure/generated/*.json` | 数据库结构生成物 | `infrastructure/metadata` 输入 | 保留生成边界，不手工改运行时结构 |
| `src/sql_guard.py` | 只读 SQL 和物理结构安全校验 | `domain/sql_safety` | 保留为确定性安全策略 |
| `src/llm_client.py` | LLM Port、OpenAI SDK、响应清理 | `ports/llm` + `infrastructure/llm` | 先抽 Port，再拆实现 |
| `src/executor.py` | Query Result、数据库执行、psycopg、只读配置 | `ports/query_executor` + `infrastructure/postgres` | 先抽执行契约，再拆实现 |
| `src/config.py` | 环境变量和 LLM 配置 | `infrastructure/config` | 保留基础设施职责 |
| `src/evaluation.py` | 执行结果比较辅助 | `evaluation` | 不进入运行时模块 |
| `scripts/metadata/export_schema.py` | Schema 导出脚本和环境加载 | `tooling/metadata` | 运行时不应依赖该脚本模块 |
| `tests/**` | 软件测试和 AI Evaluation | `tests` / `evaluation` | 保持与运行时边界分离 |

## 5. 当前依赖问题

### 5.1 Pipeline 依赖具体执行器

当前 `pipeline.py` 使用具体的 `QueryExecutor` 类型。目标是让 Application 只依赖：

```text
QueryExecutorPort.execute(ValidatedSql) -> QueryResult
```

PostgreSQL 只是该 Port 的一个实现。

### 5.2 LLM Port 和 Provider 实现混合

当前 `llm_client.py` 同时包含 `LlmClient` Protocol 和 OpenAI-Compatible 实现。目标是：

```text
ports/llm.py
└── LlmClient

infrastructure/llm/openai_compatible.py
└── OpenAICompatibleLlmClient
```

Application 只依赖 `LlmClient`。

### 5.3 Runtime 依赖 scripts

当前 `config.py` 和 `executor.py` 使用 `scripts/metadata/export_schema.py` 中的 `load_env`。这会让运行时模块反向依赖脚本目录。

目标是把环境配置加载能力放入运行时基础设施配置模块，Schema 导出脚本只调用公共配置能力，不被运行时反向调用。

### 5.4 Semantic 和 Structure 的加载职责混合

当前 Catalog 同时承担事实模型和 JSON 文件加载。目标是：

```text
Domain Model / Catalog Contract
          ↑
JSON Metadata Adapter
```

当前不改变指标和结构数据，只调整责任位置。

## 6. Query 模块首个 Contract

### 6.1 Application 用例

```text
QueryService.execute(QueryCommand) -> QueryOutcome
```

### 6.2 QueryCommand

```text
QueryCommand
├── question       必填，自然语言问题
└── context        RequestContext
```

其中 `RequestContext` 来自平台接入通用契约，当前 CLI 使用本地调用上下文。

Application 不接收 HTTP Request、平台 SDK 对象或原始 Authorization Header。

### 6.3 QueryOutcome

```text
QueryOutcome
├── success
├── request_id
├── result_set，可选
│   ├── columns
│   └── rows
├── metric_codes，可选
├── validated_sql，可选，仅供受控调试
└── failure，可选
```

### 6.4 QueryFailure

```text
QueryFailure
├── code
├── message
├── retryable
└── retry_after，可选
```

Query 模块使用平台无关错误码，例如：

- `invalid_request`
- `unsupported_question`
- `query_rejected`
- `query_execution_failed`
- `provider_unavailable`
- `internal_error`

外部平台的认证、权限和网关错误由 Adapter 映射到平台接入契约；Query 模块不依赖具体平台错误类型。

## 7. Query 模块内部节点

```text
QueryService
├── QueryParser
├── PromptBuilder
├── LlmClient Port
├── SqlGuard
└── QueryExecutor Port
```

主链不变：

```text
question
→ parse
→ prompt
→ LLM SQL candidate
→ deterministic SQL Guard
→ read-only execution
→ QueryOutcome
```

不允许：

- LLM 直接调用数据库。
- CLI 绕过 QueryService 调用数据库。
- Application 绕过 SQL Guard 调用 Query Executor。
- 平台 Adapter 直接拼接或执行 SQL。
- QueryService 根据平台名称分支业务逻辑。

## 8. 第一轮实现边界

第一轮只做 Port 和 Application 边界，不移动所有目录：

1. 定义 `QueryService` 的应用契约。
2. 将 LLM Port 从 OpenAI 实现中分离。
3. 将 Query Executor Port 从 PostgreSQL 实现中分离。
4. 让当前 Pipeline 依赖两个 Port。
5. CLI 继续负责具体实现的组装。
6. 保持当前 JSON 输出和查询行为不变。

第一轮不做：

- 新增 HTTP。
- 新增 HiMarket / Higress Adapter。
- 改变 Prompt 规则。
- 改变 SQL Guard 策略。
- 改变数据库账号或数据库结构。
- 把所有文件一次性搬到新目录。

## 9. 验收标准

第一轮模块化实现完成后必须满足：

1. CLI 仍然可以执行当前查询链。
2. Application 不导入 OpenAI SDK 或 psycopg。
3. Domain 不导入平台 SDK、HTTP 或数据库驱动。
4. PostgreSQL Adapter 仍使用 `chatbi_app` 只读账号。
5. SQL Guard、Statement Timeout 和最大行数不变。
6. 现有 POC 软件测试通过。
7. 真实 LLM Execution Accuracy 仍保持当前验收结果。
8. `git diff --check` 通过。
9. 不新增数据库修改，不暴露 Secret。

## 10. 下一步

下一步进入实现前，先完成 Query 模块的 Module Implementation Design：

- 明确 `QueryService`、`LlmClient Port`、`QueryExecutor Port` 的代码落位。
- 明确失败类型和测试替换点。
- 明确旧 `PocResponse` 与新 `QueryOutcome` 的兼容策略。
- 明确只改 Query 模块，不扩展到平台接入和微服务。
