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

Result: clean candidate `bbe2cce` 的隔离安装、RAG、失败保护、API启动及Chromium sandbox均通过。Windows Edge问数/追问和图表/XLSX导出通过，经营分析执行到达终态`failed`；该次报告未保存安全错误码，尚不能区分模型拒答/格式问题与应用处理缺陷。验收helper现按终态读取并只记录该执行的状态与公开`error_code`，待以新clean candidate重跑以分类。专属验收资源已清理。Ticket 06本地代码、软件和OTLP集成Review已完成，稳定环境OTLP解析为关闭。真实stable切换、云端Trace查询和Push/PR均未执行。
Comments: Ticket 06本地提交为`1293208`。本目标修复仅调整隔离验收装配与测试等待/诊断，不改生产API/Contract。Compose挂载回归测试先Red后Green，`tests/scripts/test_local_acceptance.py`10项通过；前端helper类型检查与终态谓词测试通过。完整验收仍须重跑，并明确记录当前环境未满足的云端Trace/容量/恢复窗口条件。
