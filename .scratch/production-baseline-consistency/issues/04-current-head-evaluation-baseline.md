# 建立当前 HEAD Evaluation 基线

Status: blocked
Owner: ChatBI 仓库维护者
Backup Owner: None
Blocked by: 06-multi-turn-dimension-replacement

## Change Profile

- Lifetime: 当前 MVP 的可追溯正确性证据；之后随行为变化重新建立。
- Size: M，覆盖 Golden Set Contract 核对和三套真实 AI Evaluation。
- Risk: 高；评估使用在线 RAG、PostgreSQL 和真实 LLM，可能产生外部请求并写本地忽略报告。
- Evidence: 当前 HEAD 报告、测试集 / 资源指纹、零失败和零无效案例统计。
- Delivery: 仅在 Ticket 01–03 完成、候选代码和文档提交稳定后执行；执行前遵循仓库 PR 前验收授权门禁。

## Canonical Source

- 评测 Contract：`docs/specs/evaluation.md`、`docs/designs/evaluation.md`。
- Golden Sets：`src/evaluation/eval_cases.json`、`src/evaluation/multi_turn_eval_cases.json`、`src/evaluation/business_analysis_cases.json`。
- Metrics Contract：`src/semantic/metrics.json` 与对应已确认产品 / 模块 Contract。
- Runner / Judge / Report：当前 `src/evaluation/` 实现。
- 历史报告：`reports/evaluation/` 中已有日期化报告；均不代替本 Ticket 生成的当前 HEAD 报告。

## What to build

在最终、已提交且工作区干净的 HEAD 上，先核对三套 Golden Set 的指标、预期结果类型、过滤条件和行为断言符合当前产品 Contract 与 `metrics.json`，再分别运行单轮、多轮和经营分析 Evaluation。

将报告作为本地 Evaluation artifact 保存，不把被 `.gitignore` 忽略的报告文件误认为已进入版本控制。报告必须可识别评测 commit、`git_dirty`、案例集和相关资源版本。若案例与 Contract 有实质冲突，或任何必需套件未达到零失败门槛，停止签发通过的基线并记录阻塞；不得为了通过而自行改业务口径或案例答案。

## Acceptance criteria

- 执行前确认 Ticket 01–03 所需代码 / 文档已完成，当前 HEAD 已提交且 `git_dirty=false`。
- Golden Set 与当前产品 Contract / `metrics.json` 的核对完成；若发现未解决的实质冲突，不签发基线，转独立的 Spec / Ticket 决策。
- 单轮 29 cases、Multi-Turn 7 conversations、Business Analysis 10 cases 三套分别运行并各自生成 JSON / Markdown 报告。
- 三套必需 Evaluation 各自满足 `0 FAIL`、`0 INVALID_CASE`；Query Understanding 6 cases 记录为辅助证据，不替代必需套件。
- 所有报告中的 `git_commit` 指向执行时的 HEAD、`git_dirty=false`，案例集和相关 RAG / 数据资源指纹能识别本次评估输入。
- 历史报告保持不变，报告内容和日志不包含 Secret；没有当前 HEAD 证据时不宣称 Baseline 通过。
- 若运行期间代码、Contract、案例、指标或资源发生变化，旧结果不作为新 HEAD 基线，必须在稳定 HEAD 重新评估。

## Owned files

- 本 Ticket 的 `Result` / `Comments` 中记录报告 ID、commit、dirty 状态、各套件统计和链接 / 路径。
- `reports/evaluation/` 由现有 Runner 生成的本地忽略 JSON / Markdown artifacts；不改报告生成代码，除非发现 Spec 所需的追溯 metadata 缺失，此时先暂停并建立实现 Ticket。
- 不修改 Golden Set 或业务指标文件；经单独确认的修正不属于本 Ticket。

## Validation evidence

