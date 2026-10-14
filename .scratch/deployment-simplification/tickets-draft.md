# Deployment Simplification Ticket 草案

Status: draft；未正式写入issues，待用户确认拆分与实施范围。
Canonical Source: [已确认Spec](spec.md)、[Design](design.md)、[Design Review PASS](design-review.md)。
共同Owner: 当前实施Agent。发现Contract外决定返回用户确认；每项完成受影响检查、Code Review及Diff检查后才可本地Commit；无Push/PR或真实Stable资源操作授权。

## 01 应用不再依赖Stable运维状态

Change Profile: 持续维护 / 小至中跨装配与状态UI / 中风险（权限、生命周期、请求保护）/ 软件与浏览器回归 / 本地交付。
Owner: 当前实施Agent。
Blocked by: None (can start immediately)

### What to build / Scope

删除backup provider、备份状态读取和Unix socket装配；删除details.backup和网页备份提示。保留应用装配、readiness、真实模型观察、状态权限、受理与共享额度、退出清理。先解除应用对Stable文件与脚本的依赖，使应用在没有备份/发布目录时正常运行。

Owned files: src/bootstrap/runtime.py、backup_status.py、operations_socket.py；src/query_api/operations.py及必要状态装配；frontend/src/OperationsStatus.tsx；tests/bootstrap/test_operations.py、test_runtime.py；tests/query_api/test_operations_state.py、test_operations_api.py、test_admission.py及受影响生命周期测试；frontend/tests/operations.spec.ts；必要bootstrap/状态Contract文档。

Out of Scope: 查询/分析链路、权限规则、DB结构、共享额度上限调整；Stable CLI和备份工具最终删除留03，不维护中间候选的Stable可运行性。

### Acceptance criteria

- 无备份目录/socket仍能装配并关闭应用，失效资源正确清理。
- 管理员响应不含details.backup，其余状态字段/权限/认证/无保活保持；普通用户仍无详情。
- readiness的成功/失败/超时/过期/恢复、模型观察及容量保护保持。
- 网页不再出现备份提示，现有状态/登录过期/安全显示测试通过。

Evidence: 受影响bootstrap、operations、admission、execution及授权回归；前端typecheck/build和operations浏览器测试。中间阶段可以使用现有容器运行命令，最终统一入口由02补齐。
Migration / Rollback: 仅删除已确认API字段，无数据迁移；源代码可由修复提交恢复。失败暂停03，禁止回退用户修改。
Done When: 上述行为及测试/Review PASS，删除的只有运维装配，状态/Bootstrap Contract同步，候选与结果写Result。
Result: 待实施。
Comments: API字段删除是用户确认的唯一业务接口例外；其余保护不能按名称删除。

## 02 开发者无需宿主Python/Node即可完成验证

Change Profile: 持续维护 / 中等跨dev、测试配置与脚本 / 中风险（临时资源、凭据和测试覆盖）/ 软件、PG、浏览器、renderer / 本地交付。
Owner: 当前实施Agent。
Blocked by: None (can start immediately)

### What to build / Scope

增加Design定义的dev test/check/evaluate入口与容器调试说明；容器执行Python/Node/评测，Bash管理隔离测试数据库。适配Playwright容器fixture并保留CI默认行为，补齐实际浏览器/renderer能力。保留现有dev初始化、热更新和卷名。

Owned files: dev；docker-compose.dev.yml及新增测试Compose override；docker/python-dev.Dockerfile、docker/node-dev.Dockerfile；scripts/run_database_tests.py及必要容器测试Bash入口；frontend/playwright*.config.ts的执行装配；tests/scripts/test_run_database_tests.py、test_container_dev.py及新增入口测试；tests/container_dev_support.py必要工具；docs/specs/container-dev-environment.md和对应Runbook命令章节。

Out of Scope: Docker socket挂业务API、新依赖、修改评测案例/业务断言、日常数据重置、CI全部容器重写。

### Acceptance criteria

- 用不含python/uv/node/npm的宿主执行环境，通过Bash/Docker完成test/check及evaluate帮助/确定性入口验证。
- test python运行全量软件回归；database分别运行CI和development隔离profile，启用相应开关并覆盖history/execution/checkpoint。
- web运行现有确定性浏览器套件，renderer启用实际Chromium/PDF检查；不以缺少浏览器跳过。
- 帮助/未知参数/失败退出码明确，all不调用收费真实LLM；报告可读取，Secret不输出。
- 失败/成功清理仅处理本次标签资源，API无migration身份/Docker socket；已有卷身份不变。
- CI原有Playwright调用仍兼容，评测参数/案例不改变。

Evidence: 入口正/负向软件验证、隔离PG两profile、浏览器与renderer、前端类型/构建、容器工具实际执行；记录适用skip；评测帮助/确定性装配不使用历史AI成绩替代。
Migration / Rollback: 先补新容器入口，后移除宿主教程；旧脚本必要逻辑迁移后才能删除。测试临时凭据/资源按运行标签清理；测试失败不得影响日常服务。
Done When: 容器入口真实可用、未隐藏宿主Python/Node调用，验证/Review PASS，开发Contract/操作入口同步。
Result: 待实施。
Comments: 此项技术上不依赖01；同一Agent按编号实施避免共享文件并发写入。

## 03 标准容器运行并删除Stable系统

Change Profile: 持续维护 / 较大部署入口收敛与旧系统删除 / 高风险（初始化、资源隔离）/ 构建、空卷初始化、失败边界 / 本地交付。
Owner: 当前实施Agent。
Blocked by: 01, 02

