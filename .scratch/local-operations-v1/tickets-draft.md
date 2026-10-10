# R7 本机运行保障 Ticket 草案

Status: 用户2026-10-08确认七项拆分与整体本地实施；Readiness READY（见 [报告](ticket-readiness.md)）。正式Ticket位于issues/。无Push/PR授权。
Canonical Source: [已确认Spec](spec.md)定义行为；[Design](design.md)定义机制；[Design Review PASS](design-review-2.md)为拆分前置证据。Baseline: `0c77d80`，stable历史runtime `2b4a8c8`。

## 整体范围与交付约束

一个目标、一个branch/worktree，按依赖连续实施；七项均属于同一运行闭环，不创建并行Agent或长期集成分支。正常查询/分析/历史/导出与Domain/SQL安全沿既有Contract；不新增多worker、公网部署、云监控平台、LLM定时探测或数据业务变更。

主要Owner统一为当前目标实施维护者（当前主Agent）；交付后随既有模块由项目维护者维护。数据恢复/权限风险由同一Owner负责检查与回退；超出Spec、陌生资源、未知凭据或所需真实环境授权缺失时升级给用户，不猜测。无需跨团队Backup Owner。

所有Ticket完成都要求受影响测试、独立只读Code Review、Diff/Secret检查、当前Ticket结果记录、适用正式文档和roadmap事实核对；候选证据注明commit或未提交范围、baseline、运行资源、覆盖和未运行项。可复用仍适用历史证据，不能重标候选身份。正式Ticket在用户确认后写入issues/，含Status/Result/Comments。

本地实施授权仅覆盖代码、工具镜像构建、确定性测试、临时且明确归属的隔离资源验证、本地Commit。保持当前实际stable与dev数据；不在真实stable自动升级、初始化密钥或恢复切换，不调整主机配置/重启、不Push/PR。密钥生成/故障注入/切换优先在专用隔离资源进行。真实Windows浏览器和阿里云验收使用现有授权范围/配置，不能取得证据时如实保留未完成项并请求必要条件。

## 依赖

| Ticket | 用户可见闭环 | Blocked by（直接） |
| --- | --- | --- |
| 01 | 动态就绪与受权限保护的运行状态 | 无 |
| 02 | 同步与后台共享执行保护 | 01 |
| 03 | 可校验的手工加密备份 | 01 |
| 04 | 定时备份、逾期提示与升级前门禁 | 03 |
| 05 | 隔离恢复、显式切换及回退 | 03 |
| 06 | 覆盖实际执行的安全诊断Trace | 02 |
| 07 | 完整恢复、业务与运行验收 | 04、05、06 |

01与03的依赖是安全状态投影入口，02依赖01的统一readiness门禁；04/05共享03的已登记副本及格式；06依赖02落定的真实执行生命周期。07依赖全部完整行为，经传递依赖涵盖01–03。无循环；同一目标串行推进，共享文件随当前Ticket修改，不覆盖后续/用户改动。

## 01 — 动态就绪、近期模型结果及安全状态入口

