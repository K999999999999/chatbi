# 本地容器开发 Ticket 草案

Status: 用户已确认；正式三项Tickets已写入issues/，本文件保留拆分依据
Canonical Source: [已确认 Spec](spec.md)；局部技术选择见 [Design](design.md)，审查见 [Design Review](design-review.md)
Owner: 当前主 Agent
Delivery: 一个目标、一个 active branch / worktree、一个最终 candidate；默认本地 Commit，Push / PR另行授权

顺序：01 → 02 → 03。三个切片逐项具有可运行行为和证据，每项同步相关文档；03集中完成整个目标的实际运行验收，不替代前两项自身验证。

## 01 容器内首次准备与可启动 API

### Change Profile / Owner

Lifetime：长期开发入口；Size：中；Risk：较高，涉及凭据、首次初始化和数据资产；Evidence：锁文件构建、配置 / CLI确定性检查、隔离初始化与API smoke。Owner：当前主 Agent。

### Blocked by

None (can start immediately)，前提是用户确认拆分并授权整体实施。

### What to build

- 增加Python开发镜像、开发Compose覆盖文件中的API / tools / migrator，以及构建上下文排除规则。
- 建立统一`dev`入口的基础设施 / 构建及四个显式Bootstrap命令，初始化运行不要求宿主Python / uv。
- 运行依赖与源码隔离；API仅运行配置白名单，无migration凭据、无`.env`挂载；工具非root、持久模型 / RAG资产可复用且不重置。
- 按基础初始化→migration→完整healthy顺序准备独立数据库，管理员密码交互输入；启动单应用worker API并启用源码重载。
- 同步Runbook首次准备与API容器步骤，以及正式开发运行Contract的对应部分，不将尚未实现的Web统一启动标为完成。

### Owned files

`docker/python-dev.Dockerfile`（新）、`.dockerignore`（新）、`docker-compose.dev.yml`（新）、`dev`（新）、`.env.example`（仅安全说明或必要占位）、`tests/scripts/test_container_dev.py`（新）、`docs/specs/container-dev-environment.md`（新）、`docs/runbook.md`、本项工作记录。保留`docker-compose.yml`服务 / volume身份，默认不改现有业务源码与依赖锁文件。

### Acceptance criteria

1. 使用锁文件构建，记录Python / uv / 基础镜像版本；宿主不运行语言工具。构建不包含Secret、本机依赖、模型和报告。
2. 一次性命令保持原Bootstrap参数与返回码，管理员密码不出现在参数 / 日志；重复创建拒绝。首次migration不陷入完整healthy等待循环。
3. 空临时卷可完成基础初始化、migration、checkpoint权限及管理员准备，正式API的`/health`可访问；失败时保持非零与安全定位提示。
4. API实际环境键无migration字段、容器源码挂载中无`.env`；模型 / RAG只读，工具可写文件的宿主所有权正常。
5. API宿主端口只回环，CPU、单worker、`restart: no`，依赖构建与运行挂载互不覆盖。

### 验证证据 / Done When

针对Shell错误传播与Compose安全边界补确定性测试；复用Bootstrap / Dev Container相关回归；实际镜像构建和隔离PostgreSQL初始化 / API smoke。证据绑定候选与资源身份，文档与Diff审查通过，当前切片相关测试通过后本地提交。

### Migration / Rollback

不新增数据库migration或改现有volume；初始化操作复用已存在的migration。失败保留原资源，停止API后使用宿主原入口。只清理带本次隔离项目身份的测试资源，禁止删除现有开发卷。

## 02 一键前后端开发与热更新

### Change Profile / Owner

Lifetime：长期开发入口；Size：中；Risk：中，涉及代理、生命周期、文件监听；Evidence：配置 / CLI测试、真实HTTP、前后端热更新。Owner：当前主 Agent。

### Blocked by

01，仅依赖已具备的API、初始化和基础命令入口。

### What to build

- 增加锁定依赖的Node开发镜像、Web Compose服务；Vite server-only代理配置保留宿主默认值，容器模式代理到API。
- 完成`./dev up / down / status / logs / build`；统一后台启动四个常驻服务，停止使用Compose stop，有界健康等待和安全诊断。
- 保留基础Compose / Dev Container行为与数据卷；非root、选择性源码挂载、可写Vite缓存。普通源码更新无需镜像重建，依赖变化显式build。
- 同步README推荐入口、Runbook日常操作及正式Spec；记录会话随后端重载丢失和刷新行为。

### Owned files

`docker/node-dev.Dockerfile`（新）、`docker-compose.dev.yml`、`dev`、`frontend/vite.config.ts`、`frontend/package.json`（仅必要启动适配；不新增业务依赖）、`tests/scripts/test_container_dev.py`、必要的Vite代理测试、`README.md`、`docs/runbook.md`、`docs/specs/container-dev-environment.md`、本项工作记录。与01共享文件按依赖顺序修改；不覆盖用户改动。

