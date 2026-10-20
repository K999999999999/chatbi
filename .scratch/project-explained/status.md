# 项目全景详解工作记录

## 规划快照

- 基线：`baseline-20261020` / `fa5dd6edbace8b866ddacbf1a9a50133d77d3468`。
- 范围与实施授权见[短 Spec](spec.md)。
- 分支：`docs/project-explained`；使用原有 worktree。
- 实时进度保存在 Git 公共目录下的 `harness/work-items/project-explained/status.md`。
- 发布授权：未取得；本轮形成可阅读文档与本地候选。

## 实施与验收

### 当前交付

- 新增[项目全景详解](../../docs/project-explained.md)，以冻结基线为业务和代码讲解依据；正文涵盖 22 个主题，从业务目标、四张地图、产品旅程读到架构、语义、链路、状态、安全、目录、运行、验证和讲解路线。
- 同一篇文档包含整体逻辑图、数据关联图、RAG 离线路线、固定经营分析流程、本机组件图，以及完整问数 SQL 示意与毛利因素计算例子。教学数据不冒称真实运行结果。
- README 新增正式阅读入口；文档维护规则登记教学职责、权威来源和同步触发要求。
- 不移动已有文档或历史，不改产品代码、数据、资源配置或冻结标签。

### 事实与覆盖核对

| 范围 | 已核对的来源与结论 |
| --- | --- |
| 目标与边界 | Product Scope、Architecture、Roadmap；保持销售领域、模块化单体、当前本机单 API 与明确非支持范围 |
| 语义与数据 | metrics / dimensions / query_bindings JSON、Sales Mart DDL、Query Understanding Contract；区分指标口径、物理投影、显示配置、检索派生资产 |
| 查询主链 | Online Query Spec / Service、授权入口、检索与 Guard 规则；语义在前、当前认证映射在后、Guard 通过才执行 |
| RAG | Online Retrieval 与 RAG Offline Specs / Designs；结构导出与离线构建分开、三类资产和关系图同版本、技术失败关闭 |
| 恢复与状态 | Query Restoration、History、Execution Specs；完整业务条件、幂等受理、只读重开、重新授权、失败不污染、真实停止后释放 |
| 分析 | Business Analysis Spec / Application；固定两期流程、产品与因素归因、确定性对账、受校验总结、独立 checkpoint |
| 安全与用户 | Web / API Specs、RBAC seed；固定角色、当前身份、历史 owner 隔离与共享业务数据边界 |
| 展示与导出 | 可视化 / 导出 Specs / Designs；认证元数据、精度与降级、成功快照、无额外查询、隔离与清理 |
| 运行与验证 | Bootstrap / readiness / container / Evaluation 文档、Compose、依赖配置与 Runbook；显式初始化、存活与就绪、软件 / AI / 业务证据区别 |
| 代码入口 | 正文 Markdown 路径经组合检查，关键入口与源码存在性核对；物理目录不冒充固定分层或调用栈 |

### 验证与 Review

- 首次 ./dev check docs：PASS，报告 20261020T115605Z-fa5dd6e-check-docs-6a23812b4014，针对未提交文档范围；不是冻结提交上原有内容的历史验收。
- 最终正文 SHA-256：4b54538e15c53f06e5a49181454f93155956f85858dd46b2b20a69fc266d325f；975 行，包含 22 个主题及阅读地图。
- 提交前 ./dev check docs：PASS，报告 20261020T115858Z-fa5dd6e-check-docs-c6475b853939；基线为 fa5dd6e，覆盖当前 staged 文档范围。文档语义与检查后记录的结果文本分开核对。
- git diff --cached --check：PASS。
- Review: PASS；范围为短 Spec 所列 5 个文件。核对完整正文、当前事实源和关键代码；已修正总图中的授权路径与“检索后认证映射”标注，未遗留 Findings。长文粒度符合用户要求，外部链接仅用于深入，正文有完整解释；维护成本通过明确事实源和更新归属约束。
- Clean Code: PASS（仅文档适用维度）；命名、职责、来源、示例与真实证据边界明确，无产品行为变更、Secret 或无关文件。
- 本轮为纯文档改动，软件测试、Python 质量门禁、AI Evaluation、真实业务和部署验收不适用且未运行；不复用旧分数冒称本次新结果。
- workflow-code-review 在当前主 Agent 上下文执行，按短 Spec 对照全文、事实源和关键代码；无需独立 Agent。

### 动态文档与历史去向

| 清单项 | 处置 |
| --- | --- |
| AGENTS.md | 复核无变化；未修改协作授权、安全或阶段规则 |
| docs/agents/documentation.md | 已更新；增加教学长文的解释职责、事实源与同步维护要求 |
| docs/agents/issue-tracker.md | 复核无变化；沿用工作记录和实时状态边界 |
| docs/agents/git-pr-workflow.md | 复核无变化；只准备本地候选，未取得 Push / PR 授权 |
| docs/roadmap.md | 复核无变化；这是现有项目的教学说明，不改变产品目标、优先级、依赖、验收方式或完成事实 |
| docs/runbook.md | 复核无变化；本文解释现行命令，不新增操作或运行路线 |
| .harness/project.json | 复核无变化；工程阶段、状态路径和风险声明保持 |
| .harness/dynamic-files.json | 复核无变化；既有治理文件的 Owner、权威来源和触发条件保持；新教学文档在文档归属表维护，未改变 Harness 清单 Contract |

原文档、历史验收和已归档导航均保留。README 仍是阅读总入口，本文提供独立连贯讲解，不新建竞争行为 Contract。

### Harness 边界

- 开始前旧只读检查：57 条记录，findings 为空；当前任务新增后按其生命周期检查。
- 候选检查：58 条记录，0 ERROR；OPEN_WORK_ITEM 对应本任务尚待发布，DIRTY_WORKTREE 的 5 个文件均属于短 Spec 的 owned files，将在本地 Commit 后消除工作区修改。
- 实际调用当前提供路径的 Plugin 容器适配 state 与 diff，可读取当前任务；记录为 legacy_read_only，累计 / 切片基线缺失，因此新版 Diff 不完整，不能声称新版 closeout 通过。
- 传统工作记录与 Git Diff 继续按现行仓库规则使用；本轮不迁移旧记录、不回填工具基线，不将普通文档任务扩大成 Harness 改造。
- 未观察到符合门槛的新增 Harness 缺口；工具对缺少显式基线的限制有明确规则，不能按偏好重复提出改造。

### 本地候选与交付状态

文档内容完成后创建本地候选；远端发布不在当前授权内，工作项在待发布阶段保持可发现。冻结标签仍指向原提交。
