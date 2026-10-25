# 根目录与正式文档一致性审核（2026-10-25）

## 文档修复后的处理状态

用户在初次审核后授权核实并修复文档，随后分别确认保留 COLUMN 默认上限 50、保留 TABLE → 可选 METRIC → COLUMN 顺序执行，并要求同步文档。DOC001 的配置 / 资源规则 / 验收已统一为 50；DOC002 的流程和调度说明已统一为顺序执行；DOC003–DOC010 也已修正，**本次审核列出的 10 项文档问题均已处理**。产品代码和测试未改；这些确认不代表已证明参数最优、并行没有收益或重新完成全量产品验收。

历史提交 `df0a853` 证实预算改动来源，初次追溯未找到当时的明确变更确认；当前预算变更依据是本轮用户确认，不从已合并或测试通过推定授权。完整逐项证据、文档位置与剩余边界见[核实与修复记录](../../.scratch/remove-roadmap-and-audit/documentation-repair.md)，实际检查结果见[验证记录](../../.scratch/remove-roadmap-and-audit/verification.md)。

以下保留初次审核基线、发现及当时“未修复”的结论，供追溯；当前处理状态以本节及逐项记录为准，初次测试结果不改标为修复后新运行成绩。

## 结论与基线

结论：文档与当前项目**并非完全一致**。已确认 10 项问题，其中 P2 7 项、P3 3 项；没有据本次证据认定 P1。最需要先裁决的是检索列候选上限和并行要求。业务定位、主要模块、单进程支持边界及核心安全链路的抽查未发现新的明显矛盾，但不能据此宣称全部实现或运行验收通过。

审查实现基线：`64d2eae2b4004dc402d006a1a524ded71a9d7304`。本次在该基线之上仅删除 Roadmap、调整必要文档与清单、修复历史链接及新增本报告；产品代码未改。基线来自已 fetch 并核对同步的 master。

覆盖：删除 Roadmap 后原有根目录 Markdown 2 份、docs/ Markdown 36 份，共 38 份逐份阅读，清单见下表；已删除的 Roadmap 另外核查和归档。本报告自身不计入 38 份。附查 PR 模板、动态文档清单、相关代码 / 配置与测试；没有把 .scratch 全部历史文档作为现行行为重新审核。

这是静态文档语义审核与定向确定性验证。未启动实际网页、未运行真实业务数据库 / RAG / LLM、全量软件回归、托管 CI 或外部 Trace 收件验收；无外部网站技术资料或当前云状态核验。本次未查阅真实 Secret 值。表中“未发现明显不一致”只表示所列核心规则的静态核对结果，不等同于完整行为证明。

## 已确认问题

### DOC001 / P2：COLUMN 上限写 20，默认实现及测试为 50

- 文档：[检索 Spec](../specs/online-retrieval.md) 的配置、资源规则、Join Key 和验收段落均写 COLUMN 总 Top-20。
- 实现：[RetrievalConfig](../../src/online_query/contracts.py) 默认 `column_top_k=50`；[资源召回](../../src/online_query/retrieval/resource_retrieval.py) 按该配置请求并裁剪普通列候选；[Contract 测试](../../tests/online_query/test_contracts.py) 明确断言 50。
- 影响：读者会错误估计候选规模、最小上下文及验收边界。这是正式 Contract 与实现 / 测试的冲突，不能仅因测试为 50 就改写已确认规则。Join Key 另有认证补充，不能用它解释普通候选默认 50。
- 处置建议：追溯扩大上限的已确认决定；若授权不可证实，按原 Contract 评估实现修复。若决定已确认，补齐正式 Contract 和对应证据。本次不裁决上限、不改产品代码。

### DOC002 / P2：TABLE 与 METRIC 并行要求没有体现在当前实现

- 文档：[检索 Spec](../specs/online-retrieval.md) 流程和[检索 Design](../designs/online-retrieval.md) 写二者并行。
- 实现：[资源阶段](../../src/online_query/retrieval/retrieval_resource_stage.py) `_retrieve_resources` 同步完成 `_table_hits` 后才构造 `metric_hits_by_query`，逐个调用 `_metric_hits`，没有并发调度；[流水线](../../src/online_query/retrieval/retrieval_pipeline.py) 的 `search` 也同步调用 store。
- 影响：并发与时延机制描述不实；本次没有测量真实延迟，不能给出性能差额。
- 处置建议：核实原并行要求是否仍有效，再决定修实现或确认调整设计；不从现有代码反向推定新决定。

