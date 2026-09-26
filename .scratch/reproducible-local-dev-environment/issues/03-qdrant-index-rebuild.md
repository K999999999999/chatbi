# Qdrant 持久化与 RAG 索引重建

Status: done
Owner: ChatBI 仓库维护者
Backup Owner: None
Blocked by: None (can start immediately)

## Change Profile

- Lifetime: 短期，Qdrant 本地服务、索引构建和恢复流程。
- Size: M。
- Risk: 高；涉及 Embedding、Qdrant 和在线 Retrieval 使用的发布资产。
- Evidence: 离线确定性测试、真实 Qdrant 构建 / 重载 / 检索验证。
- Delivery: 当前 Feature branch 上的独立逻辑切片；复用现有 RAG Offline Build。

## Canonical Source

- 行为基线：`../spec.md`。
- RAG 行为与资产事实：`docs/specs/rag-offline-build.md`、`docs/designs/rag-offline-build.md`。
- 源资产：`src/structure/generated/` 和 `src/semantic/metrics.json`。

## What to build

将 Qdrant 运行数据从源码 `data/qdrant` bind mount 改为项目专属 named volume。明确服务启动、索引首次构建、索引重建和数据清除之间的区别。

复用 `src.rag_offline` 构建入口，从 tracked 源资产构建 TABLE / COLUMN / METRIC 集合、Relationship Graph、版本发布指针并验证检索。固定 BGE-M3 的不可变模型 revision，说明首次下载方式和可复用的本地模型缓存。

## Acceptance criteria

- 日常 `docker compose up` 只启动 Qdrant，不自动加载 Embedding 模型或重建索引。
- 全新 Qdrant volume 可从仓库源资产重复构建三个逻辑集合和关系图，并通过集合数量、重载和检索验证。
- 新版本构建失败时不替换当前发布指针或损坏已发布资产。
- Embedding 模型名称 / 不可变 revision、维度和必要运行配置明确；模型权重与缓存不提交 Git。
- Qdrant 清除 / 重建只针对 Qdrant 数据，不删除 PostgreSQL volume；清除后可从仓库资产重新恢复。

## Owned files

- `docker-compose.yml`
- `.env.example`
- `src/rag_offline/config.py`、`src/rag_offline/embedding.py`、`src/rag_offline/__main__.py`
- `tests/rag_offline/`
- `docs/runbook.md`（Qdrant、模型准备、构建、重建和验证说明）

## Validation evidence

- 运行现有离线构建、来源校验、Embedding Contract 和 Qdrant store 确定性测试。
- 使用真实本地 Qdrant 从空 volume 构建资产并完成重载 / 检索验证。
- 验证失败构建保留旧发布版本、Qdrant-only 清除不触碰 PostgreSQL。
- 最终交付按仓库高风险链路规则完成相应验收；真实 LLM Evaluation 仍需单独授权，不作为 Compose 启动步骤。

## Migration / Rollback

- 不迁移、读取、覆盖或删除旧 `data/qdrant` 与 W11 旧数据。
- Qdrant 当前索引由版本化发布指针管理；失败构建不清理当前可用版本。
- 显式删除 Qdrant named volume 后，仅通过本 Ticket 的索引构建流程恢复；PostgreSQL volume 保持不变。

## Done When

Qdrant 使用独立持久 volume，索引能从 Git 源资产及固定 Embedding revision 重建、验证和恢复，且服务日常启动不会自动重新向量化。

## Result

Windows 与 WSL/Linux 的 Qdrant 服务均在独立 named volume 上启动并通过健康验证。准备并复用了 BGE-M3 revision `5617a9f61b028005a4858fdac845db406aefb181` 本地缓存；从当前工作树及最终 clean clone 的 Git 源资产发布 7 个 TABLE、69 个 COLUMN、6 个 METRIC 文档及 9 条关系边。Windows Qdrant-only reset 后成功重建 v2，在线检索对 TABLE/COLUMN/METRIC 各返回 3 个候选；服务重启及 Dev Container 服务重建后索引仍可检索。Qdrant 清理未改变 PostgreSQL 指纹。

## Comments

- 当前离线 Builder 已实现版本化集合、Relationship Graph、旧发布保护和检索验证；优先复用现有能力，避免重复实现。
