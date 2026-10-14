# 容器开发环境

本文定义容器开发命令、数据保留和宿主隔离行为。dev为唯一推荐开发入口，宿主不要求Python/uv/Node；操作方式见 [Runbook](../runbook.md)。

## 初始化与命令

| 命令 | 可观察行为 |
| --- | --- |
| `./dev build` | 依据锁文件构建 Python / Node 开发镜像；依赖变化后显式执行 |
| `./dev infra` | 启动 PostgreSQL、Qdrant，不等待未 migration 的完整健康状态 |
| `./dev migrate` | 等基础初始化后显式 migration，再等待完整 PostgreSQL healthy |
| `./dev create-admin --username NAME` | 交互隐藏输入密码；复用首次管理员创建 / 重复拒绝 Contract |
| `./dev prepare-model` | 显式准备固定 revision 模型，复用缓存 |
| `./dev build-rag` | 显式构建 / 验证 / 发布索引，不自动重播 Seed |
| `./dev up` | 镜像缺失时构建，后台启动四个常驻服务，有界等待 HTTP / 基础设施与应用ready；未完成必要准备返回非零 |
| `./dev down` | 停止 API / Web / PostgreSQL / Qdrant，保留数据卷、缓存与资产 |
| `./dev status`、`./dev logs [--follow]` | 查看本项目运行状态 / 最近日志 |
| `./dev test [python\|database\|web\|renderer\|all]` | 在容器中运行对应验证，数据库/浏览器资源隔离，失败返回非零 |
| `./dev check` | 容器执行锁文件、文档/边界、Python质量和前端构建 |
| `./dev evaluate [参数]` | 在开发网络中执行原评测入口并输出报告；真实调用显式执行 |

失败保持非零退出码和安全阶段诊断，不输出完整配置。`up`不自动初始化。`/health`仍只证明API启动后HTTP存活，依赖检查不等于真实问数通过。

## 开发边界

- API / Web / PostgreSQL / Qdrant统一使用`unless-stopped`；显式启动后不随终端关闭退出，Docker重启后恢复此前运行的服务。主动停止后保持停止，直到再次`up`；电脑重启后需Docker先启动。
- 自动恢复只启动已有容器，不执行构建或初始化；tools / migrator保持`restart: "no"`。配置变化通过`up`应用，依赖变化先显式构建；恢复后的依赖与资产仍须通过就绪门禁。
- Docker自动恢复不保证Compose的依赖启动顺序。开发API在启动热重载父进程前有界等待控制库；等待超时退出，由容器策略重试。Qdrant、业务库和资产的完整就绪仍由应用检查，不调用LLM探测，不绕过初始化。
- 宿主端口仅`127.0.0.1`，默认Web5173 / API8000；内部网络沿用Cookie / CSRF / Origin校验。
- 单应用worker自动重载Python源码；Vite热更新前端。重载 / 重启丢失进程内多轮会话，刷新按历史规则只读恢复已保存对话，不自动重发；进程内短期会话不保证重启恢复。
- 选择性源码挂载，不覆盖镜像依赖。依赖 / 新增根配置显式重建；环境变量变化执行`up`重建容器配置。
- 本地Embedding默认CPU / FP32，远端LLM沿用配置，不承诺GPU或性能指标。
- 数据库和Qdrant卷保持原身份；模型 / RAG复用主机路径，API只读、工具可写，宿主UID / GID正常，不修改已有数据所有权。
- API不挂`.env`、不注入migration身份。Secret不入构建上下文 / 镜像，前端不取得后端凭据。

## 兼容与验证

基础Compose不隐式启动应用；Dev Container保留原配置，不是本次验收入口。端口冲突不杀未知进程；故障修复后重试，停止后仍通过同一dev容器入口恢复，数据保留。

运行验收覆盖独立空卷初始化、热更新、持久性、故障、实际Compose网页的真实两轮查询和账号清理；证据绑定候选 / 资源。日期化结果见[历史验收记录](../../.scratch/container-dev-environment/history/acceptance--container-dev-environment-20261003.md)，不改写历史 Evaluation 身份。

操作见[Runbook](../runbook.md)，初始化见[Bootstrap](bootstrap.md)，网页行为见[Web Spec](web-dialogue-v1.md)。
