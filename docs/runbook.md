# ChatBI Runbook（运行手册）

## 1. 用途与边界

本文档用于本地 ChatBI POC 的启动、验证、RAG Offline Build（RAG 离线构建）、评测和停止。

当前系统是本地单用户、同步运行的 POC，不是 Production Ready（生产可用）部署。本文档中的命令默认在仓库根目录执行：

`E:/Kaifa/project 2026/chatbi-engine`

当前运行边界：

- PostgreSQL 保存 `mart_sales` 业务数据，使用 `chatbi_app` 只读身份执行查询。
- FastAPI 提供 Query API（查询接口）。
- Streamlit 是当前 POC 页面。
- BGE-M3 和 Qdrant 用于离线检索资产构建、评测，以及 Online Retrieval V1 的在线查询向量和上下文检索。
- 已发布 RAG 资产默认接入 Online Query V1：实体类、单指标和多指标问题统一走 `metrics=0/1/N` 动态检索上下文；在线 RAG 技术故障 Fail Closed（失败关闭）并返回 `CONTEXT_ERROR`，不回退静态全量 Schema。多指标最多 5 个，直接关系只使用认证 FK→PK 和 `LEFT JOIN`。

## 2. 系统拓扑

```text
PostgreSQL（127.0.0.1:5433）
    └─ mart_sales / chatbi_app 只读

Qdrant（127.0.0.1:6333）
    └─ TABLE / COLUMN / METRIC 版本化集合

FastAPI（127.0.0.1:8000）
    └─ Online Query + SQL Guard + PostgreSQL

Streamlit（127.0.0.1:8501）
    └─ HTTP 调用 FastAPI
```

## 3. 首次准备

### 3.1 环境要求

- Windows PowerShell。
- Python 3.11。
- `uv`。
- Docker Desktop。
- 可用的 LLM 配置，用于 Online Query 和真实 Evaluation。
- 本地 `models/bge-m3`，用于 RAG Offline Build 和 Online Retrieval V1 的查询向量生成。

### 3.2 配置文件

首次使用时复制安全模板：

```powershell
Copy-Item .env.example .env
```

然后在 `.env` 中填写本地真实配置：

- PostgreSQL：`POSTGRES_DB`、`POSTGRES_MIGRATOR_USER`、`POSTGRES_MIGRATOR_PASSWORD`、`POSTGRES_APP_USER`、`POSTGRES_APP_PASSWORD`
- Query API 身份与授权：`CHATBI_ENV`、`CHATBI_IDENTITY_PROVIDER`、`CHATBI_IDENTITY_SUBJECT_ID`、`CHATBI_AUTH_POLICY_FILE`
- LLM：`LLM_API_KEY`、`LLM_MODEL`，必要时填写 `LLM_BASE_URL`
- Qdrant：`QDRANT_API_KEY`
- RAG：通常保持 `RAG_MODEL_DIR=models/bge-m3` 和 `RAG_EMBEDDING_DEVICE=auto`

`.env` 不得提交到 Git。不要在终端回显密码、API Key 或完整连接字符串。

本地 Query API 必须显式选择 `demo` 或 `test` Identity Provider，并配置外部 JSON 授权策略文件。仓库提供的
`config/authorization-policy.example.json` 只包含演示主体 `analyst-1`；实际环境应通过部署配置注入策略文件路径和允许访问的主体。
`production` / `prod` 环境会拒绝启动 `demo` / `test` Provider，不会自动回退到演示身份。当前版本尚未接入企业 SSO。

## 4. 启动基础设施

启动 PostgreSQL 和 Qdrant：

```powershell
docker compose up -d postgres qdrant
docker compose ps
```

预期：

- PostgreSQL 状态为 `healthy`。
- Qdrant 容器处于 `Up`。
- 两个服务只绑定本机回环地址。

