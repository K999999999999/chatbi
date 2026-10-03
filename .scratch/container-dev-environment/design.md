# 本地容器开发实现设计

依据：[已确认 Spec](spec.md)。Owner：当前主 Agent。此文档描述待实施方案，不是运行通过证据。

## 1. 最小结构与方案选择

使用现有 `docker-compose.yml` 保留 PostgreSQL / Qdrant / Dev Container，新增独立 `docker-compose.dev.yml`，承载 API、Web 和一次性初始化工具。统一入口为根目录 `dev` Shell 脚本，固定从仓库根目录解析这两份配置；支持 `up`、`down`、`status`、`logs`、`build`、`infra` 与四类 Bootstrap 子命令。`down` 的语义是停止四个常驻服务，实际使用 Compose stop，不删除容器卷或其他项目。

对比方案：直接将应用加入基础 Compose 会让既有基础设施 / 本机调试命令隐式启动应用；重建完整 Dev Container 则增加 IDE 生命周期和独立入口维护。选择开发覆盖文件，让现有基础命令仍只管理基础设施，并复用现有项目 / 数据卷。Shell 仅编排 Compose 和容器命令，不复制 migration、身份或 RAG 实现，不引入命令框架。

本项所有脚本与配置由主 Agent 维护；未来新增平台、GPU、生产部署或迁移现有配置消费者时重新评估，不提前建插件 / 发布平台。

## 2. 镜像与依赖

- Python 开发 Dockerfile 基于 Python 3.11 Debian 环境，固定 uv 0.12.2，使用现有 `pyproject.toml` / `uv.lock` 的 `uv sync --locked`；依赖放镜像内 `/opt/venv`，运行时不重新 sync。构建不需要 Secret，不 COPY 本机 `.venv`。
- Node 开发 Dockerfile 使用 Node 24，依据 `package-lock.json` 执行 `npm ci`，依赖放镜像内前端目录。Vite 缓存指向容器可写临时目录，不写宿主依赖。
- 基础镜像在实施时核实可用的具体补丁版本及 digest，记录版本身份；不新增浮动 latest，不为了 CPU 改写现有 Torch 依赖来源 / 版本。CPU 是执行配置，不是更换包分发。
- `.dockerignore` 默认排除 `.git`、`.env` 及真实配置、模型 / 数据 / 报告、本机依赖与缓存；Dockerfile 只复制构建所需锁文件和安全源文件。管理员密码 / LLM Key 不使用 build args。
- 源码和必要配置选择性 bind mount。Python 绑定 `src/` 等所需目录，不绑定仓库根目录或 `.env`。前端绑定 `src/`、`index.html` 和必要配置文件，不覆盖镜像中的 `node_modules`；新增根级配置按文档更新挂载 / 重建。
- 容器非 root 运行。初始化工具使用宿主 UID / GID 写模型缓存及 RAG 目录；目录由宿主 Shell 创建，禁止递归 chown 现有数据。依赖可读、必要缓存 / HOME / tmp 可写，不挂宿主 Docker socket。
- `dev build` 显式更新镜像依赖，`dev up` 使用 build 缓存创建 / 更新服务。锁文件变化须先重建；普通源码变化仅重载。

## 3. 配置、网络与 Secret 边界

- 使用 Compose 插值读取现有 `.env`，保留配置入口和宿主调试默认值；API 使用明确的运行配置白名单，不使用整份 `env_file`，也不挂 `.env`。
- API 注入业务 / Control DB 运行账号、LLM、RAG、浏览器和可观测性必要配置，不包含三项 migration 身份配置。保留原始 API 环境过滤行为作为额外防护；证明点同时检查容器定义与实际环境的键名，不回显值。
- 一次性 `tools` 服务复用 Python 镜像，仅提供管理员创建、模型准备和 RAG 构建所需配置；一次性 `migrator` 服务额外取得 migration 身份。两者置于工具 profile，日常 `up` 不启动；`run --rm --no-deps` 不自动拉起需要 healthy 的 API。
- 容器内覆盖数据库地址为 `postgres:5432`、Qdrant为`http://qdrant:6333`，RAG输出使用固定容器路径，CPU / FP32；不修改用户`.env`。模型缓存挂载目标保持主机解析后的绝对路径，运行配置使用相同路径，以兼容既有manifest的模型路径身份；不改manifest或模型校验。空本地Qdrant path保持服务模式。
- Web 不接收后端凭据。Vite 用专用非 `VITE_` 的 server-only 代理配置选择 `http://api:8000`；未配置时仍默认本机 `http://127.0.0.1:8000`。此配置不进入浏览器 bundle。
- 容器进程监听 `0.0.0.0` 以供内部网络 / 端口映射访问，宿主发布保持 `127.0.0.1`；浏览器 Origin 仍为 `http://127.0.0.1:5173`。不放宽 CSRF、Cookie 和 allowed hosts 到任意域。
- 相对模型 / 资产路径可复用当前默认目录；自定义路径时明确宿主挂载源与容器目标，由统一入口检查目录，不静默换用不同资产。只检查必要配置键与存在性，不输出解析后的完整 Compose 环境。

