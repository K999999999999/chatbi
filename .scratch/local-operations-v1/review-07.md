# Ticket 07 实现 Review

## 安全记录补丁（2026-10-09）

Review: PASS
Scope: BASE `515c253489eea0e99cadc6dc833b42ed563a33f7`; `frontend/tests/container-real.spec.ts`、`.scratch/local-operations-v1/issues/07-acceptance.md`、`docs/acceptance/local-operations-v1.md`、`docs/roadmap.md`。
Change Description: 首条真实问数没有成功快照时，从执行对象读取公开 `error_code`，仅将 Ticket Contract 中的固定允许码写入验收报告，未知值归一为 `UNCLASSIFIED`，并使用固定断言错误文本；用于定位上次 Edge 验收停止原因，不保留错误正文或业务响应。风险限于诊断报告字段，业务执行和公开 API 不变。验证：`npm run typecheck`、Markdown 链接检查和 `git diff --check` 通过；候选真实运行尚未复验。

Findings:
- 无。

Review Dimensions: Correctness / Comprehension / Consistency / Testability / Architecture / Security 均通过。错误码允许列表与 `QueryErrorCode` 一致；`Set.has` 只接受精确匹配，其他输入不写入报告；固定失败文本不包含响应正文或异常内容。变更不影响生产运行代码或稳定服务。

Tests: 复用本次 `npm run typecheck`、`uv run --frozen python -m scripts.check_markdown_links`、`git diff --check`。`515c253` 的模块回归 `tests/bootstrap` 与 `tests/business_analysis` 为 104 passed；本补丁需由后续隔离候选复验覆盖真实报告路径。

Next: 将本次本地诊断与验收记录提交，再对提交构建隔离候选并继续 Ticket 07 验收；真实 Edge 复验用于确认诊断码和观察已修复的分析路径。

## 追问等待超时诊断补丁（2026-10-09）

Review: PASS
Scope: BASE `2d907c03ee0b5eab353fb3478b6883793c823048`; `frontend/tests/container-real.spec.ts`、`.scratch/local-operations-v1/issues/07-acceptance.md`、`docs/acceptance/local-operations-v1.md`、`docs/roadmap.md`。
Change Description: 最新隔离运行首问及 XLSX 成功，但追问未观察到终态。E2E 现在汇总执行详情 GET 的请求数、HTTP 状态、白名单内执行状态和公开错误码，用于区分无终态响应时的浏览器观察结果。报告不保留执行 ID、原始响应、错误消息或业务数据。验收与路线图更新为本次候选的真实结果，并明确分析尚未执行。风险仅涉及本地验收证据；产品 Contract 和生产运行行为不变。验证：`npm run typecheck`、`git diff --check` 通过；真实复验未运行。

Findings:
- 无。

Review Dimensions: Correctness / Comprehension / Consistency / Testability / Architecture / Security 均通过。轮询结果只接受固定状态集合和与 QueryErrorCode 对齐的错误码集合；未匹配的值被丢弃。异步响应 JSON 读取失败时安全忽略，报告仍记录已观察的请求数与 HTTP 状态。

Tests: `npm run typecheck --prefix frontend` 通过；当前候选 `2d907c0` 已证明首问和 XLSX 流程通过，但追问超时且未暴露终态。该补丁仍需一次新的隔离 Edge 运行验证报告字段。

Next: 本地提交补丁与本次验收记录。是否再次发起真实模型/Edge 候选复验，需取得用户对下一次外部调用的确认。

## 执行提交请求安全计数补丁（2026-10-09）

Review: PASS
Scope: BASE `8f73ab12e0b078ffca7c6416ab8ae7ea055522a9`; `frontend/tests/container-real.spec.ts`、`.scratch/local-operations-v1/issues/07-acceptance.md`、`docs/acceptance/local-operations-v1.md`、`docs/roadmap.md`。
Change Description: `8f73ab1` 的复验只观察到首问详情轮询，未记录追问的提交请求。补丁为验收报告增加执行提交 POST 的请求数、响应数、HTTP 状态和允许列表内公开错误码，并汇总 SSE 连接计数；现有执行详情状态/错误码摘要保持不变。输出不含 URL 路径、执行 ID、错误正文或业务数据。文档记录 `8f73ab1` 已核实结果，并把分析未运行和后续待项明确保留。风险仅涉及验收诊断；产品 API 和运行行为不变。验证：`npm run typecheck`、Markdown 链接检查、`git diff --check` 通过；新字段尚未由真实候选复验验证。

Findings:
- 无。

Review Dimensions: Correctness / Comprehension / Consistency / Testability / Architecture / Security 均通过。只统计固定执行提交路由及响应状态；从提交响应读取的错误码仅接受公开错误码白名单，其他值不保存；解析失败时不传播、不记录原始响应。SSE 连接只聚合为总数，不保留执行 ID。

Tests: `npm run typecheck --prefix frontend`、`uv run --frozen python -m scripts.check_markdown_links`、`git diff --check` 通过。候选 `8f73ab1` 已证明首问和 XLSX 流程，但追问未观察到终态；本补丁需后续隔离运行验证新的提交计数。

Next: 提交本地诊断和验收记录；再进行真实模型/Edge 候选验收前需取得用户确认。