### DOC003 / P2：Web Spec 与分析运行身份仍混用旧同步流程

- 文档：[Web Spec](../specs/web-dialogue-v1.md) 的模式、普通问数及经营分析段落仍要求页面保留 / 携带 `conversation_id`，发送 `mode=analysis`、问题与客户端 UUID `analysis_run_id`；[经营分析 Spec](../specs/business-analysis.md) 也把客户端生成运行 ID 写成未区分入口的规则。
- 实现：[Chat](../../frontend/src/Chat.tsx) 先 POST histories，再 POST histories/{id}/executions；问数提交 expected_context_revision，分析提交 expected_record_revision，不由页面提交 analysis_run_id。[Store.create](../../src/chatbi_control/history.py) 为分析历史生成运行 UUID。当前[Web Design](../designs/web-dialogue-v1.md)、[历史 Design](../designs/history-results-v1.md) 和[执行 Design](../designs/execution-streaming-v1.md) 已描述新流程。
- 影响：依 Spec 接入网页会选错接口与状态身份。旧 `/api/v1/query` 及其客户端 run ID 规则仍有效，不能删除兼容 API。
- 处置建议：明确旧同步 API 与当前网页的适用入口，Web Spec 用 history / execution / revision 叙述，分析 Spec 区分运行 ID 来源。

### DOC004 / P2：观测性文档要求一次综合指标检索，实际每指标一次