Change Profile: 持续维护 / API+bootstrap+前端+CLI的单一状态闭环 / 高风险（权限与就绪）/ Software+隔离依赖+浏览器 / 本地Commit。
Owner: 当前目标实施维护者。
Blocked by: 无。
What to build: 复用启动资产门禁，增加有界15秒周期探测、10秒周期上限、30秒过期规则与近期15分钟真实模型结果；/health保持兼容，/ready与operations/status按Design DTO；网页普通/管理员投影、./local status实时容器事实及安全状态。提供备份状态projection的受限读取边界，03再提供真实写方；缺证据显示未初始化/未知。
Acceptance Criteria:
- 依赖成功/故障/恢复/超时/资产变化/过期有确定性状态；运行且网页打开时故障和恢复60秒内显示；挂住探测不阻塞后续恢复，关停无无界worker。
- 定时检查不调用LLM；模型Adapter实际结果更新，过15分钟或重启unknown；后续SQL失败不改变模型结果。
- 未登录401；普通无details；管理员仅安全详情；Control身份核验失败不泄露；Cookie来源/expected-user/混用Bearer规则保持。
- 状态轮询不触碰last_seen、30分钟Idle/8小时Absolute、Cookie；禁用/撤销及时拒绝，HTTP/网络失败不显示旧正常。
owned files: src/query_api/app.py、browser.py和新增最小运行状态文件；src/bootstrap/readiness.py及装配；实际模型Adapter的结果观察；frontend/src/api.ts、App.tsx和最小状态组件；local/scripts本机状态读取；对应tests/query_api、tests/bootstrap、tests/scripts、frontend/tests。
验证证据: 注入clock/probe的状态矩阵；真实HTTP权限/TTL数据库读写断言；隔离PG/Qdrant故障计时；浏览器两种role与断网恢复；./local status读取不到证据用unknown。
Migration / Rollback: 无业务schema migration；缺新projection兼容显示未初始化；缺stable必要装配fail closed。新资产/状态格式version1；撤回代码仅能在兼容既有配置时回原候选，不改数据。
Done When: 上述证据、Review、Spec/API/Runbook/Design相关章节与状态提示说明完成；60秒真实证据若依赖最终整体验收，明确暂不宣称总目标完成。

## 02 — 跨同步与后台入口的就绪和共享额度

Change Profile: 持续维护 / 同一受理闭环 / 高风险（执行生命周期）/ Software+HTTP并发集成 / 本地Commit。
Owner: 当前目标实施维护者。
Blocked by: 01。
What to build: 在现有ExecutionRuntime内抽出共享owner/API容量lease，R4组合原history/analysis互斥，同步Query/Analysis接入相同计数且不伪造history；新受理应用readiness，已持久幂等重放优先读取原结果。业务1/4与导出1/2分别保护。
Acceptance Criteria:
- 同步/网页混合请求共享每账号1/API4，超过立即429 EXECUTION_LIMIT_REACHED，无排队/自动重试；新增SERVICE_NOT_READY映射503，成功DTO兼容。
- 同步不新增持久history/execution，不重复取analysis lease；取消/超时/断连时真实调用未结束仍占额度，finally完成才释放一次。
- 重放不重复计数，关闭不受理；授权失败/异常/存储受理失败无额度泄漏；原R4 epoch/stop/保存规则及R5限额保持。
owned files: src/query_api/execution_runtime.py、execution.py、app.py；src/online_query/contracts.py仅增加批准错误码；相关执行context装配；frontend错误提示及tests/query_api、tests/online_query、frontend/tests。
验证证据: 用真实阻塞worker/Event验证跨入口合计、断开等待但仍占用、drain与异常释放；HTTP状态码/原DTO/幂等/权限回归；分析与导出各自guard检查。
Migration / Rollback: 不改变持久execution schema或同步持久化行为；同一进程统一装配，无两套配额；撤回到兼容候选时沿原R4停机drain。
Done When: 受理、停止、失败矩阵及Review通过；R4/Query/API/运行保障Contract与Runbook更新，额度为保护上限而非四并发性能承诺。

## 03 — 固定工具镜像与可恢复的手工加密备份

