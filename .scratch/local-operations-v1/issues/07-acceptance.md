# 07 — 当前候选完整业务、恢复与容量验收

Status: in-progress
Authorization: 用户2026-10-08确认七项拆分与全部本地实施、验证、Review和Commit；无Push/PR或实际stable切换授权。
Canonical Source: [Spec](../spec.md)、[Design](../design.md)；共同约束见 [已确认拆分](../tickets-draft.md)。


Change Profile: 本目标发布验收并持续保留证据 / 同一目标最终验证 / 高风险（数据和运行结论）/ Software回归+真实浏览器+运行/安全验收 / 本地Commit，发布另行授权。
Owner: 当前目标实施维护者。
Blocked by: 04、05、06。
What to build: 复用适用测试建立clean candidate、专属运行资源与真实Windows入口证据；汇总60秒故障/恢复、30分钟恢复、24小时条件RPO/失败提醒、共享预算、单用户性能和阿里云trace；固化正式事实源，不以状态记录或CI代替验收。
Acceptance Criteria:
- clean image绑定候选commit/image/config/Seed/model；管理员/普通账号问数、追问、分析、历史/成果和三格式导出成功；状态无保活且隔离正常。
- 备份与私钥/镜像/固定model缓存已具备时，从恢复开始到DB恢复/index重建/登录历史成果核验不超过30分钟；下载单列，外部LLM不混算。条件不满足或超时记录失败，不重新定义目标。
- 单用户代表用例逐次耗时和CPU/内存峰值；跨入口超额立即拒绝、180s/1200s/60s保护及取消/失败释放可再次执行；不冒称四并发容量或p95 SLA。
- 两种role依赖故障/恢复60秒证据、云真实span与云失败业务成功、备份损坏/权限/归属/中断恢复安全证据齐全；真实stable/dev数据未被验收覆盖。
owned files: scripts/local_acceptance.py及最小R7验收入口；受影响软件/浏览器验收文件；docs/specs、docs/designs、docs/acceptance、docs/runbook.md、docs/roadmap.md、docs/product-scope.md与Architecture适用章节；.scratch/local-operations-v1记录。
验证证据: 精确命令/候选/资源/配置身份与结果，受影响required checks；Windows实际浏览器、真实模型业务/Trace及隔离恢复计时；Secret扫描；未运行项及限制明确。Prompt/业务算法不变可复用适用AI Evaluation，不重标报告；改变相关行为则重跑受影响Evaluation。
Migration / Rollback: 不执行真实stable数据激活、整机/Docker重启或永久IDM变更；隔离资源按明确标签清理且先留证据。发布前报告当前范围/风险/验证/自动合并规则再取得Push/PR授权。
Done When: 01–06适用证据均可追溯，完整Review和文档链接检查通过；全部Done When满足或必要条件明确待补，未完成项不报告全目标完成；只完成本地candidate，不自动远端发布。

Result: clean candidate `f1b98d73c72b572a37d7b6a3ff5dd19da9d46b3b`（`git_dirty=false`）于 `20261008T172902Z-2f1178cf` 和 `20261009T090758Z-b87ca1ff` 两次隔离验收。两次均通过隔离启动、数据库/RAG readiness、五类预期失败保护、Chromium sandbox、Windows Edge问数/追问及PNG/XLSX导出；两次经营分析均到达真实终态`failed`，公开分类为`LLM_ERROR`。获准的隔离诊断复测`20261009T093333Z-179e5fee`捕获内部分类`PROVIDER_STREAM_UNAVAILABLE`；源码定位到 R7 `ObservedModel` 未代理底层模型的`stream()`，导致摘要流在Provider请求前失败。当前工作区已修复转发并新增确定性回归，尚未构建clean candidate及重跑真实模型/Edge验收；PDF步骤未运行。最新验收容器/网络/卷均为0，临时账号已禁用且active sessions为0。稳定R6服务曾在两次验收之间停止，之后已用原`2b4a8c8`发布恢复；当前API/PostgreSQL healthy、Qdrant running，原因未确认。当前候选验收不完整，正式报告见[Acceptance](../../../docs/acceptance/local-operations-v1.md)。阿里云Trace、当前候选容量与完整恢复/RTO矩阵均未验收；无Push/PR或实际R7升级、密钥初始化、恢复激活。
Comments: 之前 `bbe2cce` 验收同样在分析阶段失败但未记录安全错误分类；首次新clean candidate已将状态/公开`error_code`写入安全报告，不记录原始异常或业务内容。同一clean候选复跑再次得到`LLM_ERROR`，安全浏览器报告不提供provider内部原因。用户确认后，单次合成JSON Provider stream probe成功并得到可解析响应；报告只保存安全分类，不保存提示词、响应正文、模型名、端点或密钥。该结果只证明探针时刻最小流式调用可用，不覆盖业务分析运行时装配。获准的隔离诊断复测只保存状态、公开码、固定内部分类及HTTP状态；本机ignored证据`.local/acceptance/diagnostic-probes/20261009T093333Z-analysis-internal-reason.json`不含提示词、响应或异常文本。源码确认`src/bootstrap/runtime.py`用`ObservedModel`包装分析模型，而该包装器此前只提供`invoke()`，隐藏了`ChatOpenAI.stream()`；因此分析摘要请求未发送到Provider。工作区已补`stream()`转发与结果观察；核心流转发回归先红后绿，`tests/bootstrap/test_operations.py`10 passed。该修复仍须进入新clean candidate并完成真实业务复验。隔离重放的容器/网络/卷均清零、活动Session为0。本目标代码变更不改公开API/SSE Contract；完整测试套件最近在前置候选`82b366e`上941 passed、41 skipped、139 subtests，后续未重跑全套。Ticket 06本地实现与OTLP集成Review已完成，实际阿里云Trace仍未验证，stable配置OTLP关闭。
