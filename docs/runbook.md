# ChatBI Runbook（运行手册）

## 1. 用途与边界

本文档说明 WSL / Linux 本地开发环境的新 clone 首次准备、日常开发、数据库和索引重建、测试与评测。命令从仓库根目录执行；流程不依赖固定电脑路径，也不使用旧项目的数据目录。

当前开发流程只使用 WSL / Linux 运行 Python、ChatBI 和 RAG 构建，并使用 Docker Compose 运行 PostgreSQL 与 Qdrant。仓库中的 Dev Container 配置文件保留，但不属于当前支持或验收的开发入口。

当前系统是本地开发 / 内部验证环境，不是 Production Ready（生产可用）部署。自动测试使用隔离 PostgreSQL 和 CI Fixture；黄金评测复用开发库 `chatbi_mvp`；生产数据库不属于本文档范围。

按目标选择流程：

- **新 clone 首次初始化：** §3 选择入口 → §4.1–4.3 配置并初始化 PostgreSQL、显式创建首个管理员 → §5 启动 Qdrant → §7 准备模型并构建索引 → §6 启动 ChatBI → §8 确定性验证；真实 LLM 评测见 §9。空 PostgreSQL volume 会自动创建数据库、Schema、固定 RBAC 和 Seed；空 Qdrant 需单独构建索引。
- **日常开发：** §5 启动服务 → §6 启动 ChatBI。PostgreSQL 数据和已发布 Qdrant 索引都会保留；不重播 Seed，也不自动重建索引。
- **重置开发数据库：** 执行 §4.4，只删除当前 Compose 项目的 PostgreSQL volume；账号也会清空，需重新创建管理员。
- **重建 Qdrant 索引：** 按 §7 操作，只处理当前 Compose 项目的 Qdrant volume，不清除 PostgreSQL。

PostgreSQL 和 Qdrant 使用 Compose named volume。日常停止服务不会删除数据；不要使用 `docker compose down -v`。

## 2. 系统拓扑

```text
PostgreSQL（Compose 服务 postgres:5432；宿主机回环端口 5433）
    └─ mart_sales / chatbi_app 只读
    └─ chatbi_control / chatbi_control_user 认证、Session、RBAC、审计

Qdrant（Compose 服务 qdrant:6333；宿主机回环端口 6333）
    └─ TABLE / COLUMN / METRIC 版本化集合

FastAPI（WSL / Linux 内监听 127.0.0.1:8000）
    └─ Online Query + SQL Guard + PostgreSQL

Streamlit（WSL / Linux 内监听 127.0.0.1:8501）
    └─ HTTP 调用 FastAPI
```

## 3. 新 clone 与开发入口

WSL / Linux 是当前唯一支持的本地开发入口。ChatBI 和 RAG 构建命令在 WSL / Linux 进程中运行，PostgreSQL 和 Qdrant 由 Docker Compose 启动。`.env.example` 的 `POSTGRES_HOST=127.0.0.1`、`POSTGRES_PORT=5433` 和 `RAG_QDRANT_URL=http://127.0.0.1:6333` 是该入口使用的连接默认值；Compose 发布端口由 `POSTGRES_PUBLISHED_PORT` 控制，与应用连接端口分开。

首次配置 `.env` 的复制命令见 §4.2。安装 Python 3.11 和 `uv` 后运行 `uv sync --locked`，再按 §1 的首次初始化顺序操作。Compose 发布端口只绑定宿主机回环地址，不能从局域网访问。

## 4. 首次准备

### 4.1 环境要求

- WSL / Linux 终端和可用的 Docker Engine / Compose。
- Python 3.11。
- `uv`。
- 可用的 LLM 配置，用于 Online Query 和真实 Evaluation。
- 首次准备时可访问 Hugging Face 下载固定 revision 的 BGE-M3 模型；模型文件保存在 Git 忽略的 `.model-cache/`。

### 4.2 配置文件

如果尚未按第 3 节创建本地 `.env`，先复制安全模板：

```bash
cp .env.example .env
```

