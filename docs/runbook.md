# ChatBI Runbook（运行手册）

## 1. 用途与边界

本文档说明 WSL / Linux 本地开发环境的新 clone 首次准备、日常开发、数据库和索引重建、测试与评测。命令从仓库根目录执行；流程不依赖固定电脑路径，也不使用旧项目的数据目录。

推荐使用 WSL / Linux 的容器开发入口：Compose 管理四个常驻服务及一次性初始化工具，不要求宿主安装 Python、uv 或 Node。宿主调试入口仍保留；Dev Container 配置保留，不作为本次支持或验收入口。

ChatBI 当前处于 MVP 向生产演进阶段。本 Runbook 覆盖本地开发 / 内部验证流程，不代表已经完成生产部署。自动测试使用隔离 PostgreSQL 和 CI Fixture；黄金评测复用开发库 `chatbi_mvp`；生产数据库不属于本文档范围。

按目标选择流程：

- **新 clone 首次初始化：** 推荐按 §3 容器命令完成；宿主方式按 §3 选择入口 → §4.1–4.3 配置并初始化 PostgreSQL、显式创建首个管理员 → §5 启动 Qdrant → §7 准备模型并构建索引 → §6 启动 ChatBI → §8 确定性验证；真实 LLM 评测见 §9。空 PostgreSQL volume 会自动创建数据库、Schema、固定 RBAC 和 Seed；空 Qdrant 需单独构建索引。
- **日常开发：** 推荐执行 `./dev up`；宿主方式按 §5 启动服务 → §6 启动 ChatBI。PostgreSQL 数据和已发布 Qdrant 索引都会保留；不重播 Seed，也不自动重建索引。
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

FastAPI（开发容器 / 宿主调试；宿主回环端口 8000）
    └─ Online Query + SQL Guard + PostgreSQL

Vite Web（开发容器 / 宿主调试；宿主回环端口 5173；打包后由 FastAPI 同源提供）
    └─ HTTP 调用 FastAPI
```

## 3. 新 clone 与开发入口

### 推荐：容器开发

前提为 WSL / Linux、Git、Bash、Docker Engine / Compose。已有开发配置和数据可以直接复用；新 clone 复制 `.env.example` 为 `.env`，填写数据库密码、随机管理员签名 Key 与 LLM 配置，随后显式执行：

```bash
./dev build
./dev infra
./dev migrate
./dev create-admin --username admin-1
./dev prepare-model
./dev build-rag
./dev up
```

打开 `http://127.0.0.1:5173`。日常只需 `./dev up`；`./dev down` 停止四个服务并保留全部数据，`./dev status` 查看状态，`./dev logs --follow` 跟踪日志。前后端手动启动后后台运行，电脑 / Docker 重启后不自动启动；数据库与 Qdrant 保留现有策略。

后端源码变更自动重载，前端 Vite 热更新。后端重载 / 重启会清空进程内多轮会话，需新开对话；刷新网页仍按 R1 清空临时展示。依赖锁文件和新增根配置变化后执行 `./dev build` 再 `./dev up`。容器依赖不使用本机 `.venv` / `node_modules`。

`.env` 的宿主回环地址保持原值，容器配置覆盖为内部服务地址，不修改现有文件。API不挂载`.env`，没有迁移身份。模型主机目录在容器内保持解析后的相同绝对路径，兼容现有manifest的模型身份校验；RAG输出挂入固定路径。已有模型和索引复用，工具写入保持宿主UID / GID。默认CPU / FP32；首次构建可能较慢。

服务启动不自动迁移、创建用户或重建索引。PostgreSQL 首次健康检查依赖 checkpoint，必须先显式 `migrate`；配置缺失、端口占用、依赖失败时返回非零。`up` 的基础依赖 / HTTP 检查不等于真实问数已通过，动态 readiness 仍属于 R7。端口只发布至本机，不开放局域网。

