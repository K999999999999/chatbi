# 01 容器内首次准备与可启动 API

Status: done
Owner: 当前主 Agent
Canonical Source: ../spec.md、../design.md
Authorization: 用户已确认三项拆分并授权整体本地实施；不含发布

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


## Result

实现完成；证据见 ../verification.md。完整目标仍等待03最终clean candidate验收。

## Comments

拆分与整体实施已获本轮确认，按01→02→03连续推进。
