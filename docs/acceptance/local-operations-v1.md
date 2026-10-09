# R7 本地运行保障验收

Status: incomplete. Ticket 01–06本地实现与Review完成；当前clean候选`6c3c639`的完整隔离业务验收由用户指定的 Linux Playwright 容器通过，12份 PDF/PNG/XLSX 均独立解析通过，重启续聊、日志Secret检查和资源清理通过。该轮没有启动 Windows 浏览器或 IDM。候选`6c3c639`的四类依赖60秒故障/恢复矩阵也已通过；11项额度/资源释放回归通过。用户已授权并完成本机备份密钥初始化（私钥权限600）；首份备份未创建，来源捕获因保存的 OTLP 配置与运行中 R6 API 配置不一致而安全拒绝，stable 未重启且仍健康。当前单用户运行资源完整采样、30分钟RTO与条件RPO演练、阿里云控制台Trace查询仍待完成。

## 候选与证据身份

- 初始验收候选源码：`f1b98d73c72b572a37d7b6a3ff5dd19da9d46b3b`，验收报告记录 `git_dirty=false`。
- 首次正式运行时间：2026-10-09（Asia/Shanghai）；运行 ID：`20261008T172902Z-2f1178cf`。同一候选于当日再次隔离复跑，运行 ID：`20261009T090758Z-b87ca1ff`。
- 后续修复候选：`515c253`（模型 `stream()` 转发）；`2d907c0`、`8f73ab1`（E2E 安全诊断），均以干净提交运行。`59e1e34` 的 Edge 成功部分绑定运行 `20261009T110752Z-b9e90d25`；`efb2f5e7` 的完整业务阶段绑定运行 `20261009T120227Z-c19f7505`；前一完整候选 `0a97182e6840ed5ae1e3fd0da012dfe98fb4d1b3` 绑定运行 `20261009T122448Z-57d6dc78`。
- 最新候选 `6c3c639af9b9d9d70829b00a4356adec95b13212` 的依赖矩阵运行 `20261009T132359Z-825fdfde`、完整浏览器验收运行 `20261009T144447Z-abed4621`；完整验收绑定的 `git_dirty=false`。
- 历史浏览器：Windows Edge `154.0.4258.62`、独立 Windows Chromium `149.0.7827.55`；本轮按用户明确要求使用 `chatbi-browser-dev:local` 中的 Linux Chromium `153.0.8010.12`。运行资源使用专属 acceptance Compose project。
- 原始证据位于本机 ignored 目录 `.local/acceptance/20261008T172902Z-2f1178cf/`，不随仓库分发。报告含运行身份和业务结果，不应复制到版本库或公开日志。
- 候选镜像构建因默认软件源不可达，使用临时镜像 URL 构建包装；包装只改临时构建上下文中的下载地址，锁文件版本与摘要保持原值，仓库文件未修改。默认网络路径下的独立重建尚未验证。
  上述是历史构建限制；`0a97182` 已通过仓库原始 `./local build` 入口构建，无临时包装。依赖层复用了本机缓存，未做禁用缓存的全部下载源重建；构建后默认 release 指针已恢复，未切换实际 stable。

## 本次结果

