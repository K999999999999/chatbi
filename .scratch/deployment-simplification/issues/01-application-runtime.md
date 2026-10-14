# 01 应用不再依赖Stable运维状态

Status: done
Canonical Source: [Spec](../spec.md)、[Design](../design.md)。用户确认四项拆分及完整本地实施、验证、Commit；无发布授权。


Change Profile: 持续维护 / 小至中跨装配与状态UI / 中风险（权限、生命周期、请求保护）/ 软件与浏览器回归 / 本地交付。
Owner: 当前实施Agent。
Blocked by: None (can start immediately)

### What to build / Scope

删除backup provider、备份状态读取和Unix socket装配；删除details.backup和网页备份提示。保留应用装配、readiness、真实模型观察、状态权限、受理与共享额度、退出清理。先解除应用对Stable文件与脚本的依赖，使应用在没有备份/发布目录时正常运行。

Owned files: src/bootstrap/runtime.py、backup_status.py、operations_socket.py；src/query_api/operations.py及必要状态装配；frontend/src/OperationsStatus.tsx；tests/bootstrap/test_operations.py、test_runtime.py；tests/query_api/test_operations_state.py、test_operations_api.py、test_admission.py及受影响生命周期测试；frontend/tests/operations.spec.ts；必要bootstrap/状态Contract文档。

Out of Scope: 查询/分析链路、权限规则、DB结构、共享额度上限调整；Stable CLI和备份工具最终删除留03，不维护中间候选的Stable可运行性。

### Acceptance criteria

- 无备份目录/socket仍能装配并关闭应用，失效资源正确清理。
- 管理员响应不含details.backup，其余状态字段/权限/认证/无保活保持；普通用户仍无详情。
- readiness的成功/失败/超时/过期/恢复、模型观察及容量保护保持。
- 网页不再出现备份提示，现有状态/登录过期/安全显示测试通过。

Evidence: 受影响bootstrap、operations、admission、execution及授权回归；前端typecheck/build和operations浏览器测试。中间阶段可以使用现有容器运行命令，最终统一入口由02补齐。
Migration / Rollback: 仅删除已确认API字段，无数据迁移；源代码可由修复提交恢复。失败暂停03，禁止回退用户修改。
Done When: 上述行为及测试/Review PASS，删除的只有运维装配，状态/Bootstrap Contract同步，候选与结果写Result。
Result: 已完成本目标范围；验证与失败处置见[验收](../acceptance.md)，当前上下文Code Review记录见[Review](../code-review.md)。
Comments: API字段删除是用户确认的唯一业务接口例外；其余保护不能按名称删除。
