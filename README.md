# ChatBI

ChatBI是面向销售数据的领域AI引擎，提供电脑端问数、多轮追问、经营分析、图表、私人历史与成果、后台执行和文件导出。模型提出候选，程序裁决业务口径、权限与SQL安全。

## 启动项目

推荐Windows + WSL / Linux。宿主只需Git、Bash、Docker Engine和Docker Compose；Python、uv、Node、浏览器和字体在容器内提供。

复制 `.env.example` 为 `.env`，填写LLM配置与随机管理员签名Key，首次执行：

```bash
./dev build
./dev infra
./dev migrate
./dev create-admin --username admin-1
./dev prepare-model
./dev build-rag
./dev up
```

打开 `http://127.0.0.1:5173`。日常 `./dev up` 启动、`./dev down` 停止并保留数据，`./dev logs --follow` 查看日志。已启动的常驻服务随Docker重启自动恢复；主动停止后保持停止，直到再次执行 `./dev up`。Docker Desktop本身需先启动。后端源码挂载并自动重载，前端Vite热更新；依赖变化后执行 `./dev build`。

新环境必须先初始化，`up`不会自动创建管理员或索引。完整配置、模型缓存、首次步骤与故障排查见[Runbook](docs/runbook.md)。Secret只放本地配置，不提交到Git。

## 构建与验证

```bash
./dev help
./dev check
./dev test all
./dev evaluate --help
```

这些命令在容器里执行，不需要宿主uv/npm。数据库和浏览器测试使用隔离资源；真实LLM评测需显式执行，会产生调用费用。

`./dev help`按八类展示环境管理、初始化、代码验证、AI评测、容器验收、诊断维护、账号恢复和开发协作。软件测试验证本地挂载源码；`./dev verify dev`是按需执行的真实业务验收，会调用真实LLM。管理员忘记密码通过`./dev recover-admin dev`显式操作，信任与恢复规则见[Runbook](docs/runbook.md#7-管理员忘记密码)。

`./dev build`构建源码开发和测试所需的依赖镜像；项目不提供独立业务APP镜像构建路线。已有APP容器、镜像、卷和配置不会被自动删除；当前支持边界见[本地源码运行Spec](docs/specs/container-deployment.md)。项目不提供Stable发布、升级回滚、备份恢复或企业生产编排。

## 项目地图

| 内容 | 入口 |
| --- | --- |
| 能力、支持范围与当前方向 | [Product Scope](docs/product-scope.md)、[Roadmap](docs/roadmap.md) |
| 模块、数据与核心链路 | [Architecture](docs/architecture.md) |
| 当前行为与实现机制 | [Specs](docs/specs)、[Designs](docs/designs) |
| HTTP、身份与控制数据 | [query_api](src/query_api)、[authorization](src/authorization)、[chatbi_control](src/chatbi_control) |
| 问数、检索与SQL安全 | [online_query](src/online_query) |
| 分析与归因 | [business_analysis](src/business_analysis) |
| 业务事实与物理结构 | [semantic](src/semantic)、[structure](src/structure)、[database](database) |
| 初始化、装配与离线索引 | [bootstrap](src/bootstrap)、[rag_offline](src/rag_offline) |
| 应用运行保护与诊断 | [就绪规则](docs/specs/application-readiness.md)、[observability](src/observability) |
| 测试、评测与协作 | [tests](tests)、[evaluation](evaluation)、[AGENTS.md](AGENTS.md) |

当前为本机单API进程，不承诺公网、多副本或多用户容量。历史方案、旧部署验收与开发记录保存在[.scratch](.scratch)，不作为当前启动教程；原始本机报告不随clone分发。