- 核对三个 Runner 的退出状态和 JSON / Markdown 报告汇总。
- 独立确认三套 case/conversation 总数和 `FAIL` / `INVALID_CASE` 为零。
- 核对每份报告的 commit、`git_dirty`、case / context / resource fingerprint 与本次目标一致。
- 将 Query Understanding 辅助报告与三套必需报告明确区分。

## Migration / Rollback

- 不覆盖或删除历史报告；当前运行报告采用新的 run ID。
- 若任一套件不通过，保留报告作为失败证据，停止发布基线；先由单独确认的实现 / Contract 工作解决，再重新运行全部必需套件。

## Done When

当前稳定 HEAD 的三套必需 Evaluation 报告均可追溯、工作区干净，且各自为 `0 FAIL`、`0 INVALID_CASE`；Golden Set 与当前产品 / 指标 Contract 的核对没有未解决的实质冲突。

## Result

四套评测曾在干净 HEAD `050416b1b66319f2587cc85f9d3f90aa4bd11da0` 上运行。单轮与经营分析通过，多轮有 1 个失败，因此该 HEAD 不能作为通过的 Baseline。历史失败暴露的维度 Contract 冲突已由用户确认按明确措辞区分替换与追加，并由 Ticket 06 实施；旧报告仍仅代表旧 HEAD。当前 Baseline 仍待 Ticket 06 的新 candidate 通过重新评测。

- 单轮 29 cases：指标均来自当前 7 项 `metrics.json`；正向查询、澄清、拒答类型与当前查询 Contract 一致。
- Multi-Turn 7 conversations / 15 turns：指标替换、时间/维度/过滤修订及失败隔离与当前 Multi-Turn Contract 一致。
- Business Analysis 10 cases：成功案例仅覆盖毛利 / 人民币净销售额和产品归因；毛利率、区域归因、歧义及无效比较分别对应当前拒答 / 澄清边界。
- 单轮：29/29 PASS，0 FAIL，0 INVALID_CASE。报告：`reports/evaluation/20260929T144601Z-050416b.json`。
- Multi-Turn：6/7 conversations PASS，1 FAIL，0 INVALID_CASE；14/15 turns PASS。失败覆盖项为 dimension replacement。报告：`reports/evaluation/20260929T145624Z-050416b-multi-turn.json`。
- Business Analysis：10/10 PASS，0 FAIL，0 INVALID_CASE。报告：`reports/evaluation/20260929T150118Z-050416b-business-analysis.json`。
- Query Understanding 辅助评测：6/6 PASS。报告：`reports/evaluation/20260929T150235Z-050416b-query-understanding.json`。
- 四份报告均记录相同完整 `git_commit`、`git_dirty=false`；三份必需 RAG 评测均记录 `rag_asset_version=provenance-20260929`，Sales Mart seed 和 data hash 一致。
- 历史阻塞：`MT-DIMENSION-REPLACE-T2` 要求把分组从“销售区域”替换为“产品线”，旧实现生成 SQL 时同时保留两者。此行为现已按用户确认的 Contract 在 Ticket 06 修正；该报告不能用来判断新实现是否通过。
- Golden Set 和历史报告未改动；评测期间工作区干净。当前工作区仅有本 Ticket 的结果记录待提交。

## Comments

- 旧报告只证明其记录的旧 commit 上曾运行过，不作为当前 HEAD 的成功证据。
- 本 Ticket 使用真实 LLM / RAG / PostgreSQL；执行须遵循仓库规定的候选验收授权，不在 Bootstrap 或确定性测试时隐式运行。
- Ticket 05 已补齐单轮 / 多轮报告的 RAG 资产身份，并通过针对性测试；本次四套报告身份完整。Ticket 06 已依据用户确认修正实现与文档，Golden Set 保持不变；待形成新 clean candidate 并获授权后，重新运行三套必需 Evaluation 和辅助评测。
- 初始只读案例核对未发现该冲突；真实 Multi-Turn 执行结果触发了对两份已确认规格及该案例来源的复查。
