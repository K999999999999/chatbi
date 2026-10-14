# ChatBI Runbook（运行手册）

## 1. 前提与配置

所有命令从仓库根目录的WSL / Linux Bash执行。宿主只需Git、Docker Engine、Compose（隔离验收要求至少2.24.4）；不需要宿主Python、uv、Node、`.venv`或`node_modules`。Dockerfile负责准备依赖，Compose组织服务，`dev`提供统一开发入口。

```bash
cp .env.example .env
bash scripts/install_git_hooks.sh
```

已有配置不要覆盖。Git Hook脚本只修改当前clone的local hooksPath，遇到已有其他有效Hook会拒绝覆盖；按[Git流程](agents/git-pr-workflow.md)保留并处理。

填写 `.env` 的 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`、数据库密码、Qdrant Key和随机 `CHATBI_ADMIN_SECRET_KEY`。模板中的本地演示密码仅用于回环环境；真实配置不进入Git、镜像或报告。构建前可以用以下基础容器命令生成签名Key，再自行填写到本地配置：

```bash
python_base=$(sed -n 's/^ARG PYTHON_BASE=//p' docker/python-dev.Dockerfile)
docker run --rm --entrypoint python "$python_base" -c 'import secrets; print(secrets.token_hex(32))'
```

默认Web5173、API8000、PostgreSQL5433、Qdrant6333/6334只绑定回环。`CHATBI_DEV_WEB_PORT`、`CHATBI_DEV_API_PORT`、`POSTGRES_PUBLISHED_PORT`可以调整端口；`CHATBI_DEV_ENV_FILE`选择独立配置，`CHATBI_DEV_COMPOSE_OVERRIDE`用于隔离验收。首次build前完成必需配置，启动API前确保LLM配置有效。

业务库 `chatbi_mvp` 的 `mart_sales` 由 `chatbi_app` 只读访问；控制库 `chatbi_control` 使用独立账号，保存用户、权限、Session、历史、执行和checkpoint。迁移身份只提供给初始化工具，API不挂载 `.env`。

## 2. 开发与本地体验

### 首次启动

```bash
./dev build
./dev infra
./dev migrate
./dev create-admin --username admin-1
./dev prepare-model
./dev build-rag
./dev up
```

打开 `http://127.0.0.1:5173`，首次管理员登录后按要求修改密码，再创建使用账号。管理员密码隐藏交互输入，不作为命令参数或Seed。

`infra`先启动PG/Qdrant；`migrate`等待基础初始化、迁移Control DB和checkpoint，再等待完整PG健康。新空卷创建合成Sales Mart演示数据；日常启动不重播Seed。`prepare-model`下载固定revision BGE-M3，复用 `.model-cache`；`build-rag`校验并原子发布索引，失败保持已有发布资产。首次下载/CPU构建可能较慢。

### 日常使用

```bash
./dev up
./dev status
./dev logs --follow
./dev down
```

服务在后台运行；停止保留数据库/Qdrant卷、模型与RAG资产。应用不随电脑/Docker重启自动启动，显式执行up；基础设施保留既有restart策略。禁止将删除volume当作常规停止方法。

源码从宿主挂载，Python自动重载、Vite热更新。依赖/锁文件或根配置变化后build再up；环境配置变化后up重建容器。重载不保证进程内会话持久，历史按正式Contract只读恢复，不自动重发请求。不要同时运行两个写同一Control DB的history runtime。

API的模型与RAG挂载只读，初始化工具可写。容器保持当前宿主UID/GID与模型路径身份，不重写已有数据所有权。本地Embedding沿用CPU/FP32，不承诺GPU或性能。

### 容器调试

```bash
docker run --rm -it --user "$(id -u):$(id -g)" -v "$PWD:$PWD:ro" -w "$PWD" --entrypoint python chatbi-python-dev:local -m pdb -m pytest tests/query_api/test_operations_state.py
```

用容器内pdb查看断点和变量；调试运行中的应用时先停止原API，再以同一Compose配置交互运行单个API，避免第二个history runtime。VS Code Dev Container可作容器内编辑环境，仍使用同一个dev入口，不另建宿主启动流程。

## 3. 标准应用容器

此方式验证或运行打包网页与API；日常开发继续使用dev。默认项目名 `chatbi-app`，与开发卷隔离；不读取Stable配置或release登记。初始化使用工具profile，不自动执行迁移或创建管理员。

```bash
docker compose --env-file .env -f docker-compose.app.yml build
docker compose --env-file .env -f docker-compose.app.yml up -d postgres qdrant
docker compose --env-file .env -f docker-compose.app.yml exec -T postgres sh /workspace/database/init/wait_for_base_initialization.sh
docker compose --env-file .env -f docker-compose.app.yml run --rm --no-deps migrator
docker compose --env-file .env -f docker-compose.app.yml run --rm --no-deps tools create-admin --username admin-1
docker compose --env-file .env -f docker-compose.app.yml run --rm --no-deps tools prepare-model
docker compose --env-file .env -f docker-compose.app.yml run --rm --no-deps tools build-rag
docker compose --env-file .env -f docker-compose.app.yml run --rm --no-deps tools verify
docker compose --env-file .env -f docker-compose.app.yml up -d --wait api
```

