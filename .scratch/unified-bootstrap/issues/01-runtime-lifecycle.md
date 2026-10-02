# 01 — 统一运行资源装配与生命周期

Status: done
Owner: 当前主 Agent
Canonical Source: ../spec.md；../design.md

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

## Result

实现、关联文档和验证完成；实现 Review PASS，适用代码候选 `213ed9a4e0d299f77448883c0b3c5d72341d4c67`；详细证据见 ../verification.md。

## Comments

用户在聊天确认三项拆分及整体实施；不包含远端发布授权。
