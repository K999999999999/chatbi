# 03 标准容器运行并删除Stable系统

Status: done
Canonical Source: [Spec](../spec.md)、[Design](../design.md)。用户确认四项拆分及完整本地实施、验证、Commit；无发布授权。


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
Result: 已完成本目标范围；验证与失败处置见[验收](../acceptance.md)，当前上下文Code Review记录见[Review](../code-review.md)。
Comments: 混合测试逐条判断归属，不根据文件名批量删除应用保护证据。
