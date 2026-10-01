# Ticket 04：建立当前候选基线并统一评测状态说明

Status: done

## Owner

ChatBI 仓库维护者负责确认真实评测授权和验收；当前实施 Agent 负责准备候选、文档核对和结果记录。

## Blocked by

Ticket 01, Ticket 02, Ticket 03.

## Change Profile

- Lifetime: 一次候选验收；评测 Contract 可在后续候选继续复用。
- Size: 中等，包含多份状态文档核对和三套真实 AI Evaluation。
- Risk: 高；评测访问 PostgreSQL、Qdrant、BGE-M3 和真实外部 LLM，并会发送测试问题与结构 / 指标上下文。
- Evidence: 最终候选 commit 身份、三套 JSON / Markdown 报告、数据和 RAG 资源指纹、文档交叉核对。
- Delivery: 报告文件保留在本地忽略目录；候选代码 / 文档变更仍按仓库 PR 流程交付。

## What to build

先统一 README、`docs/product-scope.md`、`docs/roadmap.md` 和 `docs/architecture.md` 对评测状态的表述：明确 `31a0454` 的基线是历史证据，当前基线只有在找到与最终候选 commit 身份匹配的三套报告后才能称为已确认。文档表达稳定的核验规则，不在评测后追加新的状态 Commit。

全部 Ticket 代码与文档变更形成最终干净候选 commit 后，核对 Golden Set 与当前 Contract，再分别运行正式单轮、多轮和 Business Analysis 套件。Query Understanding 是辅助评测，不替代三套正式基线。原始报告继续写入本地忽略的 `reports/evaluation/`，不得提交报告文件或 Secret。

该 Ticket 不授权现在发送真实 LLM 请求。执行真实评测前，必须另行满足仓库的明确授权要求。

## Acceptance criteria

- README、产品范围、路线图和架构文档对于“哪些报告可证明当前基线”保持一致，并明确区分历史 commit `31a0454` 与本次候选。
- 状态文档在最终评测前随候选一起提交；每份正式报告记录的 `git_commit` 等于该候选 HEAD，且 `git_dirty=false`。评测后如再改动任何受版本控制文件，必须形成新候选并重跑三套。
- Golden Set 与当前产品 Contract / `metrics.json` 已核对；发现实质冲突时停止，不自行改变业务口径或答案。
- 单轮 29 个案例、多轮 7 个 Conversation / 15 个轮次、Business Analysis 10 个案例分别出报告；每套均为 `0 FAIL`、`0 INVALID_CASE`。
- 报告包含 Contract 要求的测试集和资源身份 / 指纹；报告与执行日志不包含 Secret。
- 报告文件仍被 `.gitignore` 忽略，不进入 Git；报告失败时保留本地报告作为证据，不得标记 Ticket 完成或声称基线通过。
- 任何真实评测只在维护者确认允许向外部 LLM 发送对应数据后执行。

## Owned files

- `README.md`
- `docs/product-scope.md`
- `docs/roadmap.md`
- `docs/architecture.md`
- 本地忽略的 `reports/evaluation/` 报告（仅作为运行产物，不提交）

## Verification evidence

- 运行并检查三个正式 Evaluation Runner 的退出状态和 JSON / Markdown 汇总。
- 核对每份报告的 `git_commit`、`git_dirty`、案例数量、FAIL / INVALID_CASE 及相关数据 / RAG 指纹。
- 交叉核对四份状态文档与最终候选及报告身份。
- 确认 `git status` 在评测启动时干净；真实评测完成后代码 / 文档状态未改变。

## Migration / Rollback

无运行时 Migration。若任何正式套件失败、报告不可比较或 Golden Set 与 Contract 存在未裁决冲突，保留报告并停止验收；修复需回到经确认的实现 / Contract 工作，再形成新候选并重跑三套。不得通过删除历史报告或降低门槛回滚失败证据。

## Done When

最终候选 commit 上三套正式 Evaluation 全部满足零失败和零无效案例，报告身份可追溯，状态文档一致，且没有在评测后产生新 Commit。

## Result

最终候选 `564343216e4493f832f07efb345c03b058a04eb5` 上完成案例 / 指标 / Contract 核对，并运行正式三套 Evaluation。有效报告均记录 `git_dirty=false`、同一 commit、同一 RAG 资产版本 `provenance-20260929`、Seed `chatbi-sales-mart-dev-v3` 和数据 Hash `5ecab061588e5084ef1dd13c9d0a969d3c49f8d26bd7418b5341f427abedeafb`：

- 单轮：29/29 PASS，0 FAIL，0 INVALID_CASE；报告 `reports/evaluation/20260930T055904Z-5643432.json`。
- Multi-Turn：7/7 Conversations、15/15 turns PASS，0 FAIL，0 INVALID_CASE；有效报告 `reports/evaluation/20260930T061354Z-5643432-multi-turn.json`。
- Business Analysis：10/10 PASS，0 FAIL，0 INVALID_CASE；报告 `reports/evaluation/20260930T060646Z-5643432-business-analysis.json`。

当前多轮套件的首轮与第二轮完整运行均只有 `MT-FAILURE-ISOLATION` 第三轮因模型返回 `CLARIFICATION_REQUIRED` 而失败；单独重放同一 Conversation 的三轮全部通过，之后完整 7 组套件 7/7 通过。所有失败与成功报告均保留在本地忽略的 `reports/evaluation/`，有效的最后一份全套报告满足 Done When。评测期间未改动 tracked 文件或数据资源。

## Comments

用户在确认“按顺序执行，一直执行完”后，已被告知真实评测会发送 Golden Set 问题及结构 / 指标上下文到配置的外部 LLM；三套正式评测按此确认执行。
