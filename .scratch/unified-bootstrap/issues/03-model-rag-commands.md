# 03 — 统一模型与 RAG 命令，完成整体入口迁移验收

Status: done
Owner: 当前主 Agent
Canonical Source: ../spec.md；../design.md

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

## Result

实现、关联文档和验证完成；实现 Review PASS，详细证据见 ../verification.md（待最终候选记录固化）。

## Comments

用户在聊天确认三项拆分及整体实施；不包含远端发布授权。
