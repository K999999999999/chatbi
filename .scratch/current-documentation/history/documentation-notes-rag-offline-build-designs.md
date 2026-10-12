# 检索资产构建与发布机制：整理前的过程记录

来源：`docs/designs/rag-offline-build.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 1. 状态

- Module Spec（模块规格）：`docs/specs/rag-offline-build.md`
- Runtime Mode（运行模式）：同步 Batch（批处理）
- 当前状态：RAG 来源指纹及 production Ready 校验已实现；当前 `data/rag/current.json` 指向 `provenance-20260929`。本文件其他历史验收记录仍表示其记录时的状态。
- 最后更新：2026-09-29

## 2. 变更背景与边界

当前数据库结构、字段、关系和指标已经形成权威 JSON 事实，但 Online Query（在线查询）仍把全部静态上下文直接放入 Prompt。RAG Offline Build 的目标是把这些已确认事实构建成可独立加载的检索资产，为后续 Online Retrieval（在线检索）提供稳定输入。

当前参与者是本地开发者和未来 Online Retrieval 启动器。当前只构建资产，不接入在线查询，不生成或执行 SQL，不修改 PostgreSQL，不建设 Agent、多租户、权限平台或 Hybrid Search（混合检索）。

当前权威事实规模：

- 7 张表。
- 69 个字段。
- 6 个指标。
- 25 条关系事实，其中 9 条 Foreign Key（外键）形成 Join Edge（连接边）。

## 6. 任务清单

| Task | 内容 | 状态 |
|---|---|---|
| T1 | 冻结 Module Spec、三逻辑集合和产物契约 | 已完成 |
| T2 | 加载和校验表、字段、关系、指标事实 | 已完成并复核 |
| T3 | 生成三类 RetrievalDocument，并分离 Metric 检索正文与结构化事实 | 已完成并通过离线文档测试 |
| T4 | 生成确定性 Relationship Graph | 已完成并补强排序、重复关系、多日期边测试 |
| T5 | BGE-M3 dense + sparse Embedding Adapter | 已完成 |
| T6 | Qdrant 三集合创建、批量写入、过滤与重载检索 | 已完成 |
| T7 | 版本化目录、BuildSummary、失败保护和原子发布指针 | 已完成 |
| T8 | 固定 Retrieval Evaluation：表、字段、字段值、指标依赖 | 已完成 |
| T9 | 配置、Compose、依赖锁定、文档状态和最终回归 | 已完成 |

## 7. 验收证据

Software Test（软件测试）、AI Evaluation（AI 评测）和 Business Acceptance（业务验收）分别记录：

- Software Test：RAG Offline 33 项确定性测试通过；全仓回归为 148 passed、6 skipped、42 subtests passed。
- Dependency Check（依赖检查）：`uv lock --check` 和 `python -m compileall -q src` 通过。
- Real Integration（真实集成）：正式构建 `20260906-bge-m3-v2` 已发布；Qdrant 三个集合重新连接、精确计数和检索通过，数量为 TABLE=7、COLUMN=69、METRIC=5，关系边=9。v1 旧资产保留，不覆盖。
- AI Evaluation：BGE-M3 固定 5 案例当前为 5/5；字段案例使用候选表过滤，毛利率案例要求同时召回两个直接依赖。
- Metric Document 契约：Metric 检索正文只保留识别语义；公式、data_source、time_field、filters、depends_on 和 notes 在 metadata 中完整保留。
- Business Acceptance：构建成功摘要为 `PUBLISHED`，三个集合重载均为 true；PostgreSQL 仍为 7 张表和原始行数，`chatbi_app` 保持 7 表 SELECT、0 表写权限。

## 8. 后续边界

进入 Online Retrieval 前仍需单独设计：

- 在线三路检索编排和失败回退。
- Schema Linking（模式链接）与精简 Schema 组装。
- Relationship Graph 的在线路径查找。
- 与现有 Online Query Prompt 的可切换接入。

这些能力不因离线集合存在而自动视为已实现。
