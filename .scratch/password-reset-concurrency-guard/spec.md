# 密码重置与自行改密并发保护（短 Spec）

## 目标
同一账号的管理员密码重置与用户自行改密并发时，不允许旧事务覆盖重置结果或继续使用已撤销的 Session。

## 行为与范围
- 对同一用户的自行改密、AuthService 管理重置和 SQLAdmin 密码重置，按 PostgreSQL 用户行锁串行化关键状态判断与写入。
- 若管理员重置先完成，自行改密必须基于重置后的密码 / Session 状态判断；旧 Session 被撤销后不得继续改密。
- 若自行改密先完成，之后提交的管理员重置最终保留管理员设置的密码，并要求用户首次登录改密。
- 保持现有密码策略、响应、审计语义、Session 撤销范围、Schema 和公共 API 不变。

## 验收与验证
- 在隔离 PostgreSQL development profile 中用确定性交错复现旧实现的并发覆盖，再验证修复后管理员重置语义始终成立。
- 覆盖 AuthService 与 SQLAdmin 密码重置入口、会话撤销和最终密码状态。
- 运行相关定向测试、development profile、全量 Python 测试、质量检查、Code Review 和 Diff 检查。

## 授权
用户于 2026-10-11 明确要求修复此问题；授权实现、必要测试和文档同步、验证、Review 与本地 Commit。不包含 Push / PR 发布或 Stable 操作。
