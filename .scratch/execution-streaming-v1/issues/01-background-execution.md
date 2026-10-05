# Ticket 01：后台受理、稳定操作查回与最终结果

ID: execution-streaming-v1/01
Status: in-progress
Authorization: 用户于 2026-10-05 确认六项拆分及连续完成整个 R4 的本地实施，包含编码、适用测试与真实验收、Review 和本地 Commit；不含远端发布。

Change Profile: 持续维护 /中偏大 /高风险事务与生命周期 /软件+真实PG+API /本地candidate。
Owner: 当前主Agent；迁移与运行状态由本项建立，后续切片维护其接口。
Blocked by: None (can start immediately)

### What to build / Scope

- 显式v4 migration、execution身份 /状态Store与Port，受理同事务关联原history turn，不复制成功snapshot /上下文。
- POST新执行 /恢复 /历史与成果重查、GET执行 /操作编号查回，后台worker使用同一查询 /分析链并返回受理身份。
- admission先查原operation再看revision /额度；相同请求去重、内容冲突拒绝；每账号1 /全局4，配置校验、不排队，worker真正结束才释放。
- history活跃登记与可转交analysis run lease覆盖受理→worker窗口，原同步入口不能抢同run或回收已受理执行。
- 结果 /成功指针 /execution成功同事务；失败与存储未知保持原上下文和受理唯一身份；初始化、shutdown signal /drain /部分装配失败清理按Design顺序。

Out of Scope: SSE网页反馈、用户取消 /文字流式、生产发布；本项暂由新API查状态 /最终turn完成纵向闭环。

Owned files: `database/control/006_execution_streaming.sql`、`src/chatbi_control/execution.py` /history.py /database.py /必要初始化映射；`src/query_api/execution_contracts.py` /execution.py /execution_runtime.py /execution_api.py、history.py /history_contracts.py /history_runtime.py /runtime.py /app.py；`src/business_analysis/run_execution.py`；`src/bootstrap/runtime.py` /必要生命周期；`.env.example`；对应 `tests/query_api/` /`tests/chatbi_control/` /`tests/bootstrap/` 和数据库验证入口；本项相关正式Contract /Runbook章节。

### Acceptance criteria / Evidence

1. 受理202后即使请求连接关闭，执行可继续；GET或原turn读取最终持久化结果，成功上下文与execution状态一致。
2. 重复 /并发同operation在同账号下只有一个turn /worker；不同内容409；响应丢失查回原身份；暂查不到无隐式重执行；跨账号不可查，未知字段 /非法UUID等受控拒绝。
3. busy /额度 /stale在适用位置拒绝，不多占额度；同run旧同步入口竞争受控；调度失败 /受理失败 /提交未知的故障seam有状态和资源证据。
4. 真实PG证明fresh /v3升级 /重复migration、事务与fencing，旧历史 /成果与marker保留；FK cascade不损独立成果。
5. 可阻塞worker证明shutdown先signal/drain后关Provider /DB /checkpointer，结束前不释放，部分装配失败无运行资源泄漏。

验证：对应Python /API /Runtime /migration targeted tests；真实隔离PG入口；旧API /R3受影响回归，锁文件 /模块边界 /静态 /Diff /文档检查。测试验证状态与结果，不能仅看submit调用次数。启动新存储实际失败与关键数据只读校验必须有证据。

Migration / Rollback: v4只增对象 /grant /marker，v2/v3保留，执行FK cascade仅元数据；显式初始化，不在请求DDL；停止worker后v3保留数据恢复将在04 /06完整验收。
Done When: 1–5通过、API /存储 /生命周期契约与适用文档完整，当前上下文Code Review PASS、Diff与本地Commit完成。
Result: 尚未实施。
Comments: 中间切片结果不冒称整个R4验收完成。