默认打开 `http://127.0.0.1:8080`，可设置 `CHATBI_APP_PORT`。模型与索引保存在本项目资产卷，初始化工具写入，非root API只读使用。PG与Qdrant不发布宿主端口。

准备完成后的日常命令：

```bash
docker compose --env-file .env -f docker-compose.app.yml up -d --wait
docker compose --env-file .env -f docker-compose.app.yml logs --tail=100 api
docker compose --env-file .env -f docker-compose.app.yml stop
```

Dockerfile的api/database targets使用普通本地构建；不要求clean Git提交或发布清单，不提供镜像上传、版本切换、自动升级、回滚、备份和恢复。企业运维由部署方负责，项目不接入发布平台。旧Stable数据、配置、备份和密钥不会自动删除或迁移；旧流程仅保留在历史归档中。

## 4. 验证与CI

```bash
./dev check
./dev test python
./dev test database
./dev test web
./dev test renderer
# 汇总执行以上四套测试，不调用真实LLM
./dev test all
```

check包含锁文件、文档/链接/模块边界、Python质量和网页/导出构建。Python全量回归不等于数据库或renderer验证；database分别启动独立CI/development fixture，覆盖真实权限、迁移、checkpoint、history和execution。web使用隔离mock API和浏览器，renderer启用真实Chromium/PDF与字体。失败返回非零，汇报skip和未执行范围。

宿主Bash负责Docker资源创建与清理，测试程序在容器执行。结构测试可只读挂载Compose CLI解析配置，测试容器无Docker socket，业务API无Docker权限。临时数据库/网络按本次标签清理，不能修改日常数据。CI仍可以内部使用uv/npm，不要求开发者在宿主安装它们。

真实容器业务验收显式执行，会产生少量LLM调用费用；只使用独立临时资源和专用账号：

```bash
scripts/verify_container_dev.sh isolated
# 标准打包应用的独立空卷验收
scripts/verify_container_app.sh
```

热更新检查可能临时修改源码，执行器必须恢复；运行记录绑定候选、镜像、模型、Seed、RAG和资源身份。历史验收不能重标为当前候选。

## 5. AI Evaluation

```bash
./dev evaluate --help
./dev evaluate --online-retrieval
./dev evaluate --query-understanding
./dev evaluate --business-analysis --online-retrieval
./dev evaluate --multi-turn --online-retrieval
```

初始化并启动对应开发基础设施，使用真实LLM配置和现有固定案例；不自动重建RAG、不修改评测案例。报告写入ignored `reports/evaluation/`，只适用于记录的提交、案例与模型/数据/资产身份。基线对比可以继续传递评测原参数，容器路径统一使用 `/workspace/reports/evaluation/`。Secret和原始敏感内容不得进入报告。

## 6. 健康与故障处理

`/health`只表示HTTP存活，`/ready`才反映应用依赖就绪；模型状态来自近期真实调用，不做定时收费探测。管理员可以查看依赖、模型和执行额度，网页不显示备份状态；刷新不延长登录期限。应用保护见[就绪Contract](specs/application-readiness.md)。

- 缺少配置：检查 `.env` 必需字段；不要输出完整Compose配置或Secret定位。
- 首次PG不healthy：先执行migrate，不等待未迁移的checkpoint健康状态。
- 模型/索引未准备：显式prepare-model/build-rag；来源校验失败不能通过删校验或静态回退解决。
- 端口占用：调整本项目端口后重试，不杀未知进程；确认实际网页Origin随端口更新。
- 业务拒绝或执行繁忙：按API安全提示处理，不绕过权限、SQL Guard或共享额度。
- 导出失败：检查镜像中的Chromium、字体、导出manifest与seccomp；保持sandbox，不以关闭保护换取成功。
- 停止后找不到历史：检查是否使用同一Compose项目/数据卷，不能用重播Seed或删除卷修复。

OTel/OTLP诊断可选，默认关闭；端点/认证配置只在本地，内容采集关闭。诊断不可用不能改变业务结果。详见[Observability](specs/observability.md)。

## 7. 当前支持边界

本机Windows+WSL/Linux，单API进程与电脑端访问。业务定义、权限、数据结构、AI链路和评测案例不因部署精简变化。公网生产、多worker/副本、企业编排和备份恢复不在项目支持范围。

当前规则见[容器开发](specs/container-dev-environment.md)、[标准容器](specs/container-deployment.md)、[Bootstrap](specs/bootstrap.md)、[Evaluation](specs/evaluation.md)；历次部署与运行验收保存在所属 `.scratch` 历史记录。
