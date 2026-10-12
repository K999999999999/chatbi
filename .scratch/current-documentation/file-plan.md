# 文档处置清单

Status: 整理方案草案，未执行迁移；规划基线 `c7f7e74`。
目标与验收见 [Spec](spec.md)。57 份现有 docs 文档及根目录入口均纳入核对；不以减少到固定文件数作为目标。

## 入口与整体说明

| 当前位置 | 整理方向 | 独有内容与引用核对 |
| --- | --- | --- |
| README.md | 唯一人类导航入口，整合项目导航的必要代码 / 文档地图 | 保留从全景到能力、模块与验证的定位能力；命令细节进入 Runbook。 |
| AGENTS.md | 简短强制规则，加文档维护入口 | 现行恢复、授权、流程和安全规则完整保留；同步新文档位置。 |
| CONTEXT.md / CONTEXT-MAP.md（仅存在者） | 保留领域语义，按当前文档阅读要求检查 | 不把领域事实改写成架构或功能 Spec；不为空目录补文件。 |
| docs/project-guide.md | 导航并入 README；细节归入所属文档，移除独立入口 | 旧稿必要追溯内容进入 project-navigation 工作记录；不直接整份复制进 README。 |
| docs/architecture.md | 当前整体架构与关键约束 | 精简重复产品范围、详细代码导航、历史状态；维护核心语义到物理映射链路。 |
| docs/product-scope.md | 按当前能力重组 | 去除阶段式追加、完成历史；保留支持和限制。 |
| docs/roadmap.md | 当前阶段与确认的未来方向 | 历次诊断 / 候选过程归所属工作记录；已有历史材料不重复归档。 |
| docs/runbook.md | 按开发、调试、Stable、验证、维护任务组织 | 保留命令前提、环境隔离、Secret 规则与数据操作影响；更新章节链接。 |

## 当前行为文档

以下现有 Spec 的当前有效规则保留，历史背景、状态进度、任务编号与候选结果归属工作记录。只调整内容归属，不改变已确认行为。

| docs/specs/ 下文件 | 整理方向 |
| --- | --- |
| bootstrap.md | 保留当前初始化与资源生命周期 Contract。 |
| container-dev-environment.md | 保留开发环境与统一命令 Contract。 |
| evaluation.md | 保留当前评测、报告身份、有效性与验收规则。 |
| execution-streaming-v1.md | 保留当前执行、取消、SSE 与恢复行为，整合已确认扩展。 |
| history-results-v1.md | 保留当前历史 / 成果 / 续聊规则，移除过期发布状态。 |
| local-deployment-v1.md | 保留当前 Stable 部署与兼容边界，验收过程归档。 |
| local-operations-v1.md | 保留当前就绪、额度、备份、恢复与运维行为。 |
| observability.md | 保留当前观测、安全属性与配置边界，移出任务完成记录。 |
| online-query.md | 保留一次有效查询与 SQL Guard Contract；引用其他模块权威规则。 |
| online-retrieval.md | 历史基线归入在线检索工作记录；根据 `.scratch/online-retrieval-v1/spec.md` 整理现行检索 Contract 替换正文。 |
| multi-metric-retrieval.md | 历史独立流水线与阶段决定归档；当前多指标规则融入 online-retrieval，不保留竞争 Spec。 |
| query-api.md | 保留当前 API / 身份 / 短期多轮接口规则；从已确认多轮规划核对未正式固化的有效规则，历史来源保留在工作记录。 |
| rag-offline-build.md | 保留发布资产、校验与失败处理 Contract。 |
| result-export-v1.md | 保留当前 XLSX / PNG / PDF 行为与安全约束。 |
| result-visualization-v1.md | 保留当前展示、数字、图表和业务证据行为。 |
| web-dialogue-v1.md | 保留当前浏览器入口、模式、身份与交互；清理旧发布进度。 |

当前经营分析规划与因素归因规则仍有 `.scratch/business-analysis-v1/`、`.scratch/business-analysis-root-cause-v1/` 来源。核对现有正式文档覆盖后，将未覆盖的当前行为集中固化为正式经营分析 Spec；不复制两份历史完整规划。明确区分原功能边界和后续扩展，不自行扩展业务范围。

其他已交付工作仅在当前正式文档依赖其历史规划作为唯一依据时提取有效规则；不为所有历史工程改动新增永久 Spec。

## 当前实现说明

逐份核对重要机制：确有独立维护价值时精简保留；仅重复架构 / Spec / Runbook 时提取未覆盖内容后归档。以下为初步落位，不表示已完成内容审查。