然后在 `.env` 中填写本地真实配置：

- 业务数据库：`POSTGRES_DB`、`POSTGRES_APP_USER`、`POSTGRES_APP_PASSWORD`。`chatbi_app` 只读访问业务库 `chatbi_mvp`。
- ChatBI 应用库：`POSTGRES_CONTROL_DB`、`POSTGRES_CONTROL_APP_USER`、`POSTGRES_CONTROL_APP_PASSWORD`、`CHATBI_ADMIN_SECRET_KEY`。`chatbi_control_user` 只访问应用库，保存账号、Session、固定 RBAC 和审计事件。
- 一次性迁移账号：`POSTGRES_MIGRATOR_USER`、`POSTGRES_MIGRATOR_PASSWORD`、`POSTGRES_CONTROL_MIGRATOR_USER`。迁移账号不进入 API 运行进程。
- 运行模式：`CHATBI_ENV`。真实入口使用应用库内置账号，不再配置 `CHATBI_IDENTITY_PROVIDER`、`CHATBI_IDENTITY_SUBJECT_ID` 或 `CHATBI_AUTH_POLICY_FILE`。
- LLM：`LLM_API_KEY`、`LLM_MODEL`，必要时填写 `LLM_BASE_URL`
- Qdrant：`QDRANT_API_KEY` 默认是仅供回环绑定本地开发的公开值，不要用于共享或生产环境。
- RAG：保持 `RAG_MODEL_DIR=.model-cache/bge-m3-5617a9f61b02` 和 `RAG_EMBEDDING_DEVICE=auto`。
  模型为 `BAAI/bge-m3` revision `5617a9f61b028005a4858fdac845db406aefb181`，dense 维度为 1024。
- `.env.example` 已包含 WSL / Linux 宿主进程使用的 PostgreSQL 和 Qdrant 回环地址；只有本机端口不同于默认值时才需要调整。

`.env` 不得提交到 Git。不要在终端回显密码、API Key 或完整连接字符串。

`CHATBI_ADMIN_SECRET_KEY` 不提供仓库默认值。使用本机密码管理器生成至少 32 字符的随机值并填入 `.env`；不要通过命令行回显、日志或 Git 保存该值。

`src/query_api/config.py` 中的 Static Provider（静态身份适配器）只保留给确定性测试和离线 Evaluation；真实入口 `src/query_api/main.py` 不读取这些配置。`production` / `prod` 环境如果仍注入旧静态身份配置会拒绝启动，也不会自动回退到演示身份。

### 4.3 初始化 PostgreSQL 和首个管理员

先在 `.env` 中准备好本地 PostgreSQL 连接配置，然后启动 PostgreSQL：

```bash
docker compose up -d --wait postgres
```

空的项目 PostgreSQL named volume 首次启动时会自动建立 `chatbi_mvp`、完整 Sales Mart Schema、`chatbi_app` 只读账号和确定性合成开发 Seed，并创建同一 PostgreSQL 服务中的 `chatbi_control` 数据库、运行账号、Schema、固定 RBAC 和权限。只有空数据卷会执行这次初始化；日常重启不会重建或重播 Seed。容器只有在两个数据库、Seed 版本和关键权限检查通过后才报告健康。

更新 Control DB migration 时可单独执行幂等 migration 命令；它不会创建管理员：

```bash
uv run --env-file .env python -m src.chatbi_control migrate
```

首个管理员创建必须显式执行。命令会隐藏读取并确认密码，要求至少 12 位；重复创建会失败：

```bash
uv run --env-file .env python -m src.chatbi_control create-admin --username admin-1
```

管理员密码不放入 `.env.example`、Compose 或 Seed。首次启动和初始化不创建任何用户。API 运行进程只使用 `POSTGRES_CONTROL_APP_PASSWORD`，不使用迁移密码。启动 API 时仍会用 `chatbi_control_user` 检查 `schema_migrations` 中的 `chatbi-control-v1`；Schema 未完整迁移时，认证、SQLAdmin 和查询入口不会启动。

### 4.4 重置 PostgreSQL 开发环境

