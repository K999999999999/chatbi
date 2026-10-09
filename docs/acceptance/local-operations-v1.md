# R7 本地运行保障验收

Status: incomplete. Ticket 01–06 的本地实现与 Review 已完成；Ticket 07 当前候选完成了部分隔离运行和真实浏览器验收，经营分析以公开分类 `LLM_ERROR` 终止，完整验收门槛未满足。

## 候选与证据身份

- 候选源码：`f1b98d73c72b572a37d7b6a3ff5dd19da9d46b3b`，验收报告记录 `git_dirty=false`。
- 首次正式运行时间：2026-10-09（Asia/Shanghai）；运行 ID：`20261008T172902Z-2f1178cf`。同一候选于当日再次隔离复跑，运行 ID：`20261009T090758Z-b87ca1ff`。
- 浏览器：Windows Edge `154.0.4258.62`；运行资源使用独立 acceptance Compose project。
- 原始证据位于本机 ignored 目录 `.local/acceptance/20261008T172902Z-2f1178cf/`，不随仓库分发。报告含运行身份和业务结果，不应复制到版本库或公开日志。
- 候选镜像构建因默认软件源不可达，使用临时镜像 URL 构建包装；包装只改临时构建上下文中的下载地址，锁文件版本与摘要保持原值，仓库文件未修改。默认网络路径下的独立重建尚未验证。

## 本次结果

| 范围 | 结果 | 证据与限制 |
| --- | --- | --- |
| 隔离候选启动、数据库/RAG 初始化与 readiness | PASS | 使用专属运行资源；原稳定服务未加入验收 Compose。 |
| 故障拒绝与状态保护 | PASS | 配置错误、启动失败、不兼容 migration、缺失索引、回环端口占用五类检查均按预期拒绝；持久状态前后检查相同。 |
| 浏览器与查询链路 | PASS | Chromium sandbox 实际启动；Edge 查询和追问成功，执行流到达 `succeeded` 终态。 |
| 图表与 XLSX 导出 | PASS | PNG 和 XLSX 均从已保存结果导出；导出期间没有新建业务执行。 |
| PDF 导出 | NOT RUN | 经营分析失败后验收停止，尚未到 PDF 步骤。 |
| 经营分析 | FAIL | HTTP 请求成功受理，执行流到达真实 `failed` 终态，公开 `error_code=LLM_ERROR`；安全报告不含原始异常，具体原因未能判定。不能记作模型拒答、应用缺陷或成功分析。 |
| 临时资源回收 | PASS | acceptance 容器、网络和卷均为 0；清理记录为 `active_sessions=0`、卷已移除。 |
| 稳定服务 | 未纳入验收项目 | 首次验收时健康；第二次复跑前稳定服务曾停止，随后按原 R6 版本恢复。两次验收均未执行升级、密钥初始化或恢复激活，恢复记录见 [R6 Acceptance](local-deployment-v1.md#稳定服务重启核验2026-10-09)。 |

## 同一候选复跑（2026-10-09）

运行 `20261009T090758Z-b87ca1ff` 再次绑定 clean 源码候选 `f1b98d73c72b572a37d7b6a3ff5dd19da9d46b3b`（`git_dirty=false`），Windows Edge `154.0.4258.62`。问数执行流 `succeeded`，PNG / XLSX 导出成功；经营分析 HTTP 受理成功并到达 `failed` 终态，公开分类仍为 `LLM_ERROR`。安全报告没有原始异常或业务内容，底层原因仍未确认；这证明该候选上的失败可复现，不证明具体由模型服务、网络或应用哪一层引起。PDF 未运行。

本次临时账号已禁用、活动 Session 为 0；按专属 Compose project 标签复核，验收容器、网络、卷均为 0。该复跑未更改稳定版。原始运行报告保留在本机 ignored 目录 `.local/acceptance/20261009T090758Z-b87ca1ff/`，不提交原始诊断文件。

## 诊断性 Provider 流式探针（2026-10-09）

用户确认后，复用候选的本机模型配置和 `LangChainAnalysisSummarizer` 使用的 ChatOpenAI 构造方式，单独发送一次不含业务内容的合成 JSON 请求。流正常结束，返回内容非空且可解析为 JSON；没有捕获异常或 HTTP 错误。权限受限的 ignored 报告 `.local/acceptance/diagnostic-probes/20261009T1723-provider-stream.json` 只记录候选身份、结果分类与“不保存提示词/响应”的标记，不含模型名、端点、密钥、提示词或响应正文。

该探针表明探针时刻当前配置可完成一次最小流式调用；它不覆盖真实经营分析的长提示词、实际结果或报告 Contract，也不是候选验收通过证据。因而不能据此定位两次 `LLM_ERROR` 的根因，经营分析验收仍失败且 Ticket 07 仍未完成。没有修改稳定服务或 Provider 配置。

## 尚未满足的 Ticket 07 验收项

- 需要先用安全证据复现并定位分析执行的 `LLM_ERROR`，再完成当前候选的分析、历史/成果和 PDF 浏览器验收。
- 尚未形成当前候选的单用户分项耗时及 CPU/内存峰值、跨入口资源回收和 60 秒依赖故障/恢复矩阵；本次不能据此声明容量或恢复 SLA。
- 当前候选的完整隔离恢复计时及 30 分钟 RTO / 条件 RPO 矩阵未完成。Ticket 05 的隔离恢复、切换和回退证据仍绑定各自候选，不自动替代本次候选验收。
- 当前候选阿里云 Trace 未查询验证；稳定环境 OTLP 当前关闭。没有执行真实 stable 升级或运行配置更改。
- 本次未重跑正式 AI Evaluation；历史报告仍绑定其原始候选，不能作为 `f1b98d7` 的通过证据。

## 软件验证

- `tests/scripts/test_local_acceptance.py`：10 passed。
- `npm run typecheck`：通过；`npm test -- --config=playwright.config.ts tests/helpers.spec.ts`：1 passed。
- 完整测试套件最近一次在前置候选 `82b366e` 上通过：941 passed、41 skipped、139 subtests。随后改动集中于验收挂载、浏览器终态等待与安全错误分类记录；本次未重跑完整套件。
- 本机 `python -m scripts.check_harness_state` 检查 22 份记录，无 ERROR；`chatbi-product-v1`、`local-operations-v1` 和 `r6-presubmit-coverage` 保留 REVIEW，需各自继续跟进。

结论：R7 Ticket 07 仍为 in-progress。当前候选只完成表中列出的部分证据，不能据此宣称 R7 全部验收通过或开始真实 stable 切换。未获本目标 Push/PR 授权。
