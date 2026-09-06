# ChatBI Runbook（运行手册）

## 1. 用途与边界

本文档用于本地 ChatBI POC 的启动、验证、RAG Offline Build（RAG 离线构建）、评测和停止。

当前系统是本地单用户、同步运行的 POC，不是 Production Ready（生产可用）部署。本文档中的命令默认在仓库根目录执行：

`E:/Kaifa/project 2026/chatbi-engine`

当前运行边界：

- PostgreSQL 保存 `mart_sales` 业务数据，使用 `chatbi_app` 只读身份执行查询。
- FastAPI 提供 Query API（查询接口）。
- Streamlit 是当前 POC 页面。
- BGE-M3 和 Qdrant 只用于已完成的离线检索资产构建与评测。
- RAG Offline 资产当前没有接入 Online Query。

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
- Python 3.11 或更高版本。
- `uv`。
- Docker Desktop。
- 可用的 LLM 配置，用于 Online Query 和真实 Evaluation。
- 本地 `models/bge-m3`，用于 RAG Offline Build。

### 3.2 配置文件

首次使用时复制安全模板：

```powershell
Copy-Item .env.example .env
```

然后在 `.env` 中填写本地真实配置：

- PostgreSQL：`POSTGRES_DB`、`POSTGRES_MIGRATOR_USER`、`POSTGRES_MIGRATOR_PASSWORD`、`POSTGRES_APP_USER`、`POSTGRES_APP_PASSWORD`
- LLM：`LLM_API_KEY`、`LLM_MODEL`，必要时填写 `LLM_BASE_URL`
- Qdrant：`QDRANT_API_KEY`
- RAG：通常保持 `RAG_MODEL_DIR=models/bge-m3` 和 `RAG_EMBEDDING_DEVICE=auto`

`.env` 不得提交到 Git。不要在终端回显密码、API Key 或完整连接字符串。

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

### 5.1 启动 FastAPI

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

### 5.2 启动 Streamlit

在另一个 PowerShell 窗口执行：

```powershell
uv run streamlit run src/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

浏览器打开：

`http://127.0.0.1:8501`

Streamlit 只调用 FastAPI，不直接访问 LLM、SQL Guard 或 PostgreSQL。

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
build_id: 20260906-bge-m3-v1
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

当前已验证结果：

```text
133 passed, 1 skipped, 42 subtests passed
```

剩余 1 个 Skip 是真实 LLM 端到端测试，不能用纯软件测试替代。

## 8. 运行真实 LLM Evaluation

真实评测会向配置的外部 LLM 发送 20 条测试问题以及结构和指标上下文。执行前必须确认：

- 当前网络和 LLM 配置可用。
- 允许发送这些测试数据。
- PostgreSQL 和 `chatbi_app` 可用。

执行：

```powershell
uv run --env-file .env python -m src.evaluation
```

指定历史报告进行回退比较：

```powershell
uv run --env-file .env python -m src.evaluation --baseline reports/evaluation/<previous-report>.json
```

报告输出到：

```text
reports/evaluation/<run_id>.json
reports/evaluation/<run_id>.md
```

评测结果属于 AI Evaluation（AI 评测），不能与 Software Test（软件测试）或 Business Acceptance（业务验收）混为一类。

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

当前尚未实现：

- Online Retrieval。
- Schema Linking。
- 关系图在线路径搜索。
- RAG 上下文接入 Online Query。
- 多轮对话和复杂分析 Agent。
- 认证、租户、审计、限流、监控和生产部署。

下一阶段必须先确认 Online Retrieval Module Spec（在线检索模块规格），不能因为 Qdrant 离线资产存在就直接把它接入线上。