## 4. 首次准备与日常生命周期

首次准备入口及顺序：

1. 复制 `.env.example` 并填本机配置。
2. `./dev build` 构建镜像；`./dev infra` 启动 PostgreSQL / Qdrant，不等待尚未 migration 的完整 PostgreSQL healthy。
3. `./dev migrate` 等待基础初始化脚本成功后，启动一次性 migrator 执行既有 Bootstrap migrate；成功后才检查完整 PostgreSQL healthy。
4. `./dev create-admin --username ...` 用 TTY 隐藏输入密码。保留 CLI 返回码及重复创建拒绝。
5. `./dev prepare-model` 复用 / 下载固定 revision；`./dev build-rag` 显式构建 / 发布索引。
6. `./dev up` 后台启动四个服务，并在有界等待内检查 PostgreSQL、Qdrant 的基础服务状态、API HTTP 和 Vite HTTP；不通过等待自动补 migration / 索引。

`up` 的构建 / 依赖等待失败返回非零，并给出安全阶段提示；未准备 PostgreSQL checkpoint 时明确提示显式 migrate，而不是永远等待。此检查不承诺动态 readiness 或真实问数成功。部分服务已启动时报告实际状态，修复后可重试；不自动停止原有依赖或清空数据。

API / Web 使用 `restart: "no"` 和合适的信号 / 停止宽限；API `uvicorn --reload --reload-dir .../src` 单应用 worker。正常退出保留 Bootstrap lifespan 清理。日志 / 状态入口只作用于本项目的指定服务，不调用 `docker compose config` 输出 Secret。

模型缓存与 `data/rag/`：API 只读，构建工具可写；PostgreSQL / Qdrant named volume 不改名、不 reset。已有本机服务与容器入口端口冲突给出诊断，由开发者选择入口；不杀进程。

## 5. 可测试性与实际验收

- Shell 的关键错误传播、服务选择及无数据删除行为可用假 Docker 命令验证；不只比较脚本文本。
- 用安全模板 / 隔离配置解析开发 Compose，断言重启策略、端口、运行配置白名单、挂载与工具 profile；禁止实际 Secret 写入测试 fixture 或 stdout。
- 首次初始化验收使用独立 Compose project、临时业务 / Control DB / Qdrant volume 和独立端口。清理前核对项目标签和资源身份，保留宿主缓存与现有项目数据。
- 前后端热更新使用可恢复的临时源码改动，记录前后浏览器 / 进程行为，在 finally 恢复验证专用改动；不覆盖用户并发修改。验收报告标注热更新实验对应候选和临时 Diff，不冒称改动期间 `git_dirty=false`。
- 真实验收必须访问实际 Compose API / Vite，不能直接复用会启动宿主替身或打包 app 的既有 Playwright webServer 配置。新增外部服务模式 / 专用配置，复用安全 reporter、问数 / 追问断言和独立 SQL 参考；真实验收以 clean candidate 为准，凭证只通过安全运行环境传递。
- 账号准备 / 清理通过现有测试支持及账号 Contract，仅创建专用测试账号，撤销其 Session 并禁用；不修改已有用户。测试支持仅挂入验收工具，不进入常驻 API。
- 针对配置 / CLI / Vite 变化跑有意义的软件回归；实际容器验收覆盖初始化、HTTP、端口、热更新、停止 / 恢复、数据身份、失败诊断与真实问数两轮。CPU 索引构建耗时实测，不承诺性能。

## 6. 兼容、恢复与文档

基础 Compose 服务和 volume 身份保持，README / Runbook 明确推荐入口和宿主调试方式。Dev Container 不作为新支持入口，不变更其依赖或关闭语义；针对共享 Compose 做现有配置回归。

失败恢复：停止新增 API / Web 后回到原本机命令，基础设施 / 账号 / 索引保留。没有新数据库迁移、生产发布或真实流量切换，不需要 Feature Flag / staged rollout；恢复不删除 volumes，不撤销原有 migration。

正式运行 Spec、Runbook、README 和 Acceptance 在实施中随切片同步。路线图仅标记本地开发准备状态，不宣称 R6 / R7 完成。已确认 Spec 是行为权威，此设计负责局部技术选择；发现需改变其边界时返回 Spec / 设计审查。

技术参考：[uv Docker 指引](https://docs.astral.sh/uv/guides/integration/docker/)、[Compose run](https://docs.docker.com/reference/cli/docker/compose/run/)、[Compose 服务配置](https://docs.docker.com/reference/compose-file/services/)。

## 实施中设计复核：已有索引模型路径

真实复用现有资产返回503；`RagRuntime._validate_manifest`比较manifest模型路径与运行配置，原manifest保存主机绝对路径。固定容器模型目标会破坏已确认的索引复用行为。最小修订：统一入口从Compose配置的安全内存流提取模型源绝对路径，创建目录后将该路径用作模型挂载目标和运行变量。RAG输出路径仍固定；不改Core、manifest、`.env`或一致性门禁，不自动重建索引。此为已确认Contract内的运行映射修订，已重新执行只读Design Review，PASS；后续真实复用链路必须复验。
