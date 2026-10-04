# 03 独立分析历史、原任务恢复与新任务重查

Change Profile: 持续维护 /中 /高风险（checkpoint与history独立事务协调）；Evidence为Business Analysis /API /真实PG /Chrome；Delivery本地逻辑提交。
Owner: 当前主Agent。
Blocked by: 01（复用完整history生命周期 /codec /runtime /基础列表，不依赖02的问数修订）。

### What to build / Scope

- 网页analysis首次明确发送创建history /服务端run UUID并受理；沿用原问题 /独立业务链，不继承query条件；报告与公开task证据经大小检查持久化后才成功。
- 重开仅读保存状态；原24h checkpoint有效可手动同问题 /原ID新attempt恢复；completed checkpoint但history未提交时仅读原completed结果，不graph.invoke。过期不续用原ID，显式新任务才新history /run。
- 旧Bearer analysis与Web共享owner /run Guard，覆盖graph执行至网页finish，保留内部任务受控重试；runtime失效 /线程未结束不放行同ID。让既有run登记expired接口供04原子删除使用。
- 报告快照独立于checkpoint，既有分析不公开SQL边界保持；未经完成 /有效归因校验的报告不是成功可保存结果。

Out of Scope: 延长checkpoint、问数路由 /共享条件、SSE /取消 /队列、多进程failover、新归因场景。

### Owned files

history Application /analysis snapshot codec /API /Store /runtime、`src/business_analysis/run_execution.py`、原Application /RunStore /contracts必要最小协作、`src/query_api/app.py`旧analysis入口共享guard、`src/bootstrap/analysis.py` /runtime注入、frontend analysis History /Chat /报告解码；`tests/business_analysis` /`tests/query_api` /PG /`frontend/tests`及正式分析 /历史文档。

### Acceptance criteria /验证证据

1. 分析成功→刷新 /重开仅读长期报告 /证据 /图表，不再次执行且不带问数context，清理checkpoint后仍可查看。
2. 未完成重开无invoke；有效期手动恢复原问题 /原ID，completed但history保存失败恢复无graph.invoke；非retryable失败依原Contract受控拒绝、不编造报告。
3. 原ID跨owner /不同问题 /24h过期 /runtime invalid均拒绝；同ID旧API与Web并发只一执行，断连仍busy至真实线程结束，不提前释放。
4. 显式分析重查新history /run，原报告固定；5MiB超限 /finish失败不网页成功，completed事实保留可在期限内明确恢复。
5. HTTP /旧analysis回归、实际PG RunStore和checkpoint生命周期、桌面Chrome状态 /恢复 /新任务交互通过；真实模型对账在06。

Evidence: 原completed branch调用计数、时钟 /归属 /互斥测试、PG run /checkpoint集成、Chrome；软件替身不得宣称真实模型报告通过。
Migration / Rollback: 复用01新表、原analysis run /checkpointSchema不破坏；runtime关闭先停执行。旧API默认不产history，旧版回滚保留长期报告且不延长原run期限。
Done When: 适用验证 /Review /Diff、本地提交、正式分析 /历史恢复Contract /Design /Runbook同步与候选证据记录完成。
Result: 未实施。
Comments: 恢复analysis与重新问数是不同Use Case；两个ID生命周期不混用。

Status: open
Canonical Source: ../spec.md、../design.md、../restoration-semantics.md
Authorization: 用户本轮确认六项拆分及整体本地实施（编码、适用真实验收、Review、本地Commit）；未授权Push /PR
