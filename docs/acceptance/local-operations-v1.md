# R7 本地运行保障验收

Status: incomplete. Ticket 01–06 的本地实现与 Review 已完成；Ticket 07 当前候选完成部分隔离运行和真实浏览器验收。经营分析的 `LLM_ERROR` 已通过隔离诊断定位到运行时 `ObservedModel` 未转发 `stream()`；修复已提交，但当前候选的 Edge 验收在追问阶段未观察到终态，尚未覆盖经营分析。完整验收门槛未满足。

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
| 浏览器与查询链路 | FAIL（最新候选部分通过） | `f1b98d7` 两次 Edge 问数/追问通过；`515c253` 首条问数未取得成功快照；`2d907c0` 首条查询及执行流成功，随后追问未观察到终态响应而超时。 |
| 图表与 XLSX 导出 | PASS（部分候选）/ NOT RUN（当前其余格式） | `f1b98d7` 的 PNG / XLSX 从已保存结果导出成功；`2d907c0` 首条查询 XLSX 导出成功；当前候选未到 PNG / PDF。 |
| PDF 导出 | NOT RUN | `f1b98d7` 经营分析失败；`515c253` 首条问数未成功；`2d907c0` 追问未观察到终态，均未到 PDF 步骤。 |
| 经营分析 | FAIL（旧候选）/ NOT RUN（修复候选） | `f1b98d7` 两次验收公开 `error_code=LLM_ERROR`；诊断捕获内部分类 `PROVIDER_STREAM_UNAVAILABLE`，源码定位到 `ObservedModel` 未转发底层模型的 `stream()`，修复已提交。`515c253` 在首条问数停止；`2d907c0` 在追问阶段停止，均未验证修复后的分析路径。 |
| 临时资源回收 | PASS | acceptance 容器、网络和卷均为 0；清理记录为 `active_sessions=0`、卷已移除。 |
| 稳定服务 | 未纳入验收项目 | 当前验收期间稳定服务继续运行原 R6 发布 `2b4a8c8`；API/PostgreSQL healthy、Qdrant running，首页与 `/health` 均 HTTP 200。没有执行升级、密钥初始化或恢复激活；此前恢复记录见 [R6 Acceptance](local-deployment-v1.md#稳定服务重启核验2026-10-09)。 |

## 同一候选复跑（2026-10-09）

运行 `20261009T090758Z-b87ca1ff` 再次绑定 clean 源码候选 `f1b98d73c72b572a37d7b6a3ff5dd19da9d46b3b`（`git_dirty=false`），Windows Edge `154.0.4258.62`。问数执行流 `succeeded`，PNG / XLSX 导出成功；经营分析 HTTP 受理成功并到达 `failed` 终态，公开分类仍为 `LLM_ERROR`。截至该次复跑完成时，安全报告没有原始异常或业务内容，具体底层原因尚未确认；后续隔离诊断与源码核对定位为模型包装器未转发`stream()`，见下文。PDF 未运行。

本次临时账号已禁用、活动 Session 为 0；按专属 Compose project 标签复核，验收容器、网络、卷均为 0。该复跑未更改稳定版。原始运行报告保留在本机 ignored 目录 `.local/acceptance/20261009T090758Z-b87ca1ff/`，不提交原始诊断文件。

## 诊断性 Provider 流式探针（2026-10-09）

用户确认后，复用候选的本机模型配置和 `LangChainAnalysisSummarizer` 使用的 ChatOpenAI 构造方式，单独发送一次不含业务内容的合成 JSON 请求。流正常结束，返回内容非空且可解析为 JSON；没有捕获异常或 HTTP 错误。权限受限的 ignored 报告 `.local/acceptance/diagnostic-probes/20261009T1723-provider-stream.json` 只记录候选身份、结果分类与“不保存提示词/响应”的标记，不含模型名、端点、密钥、提示词或响应正文。

该探针表明探针时刻当前配置可完成一次最小流式调用；它不覆盖真实经营分析的长提示词、实际结果或报告 Contract，也不是候选验收通过证据。因而不能据此定位两次 `LLM_ERROR` 的根因，经营分析验收仍失败且 Ticket 07 仍未完成。没有修改稳定服务或 Provider 配置。

## 隔离分析诊断与本地修复（2026-10-09）

用户确认后，在独立临时 clone 对 clean candidate `f1b98d73c72b572a37d7b6a3ff5dd19da9d46b3b` 进行一次分析诊断复测，运行 ID `20261009T093333Z-179e5fee`。问数执行流成功，PNG / XLSX 导出成功；经营分析到达 `failed` 终态，安全 checkpoint 只读出 `public_error_code=LLM_ERROR`、`internal_reason=PROVIDER_STREAM_UNAVAILABLE`、`http_status=null`。受限本机记录 `.local/acceptance/diagnostic-probes/20261009T093333Z-analysis-internal-reason.json` 仅含固定分类与运行身份，权限为目录 `0700`、文件 `0600`；未保存提示词、模型响应或异常文本。隔离 Compose 容器、网络、卷均清理为 0，活动 Session 为 0。

源码核对定位了原因：`src/bootstrap/runtime.py` 把用于模型调用状态观察的 `ObservedModel` 注入经营分析；该包装器此前只转发 `invoke()`，未转发底层 `ChatOpenAI.stream()`。报告生成通过流式路径时，`LangChainAnalysisSummarizer` 因包装器缺少 `stream()` 在 Provider 请求前报 `PROVIDER_STREAM_UNAVAILABLE`，所以本次没有摘要 HTTP 状态。此前合成 Provider 探针直接构造 ChatOpenAI，没有经过该包装器，无法覆盖此故障。

该次隔离诊断后，工作区为 `ObservedModel` 增加惰性 `stream()` 转发：流完整结束后记录成功，流不受支持、创建失败或迭代失败时记录失败，不保存提示词或内容。核心流转发回归先因包装器缺少 `stream()` 而失败；修复后 `tests/bootstrap/test_operations.py` 为 10 passed。当时尚未构建新 clean candidate；后续候选 `515c253` 的复验结果见下文，尚未覆盖分析步骤。稳定 R6 服务及其配置未更改。

## 修复候选 Edge 复验（2026-10-09）

候选 `515c253489eea0e99cadc6dc833b42ed563a33f7` 的 API / PostgreSQL 固定镜像构建通过，RAG 初始化、配置/兼容/失败保护及 Chromium sandbox 检查通过。隔离验收运行 `20261009T095740Z-a125115e` 在 Windows Edge 首条问数阶段停止：HTTP 请求为 `200`，执行终态响应未包含成功 `turn.snapshot`，浏览器未进入追问、经营分析、历史/成果或导出步骤。该版本的 E2E 报告未保存执行对象中的 `public_error.error_code`，因此不能判断这是 Provider、查询解析或其他执行失败；没有把它归为 `LLM_ERROR`。本次运行尚未覆盖 `ObservedModel.stream()` 修复。

失败报告的错误位置仅指向缺少快照后的 UI 校验；受限报告只保存该静态校验分类和浏览器状态，没有保存响应正文。临时账号已禁用、活动 Session 为 0、验收容器/网络/卷均清理为 0。稳定 R6 API/PostgreSQL 仍 healthy、Qdrant running，`/` 和 `/health` 均返回 `200`。随后在工作区补充 E2E 安全记录：只保留允许列表中的执行错误码，并在无快照时给出固定失败分类；`npm run typecheck` 通过。该报告改进尚未重跑验收。

## 最新修复候选 Edge 复验（2026-10-09）

clean 候选 `2d907c03ee0b5eab353fb3478b6883793c823048` 的 API / PostgreSQL 固定镜像构建通过。隔离运行 `20261009T101046Z-94af86a8` 的启动、RAG readiness、配置/兼容/失败保护及 Chromium sandbox 检查通过。Windows Edge `154.0.4258.62` 的首条问数 HTTP 200，快照结果符合验收参考值；执行流到达 `succeeded`，阶段覆盖 `query_understanding`、`retrieval`、`sql_generation`、`sql_validation`、`query_execution` 和 `result_saving`。从该快照导出的 XLSX 成功。

同一对话追问后，测试未观察到 `/api/v1/executions/{id}` 的终态响应，在 Playwright 等待窗口结束后停止。报告定位为 `container-real.spec.ts:288:33`，没有追问 HTTP 终态、执行错误码或终态执行状态；因此无法区分浏览器未发出后续请求、请求未完成或执行状态未到终态，也不能据此判断分析 Provider。经营分析、历史/成果、后续 PNG / PDF 与重启续聊步骤均未运行。本次没有验证 `ObservedModel.stream()` 的分析修复。

临时账号已禁用、活动 Session 为 0；按本次 Compose project 标签复核，容器、网络、卷均为 0。稳定 R6 仍绑定 `2b4a8c8`，API/PostgreSQL healthy、Qdrant running，首页和 `/health` 均 HTTP 200。验收结束后本机默认 release 指针恢复为原 `f1b98d7`，文件权限为 `0600`。为下一次诊断，当前本地 E2E 改动汇总执行详情轮询的 HTTP 状态、允许列表内执行状态与错误码，不保存执行 ID、错误正文或业务响应；`npm run typecheck` 和 `git diff --check` 已通过，尚未提交或重跑。

## 尚未满足的 Ticket 07 验收项

- 已定位并在本地修复分析流式包装器；`2d907c0` 的真实问数及 XLSX 通过，但追问未观察到终态。当前候选仍需完成追问、经营分析成功、历史/成果及 PNG/PDF 浏览器验收。
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