### Acceptance criteria

1. 已准备环境一条命令启动四个服务，终端关闭后继续运行；网页`127.0.0.1:5173`通过容器Vite访问API，Cookie / CSRF继续有效。
2. 后端临时源码修改实际触发重载，前端临时修改在浏览器生效；镜像内依赖不被宿主依赖覆盖。恢复临时改动并记录实验身份。
3. 所有宿主发布端口回环绑定；API / Web不会因Docker重启自动启动，基础设施保留已有策略。
4. 停止不删除数据，再启动恢复持久数据及资产；`status` / `logs`只针对本项目指定服务。
5. 缺少必要配置、端口冲突、数据库 / Qdrant故障或未migration在有界时间内返回可识别失败；不杀其他进程、不自动初始化或重置。
6. 原宿主Vite / API入口仍可按文档使用；不将新容器模式当作生产运行保障。

### 验证证据 / Done When

Shell真实调用行为测试、模板Compose解析、既有Vite代理回归、实际四服务启动 / HTTP、临时源码热更新、启停 / 端口 / 数据身份核对。文档及Diff审查通过，相关回归通过后本地提交；03仍负责最终candidate整体真实验收。

### Migration / Rollback

新增入口与原入口并存；端口冲突显式切换，停止新增应用服务后可返回宿主运行。无生产流量、数据库Schema或资产格式迁移。

## 03 完整运行验收与交付证据

### Change Profile / Owner

Lifetime：持续维护的验收入口及日期化证据；Size：中；Risk：较高，涉及真实API费用、账号和测试清理；Evidence：隔离新环境、真实Compose浏览器、独立SQL参考、运行资源身份。Owner：当前主 Agent。

### Blocked by

02，实际四服务与统一入口已完成；不重复列传递依赖01。

### What to build

- 建立可重复的开发运行验收入口，独立project / volume / 端口验证首次准备、状态、故障与持久性；无宿主Python / Node依赖。
- 为实际Compose网页 / API建立外部服务模式的浏览器配置与两轮真实问数验证，复用已有安全reporter、账号与参考值逻辑。不能让webServer另起宿主替身取代被验收目标。
- 真实调用少量已获授权；只创建 / 禁用专用验收账号并撤销Session，保留审计，不变更已有用户。
- 完成最终candidate的针对性软件回归、CPU / 模型与索引命令验证、运行检查、Code Review、正式Contract / Runbook / README / Acceptance及roadmap完成事实。

### Owned files

`scripts/verify_container_dev.sh`（新，或同等单一入口）、`frontend/playwright.container.config.ts`（新）、`frontend/tests/container-real.spec.ts`（新）、必要的`tests/browser_*`验收支持和`tests/scripts/test_container_dev.py`；`docs/acceptance/`的本目标记录、README / Runbook / 正式开发Spec、`docs/roadmap.md`、本项工作记录。测试工具和临时支持不得进入常驻API；原始报告写ignored目录。准确路径在实施中按最小复用决定，不扩展产品功能。

### Acceptance criteria

1. 隔离空数据卷首次准备至浏览器登录可复现；临时项目清理只作用于经标签 / 身份核实的本次资源。
2. 模型准备 / RAG构建的容器入口可用，固定模型身份和既有资产复用得到核实；实际CPU构建耗时记录，不预设性能承诺。
3. 实际Compose链路完成登录→问数→同一对话追问，匹配只读账号的独立SQL参考；浏览器报告记录candidate、镜像、模型、RAG和数据范围，凭证不入报告。
4. 热更新证据单列临时实验Diff；恢复后在clean candidate执行最终真实链路，不把脏状态改称clean。
5. 正常停止重启持久数据 / 模型 / 索引身份保持，故障和配置缺失证据齐全；账号disabled与活跃Session为0有安全核对。
6. 全部适用软件 / 浏览器 / 运行检查及Review通过；未执行项如实列出，不重跑或声明新的全套AI Evaluation基线。
7. 正式事实源可供新clone使用，roadmap只标本地开发准备完成并返回R2，R6生产部署仍待验收。

### 验证证据 / Done When

执行并记录Spec验收表全部适用场景；记录无关 / 可复用证据理由，发现真实失败补回归并修复。验证与Review绑定最终candidate，文档 / Diff检查完成、工作项状态准确，形成本地交付报告与Commit。Push / PR发布授权独立取得，当前Ticket不包含远端动作。

### Migration / Rollback

验收失败保留诊断和持久开发数据，不降低通过条件。撤销本次账号会话、禁用专用账号，清理经核实的临时容器卷；无生产发布、Feature Flag或线上回滚要求。外部资源不可用如实阻塞，不替换为假模型宣称真实通过。
