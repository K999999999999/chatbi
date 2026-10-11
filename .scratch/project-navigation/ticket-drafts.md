# ChatBI 新人项目导航：Ticket 草案

状态：用户已确认拆分及依赖；正式 Ticket 已写入 `.scratch/project-navigation/issues/`。
来源：用户确认的 `.scratch/project-navigation/spec.md`；Design Review `PASS WITH MINOR FIXES`。
Owner：当前主 Agent。

## 01. 建立全项目功能、模块与事实源导航

- Change Profile：Lifetime M；Size M；Risk Low；Evidence Markdown / 代码入口交叉核对、链接检查和新人走查；Delivery 本地文档提交，无运行时发布。
- Owner：当前主 Agent；Backup Owner：不适用（单人文档工作）。
- Blocked by：None (can start immediately)
- Canonical Source：产品范围以 `docs/product-scope.md` 与已确认 Spec 为准；架构以 `docs/architecture.md` 为准；实现入口以当前源码为准；验证和运行命令分别以 Tests / Evaluation / Acceptance / `docs/runbook.md` 为准。新导航只建立索引和关系，不复制上述 Contract。
- What to build：盘点并呈现当前所有主要产品能力和一级工程子系统；说明新人阅读顺序、核心查询链路、模块 / 目录 / 关键入口，以及相应事实文档、验证和运行入口。以新项目导航页承载详图，并从 README 提供清晰入口；覆盖表应以当前源码、产品范围和适用事实文档交叉核对。将已退役或仅计划的能力明确标注，不将其混入当前能力。
- Owned files：`README.md`（仅项目导航入口和阅读顺序）；新增 `docs/project-guide.md`（暂定名，可按现有文档惯例调整）；必要时仅修改与导航直接相关的文档索引。不得编辑 `docs/architecture.md` 的架构 Contract 或功能 Spec 来迎合导航。
- Acceptance Criteria：
  1. 新人从 README 可沿确定顺序理解 ChatBI 定位、支持边界、成熟度、架构和主查询链路。
  2. 当前产品能力及主要工程子系统逐项映射到模块 / 目录 / 关键入口，并尽可能链接适用 Spec / Design、测试 / Evaluation / Acceptance、Runbook 命令；没有独立 Contract 的工具清楚标注事实源，不补建空文档。
  3. 代表性在线查询可从 Web/API 追至业务语义解析、授权、检索、SQL Guard、数据库和结果返回；历史、执行流、导出、经营分析、Semantic / Structure、RAG、Bootstrap、Observability、Evaluation、数据 / 脚本 / 测试等均有专题定位。
  4. 新人走查清单可由非文档作者独立执行并留存结果，能定位关键路径且无需口头补充；当前能力、计划能力和历史入口可区分。
  5. 所有新增本地 Markdown 链接有效，导航中的代码入口已在当前树中核实。
- Verification Evidence：源码 / 文档目录盘点记录；代表性链路入口交叉核对；`python3 scripts/check_markdown_links.py`；新人走查记录（按 Spec 标注环境限制）。
- Migration / Rollback：不适用；仅新增 / 修改导航文档，按 Git diff 可逆恢复，不移动业务源码和运行资产。
- Done When：覆盖矩阵、入口和关键代码路径经当前仓库核对；链接检查通过；新人走查清单结果已记录；无未经确认的模块职责或业务 Contract 变化。

## 02. 校准仍作为当前事实的文档状态与路径

- Change Profile：Lifetime S；Size S–M；Risk Low；Evidence 权威 Spec / Acceptance / Roadmap 与现有内容逐项核对；Delivery 本地文档提交，无运行时发布。
- Owner：当前主 Agent；Backup Owner：不适用。
- Blocked by：01（先固定当前导航所引用的内容和入口，避免重复编辑 / 形成不一致）。
- Canonical Source：已确认的 Spec / Acceptance 和可核实的当前代码 / 运行记录；Roadmap 汇总状态须链接或遵从这些事实源。日期化 Acceptance 保留历史语义。
- What to build：审计 README、Runbook、Product Scope、Roadmap、模块 Spec 及既有 workspace map 中仍被读作当前状态的陈述；按权威证据修正明确过期的状态、链接和入口，或将只对历史候选成立的陈述清楚标为历史 / 候选绑定事实。优先修正已发现的 R5 README 验收描述、Runbook 的 R7 阶段说明、R7 Spec 状态字段及过时 workspace map。不得改写日期化 Acceptance 的历史结果。
- Owned files：`README.md`（当前功能 / 验收状态段）；`docs/runbook.md`；`docs/product-scope.md`；`docs/roadmap.md`；被核实需要修订的当前 Spec 状态元数据；`.scratch/repository-structure-readability/workspace-map.md`（只在确认其仍被引用且会误导时更新或标记快照）。不触碰 `.git/` 实时记录或任何用户本机运行配置。
- Acceptance Criteria：
  1. 每项修订附有可追溯依据，不从旧实现、过时候选或纯链接检查推断当前状态。
  2. 当前页面不再把已完成能力写成待完成；候选专属限制和日期历史仍准确标示其身份。
  3. 不更改 Acceptance 的历史结果，不重排 Roadmap 优先级，不新增产品承诺；链接和交叉引用有效。
  4. README、导航页、Runbook、Roadmap 与当前主要目录 / 入口不存在已发现的相互矛盾陈述。
