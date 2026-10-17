# 审计修复设计审查

Review: PASS WITH MINOR FIXES

Review Target: 用户已确认的[Spec](spec.md)，基线`8d01740474b2c727131e54a70a2f186713b306ad`。

本审查由当前主Agent只读执行，未启动独立Agent。下面的修订由审查结束后主Agent落实；没有修改产品代码、测试或配置。

## 核心判断

目标是恢复既有SQL语义、安全、状态和验证Contract。模块职责及依赖方向保持，不增加服务、Provider、依赖或持久化Schema。正常行为、失败结果与22项验收足够明确。公开API继续使用既有错误外壳，兼容路由与旧合法快照保留；真实评测和业务验收分层记录。

## Findings

### D1：兼容受理必须位于幂等判断与新状态写入之间

- Signal: 单纯HTTP外层admit会让幂等重放占额；在_execute_attempt取额则新attempt已写入，拒绝会遗留状态。
- Evidence: `src/query_api/admission.py`每次调用都会reserve_owner；`src/query_api/history.py`在begin_attempt/begin_requery后才执行；`src/chatbi_control/history.py`在_begin内判断既有operation，再插入accepted和active_turn；后台ExecutionApplication已有预占租约。
- Impact: 错误时序破坏幂等与生命周期保护；重复实现额度会增加规则分散。
- Recommendation: Application提供无Framework类型的可选内部受理回调，在既有事务的幂等/归属/revision校验后、新状态写入前调用；Application退出栈管理同一租约，后台预占额路径不重复受理，受理失败不写新状态。

### D2：清理应回收遗留checkpoint并保留失效身份

- Signal: 简单移除status过滤会反复更新所有历史expired行；直接删除run则可能改变ID重用行为。
- Evidence: run_store.cleanup_expired当前仅处理status非expired行；history.delete_history预先写expired；claim依赖expires_at/status拒绝原ID。
- Impact: 数据残留、清理成本及ID生命周期均受影响。
- Recommendation: 选择到期run并覆盖仍有checkpoint的expired遗留记录，事务内删除三类子表；保留tombstone，以真实PG证明范围和重复清理行为。

### D3：首个管理员互斥必须独立于角色是否已seed

- Signal: 检查后再锁角色无法保护检查窗口；仅锁角色依赖固定角色存在；串行SQLite测试不能证明PG竞态。
- Evidence: create_first_admin先查询管理员，再seed_rbac；CLI在session.begin内调用；现有软件测试以空SQLite表直接初始化。项目已有不同用途advisory锁。
- Impact: 不完整锁范围或碰撞锁身份会造成权限不变量失效或无关串行化。
- Recommendation: PostgreSQL使用专用固定事务advisory lock，先锁后查并覆盖提交/回滚；与角色行锁方案比较后选择前者。保留SQLite串行软件测试，新增真实PG同步竞态及回滚测试。

### D4：公开结构校验和隔离验收恢复不能只有顶层描述

- Signal: 简单敏感词删除会误处理合法query.sql，且不能保证分析结构；热更新仅try/finally不能单独证明信号清理；账号先提交后落盘仍有身份窗口。
- Evidence: history_codec只对query详细校验；Analysis/pdfReport均有多个嵌套结构；verify_container_dev的源码只读挂载与写测试冲突，cleanup依赖account.json；prepare提交账号后才写文件。
- Impact: 数据公开边界、回归兼容、验收资源及源码恢复结果难预测。
- Recommendation: 按现有分析公开结构逐层校验，保留合法旧可选字段；隔离写路径+源码备份+信号恢复+Hash核对；提交前身份落盘或异常精确补偿，维持禁用/Session撤销语义。

## 修订核对

主Agent已在Spec“设计审查后的实施约束”逐项落实D1–D4，并细化模型路径/报告变量优先级及.env读入前防护。逐项复核：与原22项验收、原公开接口和隔离范围一致，无新增用户决定、依赖或Schema迁移。

Reference: 已读取Architecture Knowledge Core，主要使用复杂度信号、依赖方向、Observable Behavior、Failure/State/Testability、Design Twice和Overengineering Guard原则。

Evidence Sources: Spec、Architecture、Product Scope、application-readiness/query-api/history/execution/bootstrap/evaluation/result-export等正式Contract；admission、HistoryApplication、HistoryStore、ExecutionApplication、HistoryRuntime、run_store、bootstrap/control、chatbi_control/bootstrap、audit_service、history_codec、embedding、Qdrant错误链、Chat/Analysis/pdfReport、Real E2E及容器验收脚本；现有对应测试seam。

Next: 修订核对完成，可进入workflow-to-tickets。此结果不是实现、Commit或发布授权。
