# 验证与当前上下文 Review

## 候选与范围

- BASE_SHA: 64d2eae2b4004dc402d006a1a524ded71a9d7304；branch: docs/remove-roadmap-and-audit。
- 只涉及 Roadmap 退役、必需规则 / 清单 / 链接变更及文档审核报告；无产品代码、测试、运行配置和凭证改动。
- 用户授权删除及审核；未获 Push / PR 授权，不操作远端写入。
- docs/roadmap.md 原正文归本目录 history/roadmap.md；仅对归档相对链接重定位。旧工作记录只修链接，不把历史状态改成当前事实。

## 验证证据

- 初始本机状态检查：59 份记录，无 ERROR / REVIEW。
- 文档组合检查、最终 diff --check、动态清单与历史链接机械校验：最终结果在本记录末尾填写。
- 容器定向文档 / Harness 回归：23 passed，0 failed / skipped；Run ID 20261025T144241Z-64d2eae-test-python-fb422fffcb54。
- 容器检索观测回归：3 passed，0 failed / skipped；Run ID 20261025T144307Z-64d2eae-test-python-84f0ae40e7cf。
- 两次测试对应 base 加当时未提交的文档改动，报告 provenance stable、git_dirty=true；文档报告后续变化不触及被测代码 / 测试 / 配置行为。原始测试证据为 ignored 本机产物，不随本次 Commit 分发。
- 没有 Python / 前端代码变更，Python 全量质量、前端构建、完整软件回归不适用本次删除验证；未运行真实数据库、模型、浏览器、文件 renderer、云 Trace 或托管 CI。
- Plugin state 通过显式只读包路径运行，读取当前工作项为 legacy_read_only；未迁移旧记录。没有 task / slice baseline，Plugin 的 cumulative / slice 完整性及 overall closeout 不通过，不声称新版整体收尾通过。使用 Git base Diff 和逐文件检查保留本次实际证据；发布仍待授权。

## 动态文档清单处置

| ID | 处置 | 位置 / 理由 |
| --- | --- | --- |
| agent-entrypoint | updated | AGENTS.md 移除 Roadmap 读取 / 更新要求 |
| documentation-rules | updated | docs/agents/documentation.md 移除归属及门禁，明确事实归属 |
| issue-tracker | reviewed-no-change | docs/agents/issue-tracker.md 未依赖 Roadmap；实时状态边界无变更 |
| git-pr-workflow | updated | docs/agents/git-pr-workflow.md 及 PR 模板取消 Roadmap 门禁 |
| runbook | reviewed-no-change | 本次删除无该文档链接；另有审核发现 DOC007，保持未修状态 |
| harness-adapter | reviewed-no-change | .harness/project.json 仍引用相同动态清单位置，无阶段图变化 |
| dynamic-file-manifest | updated | .harness/dynamic-files.json 只移除 roadmap 项，其他 Owner / authority / history 不变 |

## Review

Review: PASS（本次删除与审核交付，不代表全仓文档正确）
Scope: BASE_SHA 64d2eae 之上的当前文档 / 清单 Diff。
Change Description: 用户明确删除 Roadmap；将历史保存并修复引用，按 38 份文档建立证据清单和 10 项发现，无产品规则改写。
Findings: 本次 Diff 无阻断项；审核报告 DOC001–DOC010 为原项目问题，尚未实施修复。
Review Dimensions: 删除要求覆盖导航 / 规则 / PR 模板 / manifest；旧链接指向归档；报告区分实现事实与已确认 Contract，未把测试通过当作 Contract 已获调整；风险与未运行项明确；不修改 Domain / Authorization / SQL Safety，不引入新依赖或真实 Secret。
Tests: 复用上述 23 + 3 项通过证据，最终文档检查覆盖新增报告与记录。
Next: 最终文档与 Diff 检查通过后本地提交；远端发布等待用户授权。

## Harness 反馈

观察到事实源同步缺口：同一旧描述跨正式 Spec / Design 重复保留，例如并行检索、一次综合指标检索和网页同步身份。现有文档规则已要求语义 Review，且结构检查明确不负责语义；本次仅记录具体发现，不另加通用平台或修改已有检查 Contract。建议后续处理 DOC001–DOC010 时先厘清单一规则入口，再对可确定参数（例如 COLUMN 默认上限）考虑定向 Contract 一致性检查；尚未获得该后续实施授权。

## 最终检查

- `uv run --python 3.11 --locked python -m scripts.check_documentation`：PASS，覆盖新增审计报告 / 本记录及全仓 Markdown 链接。
- `git diff --check`：PASS。
- 机械核对：22 份旧 .scratch 文档只变更 Roadmap 链接目标；7 项剩余动态清单 path / history_path 均存在；审核表覆盖 38 / 38 份原有现行文档。
- 案例数复核：single_turn=29、multi_turn=7、business_analysis=10、query_understanding=7，与当前正式评测 Spec 一致。
- Plugin `diff --json` 与 `closeout check` 已实际运行；缺 task / slice baseline，缺扩展状态的文档评估与候选绑定证据，overall_ready=false；无发布授权。首次 closeout 误传 --json 被 CLI 拒绝，移除该参数后正确运行；不把参数解析失败计为审核通过。
- 本地 Review PASS；DOC001–DOC010 未修是用户所要求审核的输出，不是本次删除目标的遗留实现项。

## 2026-10-25 文档修复切片（base e69eb2b）