此命令会先显示并确认当前 Compose 项目拥有的 PostgreSQL named volume，然后只删除 `postgres_data`，重新启动并等待 PostgreSQL、Sales Mart、Control DB 和 Seed 健康：

```bash
uv run python -m scripts.reset_dev_postgres
```

该重置会清除 `chatbi_mvp`、`chatbi_control` 中所有开发数据、账号、Session 和审计记录。它不会删除 Qdrant volume 或其他 Compose 项目的数据。正常启动和关闭使用 Compose 服务命令，不使用 `docker compose down -v`。

重置后需按 §4.3 再次显式创建首个管理员；Qdrant volume 和已发布 RAG 索引仍保留。

### 4.5 登录、首次改密和管理后台

- Streamlit 打开后先使用内置账号登录；首个管理员首次登录必须修改密码。
- HTTP 客户端先调用 `POST /auth/login`，再把返回的 `access_token` 作为 `Authorization: Bearer <token>` 访问 `/auth/me`、`/auth/change-password`、`/auth/logout` 和查询接口。
- 管理员访问 `http://127.0.0.1:8000/admin`，使用同一套 ChatBI 账号。只有 `admin` 角色可以进入 SQLAdmin；`analyst` 只能执行查询。
- SQLAdmin 的用户、角色、权限和审计事件页面使用 `chatbi_control`；用户禁止物理删除，角色 / 权限 / 审计事件只读。
- 审计事件保存登录、密码、用户 / 角色变更、授权决策和查询结果状态，但不保存 Password Hash、Session Token、Secret、完整 SQL、问题文本或结果行。

## 5. 启动基础设施

启动 PostgreSQL 和 Qdrant：

```bash
docker compose up -d --wait postgres qdrant
docker compose ps
```

预期：

- PostgreSQL 状态为 `healthy`。
- Qdrant 容器处于 `Up`。首次启动的空 Qdrant 尚无 ChatBI 检索索引，按 §7 构建后才可用于在线检索。
- 两个服务只绑定本机回环地址。

Qdrant 健康检查会从 `.env` 读取本地 API Key，并且不会回显密钥：

```bash
uv run python scripts/check_dev_qdrant.py
```

停止基础设施但保留本地数据：

```bash
docker compose stop postgres qdrant
```

查看容器日志：

```bash
docker compose logs --tail=100 postgres
docker compose logs --tail=100 qdrant
```

PostgreSQL 和 Qdrant 都使用 Compose 项目专属 named volume，不读取源码目录 `data/postgres` 或 `data/qdrant`。PostgreSQL 开发库重置使用 4.4 节的有范围保护命令；Qdrant 重置和索引重建见第 7 节。

## 6. 启动 Online Query

### 6.1 启动 FastAPI

在 WSL / Linux 终端中运行，并绑定到回环地址：

```bash
uv run uvicorn src.query_api.main:app --host 127.0.0.1 --port 8000
```

检查：

```bash
curl --fail http://127.0.0.1:8000/health
```

预期响应：

```json
{
  "status": "ok"
}
```

`/health` 表示应用已通过启动检查并正在运行；启动检查至少验证 `chatbi_control` Schema 版本。它不代表 LLM、业务 PostgreSQL、Qdrant 或真实查询链路可用。

### 6.2 启动 Streamlit

在另一个 WSL / Linux 终端中运行，并绑定到回环地址：

```bash
uv run streamlit run src/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

浏览器打开：

`http://127.0.0.1:8501`

Streamlit 只调用 FastAPI，不直接访问 LLM、SQL Guard 或 PostgreSQL。

### 6.3 Observability / Trace ID（可观测性 / 链路编号）

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

## 7. 构建 RAG Offline 资产

Qdrant 服务启动与索引构建是两个独立步骤：Compose 负责启动有持久 volume 的 Qdrant；以下流程从 Git 跟踪的结构和 Semantic 源资产重新生成 Embedding、集合和关系图。

### 7.1 准备 Embedding 模型

RAG Offline Build 读取以下权威事实源：