`CHATBI_DEV_ENV_FILE` 可选择本地配置文件；`CHATBI_DEV_API_PORT` / `CHATBI_DEV_WEB_PORT` 可调整应用宿主端口，网页 Origin 随 Web 端口更新。`CHATBI_DEV_COMPOSE_OVERRIDE` 用于隔离验收的附加 Compose 文件。默认不更改基础项目名称，避免误用另一套数据卷。

构建镜像使用明确版本 / digest。受网络限制时，可通过 `CHATBI_DEV_PYTHON_BASE` / `CHATBI_DEV_NODE_BASE` 指向可信镜像地址，保持相同版本 / digest；不关闭 TLS 校验或修改系统证书。原生依赖随 `uv.lock` 安装，CPU执行不意味着镜像中不含锁定的CUDA包。

运行语义见[开发环境 Contract](specs/container-dev-environment.md)。正式生产镜像、HTTPS、升级 / 回滚和容量验收由 R6 / R7 完成。

容器运行验收使用以下入口，要求干净候选提交和可用的真实 LLM 配置，会产生少量模型调用费用。隔离模式需 Compose ≥2.24.4：

```bash
scripts/verify_container_dev.sh isolated
scripts/verify_container_dev.sh real
```

两种模式顺序执行：热更新检查会临时修改源码并恢复。`isolated` 验证空卷首次初始化并清理经项目标签核实的临时卷；`real` 复用现有开发资产。专用账号在结束后禁用并撤销会话，现有用户和数据保留。证据身份及限制见[容器验收记录](acceptance/container-dev-environment-20261003.md)。

### 保留：宿主调试

以下 §4–§9 的 `uv run` / `npm` 命令是宿主调试和既有评测入口，需本机 Python / uv / Node。日常容器开发不需要执行这些宿主命令。


WSL / Linux 是当前唯一支持的本地开发入口。ChatBI 和 RAG 构建命令在 WSL / Linux 进程中运行，PostgreSQL 和 Qdrant 由 Docker Compose 启动。`.env.example` 的 `POSTGRES_HOST=127.0.0.1`、`POSTGRES_PORT=5433` 和 `RAG_QDRANT_URL=http://127.0.0.1:6333` 是该入口使用的连接默认值；Compose 发布端口由 `POSTGRES_PUBLISHED_PORT` 控制，与应用连接端口分开。

首次配置 `.env` 的复制命令见 §4.2。安装 Python 3.11 和 `uv` 后运行 `uv sync --locked`，再按 §1 的首次初始化顺序操作。Compose 发布端口只绑定宿主机回环地址，不能从局域网访问。

## 4. 首次准备

应用初始化统一使用 `python -m src.bootstrap`，提供 `migrate`、`create-admin`、`prepare-model` 和 `build-rag`。`--help` 或子命令的 `--help` 查看参数；旧 Control DB、模型准备脚本和 RAG 模块命令入口已移除，不提供兼容转发。各操作仍显式执行，服务启动不会自动迁移、创建管理员、下载模型或重建索引。生命周期与失败边界见 [初始化 Spec](specs/bootstrap.md)。

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
- Observability 默认关闭。需要导出 Trace 时再设置 `CHATBI_OBSERVABILITY_ENABLED=true` 并配置 OTLP Endpoint / Headers；内容 Trace 默认保持关闭。变量语义和 Secret 处理见 [`docs/specs/observability.md`](specs/observability.md)。
- `.env.example` 已包含 WSL / Linux 宿主进程使用的 PostgreSQL 和 Qdrant 回环地址；只有本机端口不同于默认值时才需要调整。

`.env` 不得提交到 Git。不要在终端回显密码、API Key 或完整连接字符串。

`CHATBI_ADMIN_SECRET_KEY` 不提供仓库默认值。使用本机密码管理器生成至少 32 字符的随机值并填入 `.env`；不要通过命令行回显、日志或 Git 保存该值。

`src/query_api/config.py` 中的 Static Provider（静态身份适配器）只保留给确定性测试和离线 Evaluation；真实入口 `src/query_api/main.py` 不读取这些配置。`production` / `prod` 环境如果仍注入旧静态身份配置会拒绝启动，也不会自动回退到演示身份。

