# 01 问数自动保存与刷新重开

Change Profile: 持续维护 /较大 /高风险（成功一致提交、认证状态、新Schema与兼容）；Evidence为确定性、API、真实PG及桌面Chrome；Delivery为一个纵向行为，可用多个相关逻辑Commit完成，不拆出独立DB /服务 /UI目标。
Owner: 当前主Agent。
Blocked by: None (can start immediately)

### What to build / Scope

- 首个网页问数从明确发送→私人history受理→既有授权 /Online Query执行→完整认证state与快照一致提交→页面显示；刷新 /退出后重登录从基础列表重开仅读快照。完整恢复state在首个成功轮次存在，续聊交互在02接入。
- 实现Restoration§1–§3 /§5首轮history profile、完整Candidate /Validated条件 /certification /codec、程序批准的semantic binding及当前发布资产闭包；R2引用同一维度映射，旧Bearer /分析任务默认profile保持。
- 实现Design§2 /§4 /§5 /§9：005 /v3对象、Store Port /PG Adapter、begin /finish、5MiB与失败状态、revision /epoch /generation /ExecutionRegistry、单API guard及停止后重启恢复，不把核心一致性推迟到最终验收。
- 新API创建 /执行问数 /header /turn详情 /基础分页列表，严格字段与owner /permission /CSRF；前端URL定位、身份清理、懒加载、旧ResultView /精度 /图表复用。

Out of Scope: 追问 /显式重查、分析history执行、改名 /搜索 /删除交互、成果管理（后续Tickets）；R4–R7、任何新依赖或业务指标。

### Owned files

新增`database/control/005_history_results.sql`、`src/chatbi_control/history.py`、`src/query_api/history.py` / `history_contracts.py` / `history_codec.py` / `history_api.py` / `history_runtime.py`、`src/online_query/semantic_state.py`、`src/semantic/query_bindings.json`及其校验加载；必要修改`src/chatbi_control/database.py`、`src/bootstrap/runtime.py`、`src/query_api/app.py` /响应与身份适配、`src/online_query/contracts.py` / `query_understanding.py` / `query_understanding_llm.py` / `prompt.py` / `service.py` / `service_execution.py` / `retrieval/retrieval_context.py` / SQL Guard、R2 mapping loader /display配置；frontend App /Chat /api /历史基础组件 /snapshot解码与样式。相关`tests/query_api`、`tests/chatbi_control`、`tests/online_query` /semantic、`frontend/tests`。

### Acceptance criteria /验证证据

1. 首次发送成功后刷新、重新登录重开，可读原问题 /表格 /SQL /图表 /说明且理解、模型、业务数据库调用次数不增加；空页面不建记录、登录默认空白问数、身份切换 /迟到响应不泄露。
2. 单值、时间 /分类、实体distinct、1至5指标、过滤、排序 /Top-N /nulls /平局、既有合法单指标聚合筛选完整认证并codec往返。前200项保留业务200而最多返回100且截断，旧相对时间持久化绝对值不跨天漂移。
3. 漏排序 /wrong LIMIT /额外WHERE /HAVING /错误公式或grouping等SQL拒绝，业务数据库0次；不能保存“成功但不可恢复”。旧Candidate六字段 /Prompt /Guard、API请求响应 /默认会话与静态替身构造回归保持。
4. begin写失败业务调用0次；finish回滚 /commit未知不返回成功、不推进已提交context；响应丢失后仅读已提交事实；精确5MiB等于通过 /多1字节拒绝，十进制字符串 /NULL /空值 /日期不丢类型 /精度。
5. 真实PG两连接同history只能受理一个attempt；当前epoch任务运行保持busy，restart旧epoch未确认 /最后成功保持，旧generation不能写回。guard失效拒绝新history执行，无任意TTL提前释放。
6. 真实PG fresh /v2 upgrade /repeat migration、必要权限与缺对象startup拒绝、资源关闭 /持锁连接不回池；同owner operation dedup，跨owner /禁用 /撤权 /CSRF /unknown字段受控无越权。

Evidence: 纯seam与httpx测试、真实PG事务 /初始化报告、确定性桌面Chrome测试；模型输出用替身证明调用边界。真实模型及整体clean报告在06。每份记录关联当前候选 /基线 /覆盖 /结果，失败保留证据并修复。

### Migration / Rollback / Done When

增加型005保留v2标记与数据，不修改用户 /RBAC /业务 /RAG内容，不从旧内存造历史。旧版回滚停止新API、保留v3表 /字节，重新升级仍读。无生产发布 /feature flag承诺；兼容或Schema验证失败停止该切片。
Done When: 上述可观察闭环与适用软件 /PG /Chrome通过；当前上下文Code Review /Diff检查通过；同步正式R3 /Query API /Web及恢复语义说明、Design和Runbook初始化 /单进程恢复规则、roadmap进度或不适用理由；本地逻辑Commit及Ticket Result记载完成，整体R3仍未验收完成。
Result:
- Candidate A `d6041af45bf4f69bb7b60053e0a404d754dc23fc` 已完成首轮实现与候选验证。Python 全量为 685 passed / 29 skipped / 139 subtests，隔离 PostgreSQL 33 passed，桌面 Playwright 36 passed；代码 Review PASS。
- Compose 真实报告 `reports/browser-real/container-1791144563-real.json` 绑定该 clean commit，首次问数 / 追问、快照重开及新登录边界通过；报告 `status=passed`、`suite_status=passed`，临时账号已禁用、活跃 Session 为 0。
- Ticket Result 与路线图同步会形成新的候选 B；本切片实现状态完成，候选 B 的最终身份验收由 Ticket 06 重新执行并记录在 Git 公共目录实时状态。
Comments: 首个切片较大是因为网页成功必须同时满足执行 /认证 /持久化 /恢复，不能横向拆出无完整成功条件的交付。

Status: done
Canonical Source: ../spec.md、../design.md、../restoration-semantics.md
Authorization: 用户本轮确认六项拆分及整体本地实施（编码、适用真实验收、Review、本地Commit）；未授权Push /PR