- 文档：[观测性 Spec](../specs/observability.md) 观察范围、[Design](../designs/observability.md) 的 metric.search 表和规则写仅一次综合检索。
- 实现：[资源阶段](../../src/online_query/retrieval/retrieval_resource_stage.py) 对 `semantic_query.metrics` 逐个检索；[现有测试](../../tests/online_query/test_retrieval_observability_t3a.py) 虽然函数名仍叫 `test_multimetric_keeps_one_comprehensive_metric_search`，实际断言 3 个请求对应 3 次检索和 3 个 metric.search Span。该文件本次定向运行 3/3 通过。[检索 Spec](../specs/online-retrieval.md#resource-retrieval资源检索) 也明确要求逐个指标说法检索。
- 影响：正确 Trace 可能被文档误判为重复检索，成本与调用次数解释错误。
- 处置建议：按正式检索规则同步观测性描述；测试名作为独立清理项记录，不在本次文档删除中改测试。

### DOC005 / P2：执行 Design 仍否认旧同步 API 共享额度

- 文档：[执行 Design](../designs/execution-streaming-v1.md#受理去重额度与-worker-交接) 写“旧同步 /api/v1/query 不新增后台执行额度承诺”。
- 事实：[就绪 Spec](../specs/application-readiness.md)、[Query API Spec](../specs/query-api.md) 和[执行 Spec](../specs/execution-streaming-v1.md#受理保护补充) 已要求同步与后台共享默认每账号 1 / 全局 4；[app.py](../../src/query_api/app.py) 同步问数与分析均使用 `admit`，[admission.py](../../src/query_api/admission.py) 调用相同 runtime.reserve_owner。
- 影响：Design 会让维护者误以为同步请求不受共享额度保护。
- 处置建议：保留同步 API 响应兼容说明，同步更新共享受理 / 占用规则。

### DOC006 / P2：展示 Spec 把维度物理引用归给错误文件

- 文档：[可视化 Spec](../specs/result-visualization-v1.md#可信结果说明) 写 `result_display.json` 拥有展示属性及维度物理引用。
- 事实：[query_bindings.json](../../src/semantic/query_bindings.json) 拥有维度映射，[result_display.json](../../src/semantic/result_display.json) 只有指标格式 / 单位；[loader](../../src/semantic/result_display.py) 显式从前者读 dimensions。[恢复 Contract](../specs/query-restoration.md) 和架构已明确两者职责。
- 影响：修改指标展示时容易误增第二份物理映射，违背单一业务事实源。
- 处置建议：修正文案并链接恢复 Contract，展示文件只拥有展示属性。

### DOC007 / P2：Trace 日志命令没有使用包含 API 的 Compose 配置

- 文档：[Runbook AI Evaluation](../runbook.md#4-ai-evaluation) 给出 `docker compose logs --since 10m api`；[观测性 Spec](../specs/observability.md) 同样使用裸 `docker compose logs api`。
- 实现：[基础 Compose](../../docker-compose.yml) 只有 postgres / qdrant；api 定义在[开发 Compose](../../docker-compose.dev.yml)，[dev_environment.sh](../../scripts/dev_environment.sh) 显式传入两份文件及选择的环境 / override。
- 影响：按 Runbook 默认环境直接执行命令无法选中 API；额外手工配置 COMPOSE_FILE 的用户可能成功，但文档未声明该前提。
- 处置建议：改用当前支持的 `./dev logs --since 10m`，或提供与 dev 一致的完整配置选择。不实际读取本机日志以免暴露业务内容。

### DOC008 / P3：Evaluation Design 遗留旧规模、旧输入数量和报告提交规则

- 文档：[评测 Design](../designs/evaluation.md#报告与版本) 写 reference_result_hash 为 21 条标准 SQL、context_hash 为五个结构与指标文件，并称报告可以单独 Commit。
- 事实：当前单轮案例为 29 个，包含无需标准 SQL 的澄清 / 拒答；[Runner](../../evaluation/suites/single_turn/runner.py) 仅为 result_match 汇集标准结果。[CLI](../../evaluation/__main__.py) `_default_context_paths` 为四个文件，分析另外添加 dimensions；[报告实现](../../evaluation/common/reporting.py) 按实际 reference_results / context_paths 计算 Hash。[评测 Spec](../specs/evaluation.md) 与 [.gitignore](../../.gitignore) 明确新报告为本机产物，默认不进入 Git。
- 影响：错误理解报告指纹及交付方式，可能把诊断报告混入源码提交。
- 处置建议：用实际适用结果集合及套件输入定义替代固定旧数量，报告规则与正式 Spec 对齐。旧已跟踪历史报告不删除、不改标。

### DOC009 / P3：当前历史 Design 把恢复 Contract 链到归档

- 文档：[历史 Design](../designs/history-results-v1.md#codec5mib与当前业务兼容) 的“完整结构化恢复Contract”指向 .scratch/history-results-v1/history/documentation-docs--designs--history-query-restoration.md。
- 事实：现行权威入口为[查询恢复 Spec](../specs/query-restoration.md)，当前历史 Spec 已链接它；归档描述过去方案 / 当时 Contract。
- 影响：链接检查能通过，但维护者容易依旧方案理解当前规则。
- 处置建议：改链正式恢复 Spec，历史链接仅在解释历史决定时保留。

### DOC010 / P3：观测性 Design 仍描述旧装配、覆盖范围及静态回退

- 文档：[观测性 Design](../designs/observability.md) 写中间件只覆盖 /api/v1/query、main.py 负责环境加载和装配，并描述在线 static_fallback；Spec / Design 还固定写 20 个评测案例。
- 事实：[main.py](../../src/query_api/main.py) 只创建 runtime_factory 应用，配置与资源在[Bootstrap runtime](../../src/bootstrap/runtime.py) 的 lifespan 内建立；[中间件](../../src/query_api/app.py) 还覆盖 histories / saved-results / executions / result-exports，并为 GET / HEAD 关闭业务 Root Trace；[OnlineQueryService](../../src/online_query/service.py) 在线检索使用 FAIL_CLOSED。显式无 retrieval_provider 的静态模式仍存在，它与在线技术故障回退不同。当前单轮案例规模见[评测 Spec](../specs/evaluation.md)。
- 影响：诊断时看错装配位置、Trace 覆盖范围和错误路径。
- 处置建议：按 Bootstrap 和后台执行的现行规则整理 Design，删除失效回退说明，案例规模引用 Evaluation。

## 逐文件审核清单

“无新增发现”表示已阅读并对照所列入口抽查关键规则，受前述证据边界限制。报告中的日期化旧审计不是当前缺陷清单。

| 文档 | 核对入口 / 重点 | 结论 |
| --- | --- | --- |
| README.md | dev 命令分派、Compose、src 目录、正式文档导航 | Roadmap 导航已移除；主要能力与运行边界无新增发现 |
| AGENTS.md | docs/agents、.harness、本机记录与 check_harness_state | 删除 Roadmap 读取 / 更新门禁；保留范围与发布授权规则 |
| docs/architecture.md | DDL、Semantic、OnlineQueryService、Guard、Bootstrap | 核心依赖 / 数据归属 / 查询链路无新增发现 |
| docs/product-scope.md | 前端入口、模块用例、Compose、正式 Spec | Roadmap 链接已移除；支持范围无新增发现 |
| docs/project-explained.md | 974 行全文；代码地图、指标、DDL、dev、各正式 Spec | 删除 Roadmap 依赖；明确冻结基线，教学公式核算正确，未把冻结结果当当前运行证明 |
| docs/runbook.md | dev、container_tasks、Compose、verify 脚本、CI | DOC007；其余初始化 / 资源隔离命令静态抽查无新增发现，未实际重建运行 |
| docs/agents/documentation.md | check_documentation、Markdown checker、动态清单 | 删除 Roadmap 归属 / 更新要求，文档角色及自动检查边界一致 |
| docs/agents/domain.md | Semantic、正式 Spec 与可选上下文文件规则 | 无新增发现；未声称外部 domain-modeling Skill 当前可用 |
| docs/agents/issue-tracker.md | check_harness_state、harness adapter、59 份初始记录 | 本机定位与只读检查边界一致；未重新验收跨仓库恢复 / 所有历史 PR |
| docs/agents/git-pr-workflow.md | Git、PR 模板、CI 和 enable-auto-merge workflow | 删除 Roadmap 门禁；发布授权与自动合并流程静态一致，未核验远端规则配置 |
| docs/audits/project-audit-20261016.md | 明确的旧 commit / 范围与 .scratch 修复记录 | 合法历史报告，保留原问题与证据，不改标为当前状态 |
| docs/specs/admin-recovery.md | admin_recovery / auth_service、dev_maintenance | 账号范围、User 锁、事务审计和显式 dev 入口抽查无新增发现 |
| docs/specs/application-readiness.md | operations、readiness、admission、operations_api | 依赖期限、默认额度、状态权限与只读校验抽查无新增发现 |
| docs/specs/bootstrap.md | bootstrap commands / runtime / lifecycle | 导入无资源初始化、显式准备和 lifespan 装配无新增发现 |
| docs/specs/business-analysis.md | application / planning / attribution、history Store | DOC003；固定两期 / 产品归因、金额公式抽查无新增发现 |
| docs/specs/container-deployment.md | dev、开发镜像和 Compose | 当前源码容器路线与旧 APP 退役说明一致 |
| docs/specs/container-dev-environment.md | dev、container_tasks、verify 脚本、Compose | 命令、重启策略、隔离和摘要规则抽查无新增发现；未运行整机恢复 |
| docs/specs/evaluation.md | suites 案例、Runner / reporting / acceptance、Real E2E workflow | 套件规模和正式证据规则抽查无新增发现；未执行真实评测 |
| docs/specs/execution-streaming-v1.md | execution / runtime / events / API / admission | 幂等、取消、SSE、共享容量抽查无新增发现；不声称竞态完整证明 |
| docs/specs/history-results-v1.md | HistoryApplication / Store / codec、migration | 归属、快照、5 MiB、续聊及兼容入口抽查无新增发现 |
| docs/specs/observability.md | retrieval_resource_stage、tracing / config、app middleware | DOC004、DOC007、DOC010；安全白名单及后台 Trace 补充抽查一致 |
| docs/specs/online-query.md | service、SQL Guard、database、query_understanding_llm | 单层 SELECT、认证口径、30s / 10s、100/101 行与受控重试抽查无新增发现 |
| docs/specs/online-retrieval.md | RetrievalConfig、resource / pipeline / join stage | DOC001、DOC002；逐指标认证与 fail-closed 错误边界抽查一致 |
| docs/specs/query-api.md | app、history / execution / export API、browser | 新旧接口及错误映射抽查无新增发现；未逐 DTO 运行全部验收 |
| docs/specs/query-restoration.md | semantic_state、restoration_conditions、history codec、Guard | 规范条件与当前认证、SQL 执行前一致性抽查无新增发现 |
| docs/specs/rag-offline-build.md | sources / documents / build / provenance | 四类输入、元数据、三集合与原子发布抽查无新增发现 |
| docs/specs/result-export-v1.md | export_application / runtime / worker / xlsx / renderer、frontend/export | 快照源、额度、文件 / 时间上限及字体配置抽查无新增发现；未渲染真实文件 |
| docs/specs/result-visualization-v1.md | Semantic loader、result_metadata、chartPlan / numberFormat | DOC006；展示降级、格式化及快照来源抽查无新增发现 |
| docs/specs/web-dialogue-v1.md | Chat、browser、auth_service、executionStream | DOC003；Cookie、CSRF、TTL、账号锁定规则抽查一致 |
| docs/designs/evaluation.md | CLI、Runner、reporting、.gitignore | DOC008 |
| docs/designs/execution-streaming-v1.md | execution/runtime/events、admission、migration 006 | DOC005；其他身份和生命周期机制抽查无新增发现 |
| docs/designs/history-results-v1.md | history Store / codec / runtime、migration 005 | DOC009；同步兼容接口表仍存在，须与执行 Design 结合阅读，不当作当前网页主入口 |
| docs/designs/observability.md | Bootstrap、app、retrieval_resource_stage、tracing | DOC004、DOC010 |
| docs/designs/online-query.md | SQL Guard 各检查及 database | 校验顺序和只读取数边界无新增发现 |
| docs/designs/online-retrieval.md | retrieval_resource_stage、pipeline、rag_runtime | DOC002；同快照与认证范围抽查一致 |
| docs/designs/rag-offline-build.md | build、embedding、qdrant_store、uv.lock | 发布与本地模型机制、锁定依赖版本抽查无新增发现 |
| docs/designs/result-export-v1.md | export runtime / worker / assets、Dockerfile、frontend/export | 进程隔离、资源上限、本地 bundle 及字体包抽查无新增发现；未重新验证字体渲染 |
| docs/designs/web-dialogue-v1.md | browser、Chat、executionStream | 已描述历史 / 后台入口，身份冲突和 CSRF 机制抽查一致 |

## 本次已完成变更与验证

- Roadmap 从现行 docs/ 删除，内容保存在[退役归档](../../.scratch/remove-roadmap-and-audit/history/roadmap.md)；仅为归档位置调整其相对链接，历史正文保留。正式规则、导航、PR 模板及动态清单取消 Roadmap 要求；旧工作记录只重定向 Markdown 链接，不批量重写历史决定。
- 初始 `uv run --python 3.11 --locked python -m scripts.check_harness_state`：59 份记录通过，无 ERROR / REVIEW。系统没有 python 命令，使用 uv Python 3.11 执行同一检查模块。
- 文档组合检查：通过；最终版本及 Diff Review 结果见[本工作项验证记录](../../.scratch/remove-roadmap-and-audit/verification.md)。
- `./dev test python tests/scripts/test_check_documentation.py tests/scripts/test_harness_adapter.py`：23 passed、0 failed / skipped；报告 ID `20261025T144241Z-64d2eae-test-python-fb422fffcb54`。
- `./dev test python tests/online_query/test_retrieval_observability_t3a.py`：3 passed、0 failed / skipped；报告 ID `20261025T144307Z-64d2eae-test-python-84f0ae40e7cf`。验证 DOC004 的当前确定性行为，不证明与旧文字要求一致。
- 两次测试使用 Python 3.11.16 的现有 dev 镜像；对应源码为基线加当时文档改动的 dirty 工作区，起止 identity stable。新增审核报告不改变被测行为，不把上述结果改称未来提交的 clean 全量结果。
- 本次发现列为审核待办，未实施 DOC001–DOC010 的业务行为或独立文档修复；完成审核不代表这些问题已解决。