- `src/structure/generated/tables.json`
- `src/structure/generated/columns.json`
- `src/structure/generated/relationships.json`
- `src/semantic/metrics.json`

首次构建前，按仓库锁定的 BGE-M3 revision 下载模型；脚本会复用本地缓存，不会把模型权重加入 Git：

```bash
uv run --env-file .env python -m scripts.prepare_embedding_model
```

该 revision 是 Hugging Face 仓库的完整 commit SHA。首次下载约 2.3 GB 的 PyTorch 模型文件；准备脚本跳过不被 `BGEM3FlagModel` 使用的 ONNX 模型和示例图片。后续运行复用 `.model-cache/bge-m3-5617a9f61b02`。不要用浮动的 `main` 代替该 revision。

### 7.2 首次构建或发布新索引

从 Git 中的结构与 Semantic 源资产构建索引。`--build-id` 可省略；省略时 Builder 会生成唯一版本号：

```bash
uv run --env-file .env python -m src.rag_offline
```

构建成功后会：

1. 创建新的 TABLE、COLUMN、METRIC Qdrant 集合。
2. 生成关系图。
3. 校验数量和检索。
4. 写入 `data/rag/<build_id>/manifest.json`。
5. 原子更新 `data/rag/current.json`。

构建失败时，旧的 `current.json` 和旧版本集合应保持不变。
Compose 启动不会下载 Embedding 模型，也不会自动构建索引。

### 7.3 验证当前发布资产

索引构建完成后检查当前发布结果：

```bash
uv run --env-file .env python -c "from src.rag_offline import OfflineBuildConfig,load_published_asset; c=OfflineBuildConfig.from_environment(); a=load_published_asset(c.output_dir); print(a.build_id, a.manifest['status'], dict(a.collection_names))"
```

新环境的集合数量以当前 tracked 源资产生成结果为准；构建摘要会报告每个集合的文档数、关系边数和检索验证结果。

### 7.4 重建索引或重置 Qdrant

更新源资产后重新运行 §7.2 的构建命令。Builder 会创建新版本，并在校验通过后切换当前版本，旧发布仍可用。

需要清空 Qdrant 开发数据并从头恢复时，执行：

```bash
uv run python -m scripts.reset_dev_qdrant
uv run python scripts/check_dev_qdrant.py
uv run --env-file .env python -m scripts.prepare_embedding_model
uv run --env-file .env python -m src.rag_offline
```

重置命令会确认并只删除当前 Compose 项目的 `qdrant_data`，然后重新启动 Qdrant。它不会删除 PostgreSQL 数据卷。清空后必须重新构建索引，再启动依赖 RAG 的 ChatBI。

## 8. 运行测试

### 8.1 纯软件回归

```bash
uv run --python 3.11 --locked python -m pytest -q
```

### 8.2 隔离 PostgreSQL 集成测试

该命令需要 Docker Engine 可用。它会启动一次性的 `postgres:16-alpine` 容器，在 WSL / Linux 宿主环境中使用本机回环地址分配临时端口。测试只读挂载仓库 `database/`，加载 `database/ci/bootstrap.sql`，然后运行数据库适配器和固定 SQL 服务链路的集成测试：

```bash
uv run python scripts/run_database_tests.py
```

测试进程使用临时容器的连接信息，不读取 `.env`，也不继承父进程中的 PostgreSQL 连接配置；Docker 不可用、容器启动失败或 fixture 初始化失败时会明确失败，不会回退到日常开发数据库。命令成功、失败或被 `Ctrl+C` 中断后，runner 只移除带有本次运行标识的临时容器及其匿名数据卷。它不会启动或清理 Compose 日常开发服务、Qdrant 或其他容器。CI 继续使用独立的临时 PostgreSQL Service 和同一份 CI fixture。

该入口默认加载小型 CI fixture。要验证完整的全新开发 Seed、Control DB 权限、migration 和首个管理员生命周期，运行开发环境 profile；它使用同一隔离容器，并从仓库初始化脚本建库：

```bash
uv run python scripts/run_database_tests.py --profile development
```

