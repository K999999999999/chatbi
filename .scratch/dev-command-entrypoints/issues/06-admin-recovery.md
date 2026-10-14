# T06 dev/app管理员紧急恢复

Status: done
Spec: [已确认行为](../spec.md)；[设计](../design.md)；[共用完成规则](../tickets-draft.md#共用done-when与证据要求)。
Authorization: 用户确认七项拆分及全部本地实现、验证与提交；远端未授权。

- Change Profile: 新本机安全Contract；中等纵向切片；高风险认证/事务；Service/TTY+真实PG竞争+两目标装配；本地交付。
- Owner: 当前主 Agent；长期规则归authorization，配置装配归Bootstrap/operations；未决安全问题返回设计审查。
- Blocked by: T01。
- What to build: recover-admin显式环境/用户名、最小容器装配、交互CLI、专用AuthService原子恢复及强制审计；相关已有用户写路径统一User锁/刷新，仅服务并发保护。
- owned files: dev及目标辅助、src/bootstrap/commands.py与恢复装配、src/authorization/auth_service.py、src/chatbi_control/admin.py及对应tests/bootstrap/authorization/chatbi_control/scripts；Dockerfile仅如打包所需；Bootstrap/认证/容器Contract、产品范围/架构及Runbook适用段落。
- Acceptance Criteria: 只已有active admin，角色/其他用户/历史不变；Hash+必须改密+清锁+撤销全部Session+独立审计同事务；审计失败全回滚；现有登录/角色/改密/禁用竞争有序；actor非被恢复用户；运行DB身份、不依赖API/LLM/QD/RAG；已有匹配镜像/初始化PG要求，无隐式build/start/migrate；TTY和0/1/2、敏感输入及提交失败安全。
- 验证证据: Service状态与审计回归、真实PG双连接屏障竞争及权限测试；真实伪终端验证回显拒绝/输入中断；临时dev/app专用管理员互不影响、缺无关LLM配置仍可恢复、错误目标与缺镜像拒绝。不能用SQLite或Docker替身替代行锁和最终容器证据。
- Migration / Rollback: 无Schema迁移；原create-admin/Web重置职责保持；新CLI代码可回滚，已恢复密码/撤销Session不可靠代码回滚复原；只操作测试账号。任一原子性/身份测试失败停止交付。
- Done When: 安全恢复完整闭环、并发回归无旧Session逃逸、两目标真实证据与正式本机信任边界文档齐全。


## Result

显式dev/app管理员恢复完成：TTY隐藏两次输入、运行账号校验、User锁、密码/Session/强制审计同事务。软件及7项真实PG锁/回滚测试通过；隔离双环境真实TTY验证成功、两次不一致与Ctrl-C、无LLM/QD/API/RAG依赖。

证据范围、故障修复及未运行验证见[整体验收记录](../acceptance.md)，[Code Review](../code-review.md)结论适用于本地候选；提交身份见Git公共目录实时记录。

## Comments

从草案正式写入，适用基线master@38e1302。
