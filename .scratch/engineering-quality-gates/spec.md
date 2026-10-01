# 工程质量门禁与评测基线对齐

Status: confirmed

## Problem Statement

当前仓库已经定义正式 AI Evaluation、Agent 入口和主要架构边界，但评测入口和状态说明存在漂移：

- 正式生产准备基线要求在最终 clean commit 上分别运行单轮、多轮和 Business Analysis 三个套件；此前完整通过的基线对应 commit `31a04549924f622777f106d4fe5a758bd2ca2beb`，后续 Evaluation 模块目录调整和文档变更使当前 HEAD 变为 `ed64608`，当前 HEAD 尚无对应的完整基线报告。
- `.github/workflows/real-e2e.yml` 调用默认单轮评测。默认 Runner 加载 `evaluation/suites/single_turn/cases.json` 中的全部 29 个案例，但 workflow 仍要求报告总数为 21；它也没有运行独立的 Multi-Turn 和 Business Analysis 套件。
- CI 尚无明确的 Markdown 内部链接检查或稳定架构依赖边界检查。
- 当前基线状态文档不一致：README、`docs/product-scope.md` 和 `docs/roadmap.md` 说明当前 HEAD 基线待核验，`docs/architecture.md` 仍描述 Ticket 04 已建立“本轮当前 HEAD 基线”。

这些差异会让维护者和后续 Agent 难以判断真实覆盖范围、当前验证证据和文档状态。

## Solution

1. 在最终 clean candidate commit 上重新核对 Golden Set 与当前 Contract，并分别运行正式的三个 AI Evaluation 套件。三个套件各自必须为 `0 FAIL`、`0 INVALID_CASE`；报告须对应该 commit、`git_dirty=false`，并记录已有 Contract 要求的案例集和资源指纹。Query Understanding 继续作为辅助评测，不替代正式套件。
2. 让手动 Real E2E workflow 的运行范围和验收范围一致。该 workflow 保持单轮在线评测范围，运行并验收其当前完整 Golden Set；验收数量应与本次加载的案例集一致，不能保留与 29 个案例冲突的 21 个硬编码期望值。正式三套件基线仍由单独的全套评测建立。
3. 在普通 CI 增加两类确定性检查：
   - 检查仓库受版本控制的 Markdown 文档中的本地路径及锚点链接；不因网络或第三方站点状态检查外部链接。
   - 对架构文档和 `AGENTS.md` 已明确的稳定模块边界建立自动检查。只把已有明确边界编码为门禁，不引入新的分层体系或未经确认的架构 Contract；失败信息应指出违反边界的依赖。
4. 统一 README、产品范围、路线图和架构文档中的当前评测状态，使状态结论可追溯到明确 commit 与对应本地报告；历史 commit 的报告不得表述为当前 HEAD 的结果。

原始 JSON / Markdown Evaluation 报告继续按当前仓库决定保存在被忽略的本地 `reports/evaluation/`，不将报告文件提交到 Git。Harness 说明继续作为简短入口说明；只有入口、组成、工作流或 Skill 依赖变化时才更新它。

## User Stories

- 作为维护者，我能从正式评测报告确认当前 clean commit 上三个必需套件的结果，不会把历史报告误认为当前能力。
- 作为 PR Review 者，我能确认 Real E2E 实际跑了哪些案例，且验收门槛与运行的案例集一致。
- 作为后续进入仓库的 Agent 和维护者，我能通过 CI 发现断链及已声明架构边界的代码违规，并从项目文档看到一致的评测状态。

## Implementation Decisions

- 正式 AI Evaluation 的范围、零失败门槛、报告身份和资源指纹遵循 `docs/specs/evaluation.md`；不新增通用准确率门槛。
- Real E2E workflow 保持当前单轮套件范围；不把 Multi-Turn 或 Business Analysis 偷渡进该 workflow，也不把单轮 workflow 结果当作完整正式基线。
- 普通 CI 不调用真实 LLM。真实评测会向外部 LLM 发送 Golden Set 问题及结构、指标上下文；运行前仍须遵循 `docs/runbook.md` 的网络、数据库和数据发送许可要求。本 Spec 确认需求范围，不授权现在执行评测。
- 架构自动检查只验证现有文档明确的边界。若设计阶段发现某条边界无法从现有 Architecture / `AGENTS.md` 客观判定，应停止扩充门禁并返回 Spec 澄清，不自行创造分层规则。
- 不为支持其他 Coding Agent 添加 `CLAUDE.md`、`GEMINI.md` 或插件安装器；当前已确认目标是保持仓库 `AGENTS.md` 入口和简短 Harness 说明。
- 本 Spec 的正式事实源是 Evaluation Spec、Architecture、Product Scope 和 `AGENTS.md`；运行入口以 Runbook 和 workflow 为准；本地 `.scratch` Ticket 记录执行过程，不替代正式报告或产品事实源。

## Testing Decisions

- 对 Markdown 链接检查和架构边界检查提供确定性验证，并在普通 CI 中运行；错误需包含可定位的文件和链接或依赖信息。
- 验证 Real E2E 的确定性验收逻辑能依据当前加载的单轮案例集核对总数，并拒绝 FAIL 或 INVALID_CASE；不在普通 CI 中调用真实 LLM。
- 对最终 candidate 的真实 Evaluation，分别核对三个正式套件的退出状态、报告总数、`FAIL` / `INVALID_CASE`、Git commit、dirty 状态和资源指纹。任何套件不通过时不得标记基线完成。
- 更新状态文档后，交叉核对 README、产品范围、路线图、架构文档与报告身份；文档检查不能替代 AI Evaluation 运行证据。
- 真实 Evaluation 的执行需要单独满足仓库的显式授权要求；当前 Spec 草案阶段不运行。

## Out of Scope

- 改变 ChatBI 产品行为、业务语义、Metric Contract、Authorization、SQL Guard、数据范围或运行时架构。
- 普通 PR CI 自动发送真实 LLM 请求，或自动执行完整多套件 Evaluation。
- 提交原始评测报告、扩充 Harness 说明为第二套工程流程手册，或增加多种 AI 工具的入口适配。
- 扩展生产部署、容量、可用性、监控或回滚方案。

## Further Notes

- 变更画像：长期维护的工程门禁与评测证据工作；范围跨 CI、评测验收和状态文档，风险主要在外部 LLM 验证授权与架构边界误编码；不改变运行时产品行为。预期证据为确定性检查、CI 和最终候选上的真实 AI Evaluation。
- 已确认决定：完整基线包含三个正式套件；Real E2E workflow 继续覆盖当前完整单轮套件并与其数量一致；Harness 文档维持说明用途。
- 保留的既有证据：Ticket 04 在 commit `31a0454` 建立过通过的三套件基线；它是历史 commit 的结果，不代表当前 HEAD `ed64608`。
- 当前无额外待用户决定项。具体 CI 检查脚本组织和现有稳定架构边界的可执行表达留给 Design Review / Ticket 阶段确定，不得扩大本 Spec 的行为范围。