两种集成测试都不启动真实 LLM。日常纯软件测试仍可在没有 PostgreSQL 的情况下运行：

```bash
uv run --python 3.11 --locked python -m pytest -q
```

测试数量记录只作为对应 Commit 的证据快照，不作为当前 checkout 的基线；真实 LLM Evaluation 仍按显式授权流程执行，不能用纯软件测试替代。

### 8.3 GitHub Actions CI

`.github/workflows/ci.yml` 在 `master` 的 Push、Pull Request 和手动触发时执行锁文件检查、纯软件回归、PostgreSQL 集成测试和 API/Streamlit 启动 Smoke Test（冒烟测试）。CI 使用 Python 3.11 和锁定的 `uv` 版本；PostgreSQL 集成测试使用 `database/ci/bootstrap.sql` 中的 CI-only 合成 Fixture（测试夹具），不使用本地业务数据。CI 不调用真实 LLM，也不替代 AI Evaluation（AI 评测）或 Business Acceptance（业务验收）。

### 8.4 PR 前本地验收流程

PR 前的分支、candidate、用户授权、验收和交付顺序以 [`docs/agents/git-pr-workflow.md`](agents/git-pr-workflow.md) 为准。本节只列本地验证入口：按改动运行 §8.1 软件回归、§8.2 PostgreSQL 集成测试；涉及 Retrieval、RAG、Embedding、Qdrant、LLM 或 SQL 生成行为时，按仓库规则再执行 §9 的真实 Evaluation。

## 9. 运行真实 LLM Evaluation

真实评测会向配置的外部 LLM 发送 21 条测试问题以及结构和指标上下文。执行前必须确认：

- 当前网络和 LLM 配置可用。
- 允许发送这些测试数据。
- PostgreSQL 和 `chatbi_app` 可用。

执行：

```bash
uv run --env-file .env python -m src.evaluation --online-retrieval
```

Query 与 Business Analysis 黄金评测复用日常开发库 `chatbi_mvp`，expected SQL 和模型 SQL 都使用同一个只读数据库账号和执行器。报告记录 Seed 版本、Sales Mart 行数 / 日期范围摘要、实际数据 Hash 和 Hash 算法。显式比较 Baseline 时，数据 Hash / 算法 / 摘要或标准结果不同、或旧报告没有指纹时会标为 `NOT_COMPARABLE`，并说明原因，不报告回退 / 改善。无需另建评测数据库。

### 9.1 Worktree 与本地 RAG 资产

`.env`、`data/rag/` 和 `.model-cache/bge-m3-5617a9f61b02/` 是本地 ignored（被 Git 忽略）资产，`git worktree` 或干净 clone 只会取得 Git 已跟踪的代码，不会自动复制这些文件。进入新的 worktree 运行真实评测前，先确认当前环境中的资产存在：

```bash
test -f .env
test -f data/rag/current.json
test -d .model-cache/bge-m3-5617a9f61b02
```

如果代码位于新的 worktree，但 RAG 资产保存在已有主工作区，应将 `RAG_OUTPUT_DIR` 和 `RAG_MODEL_DIR` 指向主工作区的绝对路径；不要让相对路径在新 worktree 中解析出另一份模型路径。`.env` 可以继续通过本机环境或评测命令注入，不要复制到 Git。

`--online-retrieval` 会在执行标准案例前完成一次 RAG Preflight（RAG 前置检查）。如果发布指针、Manifest、Embedding Model、向量集合或运行时依赖不可用，评测会直接输出单个前置错误并退出，不会把所有案例伪装成业务失败。

指定历史报告进行回退比较：

```bash
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

## 10. 典型故障处理

### API 无法启动

依次检查：

1. `.env` 是否包含 LLM 和 PostgreSQL 必需配置。
2. PostgreSQL 是否处于 `healthy`。
3. 静态事实文件是否存在且为合法 JSON。
4. 是否已有进程占用 8000 端口。

### 页面无法连接

检查 FastAPI：

```bash
curl --fail http://127.0.0.1:8000/health
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
