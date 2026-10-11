# Code Review：密码重置与自行改密并发保护

Review: PASS
Clean Code: PASS
Mode: Main Agent
Base: `b7dd82386d877ccf6669bd2e02698e81da19f975`

- Correctness / Security：自行改密先锁定并刷新用户行，再重新读取 Session；锁等待期间若管理员已撤销该 Session，操作以既有 `SessionExpired` 语义停止。SQLAdmin 重置在撤销 Session 前获取同一用户行锁，避免旧改密事务覆盖重置结果，也保持用户行到 Session 行的锁顺序。
- Contract / Scope：落实 `docs/specs/web-dialogue-v1.md` 的改密、重置与旧 Session 规则；无 API、Schema、密码策略或权限行为变化。
- Testability：隔离 PostgreSQL 并发测试通过公共 `AuthService.change_password` 和 SQLAdmin `on_model_change` 路径观察最终持久状态，并确认数据库报告了行锁等待。
- Comprehension / Consistency：行锁与刷新逻辑贴近状态判断处；没有引入新抽象或依赖。
- Security：未发现 Secret、权限绕过或错误扩展。

Findings: 无阻塞项。
