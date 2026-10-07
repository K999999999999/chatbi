# Ticket 03：指定版本升级与兼容回滚

Status: open
Owner: 当前主Agent
Blocked by: 02
Result: 未开始
Comments: 本地实施授权于2026-10-07取得；发布授权未取得。


Change Profile: 持续维护 / 中 / 兼容判定与持久状态风险 / 确定性兼容测试+真实版本对集成 / 本地Commit。
Owner: 当前主Agent；后续交付及数据库/RAG兼容描述维护者。
Blocked by: Ticket 02。
What to build: 发布兼容声明与实际DB marker/catalog/checkpoint/快照/Seed/RAG身份只读检查；upgrade/rollback、环境锁和原子状态记录；失败保留最后成功版本及实际失败阶段。
Owned files: local、scripts/local_release.py、发布描述/兼容性数据、对应tests、Runbook升级回滚及正式部署Contract；不引入业务migration或修改历史Spec。
Acceptance Criteria:
- 已验证状态兼容才允许启动目标；镜像缺失/commit不匹配/未知marker/Schema/资产不匹配拒绝，不能只靠旧marker或镜像存在放行。
- upgrade停止旧API，显式操作必要迁移/资产，检查并启动新版本；rollback不迁移、不删除数据，不兼容在停当前API前拒绝。
- 两个真实clean release候选完成升级、兼容回滚和再升级后读取同一账号/历史/成果。
- 迁移或启动失败不自动逆向恢复，状态报告真实，兼容旧版可显式恢复；并发操作拒绝，工具无Secret回显。
Evidence: 兼容矩阵与状态写入/失败分支软件检查；真实隔离数据库版本对集成、不兼容状态拒绝前后数据对比、失败恢复和并发检查。
Migration / Rollback: 沿用现有migration，无DROP/downgrade；未知状态fail closed，兼容已验证列表由源DDL/锁文件与证据维护。动态监控/备份恢复不纳入此项。
Done When: 版本对SHA/image ID和数据/资产证据明确，长期状态不丢失、拒绝操作无副作用，文档与Code Review完成。