- Verification Evidence：逐条来源对照表；`python3 scripts/check_markdown_links.py`；变更 Diff 的事实一致性检查。
- Migration / Rollback：不适用；文档改动可按 Diff 回退。若发现来源证据冲突且无法确定当前事实，保留原文并标注未确认，不猜测改写。
- Done When：所有发现项有“修正 / 保留并标明历史 / 无足够证据且已列明”的处置，且没有改写历史验收证据。

## 03. 验证隔离新 clone 的新人启动与确定性检查路径

- Change Profile：Lifetime S；Size M；Risk Medium（会启动本地容器并下载开发依赖 / 模型，但不得接触已有数据）；Evidence 隔离新 clone 启动、健康检查、纯软件测试及新人走查；Delivery 本地文档 / 验收记录，无运行时发布。
- Owner：当前主 Agent；Backup Owner：不适用。
- Blocked by：01、02（依赖最终导航入口和已校准的 Runbook / 状态事实）。
- Canonical Source：初始化 / 配置 / 健康命令以 `docs/runbook.md` 和 `./dev` 实际行为为准；确定性软件测试以 Runbook、`pyproject.toml`、前端 package scripts 与 CI 配置为准；成功证据记录在本工作项验收结果中，不覆盖历史 Acceptance。
- What to build：在与当前 Dev / Active Stable 隔离的新 clone 或等效隔离开发环境中，按推荐路径核对配置前提、初始化顺序、服务启动、健康检查和确定性测试命令；核实文档是否会误导新人复用现有 `.env`、卷、模型或 Qdrant 资产；形成简洁的新人走查清单和本次复现记录，并从导航链接到 Runbook。真实浏览器业务验收和真实 LLM Evaluation 只列进阶路径，不作为默认首次上手门槛。
- Owned files：必要时小范围修改 `docs/runbook.md` 或 `docs/project-guide.md` 中已核实的新人步骤 / 检查表；验收结果写 `.scratch/project-navigation/`。禁止读取、复制、覆盖、清理或迁移当前 Stable / 用户数据、配置和运行资产。
- Acceptance Criteria：
  1. 使用新 clone / 全新隔离容器、卷、数据库、Qdrant 和配置；不连接、挂载或复用现有 Dev / Active Stable 数据、`.env`、管理员或外部云凭据。
  2. 按文档可完成配置、显式初始化、启动和 HTTP 健康检查；健康检查与真实业务验收的边界写清楚。
  3. 至少运行 Runbook 标记的确定性纯软件测试入口；如本环境满足前提，记录适用的隔离集成或前端测试结果，不把未运行项目写成通过。
  4. 非导航作者按清单可自行找到启动、健康和测试命令；阻塞或外部依赖限制如实记录。
  5. 隔离资源清理仅针对本 Ticket 创建且身份明确的资源；清理失败时保留资源并记录恢复指引，不碰未知资源。
- Verification Evidence：隔离环境身份与创建方式；实际命令及退出结果；健康响应；测试范围 / 结果；资源清理核对；新人走查记录。真实 LLM Evaluation / 完整浏览器 Acceptance 不属于默认证据。
- Migration / Rollback：没有持久产品迁移或运行时发布。仅移除本 Ticket 明确创建的隔离资源；若身份不明确，停止清理并保留证据。
- Done When：新人基础路径已在隔离环境复现或明确记录具体不可复现条件；文档能准确说明命令前提和证据边界；隔离资源处置有记录，现有 Dev / Stable 状态未受影响。

## 总体依赖

```text
01 项目导航
  → 02 当前状态校准
  → 03 隔离新人上手验证
```

以上草案经用户确认后转为正式 Ticket；实施按 `01 → 02 → 03` 连续进行。
