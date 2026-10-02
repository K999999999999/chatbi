# 实施 Ticket 草案

Status: confirmed（用户已确认；正式 Tickets 见 issues/，本文件保留拆分依据）
Canonical Source: spec.md；设计约束见 design.md；审查见 design-review.md
Owner: 当前主 Agent；长期维护按所属模块负责
Change Profile: 长期维护；跨模块、中等规模；生命周期和命令兼容性风险；确定性测试 + 隔离 PostgreSQL + startup smoke；默认本地 Commit，远端发布未授权。

## 01 — 统一运行资源装配与生命周期

Blocked by: None (can start immediately)

### What to build

建立 bootstrap 运行资源 / 就绪检查入口，迁移 Query API 和经营分析生产装配；API main 保留现有启动路径，仅创建无资源副作用的应用。单一 FastAPI 在 lifespan 内创建、检查、绑定并释放资源，保持原有直接注入测试 seam 和 SQLAdmin 行为。

### owned files

- 新增 src/bootstrap 的运行资源、检查及最小 package 入口。
- src/query_api/main.py、app.py、config.py（仅需要的真实配置装配迁移）。
- src/business_analysis/runtime.py、application.py；src/online_query/retrieval/rag_runtime.py 的失败释放相关部分。
- 受影响 Query API、Business Analysis、RAG Runtime、Observability 的测试及新增 bootstrap 生命周期测试。
- docs/specs/query-api.md、docs/designs/query-api.md 的生命周期描述及需要的正式说明。

### Acceptance criteria / 验证证据

- 无配置导入 main / bootstrap 不打开连接、装载模型或启动线程；进入 lifespan 才创建资源。
- 正常启动路由、认证 / 授权、分析和 SQLAdmin 使用当前已绑定资源；production 保留现有门禁及开发环境差异。
- 任意创建 / 检查失败释放已取得资源，包括 builder 内部部分创建；单个 cleanup 抛错仍尝试全部资源，原始启动原因保持。
- 关闭释放线程、engine、checkpoint、RAG clients、Tracing；重复 lifespan 不重复 mount、不复用已关闭资源、不重复释放。
- 直接注入测试不被真实配置或新资源所有权破坏；查询逐请求连接策略不改变。
- 证据：生命周期故障注入测试，Query API / admin / Business Analysis / RAG Runtime 受影响回归，模块边界检查、API startup smoke。

### Migration / Rollback / Done When

无数据迁移；所有 app 绑定和装配更改同一切片完成。受影响检查通过、正式生命周期说明更新、Diff 与实现 Review 完成后才本地提交。失败停止并修复；回滚使用本目标提交的 revert，不操作用户无关改动。

## 02 — 统一数据库迁移和管理员命令，移除旧入口

Blocked by: None (can start immediately)

### What to build

建立统一命令分发，提供 migrate、create-admin，迁移命令解析与装配，继续调用 Control DB 所属实现。一次完成全部消费者迁移和旧 Control DB CLI 入口删除，不保留转发。

### owned files

- src/bootstrap/__main__.py、commands.py 和数据库命令装配文件；package 入口仅必要编辑。
- 移除 src/chatbi_control/__main__.py、cli.py 的旧命令职责；保留 bootstrap.py、database.py 的具体实现。
- scripts/run_database_tests.py、reset_dev_postgres.py（仅命令调用替换）。
- .github/workflows/ci.yml 的数据库命令调用、相关 CLI / bootstrap / 集成 / reset 测试。
- README.md、docs/runbook.md、docs/architecture.md 当前数据库初始化入口说明。

### Acceptance criteria / 验证证据

- 新命令帮助、参数、退出码符合 Spec；帮助和 migrate 不加载在线服务 / Embedding。
- migration 可重复安装 Schema、RBAC、checkpoint 和 grants，不创建用户。
- create-admin 隐藏密码及确认，首次成功，重复拒绝，权限与 Secret 边界保持。
- 旧 python -m src.chatbi_control 入口不可执行；无可执行消费者残留，历史记录除外。
- reset 和测试 runner 操作语义保持，仅调用新入口。
- 证据：CLI / 故障测试、既有隔离 PostgreSQL dev profile migration / 权限 / 管理员生命周期、调用替换回归与静态搜索。

### Migration / Rollback / Done When

新命令、删除旧入口与调用迁移同一切片完成；无数据变更。参数 / 权限回归和隔离集成通过，说明更新、Diff / Review 完成后本地提交。回滚整组入口及消费者，不保留半迁移状态。

## 03 — 统一模型与 RAG 命令，完成整体入口迁移验收

Blocked by: 02（复用已建立的统一命令分发）；整体目标收尾还需 01 完成。

### What to build

加入 prepare-model、build-rag，迁移模型准备及 RAG 命令装配，删除旧脚本和模块命令入口。完成当前文档、CI、测试及调用迁移，验证所有四类命令和运行入口形成闭环。

### owned files

- src/bootstrap 的模型 / RAG 命令装配和 commands.py 分发。
- 移除 scripts/prepare_embedding_model.py、src/rag_offline/__main__.py；保留 rag_offline 模块业务 API。
- tests/scripts/test_prepare_embedding_model.py 迁移为 bootstrap 命令测试；RAG CLI、分发、资源释放和受影响 builder 软件测试。
- .github/workflows/real-e2e.yml 命令调用；README.md、docs/runbook.md、适用的 Architecture / RAG Spec / Design 和代码地图。
- docs/roadmap.md（仅有已确认事实受影响时更新）、本目标规划 / 验证记录。

### Acceptance criteria / 验证证据

- 四类命令和帮助完整；模型配置、revision / 缓存、RAG 参数 / 退出码 / 发布行为保持。
- 单一命令不装配无关运行资源；Qdrant 临时资源成功和失败时释放，RAG 失败不更新现有指针。
- 旧模型准备 / RAG 命令入口删除；所有当前调用迁移，新入口无需兼容转发。
- 历史证据保留原身份；受影响正式文档更新，路线图检查有更新或不适用理由。
- 证据：替身模型下载 / CLI 与 Qdrant 失败释放测试，现有 builder 软件回归，命令残留搜索、模块边界、Markdown links、Diff；01、02 证据仍适用于最终候选时复用，基线受影响时补跑。
- 整体最终候选完成仓库要求的测试、隔离数据库验证、API startup smoke 和 Code Review；无真实模型下载 / RAG 写入 / LLM 请求的隐式测试。

### Migration / Rollback / Done When

删除旧入口和消费者迁移同一切片完成；无 Schema、索引或配置格式变化，不改变真实数据。01、02、03 均完成，正式文档、验证身份、路线图检查及本机记录齐备才报告整体完成。回滚该命令组及消费者；未获发布授权不 Push / PR。

## 执行与升级路径

- 默认同一目标、同一 branch / worktree 串行实施 01 → 02 → 03；01 和 02 无代码启动依赖，不为顺序制造虚假依赖。
- 每项维护自己关联的测试与文档，避免最后才补无证据的大量迁移。
- 遇到未决权限、HTTP、状态、依赖方向或 Spec 范围变化时停在对应边界，返回设计 / Spec；测试失败在已确认范围内修复。
- 用户确认拆分并授权整体实施后连续完成全部 Tickets，不逐项等待；发布授权独立。
