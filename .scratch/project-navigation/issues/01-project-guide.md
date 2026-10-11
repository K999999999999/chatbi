# Ticket 01：建立全项目功能、模块与事实源导航

Status: done
Owner: 当前主 Agent
Blocked by: None (can start immediately)
Change Profile: Lifetime M；Size M；Risk Low；Evidence Markdown / 代码入口交叉核对、链接检查和新人走查；Delivery 本地文档提交，无运行时发布。
Canonical Source: 产品范围以 `docs/product-scope.md` 与已确认 Spec 为准；架构以 `docs/architecture.md` 为准；实现入口以当前源码为准；验证和运行命令分别以 Tests / Evaluation / Acceptance / `docs/runbook.md` 为准。

## What to build

盘点并呈现当前主要产品能力和一级工程子系统；说明新人阅读顺序、核心查询链路、模块 / 目录 / 关键入口，以及相应事实文档、验证和运行入口。以项目导航页承载详图，并从 README 提供清晰入口。将仅计划或已退役能力明确标注。

导航索引权威来源，不复制完整 Contract；不改变架构、业务行为或事实源职责。

## Acceptance criteria

1. 新人从 README 可沿确定顺序理解 ChatBI 定位、支持边界、成熟度、架构和主查询链路。
2. 当前产品能力及主要工程子系统逐项映射到模块 / 目录 / 关键入口，并链接适用 Spec / Design、测试 / Evaluation / Acceptance、Runbook 命令；无独立 Contract 的工具不补建空文档。
3. 代表性在线查询可从 Web/API 追至业务语义解析、授权、检索、SQL Guard、数据库和结果返回；历史、执行流、导出、经营分析、Semantic / Structure、RAG、Bootstrap、Observability、Evaluation、数据 / 脚本 / 测试等均有专题定位。
4. 新人走查清单可由非导航文档作者独立执行并留存结果，无需口头补充；当前能力、计划能力和历史入口可区分。
5. 新增本地 Markdown 链接有效，代码入口已在当前树中核实。

## Owned files

- `README.md`（仅项目导航入口和阅读顺序）
- 新增 `docs/project-guide.md`
- 仅必要的导航索引修订

不改写 `docs/architecture.md` 的架构 Contract 或功能 Spec。

## Verification evidence

- 源码 / 文档目录覆盖核对
- 代表性查询链路入口交叉核对
- `python3 scripts/check_markdown_links.py`
- 新人走查记录

## Migration / Rollback

不适用；按 Git Diff 可逆恢复。不移动业务源码或运行资产。

## Result

已新增 `docs/project-guide.md`，建立新人阅读顺序、产品和架构说明、主要能力 / 工程模块交叉导航、代表性查询链路、专题路线、仓库结构、事实源 / 验证边界及新人自查清单；README 提供导航入口、轻量项目概览、容器快速开始、Hook 首次配置、主链路和文档 / 测试索引，详细模块及功能地图保留在项目导航和专题文档。Roadmap 增加新读者现状速览，不改阶段事实和优先级。源码 / 文档目录盘点完成，`python3 scripts/check_markdown_links.py` 和 `git diff --check` 均通过。隔离启动及非作者独立走查由 Ticket 03 验证。

## Comments

- 来源：用户确认的 `.scratch/project-navigation/spec.md` 与 `ticket-drafts.md`。
- Ticket Readiness：READY（当前上下文只读检查）。