### 4.3 初始化 PostgreSQL 和首个管理员

先在 `.env` 中准备好本地 PostgreSQL 连接配置，然后启动 PostgreSQL：

```bash
docker compose up -d postgres
docker compose exec -T postgres sh /workspace/database/init/wait_for_base_initialization.sh
uv run --env-file .env python -m src.bootstrap migrate
docker compose up -d --wait postgres
```

空的项目 PostgreSQL named volume 首次启动时会自动建立 `chatbi_mvp`、完整 Sales Mart Schema、`chatbi_app` 只读账号和确定性合成开发 Seed，并创建同一 PostgreSQL 服务中的 `chatbi_control` 数据库、运行账号、Schema、固定 RBAC 和权限。接着必须运行 `migrate`；该命令幂等地应用当前 Control DB migration，并通过锁定版本的 LangGraph `PostgresSaver.setup()` 建立 `checkpoints`、`checkpoint_blobs`、`checkpoint_writes` 和 `checkpoint_migrations`，再授予运行账号所需的 checkpoint 表权限。

首次启动时不能在 migration 前使用 `docker compose up --wait postgres`：健康检查会有意等待 checkpoint 对象，而它们由宿主机上的 migration 命令安装。上面的流程先启动容器但不等待健康，再等待 PostgreSQL 接受连接、完成 migration，最后等待完整健康检查。健康检查验证两个数据库、Seed 版本、Control DB migration、checkpoint 表及版本记录和运行权限；缺少其中任一项时 PostgreSQL 容器保持不健康。日常重启不会重建或重播 Seed，也不会移除 checkpoint 状态。

更新 Control DB migration 时可单独执行幂等 migration 命令；它不会创建管理员：

```bash
uv run --env-file .env python -m src.bootstrap migrate
```

首个管理员创建必须显式执行。命令会隐藏读取并确认密码，要求至少 12 位；重复创建会失败：

```bash
uv run --env-file .env python -m src.bootstrap create-admin --username admin-1
```

管理员密码不放入 `.env.example`、Compose 或 Seed。首次启动和初始化不创建任何用户。API 运行进程只使用 `POSTGRES_CONTROL_APP_PASSWORD`，不使用迁移密码。启动 API 时会用 `chatbi_control_user` 检查 `schema_migrations` 中的 `chatbi-control-v2`，并验证 checkpoint 表、版本记录及运行权限；Schema 未完整迁移时，认证、SQLAdmin 和查询入口不会启动。

### 4.4 重置 PostgreSQL 开发环境

升级本地开发 Seed（例如 v2 到 v3）时不执行数据迁移；使用此命令全量重建本地 PostgreSQL 开发环境。命令会先显示并确认当前 Compose 项目拥有的 PostgreSQL named volume，然后只删除 `postgres_data`，重新启动、等待 Sales Mart Seed 与 Control DB 基础 migration 完成、安装 checkpoint，再等待 PostgreSQL、Control DB、checkpoint 和 Seed 的完整健康检查：

```bash
uv run python -m scripts.reset_dev_postgres
```

该重置会清除 `chatbi_mvp`、`chatbi_control` 中所有开发数据、账号、Session 和审计记录。它不会删除 Qdrant volume 或其他 Compose 项目的数据。正常启动和关闭使用 Compose 服务命令，不使用 `docker compose down -v`。

重置命令已自动应用应用库迁移并安装经营分析所需的 LangGraph checkpoint 表；它可重复运行且不会创建管理员。随后按 §4.3 显式创建首个管理员。Qdrant volume 和旧的已发布 RAG 索引仍保留；若 Seed 或 `columns.json` metadata 已更新，必须按 §7.2 构建、验证并发布匹配新数据的新索引，不能把旧索引当作已更新资产。

### 4.5 登录、首次改密和管理后台

