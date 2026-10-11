# ChatBI 0.1.0

ChatBI 是面向业务数据查询的 Domain AI Engine（领域 AI 引擎），采用 Modular Monolith（模块化单体）。它把自然语言问题转换为业务语义、受控 SQL 和数据库结果，并由确定性程序校验模型提出的候选。

当前 MVP 已包含 Web 问数、经营分析、登录与 RBAC、多轮查询、历史成果和结果导出。本机 Stable 的 R7 运行保障已通过 Docker Desktop 与 Windows 整机重启恢复核验；公网生产部署仍未完成。AI Evaluation 结果只适用于报告记录的 commit 和运行资源。产品边界及当前阶段见[产品范围](docs/product-scope.md)和[路线图](docs/roadmap.md)。

第一次接手仓库？从[新人项目导航](docs/project-guide.md)开始。它会带你从产品全景找到功能模块、关键代码、行为事实、验证入口和本地启动步骤。

## 新 clone：容器开发

推荐在 WSL / Linux 环境使用 `./dev`。需要 Git、Bash 和 Docker Engine / Compose；容器提供应用依赖，无需在宿主安装 Python 或 Node。首次启动需要下载固定版本的 BGE-M3 模型并构建 RAG 索引，需预留网络和磁盘空间。完整前提、配置说明和故障处理见[Runbook 第 3 节](docs/runbook.md#3-新-clone-与开发入口)。

复制安全模板并在本机 `.env` 中填写所需配置；不要提交真实 Secret。新 clone 首次提交前安装仓库 Hook，然后初始化并启动：

```bash
cp .env.example .env
# 按 Runbook 填写本机数据库密码、随机 CHATBI_ADMIN_SECRET_KEY 和 LLM 配置
bash scripts/install_git_hooks.sh
./dev build
./dev infra
./dev migrate
./dev create-admin --username admin-1
./dev prepare-model
./dev build-rag
./dev up
```

网页默认位于 `http://127.0.0.1:5173`。日常使用 `./dev up`、`./dev down`、`./dev status` 和 `./dev logs --follow`；`down` 会保留数据库和检索数据。不要用 `docker compose down -v` 重置数据。Hook 已有其他有效配置时，安装脚本会停止并保留原设置，按 Runbook 的 Hook 说明处理。

宿主调试入口、服务健康检查、数据重置和测试命令见 [Runbook](docs/runbook.md)。健康检查只证明服务存活，不等于真实问数验收。

## 主查询链路

```text
自然语言问题
  → 业务语义解析与认证映射
  → Online Retrieval 组装上下文
  → LLM 提出 SQL 候选
  → SQL Guard 确定性校验
  → 只读 PostgreSQL 查询
  → Query API 返回结果给 Web
```

核心原则是 `Model proposes, program decides`：模型不决定业务口径、权限、数据范围或 SQL 是否执行。更完整的架构和代码路线见[架构文档](docs/architecture.md)与[新人项目导航](docs/project-guide.md)。

## 文档与验证

- [新人项目导航](docs/project-guide.md)：按功能定位模块、关键代码、Spec、测试和运行入口。
- [产品范围](docs/product-scope.md)：当前支持的业务能力与明确边界。
- [架构](docs/architecture.md)：模块职责、依赖方向和核心链路。
- [Runbook](docs/runbook.md)：开发环境、初始化、日常运行、测试、Evaluation 和运维步骤。
- [`docs/specs/`](docs/specs/) 与 [`docs/designs/`](docs/designs/)：行为 Contract 和实现设计。
- [`tests/`](tests/)、[`evaluation/`](evaluation/) 与 [`docs/acceptance/`](docs/acceptance/)：软件测试、AI Evaluation 和业务验收证据。历史结果按其 commit、案例集和运行资源判断，不自动代表当前候选。

宿主机确定性 Python 回归命令（使用 `uv` 与 Python 3.11）：

```bash
CHATBI_WEB_ORIGIN=https://example.invalid uv run --python 3.11 --locked python -m pytest -q
```

完整测试前提及 Origin 覆盖原因见 [Runbook 测试章节](docs/runbook.md#8-运行测试)。纯软件测试不证明真实 LLM 准确率或公网生产就绪。