### What to build / Scope

简化并迁移应用Dockerfile，提供仅本地build的标准Compose；先验证必要初始化/运行门禁可用，再按Spec清单删除Stable CLI、运维镜像、发布状态、升级回滚、备份恢复/调度/锁/绑定、模板和专属测试。移植local容器验收中必要隔离/数据/业务验证能力，移除专属发布身份依赖。

Owned files: Dockerfile（由docker/local.Dockerfile迁移）、.dockerignore；docker-compose.local.yml及标准应用Compose；.env.local.example及必要安全模板；local；docker/operations.Dockerfile；scripts/local_*、verify_local_*中Spec列明的运维文件与验收迁移部分；scripts/verify_container_dev.sh；对应tests/scripts/test_local_*；src/bootstrap/readiness.py/commands.py及必要通用检查；相关部署Contract/Design文档。

Out of Scope: database/**/*.sql内容变化、现有真实卷/密钥/备份清理、业务API变更扩大、镜像发布、生产切换、新通用编排系统。

### Acceptance criteria

- api/database targets无需Git发布参数/release文件即可构建；frontend/export资产、Seed、字体、浏览器和非root约束完整。
- 独立空卷Compose依次infra/migrate/admin/model/rag/API成功，模型缓存可复用，完整PG健康与迁移不相互等待。
- 缺少必要配置/资产或端口冲突安全失败；不删除现有资源、不输出Secret。
- 应用不依赖.local、release/state/socket/backup工具；必要数据库/RAG/catalog/导出校验有对应验证，不通过删除预检绕过校验。
- Stable运维入口与专属测试消费者清零；普通文件锁、应用advisory lock/epoch/generation保持。
- 保留的容器测试仍可执行；日常dev初始化/热更新/数据持久性不回归。

Evidence: 全部保留Dockerfile适用target构建、Compose配置安全断言、独立空卷初始化/健康/持久性及失败验证，受影响全量pytest和容器部署测试，删除前后依赖搜索与Review。
Migration / Rollback: 必要校验和验收先迁移，标准环境可用后删除旧入口；构建/初始化失败停止后续删除并修复。无Schema迁移，不操作旧Stable；已确认API例外仅来自01。
Done When: 标准运行能力通过、旧系统代码/专属CI入口无消费者、删除闭包与Review PASS，必要当前Contract已有替代入口；完整文档归档和最终验收留04。
Result: 待实施。
Comments: 混合测试逐条判断归属，不根据文件名批量删除应用保护证据。

## 04 单一使用说明与最终全量验收

Change Profile: 本次交付关闭与持续文档 / 中等 / 中风险（证据完整、首次部署）/ 全量验证、Business Acceptance与Code Review / 默认本地交付。
Owner: 当前实施Agent。
Blocked by: 03

### What to build / Scope

整理README/Runbook，移除宿主/Stable教程，说明dev与Dockerfile用途、首次步骤、配置、测试、调试和标准构建。迁移R7剩余应用Contract，归档失效运维Spec/Design，修复当前及历史链接，同步Architecture/Product Scope/Roadmap。清理失效CI入口，完成最终候选全量测试、构建、独立首次部署与真实业务闭环。

Owned files: README.md、docs/runbook.md、architecture.md、product-scope.md、roadmap.md；docs/specs/local-deployment-v1.md、local-operations-v1.md及query-api/execution/observability/bootstrap/container-dev的相关规则；docs/designs/local-deployment-v1.md、local-operations-v1.md；.github/workflows/ci.yml、real-e2e.yml必要适配；历史文档归档与引用；.scratch/deployment-simplification验收/Review/状态证据。

Out of Scope: 功能优先级重排、历史报告重标、评测案例变化、实际Stable资源替换/删除、Push/PR。

### Acceptance criteria

- README唯一推荐dev入口，宿主仅要求Docker/Compose/Git/Bash；Runbook覆盖配置、首次/日常、测试/调试/评测，当前步骤实际可执行。
- R7应用保护规则有唯一正式权威入口，运维历史保留且不再作为当前承诺；当前/历史Markdown链接通过。
- 最终候选全量Python、两PG profile、前端类型/build/export、浏览器、renderer、质量/锁文件/文档/边界及适用安全检查完成。
- 开发和标准应用Compose各在隔离资源验证首次准备；真实登录、问数/追问、分析、历史成果、XLSX/PNG/PDF及重启持久性验证；源码热更新在开发模式验证。
- 记录所有失败/skip/未执行项及原因、候选/资源身份；未完成的必要验收不能标done。业务/模型不变的历史Evaluation只作为原基线并说明未重跑理由。
- 日常/旧Stable容器、卷、配置、备份和密钥未被更改；仅清理新建验收资源及临时账号。

Evidence: 验收报告和运行资源身份、测试结果、目标Commit关联、完整Diff/Contract Code Review、历史去向和链接、Roadmap适用性结论、Harness检查。
Migration / Rollback: 链接在归档前列出闭包，独有历史内容不丢失；验收失败修复后重跑受影响检查，不伪造完成；真实资源不做rollout，因此无平台回滚步骤。
Done When: 所有适用验收通过且限制准确披露，正式事实源/历史去向/CI/Review一致，全部Tickets完成；本地交付与发布授权边界明确。
Result: 待实施。
Comments: 真实模型验收按本目标确认的测试范围运行；不可用凭据或下载失败需报告并保留未完成状态。发布须另行明确授权。
