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
| `./dev test [python\|database\|web\|renderer\|all]` | 在容器中运行对应验证，数据库/浏览器资源隔离，失败返回非零并生成机器可读运行摘要 |
| `./dev check` | 容器执行锁文件、文档/边界、Python质量和前端构建，并生成机器可读运行摘要 |
| `./dev evaluate [参数]` | 在开发网络中执行原评测入口并输出报告；真实调用显式执行 |

分类入口包括check docs/python/boundaries定向检查（固定Ruff0.16.8）、evaluate validate（完整commit/RAG/cases报告身份，无LLM / 业务查询）和verify dev（默认isolated，real显式触及当前开发环境）。软件测试直接验证挂载源码，不需要构建业务APP镜像；帮助无.env或Docker要求。旧`app`、`verify app`、`doctor app`和`recover-admin app`调用以状态码2拒绝，不切换目标或操作资源。

`dev test`与`dev check`每次写入唯一的ignored `reports/tests/<run_id>.json`，另保留JUnit / Playwright机器结果。摘要记录源码起止身份、命令范围、已运行 / 失败 / 未运行步骤、适用计数、清理状态，以及适用的`uv.lock` / `package-lock.json` SHA-256和实际Python / Node / Browser / PostgreSQL容器镜像ID；没有真实计数的构建 / lint步骤使用null（不适用）。测试计数缺失、存在skip、源码或环境身份不稳定 / 无法核实或报告无法保存时，不标为完整通过；命令失败仍返回非零。所有运行只使用本地开发验证容器，不构建或启动独立APP镜像。

`verify dev`是独立的业务验收，不并入软件测试摘要。运行中`browser.json`留在私有暂存目录供流程更新；清理后以独立Run ID排他发布到`reports/browser-real/<run_id>.json`，原始证据放在`reports/browser-real-artifacts/<run_id>/`。摘要区分`container-dev`与宿主`browser-real`，包含清理状态、浏览器用例计数并关联RAG配置身份文件`runtime.json`；RAG身份从应用实际使用的`RAG_MODEL_DIR/config.json`读取。报告冲突不会覆盖既有结果。

诊断维护：doctor dev只读有界检查依赖/HTTP/资产，不启动或修复、不改密、不调用LLM，未知不ready；metadata export使用既有catalog SELECT并写三份结构JSON，不改Semantic、不隐式build-rag；reset postgres/qdrant仅开发项目，经确认、归属与停止验证后只删目标卷。PG重建Seed和完整迁移但不创建管理员；QD只重建服务。API/Web保持停止，卷删除不可回滚；取消、外部卷、标签错及停止失败不删除。

协作：hooks install复用本机安装器，harness check只读本机Git记录；无业务配置要求。普通clone/linked worktree保留真实Git公共目录身份，Git不可见不能当clean。开发保留CHATBI_DEV_ENV_FILE/CHATBI_DEV_COMPOSE_OVERRIDE及宿主路径/UID规则；维护目标固定为dev，并拒绝旧APP / Stable Compose资源。

[管理员恢复](admin-recovery.md)仅支持dev并显式选择用户名，隐藏交互输入、运行身份、原子改密/撤销Session与强制审计，不依赖完整应用。内部helper与CI专用Smoke不公开为日常命令。旧宿主启动退出支持；数据库runner及前端真实浏览器的独有验证保留非推荐兼容路径，不能删除回归断言。

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