- Web 网页打开后先使用内置账号登录；首个管理员首次登录必须修改密码。
- HTTP 客户端先调用 `POST /auth/login`，再把返回的 `access_token` 作为 `Authorization: Bearer <token>` 访问 `/auth/me`、`/auth/change-password`、`/auth/logout` 和查询接口。
- 管理员访问 `http://127.0.0.1:8000/admin`，使用同一套 ChatBI 账号。只有 `admin` 角色可以进入 SQLAdmin；`analyst` 只能执行查询。
- SQLAdmin 的用户、角色、权限和审计事件页面使用 `chatbi_control`；用户禁止物理删除，角色 / 权限 / 审计事件只读。
- 审计事件保存登录、密码、用户 / 角色变更、授权决策和查询结果状态，但不保存 Password Hash、Session Token、Secret、完整 SQL、问题文本或结果行。

## 5. 启动基础设施

按 §4.3 完成 PostgreSQL 的首次 migration 和 checkpoint 初始化后，再启动 PostgreSQL 和 Qdrant：

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

`main.py` 导入只创建应用。服务启动时由 `src/bootstrap/` 装配运行资源并完成就绪检查，失败时释放已创建资源并拒绝启动；正常关闭统一释放数据库、checkpoint、RAG、模型 HTTP clients 和 Tracing。RAG 内部继续按需加载，production 门禁要求的加载仍在启动检查期间执行。

在 WSL / Linux 终端中运行，并绑定到回环地址：

```bash
uv run uvicorn src.query_api.main:app --host 127.0.0.1 --port 8000
```

当前多轮会话 Store 为进程内存，按上述单 worker 方式运行。增加 `--workers` 或多副本后，不同进程无法识别彼此的 `conversation_id`；生产扩容前必须确认会话路由 / 可见性 Contract。该限制不要求现在引入共享存储。

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

生产探针设计须区分 HTTP liveness 与动态 readiness；当前固定 `/health` 响应不能作为下游恢复或完整就绪证据。启动时 production 来源指纹 / catalog 门禁也不等于运行期间持续监测。

### 6.2 启动电脑端 Web

安装 Node 24；开发前显式设置 `CHATBI_WEB_ORIGIN=http://127.0.0.1:5173`，保持 `CHATBI_WEB_DIST_DIR` 为空，再启动上节 FastAPI。

```bash
cd frontend
npm ci
npm run dev
```

