# 07 — 当前候选完整业务、恢复与容量验收

Status: in-progress
Authorization: 用户2026-10-08确认七项拆分与全部本地实施、验证、Review和Commit；用户后续授权stable备份密钥、首份加密备份及隔离恢复；用户于2026-10-10明确确认active Stable由R6切到已验收候选6d764ac、验证备份调度/RPO并在失败时回退原R6；无restore-activate、Push/PR或云部署授权。
Canonical Source: [Spec](../spec.md)、[Design](../design.md)；共同约束见 [已确认拆分](../tickets-draft.md)。

## 2026-10-10 最新候选验收与剩余条件

clean candidate `6d764aca6428bd225afe30395723dfaeb4ae0e0b` 由 `./local build` 构建，隔离运行 `20261009T170425Z-444d837d` 完整通过。Linux Chromium 153 两阶段问数/追问/分析/历史/成果/重启续聊成功，12份 PDF/PNG/XLSX 独立解析通过；账号已禁用、`active_sessions=0`、外部 Docker 资源未变、专属卷已清理、最终日志 Secret 检查通过。导出耗时为 XLSX `0.718–0.848s`、PNG `2.329–5.977s`、PDF `2.298–3.753s`。10项问数/分析耗时、API/PostgreSQL/Qdrant资源样本已归档到 `reports/browser-real-artifacts/r6-local-deployment/6d764aca6428-20261009T170425Z-444d837d/`；完整数据见[正式验收](../../../docs/acceptance/local-operations-v1.md#6d764ac-当前-clean-候选完整验收与单用户基线2026-10-10)。

`6d764ac`相对依赖矩阵候选`6c3c639`仅更改 E2E 报告耗时字段和Review记录，`src/`、`frontend/src/`及镜像定义未变；依赖矩阵按既有证据重用并保留其原候选身份，不冒称由`6d764ac`重新注入。采样不构成多用户容量或SLA。

新发现的跨浏览器文件名问题：该次 Linux Chromium 对12次下载均建议名称`download`，独立原生Chrome CDP探针也实际保存中文Blob下载为`download`；文件内容与格式均正确。当前导出源码与此前 Windows Chromium 验收的 `0a97182` 相同，旧报告中的`suggested_filename`为预期中文名。未在本次R7授权内改变R5下载 Contract/产品代码。通用入口的 `runtime.json` 写有 `browser_channel=msedge`，但实际使用Linux Chromium executable，须以 `browser.json` 的153.0.8010.12版本和本机适配器命令为准。

后续Stable验收（2026-10-10）：用户授权后`./local upgrade 6d764aca6428bd225afe30395723dfaeb4ae0e0b`成功，部署状态running/succeeded。升级前R6备份`9d01c195caeb4b71ad5cdb7ca726bfae`及升级后R7手工备份`ce589d79d5a643c48af315756a72ff22`均登记。Stable `/`、`/health`、`/ready`为200，依赖ready，自动备份进程运行，状态known且未逾期。23项调度/升级前门禁/逾期状态测试通过；真实下一次6小时自动备份尚待周期观察，未人为改写Stable状态来模拟24小时过期。阿里云Span已从隔离真实业务发送但`.local/r7-cloud-connection-probe.json`仍为`cloud_query_verified=false`，需要控制台只读核验。


## 2026-10-10 Active Stable R7切换

候选`6d764aca6428bd225afe30395723dfaeb4ae0e0b`通过兼容只读预检后执行`./local upgrade`。升级前R6副本`9d01c195caeb4b71ad5cdb7ca726bfae`成功；migration与迁移后兼容检查通过，Stable API切到R7且healthy，PostgreSQL/Qdrant保持运行。切换后创建R7来源副本`ce589d79d5a643c48af315756a72ff22`。`./local status`显示依赖ready、backup known/not-overdue；独立调度容器进程运行，安全日志无失败。23项定向调度/逾期状态测试通过。六小时调度真实周期尚未到达，活动Stable上的24小时逾期状态未人为触发，因此长周期RPO仍待后续观察。

完整验收记录见[正式Acceptance](../../../docs/acceptance/local-operations-v1.md#active-stable-r7切换与备份观察2026-10-10)。

## 2026-10-09 顺序处理授权与当前修复

用户明确要求“开始以一个一个处理问题”，继续授权在既有 Contract 内顺序排查、修复、隔离真实模型 / 浏览器验收、Review 和本地 Commit；随后明确当前验收使用 WSL/Linux 专用 Playwright 浏览器，不启动 Windows 浏览器或 IDM。该平台决定覆盖本轮浏览器验收方式，不代表 Windows 浏览器集成通过；不包含实际 stable 切换、密钥初始化或本目标远端发布。此前单次复测已执行完毕的记录是历史范围，不再作为本轮本地验证的等待条件。

当前短 Spec：服务在持久受理前以 HTTP 503 / `SERVICE_NOT_READY` 明确拒绝时，网页应显示安全拒绝原因，保留原成功结果与上下文，恢复后允许用户明确再次提交；不得误报为提交响应丢失。普通未知 5xx / 网络断连仍按既有 R4 受理恢复与幂等 Contract 处理，不自动重发。覆盖问数、经营分析和重新查询的确定性浏览器回归；修复不改变权限、公共 API、业务语义或模型 Prompt。

浏览器验收方式决定（2026-10-09，用户明确要求）：本轮使用项目现有 `chatbi-browser-dev:local` Linux Playwright 容器，记录实际 Chromium 版本；不启动 Windows 浏览器或 IDM，不修改 IDM、用户浏览器设置或系统安装。下载预检通过后再以 clean candidate 验证真实 PDF / 历史 / 成果 / 重启续聊及独立文件解析。该证据覆盖 Linux Chromium 浏览器行为，不宣称 Windows Edge 特有集成通过。当前仓库验收入口仍以 Windows 为默认，因此本次通过本机 ignored 适配器运行既有验收用例。


阿里云接入短 Spec（2026-10-09 用户明确确认）：本地 `.env.local` 保存地址、服务名和开关，`.env.local.secrets` 保存认证 Header，均保持 600 权限；白名单在既有 Authorization/Authentication 基础上增加三个固定阿里云名称，总数上限五项，保留长度、控制字符、重复名称及不回显保护。内容采集仍关闭；不自动重启实际 stable。通过合成配置与 exporter 回归后再进行隔离云端验收，不能将配置保存或软件测试通过称为云端已可观测。

验收前置短 Spec：首条及重启后的真实业务提交前，对专属回环 `/ready` 等待最多60秒，只有 HTTP200/status=ready 可继续，超时安全记录并停止；不重定义 `/health` 或放宽业务断言。显式 `CHATBI_ACCEPTANCE_TRACE_ENABLED=1` 才读取权限600的专用配置/认证 Header，临时环境仍生成独立数据库/管理员/索引凭据并关闭内容采集；默认不导出，清除宿主 OTEL 变量。配置保存与 exporter 配置验证不代表云端可查询。

就绪性能修复短 Spec：已确认当前探针因 package eager import 连带加载 HTTP 应用；保留 QueryService/create_app 的公开身份，只有访问公开入口时才加载 app，使轻量状态模块可单独导入，不更改10秒探针上限与30秒过期规则。恢复固定配置白名单同步支持已批准的 OTEL_SERVICE_NAME 和关闭内容采集配置，其他未知字段仍拒绝。分别覆盖新进程导入边界、公开入口兼容、恢复配置与既有 API/运行回归。

验收隔离与配置比较修复短 Spec：按已确认R7挂载Contract，验收仅接受两个只读模型/RAG目录和一个可写专属runtime目录的bind挂载，继续拒绝迁移账号、额外挂载及资产写入。备份来源按受支持的单/双引号环境值语义比较实际容器配置，保留原始加密输入字节，不执行shell展开，真实配置漂移仍拒绝。只修验收/运行适配，不重跑未变化的模型算法或将旧候选报告重标新HEAD。

Change Profile: 本目标发布验收并持续保留证据 / 同一目标最终验证 / 高风险（数据和运行结论）/ Software回归+真实浏览器+运行/安全验收 / 本地Commit，发布另行授权。
Owner: 当前目标实施维护者。
Blocked by: 04、05、06。
What to build: 复用适用测试建立clean candidate、专属运行资源与用户指定的Linux Playwright真实浏览器证据；汇总60秒故障/恢复、30分钟恢复、24小时条件RPO/失败提醒、共享预算、单用户性能和阿里云trace；固化正式事实源，不以状态记录或CI代替验收。
Acceptance Criteria:
- clean image绑定候选commit/image/config/Seed/model；管理员/普通账号问数、追问、分析、历史/成果和三格式导出成功；状态无保活且隔离正常。
- 备份与私钥/镜像/固定model缓存已具备时，从恢复开始到DB恢复/index重建/登录历史成果核验不超过30分钟；下载单列，外部LLM不混算。条件不满足或超时记录失败，不重新定义目标。
- 单用户代表用例逐次耗时和CPU/内存峰值；跨入口超额立即拒绝、180s/1200s/60s保护及取消/失败释放可再次执行；不冒称四并发容量或p95 SLA。
- 两种role依赖故障/恢复60秒证据、云真实span与云失败业务成功、备份损坏/权限/归属/中断恢复安全证据齐全；真实stable/dev数据未被验收覆盖。
owned files: scripts/local_acceptance.py及最小R7验收入口；受影响软件/浏览器验收文件；docs/specs、docs/designs、docs/acceptance、docs/runbook.md、docs/roadmap.md、docs/product-scope.md与Architecture适用章节；.scratch/local-operations-v1记录。
验证证据: 精确命令/候选/资源/配置身份与结果，受影响required checks；用户指定的Linux Playwright浏览器、真实模型业务/Trace及隔离恢复计时；Secret扫描；未运行项及限制明确，不宣称未运行的Windows浏览器集成通过。Prompt/业务算法不变可复用适用AI Evaluation，不重标报告；改变相关行为则重跑受影响Evaluation。
Migration / Rollback: 不执行真实stable数据激活、整机/Docker重启或永久IDM变更；隔离资源按明确标签清理且先留证据。发布前报告当前范围/风险/验证/自动合并规则再取得Push/PR授权。
Done When: 01–06适用证据均可追溯，完整Review和文档链接检查通过；全部Done When满足或必要条件明确待补，未完成项不报告全目标完成；只完成本地candidate，不自动远端发布。

## 前一候选完整验收（2026-10-09）

clean候选`0a97182e6840ed5ae1e3fd0da012dfe98fb4d1b3`绑定隔离运行`20261009T122448Z-57d6dc78`；专属Docker project为`chatbi-r6-accept-20261009t122448z-57d6dc78`。仓库原始`./local build`成功，Windows Chromium `149.0.7827.55`完整两阶段业务通过：问数、追问、多指标、重新查询、取消、经营分析/流式阶段、历史与成果保存/读取、重启后续聊及再次登录空白均通过。PDF、PNG、XLSX共七份文件由独立解析器验证通过。`scripts.verify_local_deployment`完整验收流程通过最终API日志Secret检查、专属账号/Session清理及外部资源前后核对；临时账号已禁用、active_sessions=0、专属容器/网络/卷清理。release指针已恢复；stable仍为R6 `2b4a8c8`，开发数据库/Qdrant未改动。安全摘要及详细本机证据见[Acceptance](../../../docs/acceptance/local-operations-v1.md#前一候选-0a97182-完整隔离验收2026-10-09)。

前一候选单用户耗时和资源采样已记录。当前代码候选的11项额度/释放回归通过，包含后台占额时同步问数被429拒绝、释放后重试成功；这验证额度逻辑，不替代候选级资源采样或并发容量结论。后续`6c3c639`完整依赖故障/恢复矩阵已通过，具体结果见下节。OTLP真实业务Trace已发送，但云端控制台查询仍待核实。

## `6c3c639` 前一候选 WSL/Linux Playwright 与依赖验收（2026-10-09）

clean候选`6c3c639af9b9d9d70829b00a4356adec95b13212`的完整隔离浏览器验收运行`20261009T144447Z-abed4621`通过，浏览器为`chatbi-browser-dev:local`内 Chromium `153.0.8010.12`。通过范围包括真实问数/追问、经营分析流式、历史与成果、重启恢复及 PDF/PNG/XLSX 共12份文件的独立解析。浏览器下载预检和验收业务均在Linux专用Playwright容器完成；没有启动Windows浏览器、没有拉起IDM，也未修改用户本机配置。安全摘要与平台限制见[正式验收报告](../../../docs/acceptance/local-operations-v1.md#6c3c639-依赖故障矩阵与历史-linux-playwright-验收2026-10-09)。

同一候选的四依赖故障矩阵运行`20261009T132359Z-825fdfde`通过：Control DB、业务 DB、Qdrant、业务资产故障与恢复均在60秒内反映，最长阶段29.588秒；Secret scan通过且外部Docker资源未变。当时未完成项包括单用户完整运行资源采样、条件RPO（active stable仍为R6，R7备份调度和24小时提醒未启用）及阿里云控制台Trace可查询性。单用户采样已由`6d764ac`补齐；条件RPO与云端查询仍待完成。用户授权的R6 API维护重启后，首份加密备份与隔离恢复已成功；84秒满足条件RTO。Ticket 07仍为in-progress，不表示可切换实际stable或开始远端发布。

用户随后明确授权初始化实际stable备份密钥、创建首份加密备份并执行隔离恢复。`./local init-backup`成功，私钥权限600、密钥目录700；第一次`./local backup`因保存的4项OTLP配置与运行R6容器环境不一致而安全拒绝，没有创建密文或catalog。之后用户确认一次维护重启，仅重建active R6 API以加载已保存配置；R6镜像、PG/Qdrant容器、RAG挂载和R7最新release指针未变，API健康检查200。首份R6密文`2e1a0cc185ac467a8f91e2adc2ca783f`登记成功；隔离恢复`0b4e8f4c3b7f62c71261f7f57703cfda`完成数据库/RAG/readiness/登录/历史核验，84秒，候选停止且恢复卷保留，未执行激活。详细证据见[正式验收](../../../docs/acceptance/local-operations-v1.md#实际-stable-r6-加密备份与隔离恢复2026-10-09)。

## 历史结果：`59e1e34` 的 PDF 客户端条件（2026-10-09）

该历史clean候选`59e1e34`于`20261009T110752Z-b9e90d25`通过Windows Edge首问/追问、多指标、PNG/XLSX和经营分析（流式报告/归因/持久保存）；旧追问超时根因当时仍未知。PDF API 200而Edge 204，当前IDM运行且接管PDF，流程当时停止，历史/成果/重启未运行。临时账号禁用、active sessions=0、专属容器/网络/卷均清理。原始`./local build`入口构建通过（复用依赖缓存，无临时包装）；stable/dev未切换。源码另确认SERVICE_NOT_READY / HTTP503被前端误报未知，三个新回归先红，修复后Windows Edge受影响18项回归通过（含未知503回查与原有网络丢失幂等行为），build/typecheck/diff通过；当时Code Review PASS。真实模型Prompt/业务算法/模型资产未改，不重跑全量正式Evaluation，不重标历史基线。

## 历史验收与诊断

原Result: clean candidate `f1b98d73c72b572a37d7b6a3ff5dd19da9d46b3b`（`git_dirty=false`）于 `20261008T172902Z-2f1178cf` 和 `20261009T090758Z-b87ca1ff` 两次隔离验收。两次均通过隔离启动、数据库/RAG readiness、五类预期失败保护、Chromium sandbox、Windows Edge问数/追问及PNG/XLSX导出；两次经营分析均到达真实终态`failed`，公开分类为`LLM_ERROR`。获准的隔离诊断复测`20261009T093333Z-179e5fee`捕获内部分类`PROVIDER_STREAM_UNAVAILABLE`；源码定位到 R7 `ObservedModel` 未代理底层模型的`stream()`，导致摘要流在Provider请求前失败。修复提交`515c253`并构建绑定该提交的固定镜像。Edge复验`20261009T095740Z-a125115e`通过隔离启动/RAG/失败保护/sandbox，但首条问数未获得成功快照，HTTP终态查询为200，E2E报告未保留执行对象中的安全错误码；验收在分析前停止，不能据此判断Provider或应用根因。clean候选`2d907c03ee0b5eab353fb3478b6883793c823048`运行`20261009T101046Z-94af86a8`与`8f73ab12e0b078ffca7c6416ab8ae7ea055522a9`运行`20261009T102635Z-456860d7`均通过启动/RAG/失败保护/sandbox及Edge首条问数/SSE/XLSX；两次追问均未观察到终态并超时，分析未运行。`8f73ab1`安全轮询摘要只记录到一个执行详情GET（首问HTTP 200、状态`succeeded`、无错误码），没有记录追问提交计数或状态，故根因未确定。临时账号已禁用、active sessions为0，按project标签核查容器/网络/卷均为0；稳定R6服务未纳入验收，仍healthy；本机默认release指针恢复到`f1b98d7`。提交`10a3a17`已为E2E补充追问提交请求计数、响应数、HTTP状态和允许错误码摘要，仅保留安全元数据；类型检查及Review通过，新增字段尚未由真实候选复验。下一次真实模型/Edge候选运行需另行确认。PDF、当前候选容量/完整恢复矩阵、阿里云Trace仍待验。正式报告见[Acceptance](../../../docs/acceptance/local-operations-v1.md)，无Push/PR或实际R7升级、密钥初始化、恢复激活。
Comments: 之前 `bbe2cce` 验收同样在分析阶段失败但未记录安全错误分类；首次新clean candidate已将状态/公开`error_code`写入安全报告，不记录原始异常或业务内容。同一clean候选复跑再次得到`LLM_ERROR`，安全浏览器报告不提供provider内部原因。用户确认后，单次合成JSON Provider stream probe成功并得到可解析响应；报告只保存安全分类，不保存提示词、响应正文、模型名、端点或密钥。该结果只证明探针时刻最小流式调用可用，不覆盖业务分析运行时装配。获准的隔离诊断复测只保存状态、公开码、固定内部分类及HTTP状态；本机ignored证据`.local/acceptance/diagnostic-probes/20261009T093333Z-analysis-internal-reason.json`不含提示词、响应或异常文本。源码确认`src/bootstrap/runtime.py`用`ObservedModel`包装分析模型，而该包装器此前只提供`invoke()`，隐藏了`ChatOpenAI.stream()`；因此分析摘要请求未发送到Provider。`ObservedModel.stream()`修复提交`515c253`，相关Python回归先红后绿，`tests/bootstrap/test_operations.py`10 passed，模块回归104 passed。`2d907c0`与`8f73ab1` Edge首问及SSE成功、XLSX通过，追问均未观察到终态并超时。`8f73ab1`仅保存一条首问执行详情GET的HTTP/状态摘要，没有追问提交请求计数；提交`10a3a17`已增加提交请求计数、响应数、HTTP状态和允许错误码摘要；该字段尚未由新的候选验收验证。再次真实候选运行需要新确认。隔离资源前后均未触及稳定R6；公开API/SSE Contract未改。完整测试套件最近在前置候选`82b366e`上941 passed、41 skipped、139 subtests，后续未重跑全套。实际阿里云Trace仍未验证，stable配置OTLP关闭。