| 范围 | 结果 | 证据与限制 |
| --- | --- | --- |
| 隔离候选启动、数据库/RAG 初始化与 readiness | PASS | 使用专属运行资源；原稳定服务未加入验收 Compose。 |
| 故障拒绝与状态保护 | PASS（`6c3c639`） | 配置错误、启动失败、不兼容 migration、缺失索引、回环端口占用五类检查均按预期拒绝；持久状态前后检查相同。 |
| 依赖故障与恢复 | PASS（`6c3c639`） | Control DB、业务 DB、Qdrant、业务资产四种隔离故障及恢复均在60秒内被网页/依赖状态观察到；单项故障与恢复最长29.588秒，Secret scan 与外部资源不变检查通过。 |
| 浏览器与查询链路 | PASS（`6c3c639`） | 用户指定的 Linux Playwright Chromium 两阶段覆盖问数、追问、取消/多标签恢复、经营分析、历史/成果、重启后续聊及重新登录；真实执行流包含问数理解、检索、SQL生成/校验/执行和结果保存。没有测试 Windows Edge 特有行为。 |
| 图表与 XLSX 导出 | PASS（`6c3c639`） | 当前、历史和重启后的成果均可导出；独立解析器验证全部文件。 |
| PDF 导出 | PASS（`6c3c639`，Linux Playwright） | 三种格式合计12份文件（PDF、PNG、XLSX）均通过独立解析；专用浏览器成功收到 PDF 下载事件。本轮未启动 Windows 浏览器、未触发 IDM、未修改 IDM 或用户浏览器设置。 |
| 经营分析 | PASS（`6c3c639`） | 真实分析、流式阶段、归因参考值、保存与重启后读取通过。 |
| 历史/成果及重启续聊 | PASS（`6c3c639`） | 浏览器两阶段均通过；持久状态指纹、未完成执行恢复规则及成功成果保留通过。 |
| 共享额度拒绝与释放 | PASS（软件回归） | `tests/query_api/test_operations_api.py::test_sync_query_shares_live_background_capacity_and_recovers`、`tests/query_api/test_execution_runtime.py`、两个导出失败释放回归共11项通过；验证后台占额时同步问数返回429、释放后可再次执行。此证据验证额度逻辑，不代表并发容量或SLA。 |
| 临时资源回收与最终日志检查 | PASS（`6c3c639`） | 专属账号禁用、`active_sessions=0`、验收容器/网络/卷清理；最终 API 日志 Secret 检查通过，验收前后外部 Docker 资源快照相同。 |
| 稳定服务 | 未纳入验收项目 | 当前验收期间稳定服务继续运行原 R6 发布 `2b4a8c8`；API/PostgreSQL healthy、Qdrant running，首页与 `/health` 均 HTTP 200。没有执行升级、重启或恢复激活。备份密钥已按用户授权初始化，但首份备份因 OTLP 配置漂移未生成；此前恢复记录见 [R6 Acceptance](local-deployment-v1.md#稳定服务重启核验2026-10-09)。 |
| 最终日志凭据检查与总体门禁 | PASS（`6c3c639`） | `logs_no_known_secrets=true`；原始`0a97182`结果仍作为各自历史报告，不改写候选身份。 |

## `6c3c639` 当前候选完整 Linux Playwright 隔离验收（2026-10-09）

clean 源码候选 `6c3c639af9b9d9d70829b00a4356adec95b13212` 绑定运行 `20261009T144447Z-abed4621`，专属 Compose project 为 `chatbi-r6-accept-20261009t144447z-abed4621`。按用户要求，浏览器由现有 `chatbi-browser-dev:local` 镜像提供，Chromium `153.0.8010.12`；没有启动 Windows 浏览器或 IDM。Playwright 在共享本次隔离 API 网络命名空间的容器内运行，浏览器 Origin 与 API 临时 Origin 均为 `http://127.0.0.1:8000`，宿主发布端口仍只绑定回环地址。测试使用本机 ignored 的一次性适配器 `.local/verify_r7_wsl_acceptance.py`，仓库脚本和应用代码未修改。

两阶段浏览器业务均通过，包含真实问数与同一对话追问、取消/多标签恢复、经营分析与执行流、历史/成果读写、重启后续聊与重新登录。启动和重启 `/ready` 均通过。PDF、PNG、XLSX 共12份导出由独立解析器全部通过；单用户运行时样本仍不构成并发容量或 p95 SLA。专属账号已禁用且活动 Session 为0；最终日志 Secret 检查通过；专属容器、网络、卷均已移除，验收前后外部 Docker 资源快照相同。稳定 API 根页面与 `/health` 均 HTTP 200；stable/dev 未切换或修改。安全摘要及解析结果位于 ignored 目录 `reports/browser-real-artifacts/r6-local-deployment/6c3c639af9b9-20261009T144447Z-abed4621/`，运行明细位于 `.local/acceptance/20261009T144447Z-abed4621/`。

首次 Linux 适配尝试 `20261009T144053Z-5697454d` 未进入业务请求：测试浏览器使用内部端口 `8000`，隔离 API 的来源校验却仍按宿主映射端口配置，登录收到来源拒绝。该次临时账号与资源均清理；修正仅把一次性隔离 API 的允许 Origin 对齐浏览器真实访问地址后，以上 `20261009T144447Z-abed4621` 完整验收通过。Windows Edge 的本机集成行为不在本次证据范围内。

独立依赖矩阵运行 `20261009T132359Z-825fdfde` 绑定同一候选 `6c3c639`：Control DB、业务 DB、Qdrant、业务资产四类故障及恢复均通过，观察到的最慢故障/恢复段为 `29.588` 秒；Secret scan 通过，外部资源保持不变。详细报告位于 `reports/browser-real-artifacts/r6-local-deployment/6c3c639af9b9-20261009T132359Z-825fdfde-dependency-faults/dependency-fault-matrix.json`。

## 前一候选 `0a97182` 完整隔离验收（2026-10-09）

clean 源码候选 `0a97182e6840ed5ae1e3fd0da012dfe98fb4d1b3` 绑定运行 `20261009T122448Z-57d6dc78`，Docker project 为专属 `chatbi-r6-accept-20261009t122448z-57d6dc78`。使用仓库原始 `./local build` 构建，无临时包装；浏览器为 Windows Chromium `149.0.7827.55`（显式自定义 executable），未修改 IDM 或用户浏览器设置。完整 `scripts.verify_local_deployment` 退出 0，全部业务阶段、末尾日志凭据检查、环境清理和外部资源前后核对通过。详细本机运行证据位于 ignored 目录 `.local/acceptance/20261009T122448Z-57d6dc78/`；安全摘要位于 `reports/browser-real-artifacts/r6-local-deployment/0a97182e6840-20261009T122448Z-57d6dc78/`。

浏览器首阶段与重启后阶段均通过：问数/追问、多指标、重新查询、取消、经营分析与流式阶段、历史和独立成果保存/读取、重启后续聊及再次登录空白均通过。PDF、PNG、XLSX 三种格式共七份文件（3 PDF、2 PNG、2 XLSX）由独立解析器验证通过。启动 readiness 为 0.007 秒，重启 readiness 为 4.075 秒；运行中直接探测 Control DB、业务 DB、Qdrant 和资产均为 ready，耗时 7.024 秒。就绪和临时账号清理证据见同目录 `readiness-*.json` 与 `cleanup.json`。

本次单用户运行样本记录六次成功问数，耗时中位数约 34.987 秒、最大 56.867 秒；另有保存成果重查 24.573 秒、经营分析 153.410 秒、取消操作 10.280 秒。一个 29.015 秒请求因验收中的重启恢复断言标为未确认，不计入成功样本。247 份约每 5 秒采集的资源样本中，API cgroup 自启动以来内存峰值为 1,404,436,480 bytes；Docker API 采样 CPU 最大 521.58%，采样内存最大约 1,279,900,254 bytes。该运行是当前机器上的单用户样本；Docker CPU 是区间采样，不能由此推导瞬时峰值、四任务并发容量或 p95 SLA。原始样本见 `r7-resource-samples.json`。

运行期间真实业务 Trace 已通过获准的 OTLP 配置发送；Exporter 成功不证明云端可查询，阿里云控制台尚未由用户确认。稳定服务仍为 R6 `2b4a8c8`，开发 PostgreSQL/Qdrant 未变；候选仅在独立 project、端口和数据卷中运行，外部资源快照前后一致。未执行 stable 切换或 Docker/主机重启。

## 依赖故障分类诊断（2026-10-09）

在专属运行 `20261009T125022Z-917566fb` 中，真实网页与后端 `/ready` 已观察到 control DB 故障（28.079 秒内）和业务 DB 故障（19.320 秒内），恢复后网页分别在 19.168 秒和 19.231 秒恢复。停止隔离 Qdrant 时，网页也显示服务不可用；但本机详细依赖断言未得到 `qdrant=not_ready`。临时账号最终禁用且 `active_sessions=0`，验收 project 容器/网络/卷已移除；stable R6 与开发 PostgreSQL/Qdrant仍运行。

源码定位为周期 `probe_dependencies()` 在单独 Qdrant 探测前调用完整 `verify_runtime()` 启动门禁；该门禁也访问 Qdrant，故异常落入 `assets=not_ready`，导致 `qdrant` 留为 `unknown`。已新增先红后绿的确定性回归，并从周期检查中移除这次重复完整门禁；R6 启动门禁保留，RAG manifest / provenance、数据库和 Qdrant 仍由各自检查验证。修改及定向回归通过，但修复候选尚未构建，所有依赖分类矩阵须在新 clean 候选上重跑，不能把这次未通过的 Qdrant 项记为PASS。

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

## 轮询诊断候选 Edge 复验（2026-10-09）

clean 候选 `8f73ab12e0b078ffca7c6416ab8ae7ea055522a9` 的固定镜像构建通过。隔离运行 `20261009T102635Z-456860d7` 的启动、RAG readiness、配置/兼容/失败保护及 Chromium sandbox 检查通过。Windows Edge `154.0.4258.62` 首条问数 HTTP 200，快照符合参考值，执行流为 `succeeded`，阶段覆盖问数理解、检索、SQL生成/校验/执行和结果保存；XLSX 导出通过。

同一对话追问后，浏览器测试等待终态执行详情超时（`TimeoutError`，位置 `container-real.spec.ts:319:33`）。新的安全轮询摘要总计记录 1 个执行详情 GET（HTTP 200，状态 `succeeded`，错误码列表为空），与首条查询的终态核验相符；没有记录追问提交请求数量，故现有证据不能判断追问是否已提交或为何未继续轮询。报告未包含追问 HTTP 终态、执行状态或错误码。经营分析、历史/成果及后续 PNG/PDF、重启续聊步骤均未运行；`ObservedModel.stream()` 修复仍未被业务分析路径验证。

临时账号已禁用、活动 Session 为 0；按本次 Compose project 标签复核，容器、网络、卷均为 0。稳定 R6 仍绑定 `2b4a8c8`，API/PostgreSQL healthy、Qdrant running，首页和 `/health` 均 HTTP 200。验收后本机默认 release 指针恢复为 `f1b98d7`。提交 `10a3a17` 已补充只记录执行提交请求计数、响应数、HTTP 状态及允许错误码的摘要，不记录执行 ID、请求/响应正文或业务数据；类型检查与Review通过。新的真实候选运行尚未执行。

## 尚未满足的 Ticket 07 验收项

- `6c3c639` 已完成当前候选 Linux Playwright 完整业务验收、12份导出解析、重启续聊、日志 Secret 检查及资源回收；同一候选四类依赖60秒故障/恢复矩阵通过。旧候选中未记录提交证据的追问超时仍按历史事实保留，不将旧运行重标。
- 当前候选的单用户完整运行资源采样与容量报告仍待完成；额度共用/释放逻辑已有11项软件回归通过，但不构成并发容量或 p95 SLA。
- 30 分钟 RTO / 条件 RPO 演练未开始：`.local/backup-keys/identity.txt` 私钥已按用户授权生成，权限为600；本机仍没有已登记密文备份。`./local backup` 在来源捕获阶段拒绝继续，因为 `.env.local` / `.env.local.secrets` 中的 `CHATBI_OBSERVABILITY_ENABLED`、`OTEL_SERVICE_NAME`、`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`、`OTEL_EXPORTER_OTLP_HEADERS` 与运行中 R6 API 的环境值不一致。没有创建密文、没有重启或修改 stable；需先决定如何协调保存配置与运行配置，再重试备份。
- 当前候选阿里云 Trace 尚未查询验证。隔离真实业务已使用用户给定的 OTLP 上报配置发送；本机没有阿里云 RAM 查询 AccessKey 或阿里云 CLI，本轮专用浏览器容器也没有控制台会话；`.local/r7-cloud-connection-probe.json` 记录 `cloud_query_verified=false`。阿里云[控制台文档](https://help.aliyun.com/zh/arms/application-monitoring/user-guide/trace-query)说明按 TraceId 查询需登录；[OpenAPI 文档](https://help.aliyun.com/zh/opentelemetry/developer-reference/api-xtrace-2019-08-08-overview)要求 AccessKey/RAM 身份，OTLP 上报 LicenseKey 本身不构成查询凭据。需要用户登录控制台人工核验，或提供最小只读查询凭据并安全存入本机环境。
- 本次未重跑正式 AI Evaluation；根据 Ticket/Spec 按实际 Diff 决定影响范围，Prompt、业务算法和模型资产未改时可复用原候选的适用行为基线，但不得冒称当前版本的新正式 Evaluation 基线。

## 顺序处理与浏览器条件核验（2026-10-09）

用户要求按顺序处理问题，继续授权既有 Contract 内的排查、修复和隔离验收。`59e1e34` 运行 `20261009T110752Z-b9e90d25` 的追问本轮成功、经营分析修复得到验证；PDF 下载在客户端受影响而失败。新安全提交诊断已实际运行：提交请求/响应均为 5，状态仅 202，公开错误码为空；终态详情 5 次，状态仅 succeeded / HTTP 200。临时账号已禁用、活动 Session 为 0，专属容器/网络/卷均清理；stable/dev 外部资源未被切换。

只读核验当前本机 IDM 运行且 PDF 接管启用。使用合成空白 PDF 做独立 Windows Chromium 对照，浏览器 `149.0.7827.55` 收到 HTTP 200 / 431 bytes，与服务器字节数一致；该探针没有模型调用、业务内容或真实凭据，也没有修改 IDM / 用户浏览器配置。它只证明隔离浏览器下载条件可用，不代替真实业务 PDF、完整文件解析或整条候选验收。日常 Edge 仍受 IDM 设置影响；既有 [Runbook](../runbook.md) 的本机下载条件继续适用。

## 软件验证

- `tests/scripts/test_local_acceptance.py`：10 passed。
- 额度与资源释放回归：11 passed，包括同步问数与后台任务共用额度、拒绝后释放额度、导出错误/授权变化清理临时资源。
- `npm run typecheck`：通过；`npm test -- --config=playwright.config.ts tests/helpers.spec.ts`：1 passed。
- 完整测试套件最近一次在前置候选 `82b366e` 上通过：941 passed、41 skipped、139 subtests。随后改动集中于验收挂载、浏览器终态等待与安全错误分类记录；本次未重跑完整套件。
- 本机 `python -m scripts.check_harness_state` 检查 22 份记录，无 ERROR；`chatbi-product-v1`、`local-operations-v1` 和 `r6-presubmit-coverage` 保留 REVIEW，需各自继续跟进。

结论：R7 Ticket 07 仍为 in-progress。当前候选只完成表中列出的部分证据，不能据此宣称 R7 全部验收通过或开始真实 stable 切换。未获本目标 Push/PR 授权。

## 隔离浏览器复验与就绪前置（2026-10-09）

clean candidate `7c12c1e9db3259ad0da92b530d9cb6bce8c02dd4`，运行 `20261009T112806Z-c99ef560`，使用独立 Windows Chromium 条件；首条执行提交 HTTP503 / `SERVICE_NOT_READY`，尚未进入持久执行，没有详情 GET，完整业务未通过。稍后真实依赖探针全部 ready（6.49秒）；证据不足以确定最初拒绝的具体依赖原因，也不能倒推之前的追问超时。临时账号与项目资源按原机制清理；资源清理报告确认专属卷移除。

验收脚本补充首次和重启后的 `/ready` 前置等待；就绪、未知、不就绪、状态码冲突与非法响应的确定性测试通过，但还需新 clean candidate 验证。`e1801a5` 阿里云固定 Header 支持完成，observability 22项与12 subtests PASS；真实配置仅保存到ignored环境文件，稳定运行未切换，云端可查询性仍待验收。

## a01545f 后续受理与探针诊断（2026-10-09）

clean候选 `a01545f224759e235b06f71e27f21cbcddbef828`，运行 `20261009T114810Z-5179539a`，启用显式云端配置与隔离WindowsChromium。首次 `/ready` HTTP200/status=ready；首问202受理、详情200/succeeded、XLSX接口200，追问提交503/SERVICE_NOT_READY，未进入执行；两条提交均获得响应。此次完整业务验收失败，不能以启动前就绪替代运行期间就绪。临时账号清理完成，专属容器/网络/卷复核均为0。

独立真实探针在稍后完成且四依赖均ready，耗时9.756秒；profiling探针11.342秒，其中导入9.371秒、源码编译4.012秒。源码确认 `src.query_api` eager import 加载整个HTTP应用，已补确定性Red并以保留公开入口的延迟导入修复；该证据确认导入开销问题，但尚未捕获最初503时具体探针的超时事件，不能将历史追问根因直接标已修复。资源采样与执行计时是本次隔离范围的安全补充，只有首问成功；采样值不代表瞬时资源峰值或完整容量PASS。

使用用户配置的独立合成OTLP连接探针返回SUCCESS，服务名chatbi，仅一个无业务内容Span；控制台可查询性仍待用户核验。连接探针不等同于真实业务完整链路验收。私有证据分别位于 `.local/r7-cloud-connection-probe.json`、`.local/r7-readiness-profile.json` 与本轮ignored目录。

## efb2f5e 业务与重启复验（2026-10-09）

clean候选 `efb2f5e7d630faad15bdd2a83f40cf8929d1449d`，run `20261009T120227Z-c19f7505`，独立 Windows Chromium，使用显式阿里云配置。浏览器两阶段均passed：首问/同对话追问/多指标/经营分析与流式、历史/成果/重新查询/取消/多标签及重启后的续聊/成果读回/再次登录空白均通过。七个导出文件由独立解析器验证，pdf/png/xlsx三种格式passed。专属API/PG/Qdrant手动停止并恢复，持久状态指纹一致、未完成执行恢复规则通过；重启ready等待3.026秒。直接真实探针7.564秒，四依赖ready。

本轮总流程仍退出1：最后的隔离检查使用R6的“两只读挂载”条件，拒绝了R7已批准的可写runtime目录。规则修复明确三个固定bind目录及各自权限；独立真实Docker元数据验证PASS，使用本轮同一API镜像，仅创建隔离容器、不启动业务服务。该补充不改写原失败退出或报告候选身份，也不代表整套验收已在后续HEAD上全量重跑。最终API日志Secret检查未由本轮脚本运行，不能标记PASS。

临时账号disabled=true、active sessions=0；专属资源按原机制清理。手工只读核验外部容器id/image/running与本轮external-before完全一致，原stable/dev未改。证据位于本机ignored运行目录及 `.local/r7-mount-guard-verification.json`；资源采样仍为补充，未标完整容量PASS。云端可查询性、60秒故障恢复角色矩阵与完整30分钟恢复矩阵仍未完成。
