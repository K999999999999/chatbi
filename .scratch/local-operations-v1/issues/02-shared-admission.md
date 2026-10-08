# 02 — 跨同步与后台入口的就绪和共享额度

Status: in-progress
Authorization: 用户2026-10-08确认七项拆分与全部本地实施、验证、Review和Commit；无Push/PR或实际stable切换授权。
Canonical Source: [Spec](../spec.md)、[Design](../design.md)；共同约束见 [已确认拆分](../tickets-draft.md)。


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


Result: 待实施。
Comments: 无。