Change Profile: 持续维护 / 手工备份完整闭环 / 高风险（Secret与数据）/ Software+真实PG/age隔离集成 / 本地Commit。
Owner: 当前目标实施维护者。
Blocked by: 01。
What to build: 固定age1.3.2/官方SHA-256与PG16客户端工具镜像；显式init-backup、backup、backup-list。保留所有Control状态与只读业务DB一致性快照、批准角色身份、固定发布/model/资产及必要敏感配置；tool内加密/完整解密校验，原子登记known catalog与安全状态。共享operation lock、最小权限、受限临时文件、固定成员/容量/超时边界。
Acceptance Criteria:
- 私钥/Secret从不进入Git、argv、日志、业务API或公开投影；重复init不覆盖key，文件/目录权限符合Design；API只能读安全public子目录。
- 正常业务写Control时dump和指纹同exported snapshot，业务只读身份前后核对；备份不中断业务，无跨库共享snapshot假承诺。
- 密文/manifest/dump损坏、磁盘不足、wrong key、锁冲突、工具超时/中断失败不登记、不删除旧副本，清除受限临时明文；解密/TOC/成员校验通过才发布。
- 登记只接受本机known id/hash/归属，拒绝任意路径/陌生archive；记录实际active版本，不把最新build代称当前运行。
owned files: local；scripts/local_*及最小backup工具；新增固定工具Dockerfile；docker-compose.local.yml仅工具/安全projection挂载；.gitignore/.env.example安全模板（如适用）；tests/scripts与隔离集成入口。
验证证据: age固定包摘要/镜像来源与PG版本记录；真实双库并发Control写入snapshot一致性；解密恢复前指纹/TOC；故障注入与权限/secret扫描；public投影原子替换可见。
Migration / Rollback: 新backup format1/catalog，不迁移原业务数据；现有R6缺keys显示未初始化。镜像/模板变化不自动初始化真实stable；停止工具不会影响原API，既有副本保留。
Done When: 可校验副本完整证据、Review与工具供应链核验；正式备份Contract、密钥保管/丢失/失败处理Runbook完成；真实空库恢复能力在05验证，当前不冒称已演练。

## 04 — 自动备份、保留期和升级失败保护

Change Profile: 持续维护 / 定时与升级两个触发的同一备份政策 / 高风险（升级数据安全）/ Software+容器生命周期集成 / 本地Commit。
Owner: 当前目标实施维护者。
Blocked by: 03。
What to build: stable独立工具服务随up/down启停，运行期间每6小时备份，超过24小时/无副本启动立即补备份；7天保留与失败/逾期提醒；升级在旧API停止前备份旧active，失败拒绝升级。
Acceptance Criteria:
- 不持Docker socket、不自动重启API；电脑/Docker停止不虚报已执行；调度失败有界重试、无热循环；锁冲突不与恢复/升级并行写。
- 最近成功时间/安全失败原因可见；超过24小时持续警告，不假承诺RPO；管理员显示详细状态，普通无备份细节。
- 只有新副本校验并登记成功才清理已知过期副本；失败保留旧副本和服务；不清理陌生文件/密钥/回退卷。
- 升级备份读取旧active release/binding，目标镜像已构建也不改变源版本；备份失败原API继续可用，成功后仍执行R6兼容门禁。
owned files: local、scripts/local_*、docker-compose.local.yml与backup scheduler；01安全状态投影展示；tests/scripts、容器隔离验收。
验证证据: clock驱动6h/24h/7d边界和重试；服务up/down、锁竞争；两真实发布版本升级前失败/成功与旧数据指纹；过期提醒权限及API不停服。
Migration / Rollback: 无DB migration；增量工具服务restart:no；升级故障在停止旧服务前退出。停止调度保留keys/catalog/已有副本并显示不再有新成功证据。
Done When: 全部时序与升级保护证据、Review、Runbook备份与升级步骤及roadmap事实核对完成。

## 05 — 隔离恢复与可回退的显式切换