用户已追加核实 / 修文档授权，范围见 spec.md 追加段与 documentation-repair.md。前次审核的“尚未修复”是历史阶段结论，本轮具体状态为 DOC003–DOC010 已修，DOC001/002 已如实标注原要求 / 当前偏差，Contract 冲突待确认。本轮不修改原审核结果或旧测试成绩。

验证：

- `./dev check docs`：PASS；Run ID `20261025T145516Z-e69eb2b-check-docs-6756339ef1a0`，源码起止 provenance stable，dirty文档候选。
- `./dev test python tests/online_query/test_contracts.py tests/online_query/test_retrieval_observability_t3a.py`：7 passed / 0 failed / 0 skipped；Run ID `20261025T145528Z-e69eb2b-test-python-9e447d59c6d8`，provenance stable，dirty文档候选。该结果确认现有默认50和逐指标Span次数，不能证明旧Contract已获调整。
- 文档 / 核实记录后续只增加来源说明及本轮验证，不触及源码 / 测试 / 配置，软件证据仍适用；最终组合文档检查覆盖这些收尾变化。
- 不运行真实LLM / 数据库 / 浏览器 / 全量回归：文档修复没有改变其行为，不冒称新运行验收通过。
- Plugin diff / closeout 已显式只读执行，仍缺历史 task / slice baseline 与扩展状态候选证据，overall_ready=false；未迁移原记录，未获发布授权，不宣称Plugin整体收尾通过。

动态文档清单：runbook updated（日志命令）；其余6项 reviewed-no-change（不改变Agent规则、工作项状态Contract、Git流程、adapter及清单自身）；Roadmap继续退役，不新建替代路线图。正式行为来源、Design机制与原归档的职责保持；本轮只将恢复Contract的现行入口改链正式Spec，不删除历史。

Review: PASS（当前上下文 workflow-code-review）
Scope: e69eb2b 之上的文档修复Diff和本工作项记录。
Change Description: 用正式历史 / 执行 / 就绪 / 恢复 / 评测规则修复旧文档，检索冲突单列，保留原要求和可核实当前事实。
Findings: 当前交付无阻断项；DOC001/002不作为已解决Contract，后续调整规则或实现须取得决定。旧测试函数名未改，无源码变更。
Review Dimensions: 无Domain / Authorization / State不变量变更；旧同步API兼容与当前网页入口分清；未让测试或已合并Commit反向覆盖原要求；文档链接、Secret、历史证据和源码范围已检查。
Harness Feedback: 同前次已记录的事实源同步缺口，无额外通用流程改动；本轮未扩大到插件或检查器建设。
Next: 最终文档 / Diff检查通过后本地Commit；远端交付仍待授权。

## COLUMN 50 确认与文档同步（base 143de69）

用户接受保留50并明确要求同步文档；授权依据、范围及验收见spec.md本轮追加段。检索Spec的配置、合计预算、Join Key说明和验收统一Top-50；Design与审计当前状态同步。DOC001完成，DOC002调度差异仍待决定，旧核实表和初始审核保留历史语义。

Review: PASS（当前上下文 workflow-code-review）
Scope: 143de69以上的两份检索文档、审计当前状态及本工作项记录。
Findings: 无本轮阻断项；确认仅覆盖预算50，不扩展到并行要求、代码或远端发布。50不是每表数量、不是保证取满，也不宣称经对比最优。
Verification: 最终组合文档检查和git diff --check执行结果见本轮命令记录；文本复核配置 / 资源 / Join Key / 验收无Top-20现行规则残留。源码 / 测试 / 配置无变化，复用上一切片7项定向通过证据（不改标新候选测试），不重跑真实LLM、数据库或全量回归。
Dynamic files: 现有7项均reviewed-no-change；本轮不涉及Runbook命令、Agent规则、工作项格式、Git交付规则或Harness清单。无Roadmap恢复。
Harness: 原记录legacy且缺历史baseline，沿用前述Plugin overall未通过的限制，不宣称新整体收尾通过；本轮只做授权的文档同步。
Harness Feedback: 未观察到新的、符合门槛且未被前述记录覆盖的缺口。

## 顺序检索确认与文档同步（base a53792a）

用户已确认保留当前顺序检索并授权修文档，依据见spec.md最新追加段。检索Spec / Design统一TABLE→可选METRIC→COLUMN，多指标逐个检索、实体跳过METRIC；移除旧并行要求及未裁决表。审核报告和核实记录顶部现列DOC001–DOC010文档修复完成，初次发现保留历史身份。

Review: PASS（当前上下文workflow-code-review）
Scope: a53792a以上的检索文档、审计当前状态及本工作项记录。
Verification: 运行代码_resource阶段仍先TABLE后逐指标METRIC，COLUMN在资源校验后进入；本轮仅改文档。最终运行组合文档检查、git diff --check和现行调度文字检查；不新写测试，复用此前7项定向证据的适用行为，不改标为本轮新测试成绩。未运行真实LLM / 数据库 / 全量回归 / 托管CI。
Dynamic files: 7项均reviewed-no-change；未触及Runbook、Agent / Git规则、状态Contract或adapter清单。Roadmap不恢复。
Findings: 无本轮阻断项；用户确认范围覆盖调度描述，不新增并发实现、性能结论或产品支持承诺。历史调度冲突已由本轮确认解决。
Harness: 沿用此前缺历史baseline与扩展证据的Plugin整体限制，不宣称整体交付收尾通过；无Push/PR授权。未观察到新的、符合门槛且未被前述记录覆盖的Harness缺口。
