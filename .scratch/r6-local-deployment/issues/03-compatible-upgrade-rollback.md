# Ticket 03：指定版本升级与兼容回滚

Status: done
Owner: 当前主Agent
Blocked by: 02
Result: 实现 Review PASS；首轮真实尝试发现 baseline 参数路由错误，在停 API / 执行 migration 前安全拒绝，修复后补回归测试并重审通过。最终 clean 候选 C `9ae32ef6900030af15c38ac9a059e3086b5dde1c`（API `sha256:2f7258763e7464efafadaf587bef9cb63e0de6bc1bf259254988604605bdf22c`；构建用 PostgreSQL `sha256:e41b6f0a804e5515fb92d165762f9708c25cf11adab66243b75a7dcab1629631`）和候选 D `995440bfd448f6057f5152431d17dff012f8bd5c`（API `sha256:1cbb2052f69c076e3ac7f89e352cf65a2b281535d4a4436f3b29560b4b1e35b4`；构建用 PostgreSQL `sha256:54101c3decd0c3d53a3dec2bfbabd2927e6ec82be96ce104c592c42045d2b1af`）完成真实往返：`733b074 → C upgrade → D upgrade → C rollback → D re-upgrade`。每次兼容检查、migration阶段、API健康及部署状态记录均成功；rollback日志未运行 migrator。运行中的 PostgreSQL 始终保留原镜像 `733b074`、容器 `cb18b903d8bd` 和命名卷，Qdrant容器 `f54cf28e0543` 与数据卷未重建；最终 active API 为 D，`.local/deployment-state.json` 记录 `running/succeeded` 且权限 `600`。

往返前后只读数据指纹完全一致：用户 `4`（管理员 `1`），SHA-256 `04a738edba195a830f3084c8d296bc607ce689fca3fde5a222452a38f5a68660`；历史 `3` 条 / turn `3` 条 / 快照 `3` 个，SHA-256 `64975e570bf0f5524f044084861cb6511f5a77f43e22ac870824dea1673ce331`；saved_results 当前为 `0` 条，前后空集指纹一致（`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`）。首个候选及修复候选真实兼容预检通过；修复后 release/state 定向测试 `45 passed`，原 Ticket 定向测试 `48 passed`，Ruff、Bash、Compose、Dockerfile、Markdown link 与 Diff 检查通过。未删除持久资源、输出 Secret 或发布远端。
Comments: 本地实施授权于2026-10-07取得；发布授权未取得。
Implementation review: Review 基线为 `e7100d9`，PASS。首次真实 upgrade 在停止 API 前发现 baseline release 参数路由错误，安全拒绝且未运行 PostgreSQL migration；随后修复并由 C / D 候选完成真实版本往返与持久化身份对照，详见 Result。


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
