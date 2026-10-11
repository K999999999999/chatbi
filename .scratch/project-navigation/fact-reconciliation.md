# 当前文档事实核对

Date: 2026-10-11
Scope: Ticket 02 当前状态、入口和项目地图审计

| 文档 / 陈述 | 核对依据 | 处置 |
| --- | --- | --- |
| `README.md` 将 R5 Ticket 01–03 标为完成，但说隔离 Compose 完整验收仍待完成 | [`docs/acceptance/result-export-v1.md`](../../docs/acceptance/result-export-v1.md) 顶部记录 Ticket 01–04 和完整隔离验收通过、PR #56 合并 | 已改为完整验收已完成并链接该 Acceptance |
| `docs/runbook.md` 将动态 readiness、备份恢复、监控验收描述为 R7 后续工作 | [`docs/specs/local-operations-v1.md`](../../docs/specs/local-operations-v1.md) 与 [`docs/acceptance/local-operations-v1.md`](../../docs/acceptance/local-operations-v1.md) 记录 R7 Contract / 验收及 PR #62 合并 | 已改为指向 R7 当前功能和验收事实；区分开发 `/health`、Stable readiness 与公网生产承诺 |
| `docs/product-scope.md` 将“电脑重启未执行”与已完成的 R6 交付并列，容易被读作当前 Stable 未验收 | [`docs/acceptance/local-deployment-v1.md`](../../docs/acceptance/local-deployment-v1.md) 说明 R6 候选证据；[`docs/acceptance/local-operations-v1.md`](../../docs/acceptance/local-operations-v1.md) 记录 Active Stable R7 的 Docker Desktop 和 Windows 重启核验 | 已明确 R6 候选未做该项核验，R7 Active Stable 已通过，并分别链接对应证据 |
| R7 Spec 元数据仍写“实施中” | [R7 Acceptance](../../docs/acceptance/local-operations-v1.md) 与 PR #62 当前完成记录 | 已更新元数据并链接 Acceptance；Contract 正文保留，不把 Spec 当验收报告 |
| `.scratch/repository-structure-readability/workspace-map.md` 将旧 branch / checkout、Streamlit 和“仓库没有 README”写作当前状态 | 文件内盘点时间为 2026-09-17；当前仓库 README 和 React Web 可直接核实，详见 [`docs/project-guide.md`](../../docs/project-guide.md) | 已在文首标为历史快照并指向当前地图；保留当时记录用于追溯，没有批量改写旧快照 |
| `docs/roadmap.md` 的当前阶段和 R5–R7 状态 | R5 / R6 / R7 对应 Acceptance、PR merge 身份与 Roadmap 顶部当前说明逐项抽查一致；较早运行片段有日期且保留为历史记录 | 未改写阶段事实、优先级和历史时间线；作者第二遍走读发现历史记录不利于新人提炼现状，因此在“当前阶段”增加“新读者先看”速览并由项目导航直达 |
| 日期化 `docs/acceptance/` 历史记录 | 各文档标识其候选、时间和当时范围 | 保持原文，未将历史证据改成当前候选结果 |

本次没有修改业务源码、行为 Contract、Runtime、Stable / Dev 数据、配置、模型或报告。Markdown 本地链接检查用于确认引用目标有效，不作为以上内容事实核对的依据。
