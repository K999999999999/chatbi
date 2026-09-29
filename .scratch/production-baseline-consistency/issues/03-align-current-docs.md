# 文档对齐当前 MVP Contract 与运行流程

Status: done
Owner: ChatBI 仓库维护者
Backup Owner: None
Blocked by: 01-rag-resource-provenance-gate, 02-clean-bootstrap-checkpoints

## Change Profile

- Lifetime: 长期维护的产品状态、架构和操作说明。
- Size: M，跨 README、Roadmap、Product Scope、Architecture、Runbook 和相关 Contract 文档。
- Risk: 中；错误文档会导致错误操作或把未支持 / 历史能力当作当前事实。
- Evidence: 文档事实逐项映射到当前代码、Contract、健康检查和 Ticket 01 / 02 的最终行为。
- Delivery: 文档切片；不改变运行时代码和业务 Contract。

## Canonical Source

- 产品定位和范围：用户确认的 MVP 向生产演进定位、`docs/product-scope.md`。
- 模块边界与不变量：`docs/architecture.md`、`docs/specs/`。
- 实际支持能力：当前 HEAD 代码、测试和已完成的 Ticket 01 / 02 行为。
- 最新 Evaluation 身份：报告中的 commit、dirty 状态和套件信息；本 Ticket 不伪造尚未运行的结果。
- 历史验收：日期化的 `docs/acceptance/` 和旧 Evaluation reports 作为历史证据保留。

## What to build

更新当前入口和操作文档，使其准确表达目前已实现的 MVP 能力、尚未完成的生产准备事项、指标与评测集当前数量、RAG 生产资源就绪要求，以及 clean-clone / Control DB 初始化顺序。

删除或改写仍将已实现能力写成“不支持”的当前状态陈述；修正文档中 5 个指标、21 个评测案例等已过期的当前数量。保留日期化 Acceptance 和历史报告原内容，通过当前文档说明其历史身份；不把旧验收结果改写成当前 HEAD 结果。

## Acceptance criteria

- README、`docs/product-scope.md`、`docs/roadmap.md`、`docs/architecture.md`、`docs/runbook.md` 及相关 Evaluation / RAG 说明在产品定位、支持能力、指标数量、套件数量、初始化和资产失配行为上没有互相冲突的当前陈述。
- 文档说明 Schema 的维护顺序为 DDL → 更新实际 PostgreSQL → 导出 Structure JSON；明确 Metrics、Structure JSON、数据库实际 Schema 和 Qdrant 派生产物的角色。
- Runbook 从 clean clone 可按文档步骤完成初始化，明确 checkpoint migration / 健康检查以及 Qdrant 索引构建和失配恢复步骤。
- 已实现的 MVP 能力不再被当前 Product Scope / Roadmap 写成未实现；未完成的生产准备工作仍明确标为待完成。
- 日期化历史 Acceptance、旧 Evaluation reports 和 `.scratch` 历史 Ticket 保留为原始证据；当前文档不暗示它们代表当前 HEAD。
- 不填写尚未执行的 Evaluation 成绩，不修改业务指标、SQL 口径或 Golden Set 期望结果。

## Owned files

- `README.md`
- `docs/roadmap.md`
- `docs/product-scope.md`
- `docs/architecture.md`
- `docs/runbook.md`
- 仅在必要时调整 `docs/specs/evaluation.md`、`docs/specs/rag-offline-build.md` 中已经与实现冲突的陈述。

## Validation evidence

- 逐项核对文档中的功能状态、指标数、Evaluation 数量、命令和错误行为与当前代码 / 测试 / Ticket 01、02 验收证据一致。
- 检查文档交叉引用和初始化步骤顺序；不运行 AI Evaluation 代替文档审查。
- 确认日期化 Acceptance 和历史 Evaluation 报告未被改写或删除。

## Done When

维护者只读当前文档即可区分当前 MVP Contract、生产准备缺口和历史验收证据；重要数量、支持状态和 clean-clone 操作没有冲突陈述。

## Result

已完成。README、Product Scope、Roadmap、Architecture、Runbook、Evaluation Spec 和 Online Query Spec 已统一更新为“MVP 向生产演进”定位，明确当前已实现的 API 认证 / RBAC、多轮查询、经营分析、RAG 资产指纹与 checkpoint bootstrap 行为。过期的 21 案例、5 指标、POC / Demo 阶段和历史 `20/21` 当前状态已更正；日期化 Acceptance / 历史报告未修改。

核对证据：

- 从当前案例和事实源文件读取并验证数量：29 单轮、7 多轮 Conversation / 15 轮、10 Business Analysis、6 Query Understanding、7 Metrics、7 表、69 列、25 条关系事实。
- 修改文档中的本地 Markdown 链接均存在。
- `git diff --check` 通过；`docs/acceptance/` 无变更。
- 没有编写尚未运行的 AI Evaluation 结果；当前 HEAD 报告由 Ticket 04 生成。

## Comments

- 必须等 Ticket 01 和 02 的实际行为落定后更新对应运行与初始化说明。
- 当前 HEAD 的真实 Evaluation 报告由 Ticket 04 建立；本 Ticket 只规定如何识别当前报告，不预填评测结果。