## 确定性前端验收用例修正（2026-10-10）

Review: PASS
Scope: BASE `a822107`；`frontend/tests/execution.spec.ts`、`frontend/tests/history.spec.ts`、`frontend/tests/result-export.spec.ts`、本Review记录。
Change Description: R7 新状态横幅增加了页面级 `role=status`，执行观察测试现限定到对话轮次中的状态；历史刷新测试补齐 ready 的 `/api/v1/operations/status` 响应。Google Chrome headless 的 Playwright download event 对 `blob:` 文件返回通用名 `download`，尽管 API `Content-Disposition` 与实际 `<a download>` 已含正确文件名；导出测试改为在真实点击事件中核对该下载名指令，并继续验证实际下载、文件签名和请求来源。产品行为与验收断言范围未放宽。

Findings:
- 无。

Review Dimensions: Correctness / Comprehension / Consistency / Testability / Architecture / Security 均通过。状态定位仍验证“生成查询”；ready 状态 mock 符合 Operations Status contract；下载用例同时验证用户文件名指令和 XLSX / PNG 字节签名。修改只影响测试，不更改产品实现、权限或公共 API。

Tests: Linux dedicated Playwright container，Google Chrome `155.0.8059.39`，全量前端 `68 passed`；`git diff --check` 通过。先前 `npm run build`、后端 pytest 证据未受仅测试文件变化影响。

Next: 本地提交修正与Review；随后构建新 clean candidate，并在隔离 R7 Compose 项目中执行真实业务验收和当前候选资源采样。

## 单用户导出耗时记录（2026-10-10）

Review: PASS
Scope: BASE `3aeb96d8f44f4116fd6695a02979798d9e13e136`；`frontend/tests/container-real.spec.ts` 与本Review记录。
Change Description: 为真实浏览器验收中的每个导出记录点击到浏览器下载完成的单次耗时，精确到毫秒，并纳入现有安全 JSON 报告；不记录文件内容或新增生产行为。该字段补齐 R7 单用户基线中 PDF / PNG / XLSX 导出时长。风险限于验收报告。

Findings:
- 无。

Review Dimensions: Correctness / Comprehension / Consistency / Testability / Architecture / Security 均通过。计时使用单调时钟，从触发按钮开始，到 `download.path()` 确认浏览器文件可用为止；文件签名与独立解析逻辑保持原样。类型检查及 Diff 检查通过，真实候选验收待运行。

Tests: `npm run typecheck` 与 `git diff --check` 通过；候选验收将验证每个导出均产生正耗时字段。

Result: commit `6d764ac` 的固定镜像构建与完整隔离验收通过，12项导出均记录正耗时，资源样本及运行结论已写入正式验收与路线图。

## 验收后平台差异复核（2026-10-10）

Finding: Linux Chromium 153 的 12 项真实导出均返回 Playwright `suggested_filename=download`；此前直接 Chrome CDP 探针也确认中文 Blob 下载实际保存名为 `download`，虽然服务端 UTF-8 文件名和 DOM `download` 值正确。实际文件内容及 PDF/PNG/XLSX 解析全部通过。Windows Chromium 旧候选 `0a97182` 报告中的`suggested_filename`为预期中文名，且当前与该候选间 `frontend/src/api.ts`、`src/query_api/result_export_api.py` 未变。

该发现超出 R7 运行保障验收计时补丁的实现范围，未修改 R5 API 或产品行为。通用接受入口的 `runtime.json` 还把 Linux Chromium 版本误标为 `msedge`；实际版本由 `browser.json` 及本机 WSL 适配器命令证明。详见[Acceptance](../../docs/acceptance/local-operations-v1.md#6d764ac-当前-clean-候选完整验收与单用户基线2026-10-10)。

Next: 保留为 R5 跨浏览器下载文件名兼容问题；若需支持 Linux Chromium 中文落盘名，应在确认修复 Contract 后另行实现和验收。R7当前等待下一次真实6小时自动备份周期；阿里云控制台Trace查询仍待人工核验。

## Active Stable R7切换核验（2026-10-10）

Review: PASS（运行操作与验收证据）

Scope: 用户明确授权的Stable R6→R7兼容升级与备份/RPO验证；候选`6d764aca6428bd225afe30395723dfaeb4ae0e0b`。

Finding: `./local upgrade`的升级前R6备份门禁、只读兼容检查、Schema/RBAC migration、迁移后复核及R7 API启动均成功。升级前R6备份`9d01c195caeb4b71ad5cdb7ca726bfae`和升级后R7来源备份`ce589d79d5a643c48af315756a72ff22`完整校验并登记。首页、`/health`、`/ready`为200，依赖状态ready，独立备份调度进程仍运行，当前备份状态known且未逾期；PostgreSQL/Qdrant保持运行。调度/门禁/逾期状态定向回归23项通过。

限制：R7升级后副本刚创建，下一次真实6小时调度尚未发生；未更改Active Stable的catalog/状态来伪造24小时逾期。故长周期RPO验收继续in-progress；阿里云控制台Trace查询与R5 Linux下载文件名问题不在本次运行操作范围。

Next: 约在`2026-10-10 07:30 +08:00`后复查自动备份目录/状态与安全日志；由用户登录阿里云控制台只读核验Trace。