打开 `http://127.0.0.1:5173`。Vite 将 `/api` / `/auth` / `/health` 代理到回环 API；网页只通过 HTTP 使用后端。打包同源运行见 [Web 开发与打包](#web-开发与打包)。

### 6.3 Observability / Trace ID（可观测性 / 链路编号）

`POST /api/v1/query` 的成功响应和 HTTP Error 都会在 Response Header（响应头）返回 `X-Trace-ID`。Trace ID 不属于 Query API JSON Body（响应体）字段；只读取这个单独的 Header，不要打印或复制完整请求头、响应头。

取得链路编号的方式：

- 直接调用 Query API 时，从成功响应或 HTTP Error 的 `X-Trace-ID` Header 读取；错误响应仍优先查看现有 `error_code`、`error_message` 和 `request_id`。
- 网页成功 / 受控错误后展开“查看请求信息”，读取独立的请求编号和链路编号；Header 缺失不当作业务失败。
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
uv run --env-file .env python -m src.bootstrap prepare-model
```

该 revision 是 Hugging Face 仓库的完整 commit SHA。首次下载约 2.3 GB 的 PyTorch 模型文件；准备脚本跳过不被 `BGEM3FlagModel` 使用的 ONNX 模型和示例图片。后续运行复用 `.model-cache/bge-m3-5617a9f61b02`。不要用浮动的 `main` 代替该 revision。

### 7.2 首次构建或发布新索引

从 Git 中的结构与 Semantic 源资产构建索引。`--build-id` 可省略；省略时 Builder 会生成唯一版本号：

```bash
uv run --env-file .env python -m src.bootstrap build-rag
```

构建成功后会：

1. 创建新的 TABLE、COLUMN、METRIC Qdrant 集合。
2. 生成关系图。
3. 校验数量和检索。
4. 写入 `data/rag/<build_id>/manifest.json`。
5. 原子更新 `data/rag/current.json`。

构建失败时，旧的 `current.json` 和旧版本集合应保持不变。
Compose 启动不会下载 Embedding 模型，也不会自动构建索引。

每个新 manifest 都包含 Structure Metadata、Metrics 和 Embedding 配置的来源指纹。修改上述任一输入后，production 服务会拒绝使用旧索引；必须先从新输入完成构建并发布。旧版 manifest 没有来源指纹，也不能作为已验证的 production 资产。

### 7.3 验证当前发布资产

索引构建完成后检查当前发布结果：

```bash
uv run --env-file .env python -c "from src.rag_offline import OfflineBuildConfig,load_published_asset; c=OfflineBuildConfig.from_environment(); a=load_published_asset(c.output_dir); print(a.build_id, a.manifest['status'], dict(a.collection_names))"
```

新环境的集合数量以当前 tracked 源资产生成结果为准；构建摘要会报告每个集合的文档数、关系边数和检索验证结果。

production 的 `src.query_api.main` 启动流程还会核验当前 RAG manifest 与本地输入指纹，并用 `chatbi_app` 只读比较 PostgreSQL catalog 和导出的表、列、关系 metadata。该校验失败会阻止服务启动；修改 Schema 后按 DDL → 数据库 → metadata 导出 → RAG 重建顺序处理，不要绕过门禁复用旧索引。

### 7.4 重建索引或重置 Qdrant

更新源资产后重新运行 §7.2 的构建命令。Builder 会创建新版本，并在校验通过后切换当前版本，旧发布仍可用。

需要清空 Qdrant 开发数据并从头恢复时，执行：

```bash
uv run python -m scripts.reset_dev_qdrant
uv run python scripts/check_dev_qdrant.py
uv run --env-file .env python -m src.bootstrap prepare-model
uv run --env-file .env python -m src.bootstrap build-rag
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

`.github/workflows/ci.yml` 在 `master` 的 Push、Pull Request 和手动触发时执行锁文件检查、纯软件回归、PostgreSQL 集成测试和 API / 打包 Web 登录、首次改密与退出的 Smoke Test（冒烟测试）。CI 使用 Python 3.11 和锁定的 `uv` 版本；PostgreSQL 集成测试使用 `database/ci/bootstrap.sql` 中的 CI-only 合成 Fixture（测试夹具），不使用本地业务数据。CI 不调用真实 LLM，也不替代 AI Evaluation（AI 评测）或 Business Acceptance（业务验收）。

### 8.4 PR 前本地验收流程

PR 前的分支、candidate、用户授权、验收和交付顺序以 [`docs/agents/git-pr-workflow.md`](agents/git-pr-workflow.md) 为准。本节只列本地验证入口：按改动运行 §8.1 软件回归、§8.2 PostgreSQL 集成测试；涉及 Retrieval、RAG、Embedding、Qdrant、LLM 或 SQL 生成行为时，按仓库规则再执行 §9 的真实 Evaluation。

## 9. 运行真实 LLM Evaluation

单轮真实评测会向配置的外部 LLM 发送当前 Golden Set 中的 29 条问题以及结构和指标上下文。多轮和 Business Analysis 是单独运行的套件，分别包含 7 个 Conversation / 15 个轮次和 10 个案例。执行前必须确认：

- 当前网络和 LLM 配置可用。
- 允许发送这些测试数据。
- PostgreSQL 和 `chatbi_app` 可用。

执行：

```bash
uv run --env-file .env python -m evaluation --online-retrieval
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
uv run --env-file .env python -m evaluation --online-retrieval --baseline reports/evaluation/<previous-report>.json
```

`--online-retrieval` 是真实 RAG 验收的必要开关；不带该参数的入口只适合显式静态上下文的确定性软件测试，不代表在线 RAG 技术故障可以回退静态 Schema。

报告输出到：

```text
reports/evaluation/<run_id>.json
reports/evaluation/<run_id>.md
```

评测结果属于 AI Evaluation（AI 评测），不能与 Software Test（软件测试）或 Business Acceptance（业务验收）混为一类。

评测命令在存在 `FAIL` 或 `INVALID_CASE` 时返回非零退出码；只有所有案例有效且通过时才返回 `0`，可直接作为 CI 门禁。

### 9.2 正式三套基线与稳定性诊断

完成所有代码、Contract 和文档提交后，确认工作区干净，再固定当前 commit 和 RAG 版本。每次验收使用新的目录，正式报告目录只包含该次三套 JSON，诊断放在其他目录：

```bash
test -z "$(git status --porcelain)" || exit 1
candidate_sha=$(git rev-parse HEAD)
rag_version=$(uv run --locked python -c 'import json; print(json.load(open("data/rag/current.json"))["build_id"])')
evaluation_dir="reports/evaluation/baseline-$(date -u +%Y%m%dT%H%M%SZ)-${candidate_sha:0:7}"
evaluation_status=0
for suite in single-turn multi-turn business-analysis; do
  uv run --locked --env-file .env python -m evaluation \
    --"$suite" --online-retrieval --output-dir "$evaluation_dir/formal" || evaluation_status=1
done
uv run --locked python -m evaluation.common.real_e2e_acceptance \
  --report-dir "$evaluation_dir/formal" --expected-commit "$candidate_sha" \
  --expected-rag-version "$rag_version" || evaluation_status=1
test "$(git rev-parse HEAD)" = "$candidate_sha" || evaluation_status=1
test -z "$(git status --porcelain)" || evaluation_status=1
printf 'Formal baseline exit status: %s\n' "$evaluation_status"
```

脚本保留正式失败报告并继续其他套件；`evaluation_status=0` 才表示本次正式基线通过。自动化调用须以该状态退出。不能重跑后挑选成功报告替换本次正式失败，修复后应形成新候选再重新验收。

额外运行三次完整多轮诊断，将每次报告写入 `$evaluation_dir/diagnostic-1`、`diagnostic-2`、`diagnostic-3`。逐次记录 Runner 退出状态与 FAIL / INVALID_CASE 数量，包括未能出报告的运行；失败时继续保留其他诊断。诊断不改变正式基线结果。`5643432` 历史候选曾两次在 `MT-FAILURE-ISOLATION` 第三轮返回意外澄清，之后完整运行通过；相关[工作记录](../.scratch/engineering-quality-gates/issues/04-current-candidate-evaluation-baseline.md#result)是模型波动证据。

GitHub 手动 Real E2E 按同一原则执行三套正式评测、确定性身份验收及三次多轮诊断；需要配置 LLM Secrets，普通 CI 通过不表示该工作流已运行。报告上传保留 14 天，需要长期追溯时由维护者保存原始文件和运行身份。评测结束后不要修改 tracked 文件来补写“当前通过”，本机实时结果保存在 Git 公共目录。

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

本地 Vite 代理指向 `http://127.0.0.1:8000`；网页使用相对 URL。检查 API 地址、`CHATBI_WEB_ORIGIN` 与实际网页 Origin 是否精确一致；打包模式同时核对 `CHATBI_WEB_DIST_DIR`。

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

## Web 开发与打包

安装 Node 24 和 npm，进入 `frontend` 执行 `npm ci`。在本地 `.env` 显式设置 `CHATBI_WEB_ORIGIN=http://127.0.0.1:5173`，启动 FastAPI 后运行 `npm run dev`；浏览器打开该地址。真实凭证仅填入本地配置和登录表单，不写入仓库。

打包使用 `npm run build`。以 FastAPI 同源提供打包网页时，设置 `CHATBI_WEB_DIST_DIR=frontend/dist`，并将 `CHATBI_WEB_ORIGIN` 设置为实际网页地址（本地如 `http://127.0.0.1:8000`）。API-only 运行可同时留空这两个配置。线上 Origin 必须为 HTTPS；完整生产部署验收仍属于 R6。

浏览器使用独立 Cookie 登录接口，旧 Bearer 和管理后台继续兼容。当前仅电脑端；刷新保持登录但不恢复临时聊天，长期历史在 R3 实现。

网页问数：登录后输入完整问题（如“2025年2月人民币净销售额是多少”），成功后可围绕上一成功状态追问。表格明确区分 NULL、零与空字符串；经校验 SQL 可展开查看。受控失败不会覆盖上一成功状态；网络中断、客户端超时或响应无效时，结果未确认，需点击“新建问数对话”并补全问题。前端不会自动重发，刷新会清空当前展示与会话编号。

网页经营分析：手动切换“经营分析”，提供完整的指标与两个时期（如“分析2025年2月相比2025年1月的人民币毛利变化”）。仅支持既有人民币净销售额 / 毛利的产品因素归因，不继承问数条件。报告、归因数值和任务证据按后端返回显示。失联后可点击“重试原分析”，草稿编辑不会改变该任务的原问题 / UUID；明确的过期或语义拒绝不能静默重建任务。等待期间两种模式都禁止再次发送与切换，仍可编辑下一条草稿或退出。

### R1 桌面浏览器验收

```bash
cd frontend
npm ci
npm run build
npx playwright install --with-deps chrome
npm test
npm run test:dev
```

`npm test` 验证打包入口，`test:dev` 验证 Vite 同源代理；两者使用真实 HTTP / Cookie / Session 和确定性业务服务替身，不调用真实模型。桌面窗口为 1440 × 1000，Chrome channel；可用 `CHATBI_CHROME_PATH` 指定本机 Chrome 可执行文件。所有配置关闭 Trace / 视频 / 自动截图。CI 使用 `scripts/smoke_web.py` 检查正式 API 的打包页面、Cookie 登录 / 首次改密 / 退出，凭证仅通过环境传递，不调用模型。

真实 AI 验收需本地 `.env` 已具备模型、RAG、业务只读 PostgreSQL、应用库和管理签名配置，服务端能读取现有数据；必须在 clean candidate 上运行：

```bash
cd frontend
npm run build
npm run test:real
```

此命令生成一个独立 `web-e2e-*` analyst 验收账号，随机密码只在进程环境中传递；服务退出时禁用该账号并撤销会话，保留应用库安全审计 / 分析记录，不修改已有账号或业务数据。实际请求复用正式 runtime、授权、SQL Guard 与数据库执行；独立参考 SQL 使用业务只读账号。报告在 ignored `reports/browser-real/`，含实际提交 / Chrome / 对照结果，不含密码 / Cookie / Session Token；不要公开上传业务原始报告。安全 reporter 不输出断言内容或凭证。真实资源缺失或闭环失败不得将确定性替身通过作为替换验收。

### R2 图表与数字展示

查询成功后默认同时显示可用图表和表格，均可收起；时间图可切折线/柱状，操作不重查。同单位一起绘图，不同单位分图；多个分组、未知单位或语义、重复分组保留表格。金额显示千分位、两位小数和元，毛利率显示百分比；可展开原始返回值，NULL显示“无数据”。截断图表只代表已返回的最多100行。

经营分析显示两期金额、产品贡献和所选产品的已有因素，数值方向由后端裁决；省略产品只声明数量。图形失败不影响报告和表格。行为详见[R2 Spec](specs/result-visualization-v1.md)。ECharts随本地应用打包，不依赖CDN；npm锁文件变化需 `./dev build` 后 `./dev up`，源码仍通过挂载热更新。

R2默认Chrome用例通过 `cd frontend && npm test` 运行，不调用真实模型。实际容器运行 `scripts/verify_container_dev.sh real`，显式使用真实LLM、现有业务只读数据与RAG，覆盖问数/追问、时间及分类多指标和两期分析；正式验收需clean candidate。专用验收账号结束自动禁用、撤销Session、移除临时凭证，原用户和持久卷保留。全量AI Evaluation仍是单独入口，不能把小范围浏览器验收冒称全套通过。