Change Profile: 持续维护 / 恢复并可安全激活的完整闭环 / 高风险（数据/权限/单写者）/ Software+真实隔离资源故障集成 / 本地Commit。
Owner: 当前目标实施维护者。
Blocked by: 03。
What to build: 本地binding兼容原固定资源；所有local操作统一解析资源归属；restore只建隔离环境；核验数据/角色/资产与登录成果；restore-activate与restore-recover按Design journal逐步切换，保留原卷/config/RAG。
Acceptance Criteria:
- 损坏/wrong key/版本不兼容/陌生归属拒绝；仅空专属卷恢复，原stable/dev数据不变；批准roles/grants恢复，无任意陌生owner/超级用户。
- 全量原指纹先验证，再撤销旧Session/epoch处理未完成执行；重新登录、已完成历史/成果可读；checkpoint原到期不延长，未完成不自动重跑。
- 固定model与业务来源重建Qdrant/RAG；完整readiness通过才candidate verified；未verified不能activate。
- 切换停止所有旧/候选writer，单PG卷仅一个PG容器附着；原子binding与journal可追溯；各阶段中断显示未完成，显式选择previous/candidate恢复，不删除/覆盖原卷或反向迁移。
- up/down/status/upgrade/rollback/backup都识别新binding；缺文件使用原R6资源，未知卷/路径拒绝；7天清理不触及原环境。
owned files: local、scripts/local_*、docker-compose.local.yml资源binding；既有bootstrap/control/init接口；tests/scripts及隔离restore验收。仅需要接入既有epoch/授权，不改Domain或业务schema。
验证证据: 真实已加密副本到空PG/Qdrant；全表指纹与权限/session/历史/checkpoint；隔离stable clone进行逐阶段故障、单写者、激活/previous回退及所有local命令兼容；原stable/dev资源前后核对。
Migration / Rollback: binding格式version1、缺失兼容旧资源；journal保留previous/candidate；操作者显式recover选择；真实stable切换需该次授权，不作为代码实施的隐含动作。
Done When: 恢复/切换/中断矩阵及Review通过；正式资源/恢复Design、Runbook和Acceptance入口完成；30分钟目标及全链路实测由07汇总，不删除原环境。

## 06 — 真实执行生命周期与阿里云Trace安全接入

Change Profile: 持续维护 / 各入口的同一诊断闭环 / 高风险（内容泄露、fail open）/ Software+OTel集成+实际云验收 / 本地Commit。
Owner: 当前目标实施维护者。
Blocked by: 02。
What to build: 复用TraceRecorder/OTLP，HTTP受理与实际worker独立scope安全关联，覆盖问数追问、分析、XLSX/PNG/PDF及同步Query；stable受限配置白名单与有界batch exporter；仅阶段/耗时/安全分类，内容采集硬关闭。
Acceptance Criteria:
- HTTP结束不结束后台真实业务span；禁止跨线程复用已关闭root，关联使用批准carrier/Link/ID；导出worker实际步骤及回收有真实证据。
- 不采集问题/SQL/结果/Secret/raw exception；身份/请求属性受白名单保护；稳定配置不继承dev端点/headers。
- 云断连/队列满/超时不阻断业务、不耗无界内存；停机有界，错误只安全分类；状态探测不产生LLM或高频业务trace噪声。
- 本机诊断仍可用；实际用户配置的阿里云可查询当前候选trace才能记cloud PASS，缺凭据/运行授权或出口条件写未验收，不以历史证据替代。
owned files: src/observability/{tracing,contracts,config,tracing_export,tracing_safety}.py；src/query_api执行/导出入口与实际worker；bootstrap装配；local/compose受限配置；tests/observability、tests/query_api和受影响业务Trace测试。
验证证据: in-memory exporter span生命周期/安全属性/故障注入；实际OTLP有界行为；各入口当前候选trace ID/安全截图证据（脱敏）；云不可用仍完成业务。
Migration / Rollback: OTel SDK在Infrastructure Adapter；保留既有TraceRecorder正常接口；开关仅控制输出，业务就绪不依赖云；新增稳定配置白名单可关闭云输出且不影响本地状态。
Done When: Trace软件/集成证据与Review完成；Observability/Runbook白名单与fail-open说明更新；真实云结果归07最终报告，缺证据不得宣称目标完成。

## 07 — 当前候选完整业务、恢复与容量验收

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