| docs/designs/ 下文件 | 重点保留 / 归档方向 |
| --- | --- |
| evaluation.md | 当前结果比较、报告身份和有效性机制；开发任务归档。 |
| execution-streaming-v1.md | 受理、去重、worker / 取消 / 关闭、事件快照等关键协调机制。 |
| history-results-v1.md | 事务、占用、状态提交、checkpoint 和恢复机制。 |
| history-query-restoration.md | 当前机制融入 history-results-v1 或相应当前 Spec；独立旧方案归 history-results-v1 工作记录。 |
| local-deployment-v1.md | 资源身份、兼容升级与回滚机制。 |
| local-operations-v1.md | 并发互斥、备份快照、隔离恢复与切换机制。 |
| observability.md | Trace 时序、上下文传播与安全属性机制；任务清单及旧验收归档。 |
| online-query.md | SQL Guard / 执行中确有独立价值的机制；重复链路和任务进度归档。 |
| online-retrieval.md | 当前文件明确 Historical Record，旧稿归档；如需保留当前关系图与上下文机制，以当前 Contract 核对后重写。 |
| multi-metric-retrieval.md | 当前文件明确 Historical Record，归档；有效当前机制并入在线检索说明。 |
| query-api.md | 装配 / 生命周期中必要机制按当前实现核对；纯接口规则移到 API Spec，操作命令移到 Runbook；无独立内容则归档。 |
| rag-offline-build.md | 版本构建、验证、发布和失败恢复机制；任务和旧证据归档。 |
| result-export-v1.md | 导出 worker、renderer 隔离及资源生命周期。 |
| result-visualization-v1.md | 独有当前规则或映射归相应 Spec / 架构；无重要独立机制则归档。 |
| web-dialogue-v1.md | 当前 Cookie / CSRF / 状态与请求协调的必要机制；退役客户端和旧迁移计划归档。 |

## 历史验收

原始报告位置、提交、日期和结论不变。优先使用既有完整工作证据；只有原正式文档包含独有证据时才完整归档原稿。归档后的链接修复在本次迁移中验证。

| docs/acceptance/ 下文件 | 所属历史工作记录 |
| --- | --- |
| business-analysis-root-cause-v1-20260928.md | .scratch/business-analysis-root-cause-v1/ |
| business-analysis-v1-20260921.md | .scratch/business-analysis-v1/ |
| container-dev-environment-20261003.md | .scratch/container-dev-environment/ |
| execution-streaming-v1.md | .scratch/execution-streaming-v1/ |
| harness-workflow-control.md | .scratch/harness-workflow-control/ |
| history-results-v1.md | .scratch/history-results-v1/ |
| local-deployment-v1.md | .scratch/r6-local-deployment/ |
| local-operations-v1.md | .scratch/local-operations-v1/ |
| multi-metric-retrieval-20260914.md | 核对原提交与关联记录后归所属检索工作；不存在所属目录时保存本工作项 history 并标明来源，不造历史任务。 |
| multi-turn-query-v1-20260919.md | .scratch/multi-turn-conversation-v1/ |
| observability-t5-20260914.md | 核对原任务来源后归属；找不到所属记录时保存本工作项 history 并标明来源。 |
| online-retrieval-20260907.md | 核对 online-retrieval-architecture / online-retrieval-v1 原始记录和提交后归属。 |
| product-v1-delivery.md | 历史交付事实归 product-v1-delivery-closeout 工作记录；当前导航、运行与验证入口融入 README / Runbook。 |
| result-export-v1.md | .scratch/result-export-v1/ |
| result-visualization-v1-20261004.md | .scratch/result-visualization-v1/ |
| web-dialogue-v1-20261003.md | .scratch/web-dialogue-v1/ |

`docs/acceptance/` 清空后不保留空目录，也不改写历史通过结果来适应当前版本。

## ADR 与协作规则

| 当前文件 | 整理方向 |
| --- | --- |
| docs/adr/0001-multi-turn-query-v1-boundaries.md | 核对多轮工作记录已保存的决定，保留独有理由 / 取舍；归历史记录。未来整体项目 ADR 按需创建。 |
| docs/agents/domain.md | 保留领域事实读取与边界；删除与入口重复的叙述并修复事实源引用。 |
| docs/agents/issue-tracker.md | 保留规划、实时状态、授权、恢复与工作生命周期；明确交付时当前规则固化，历史留在工作记录。 |
| docs/agents/git-pr-workflow.md | 保留现行候选、验证、发布、Auto-merge 与收尾规则；纳入文档核对，不新增用户 Review 阶段。 |
| docs/agents/agent-harness.md | 当前必要规则分入上述对应说明；导航融入 README / AGENTS；独立演变过程归已有 Harness 工作记录。拟用文档维护说明集中承接归属与更新规范。 |
| docs/agents/documentation.md（拟） | 当前文档维护规范唯一详细位置：文档分工、更新触发、归档、检查和 Review；不重复完整 Git 流程。 |
| .github/pull_request_template.md | 在现有文档 / Agent Review 部分记录当前文档更新、历史记录及不适用理由。 |

## 工具与证据

现有 Markdown 链接检查继续适用于工作记录。新增结构规则接入现有 Deterministic tests job，并建立不依赖外部服务的 fixture 回归；共享解析规则以避免本地 / CI 差异和代码块误报。

迁移完成后记录逐文件结果、最终权威位置、历史归档位置、链接修复与语义核对证据。该记录属于本工作项，不再回写为正式文档中的实施日志。
