# R7 长期规划记录

当前：01–06本地实现/Review完成；07仍in-progress。clean候选`6c3c639`的四依赖故障/恢复矩阵运行`20261009T132359Z-825fdfde`通过；完整两阶段浏览器验收运行`20261009T144447Z-abed4621`使用`chatbi-browser-dev:local`中的Linux Chromium `153.0.8010.12`通过，PDF/PNG/XLSX共12份导出独立解析，经营分析、重启续聊、日志Secret扫描、账号禁用与临时资源清理通过。没有启动Windows浏览器/IDM。首个WSL尝试的临时API Origin与浏览器内部访问地址不匹配，登录请求被拒且未进入业务；对齐本次隔离Origin后完整验收通过。11项额度拒绝/释放回归通过（后台占额时同步问数返回429，释放后可重试），当前候选单用户完整资源采样仍待补。用户已授权并初始化实际stable备份私钥（权限600）；首份`./local backup`在来源捕获阶段因保存的4项OTLP配置与运行R6容器环境不一致而安全拒绝，未创建密文或catalog。stable仍为R6 `2b4a8c8`且健康，未重启/切换；需用户决定是否通过一次受支持的stable重启应用当前保存配置后再备份。阿里云控制台Trace仍待查询，本机只有OTLP上报配置，没有RAM查询凭据或专用浏览器Console会话。用户授权既有Contract内顺序修复、隔离复验、Review与本地Commit。无本目标Push/PR或恢复激活授权。历史过程保留于下文，实时阶段见Git公共目录记录。

## 初始规划快照（拆分确认前）

2026-10-08：用户已整体确认 [Spec](spec.md)。首轮Design Review NEED FIX后在既有Contract内补齐 [Design](design.md)，[复审PASS](design-review-2.md)。[七项Ticket草案](tickets-draft.md)经当前主Agent [Readiness READY](ticket-readiness.md)，待确认拆分与完整本地实施范围。

尚无工程实现、Commit或本目标Push/PR授权；当前只是规划文档。Baseline `0c77d80`，Stable历史runtime `2b4a8c8`。真实stable升级/密钥初始化/恢复切换不隐含在本地实施授权内。

正式Ticket确认后按01–07依赖连续推进。新验收由候选建立，既有R6/Evaluation/云接入报告不重标。roadmap仅更新确认及准备事实，不重排优先级。

实时阶段/授权/阻碍/下一步以Git common-dir的harness/work-items/local-operations-v1/status.md为准；产品总目标引用该子工作项。

2026-10-08：用户确认七项拆分和全部本地实施、验证与Commit；正式issues/已生成，按依赖连续推进。无Push/PR或实际stable资源切换授权。

Ticket 01本地实现、软件及Windows Edge确定性入口验证/Review PASS；probe在原stable资源只读核验PASS（4.624秒）。完整clean候选运行验收留07，未发布或修改stable。开始02共享受理保护。

Ticket 02共享受理保护已完成本地实现与Review，205+14subtests、追加37/14、WindowsEdge12项PASS；2项依赖真实renderer条件SKIP，07完整验证补齐。开始03手工加密备份。

Ticket 03手工备份本地实现/Review PASS；固定age工具、真实PG并发snapshot到空库恢复指纹、wrongkey/损坏/unknownrole/明文清理PASS，24新增与87相关回归PASS；原stable仅只读来源核验，未初始化真实key或备份。继续04自动调度/升级前保护。

Ticket04本地实现/Review PASS：6h/24h/7d、失败冷却/锁/已知清理/升级保护软件验证，真实PG/age scheduler产物与0.016s停止、WindowsEdge14项PASS。来源处理已回归Spec宿主无新依赖，原R6仅只读核验，未修改实际服务/key/data。跨版本完整矩阵留07。继续05隔离恢复与显式资源切换。

Ticket05本地实现/Review PASS：本地恢复测试与binding测试纳入118项R7本地回归，Ruff与diff检查通过；真实加密备份恢复至隔离PG/Qdrant、全表指纹/角色权限/session与epoch、RAG readiness、临时登录/历史/成果核验通过。独立stable clone完成candidate激活与previous回退；另验证恢复失败会清除解密payload。stable/dev运行容器和身份前后未变，未初始化实际stable key、未切换实际stable。详见 [Ticket 05](issues/05-isolated-restore.md) 和 [Review](review-05.md)。开始06。

Ticket06本地实现与Code Review PASS：immutable carrier/Link覆盖后台问数、分析和导出worker，受限OTLP配置、内容硬关闭、有界Batch及只读状态轮询通过。受影响回归334 passed、2 skipped、26 subtests passed；实际阿里云Trace未使用历史证据代替，留Ticket07当前候选验收。稳定配置未启用OTLP，stable/dev服务未修改。详见 [Ticket 06](issues/06-safe-traces.md) 和 [Review](review-06.md)。继续07。