健康检查：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:6333/healthz
```

停止基础设施但保留本地数据：

```powershell
docker compose stop postgres qdrant
```

查看容器日志：

```powershell
docker compose logs --tail=100 postgres
docker compose logs --tail=100 qdrant
```

不要在不知道数据归属时执行 reset、reseed 或删除 `data/postgres`、`data/qdrant`。

## 5. 启动 Online Query

### 5.1 一键启动（本地开发）

在项目根目录执行：

```powershell
.\scripts\start-dev.ps1
```

脚本会确认 PostgreSQL 和 Qdrant 已启动，并分别打开 FastAPI、Streamlit 两个可见终端。启动成功后浏览器打开 `http://127.0.0.1:8501`；停止服务时，在两个服务终端中分别按 `Ctrl+C`。

脚本不会自动终止占用 8000 或 8501 端口的现有进程，也不会重建或删除数据库、Qdrant 和本地资产。

### 5.2 手动启动 FastAPI

在一个 PowerShell 窗口执行：

```powershell
uv run uvicorn src.query_api.main:app --host 127.0.0.1 --port 8000
```

检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

预期响应：

```json
{
  "status": "ok"
}
```

`/health` 只表示 HTTP 服务正在运行，不检查 LLM、PostgreSQL 或静态上下文是否可用。

### 5.3 手动启动 Streamlit

在另一个 PowerShell 窗口执行：

```powershell
uv run streamlit run src/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

浏览器打开：

`http://127.0.0.1:8501`

Streamlit 只调用 FastAPI，不直接访问 LLM、SQL Guard 或 PostgreSQL。

### 5.4 Observability / Trace ID（可观测性 / 链路编号）

`POST /api/v1/query` 的成功响应和 HTTP Error 都会在 Response Header（响应头）返回 `X-Trace-ID`。Trace ID 不属于 Query API JSON Body（响应体）字段；只读取这个单独的 Header，不要打印或复制完整请求头、响应头。

取得链路编号的方式：

- 直接调用 Query API 时，从成功响应或 HTTP Error 的 `X-Trace-ID` Header 读取；错误响应仍优先查看现有 `error_code`、`error_message` 和 `request_id`。
- 使用 Streamlit 时，从成功页面或错误页面的“链路编号：<trace_id>”读取；“请求编号：<request_id>”仍保持独立显示。
- Header 缺失时不代表查询失败，也不应人为把 JSON Body 中的字段当作 Trace ID。

定位一次查询时，以同一个 `trace_id` 从 `query.request` 根节点开始，依次查看固定节点：

```text
query.request -> retrieval -> llm -> sql -> database
```

优先结合固定 `status`、`error_code`、节点耗时和 `trace_id` 判断失败节点或最慢节点。Production（生产）只查看这些固定状态、错误码、耗时和链路编号；不要查看或传播原始异常、Prompt、候选/最终 SQL、RAG 正文、结果行、API Key 或完整请求头。

如果没有配置或连接 Trace Exporter（链路导出器），服务仍可以正常运行，Query API 仍会返回链路编号；这只表示本地链路上下文可用，不等于 Trace 已经导出到后端。`GET /health` 只检查 HTTP 服务存活，不创建 Query Trace，因此正常不会返回 `X-Trace-ID`。

## 6. 构建 RAG Offline 资产

RAG Offline Build 读取以下权威事实源：

- `src/structure/generated/tables.json`
- `src/structure/generated/columns.json`
- `src/structure/generated/relationships.json`
- `src/semantic/metrics.json`

使用唯一的构建 ID 执行：

```powershell
uv run --env-file .env python -m src.rag_offline --build-id 20260906-bge-m3-v2
```

构建成功后会：

1. 创建新的 TABLE、COLUMN、METRIC Qdrant 集合。
2. 生成关系图。
3. 校验数量和检索。
4. 写入 `data/rag/<build_id>/manifest.json`。
5. 原子更新 `data/rag/current.json`。

构建失败时，旧的 `current.json` 和旧版本集合应保持不变。

检查当前发布资产：

