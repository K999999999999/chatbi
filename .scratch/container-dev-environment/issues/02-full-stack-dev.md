# 02 一键前后端开发与热更新

Status: done
Owner: 当前主 Agent
Canonical Source: ../spec.md、../design.md
Authorization: 用户已确认三项拆分并授权整体本地实施；不含发布

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


## Result

实现完成；证据见 ../verification.md。03已完成最终clean candidate验收，代码候选38602d9；无远端发布。

## Comments

拆分与整体实施已获本轮确认，按01→02→03连续推进。