```powershell
uv run --env-file .env python -c "from src.rag_offline import OfflineBuildConfig,load_published_asset; c=OfflineBuildConfig.from_environment(); a=load_published_asset(c.output_dir); print(a.build_id, a.manifest['status'], dict(a.collection_names))"
```

当前已经验证的资产：

```text
build_id: 20260906-bge-m3-v2
TABLE: 7
COLUMN: 69
METRIC: 5
Relationship Edge: 9
status: READY
```

## 7. 运行测试

### 7.1 纯软件回归

```powershell
uv run --with pytest python -m pytest -q
```

### 7.2 包含本地 PostgreSQL 集成测试

该命令会验证真实只读事务、查询超时、结果截断、写操作拒绝和固定 SQL 的服务链路：

```powershell
$env:RUN_DATABASE_TESTS = '1'
uv run --env-file .env --with pytest python -m pytest -q
```

本命令会接触本地 PostgreSQL，本次交付不代替用户重新执行；运行前需再次确认数据库状态，并以终端输出作为当前证据。当前不依赖外部服务的全量回归结果为 `251 passed, 6 skipped, 85 subtests passed`；其中真实 LLM、数据库等外部集成测试仍按显式开关单独执行，不能用纯软件测试替代。

### 7.3 GitHub Actions CI

`.github/workflows/ci.yml` 在 `master` 的 Push、Pull Request 和手动触发时执行锁文件检查、纯软件回归、PostgreSQL 集成测试和 API/Streamlit 启动 Smoke Test（冒烟测试）。CI 使用 Python 3.11 和锁定的 `uv` 版本；PostgreSQL 集成测试使用 `database/ci/bootstrap.sql` 中的 CI-only 合成 Fixture（测试夹具），不使用本地业务数据。CI 不调用真实 LLM，也不替代 AI Evaluation（AI 评测）或 Business Acceptance（业务验收）。

### 7.4 PR 前本地验收流程

PR（Pull Request，合并请求）不按固定 commit 数量创建。一个 PR 对应一个清晰目标；多个相关 commit 可以属于同一个 PR，较大功能按逻辑边界拆分。开发过程中先运行针对性测试，准备提交 PR 的最终 candidate commit（候选提交）再进行一次完整本地验收。

推荐顺序：

```text
逻辑阶段 commit
→ 运行 targeted tests（针对性测试）
→ Agent 判断是否已经形成 candidate commit
→ Agent 提醒用户准备 PR
→ 用户确认
→ 确认 git_dirty=false
→ 必要时更新本地 RAG asset（资产）
→ 运行完整 Real E2E
→ 21/21 通过且 Execution Accuracy=100%
→ Push 并创建或更新 PR
```

Agent 的提醒必须明确说明：用户这一次确认会授权先执行本地最终验收，并且在完整 E2E 通过后 Push、创建或更新 PR。用户确认前，Agent 不 Push、不创建 PR。确认后如果完整 E2E 失败，不提交 PR；修复后必须重新形成 candidate commit 并重新验证。完整 E2E 通过后又修改 Retrieval、Prompt、RAG、LLM 或 Evaluation cases 等行为代码时，必须重新运行。

最终 candidate commit 的本地检查可以使用：

```powershell
git status --short --branch
uv run --with pytest python -m pytest -q
uv run --env-file .env python -m src.evaluation --online-retrieval
git status --short --branch
```

如果改动影响结构 Metadata、`metrics.json`、离线构建逻辑、Embedding 配置或已发布集合，先按本地 RAG Offline Build 流程更新资产，再运行上述 Evaluation。文档、注释、纯 CI 或不影响运行行为的修改不要求完整 Real E2E。

## 8. 运行真实 LLM Evaluation

真实评测会向配置的外部 LLM 发送 21 条测试问题以及结构和指标上下文。执行前必须确认：

- 当前网络和 LLM 配置可用。
- 允许发送这些测试数据。
- PostgreSQL 和 `chatbi_app` 可用。

执行：

```powershell
uv run --env-file .env python -m src.evaluation --online-retrieval
```

### 8.1 Worktree 与本地 RAG 资产

`.env`、`data/rag/` 和 `models/bge-m3/` 是本地 ignored（被 Git 忽略）资产，`git worktree` 或干净 clone 只会取得 Git 已跟踪的代码，不会自动复制这些文件。进入新的 worktree 运行真实评测前，先确认当前环境中的资产存在：

```powershell
Test-Path -LiteralPath '.env'
Test-Path -LiteralPath 'data/rag/current.json'
Test-Path -LiteralPath 'models/bge-m3'
```

如果代码位于新的 worktree，但 RAG 资产保存在已有主工作区，应将 `RAG_OUTPUT_DIR` 和 `RAG_MODEL_DIR` 指向主工作区的绝对路径；不要让相对路径在新 worktree 中解析出另一份模型路径。`.env` 可以继续通过本机环境或评测命令注入，不要复制到 Git。

`--online-retrieval` 会在执行标准案例前完成一次 RAG Preflight（RAG 前置检查）。如果发布指针、Manifest、Embedding Model、向量集合或运行时依赖不可用，评测会直接输出单个前置错误并退出，不会把所有案例伪装成业务失败。

指定历史报告进行回退比较：

```powershell
uv run --env-file .env python -m src.evaluation --online-retrieval --baseline reports/evaluation/<previous-report>.json
```

`--online-retrieval` 是真实 RAG 验收的必要开关；不带该参数的入口只适合显式静态上下文的确定性软件测试，不代表在线 RAG 技术故障可以回退静态 Schema。

报告输出到：

```text
reports/evaluation/<run_id>.json
reports/evaluation/<run_id>.md
```

评测结果属于 AI Evaluation（AI 评测），不能与 Software Test（软件测试）或 Business Acceptance（业务验收）混为一类。

评测命令在存在 `FAIL` 或 `INVALID_CASE` 时返回非零退出码；只有所有案例有效且通过时才返回 `0`，可直接作为 CI 门禁。

## 9. 典型故障处理

### API 无法启动

依次检查：

1. `.env` 是否包含 LLM 和 PostgreSQL 必需配置。
2. PostgreSQL 是否处于 `healthy`。
3. 静态事实文件是否存在且为合法 JSON。
4. 是否已有进程占用 8000 端口。

### 页面无法连接

检查 FastAPI：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Streamlit 的 `CHATBI_API_BASE_URL` 默认是 `http://127.0.0.1:8000`；只有 API 使用其他地址时才需要修改。

### 查询被拒绝

检查返回的 `error_code`：

- `CANNOT_ANSWER`：当前结构和指标无法回答。
- `SQL_REJECTED`：LLM SQL 候选未通过 SQL Guard。
- `DATABASE_ERROR`：数据库连接或执行失败。
- `QUERY_TIMEOUT`：查询超过 10 秒。

不要手工绕过 SQL Guard，也不要把模型输出直接复制到数据库执行。

### RAG 构建失败

检查 CLI 输出中的失败分类：

- `SOURCE`：事实源问题。
- `EMBEDDING`：BGE-M3 或向量输出问题。
- `VECTOR_STORE`：Qdrant 连接或写入问题。
- `VALIDATION`：文档、数量或维度问题。
- `FILESYSTEM`：本地目录或权限问题。

先确认 `current.json` 仍指向旧版本，再处理失败构建；不要直接删除旧集合。

## 10. 当前明确边界

当前已经完成：

- Online Query POC。
- Query API。
- Streamlit 页面。
- Evaluation 评测模块。
- RAG Offline Build、BGE-M3 和 Qdrant 离线资产。

当前已完成：

- Online Retrieval V1。
- Schema Linking。
- 关系图在线路径搜索。
- RAG 上下文接入 Online Query。

当前仍属于后续边界：

- 多轮对话和复杂分析 Agent。
- 认证、租户、审计、限流、监控和生产部署。

下一阶段如果继续，应单独设计多指标组合编排和生产化治理；当前 V1 已完成最小在线检索闭环。
