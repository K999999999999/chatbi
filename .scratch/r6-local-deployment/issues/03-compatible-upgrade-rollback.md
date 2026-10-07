# Ticket 03：指定版本升级与兼容回滚

Status: in-progress
Owner: 当前主Agent
Blocked by: 02
Result: Ticket 02已在clean candidate `733b074`完成最终安装 / 启停 / 端口 / 浏览器 / 持久性验收。兼容声明、只读状态核验、指定版本 upgrade / rollback 编排和原子部署状态已实现；以 `d48307e` 为基线的本地实现 Review PASS，覆盖当前 Ticket owned files；local deployment 定向测试 48 项通过，Ruff、Bash / Compose / Dockerfile / Markdown link 检查通过。Ticket 03候选 `4f39d567783917f35743eaeeedebf93acb37feaa` 本地构建成功（cache source `4d4732b7896a46b231a4a3437c703e74b5ae513f`；API `sha256:ee5cc7d99463d595ef809e4e230ab9b6622c2c5617db24d6094cb86ce1e66189`；PostgreSQL `sha256:8e6de79a2da32d04e59a462b5e768d38c79e4a137913d458d468420ffe5f55d7`），其对当前稳定数据库 / 快照 / Sales catalog / RAG 的只读兼容检查通过，未切换运行服务。两个clean release候选的实际升级 / 回滚 / 再升级、持久账号 / 历史 / 成果核对仍待完成；不引入反向migration、自动删卷或公网发布。
Comments: 本地实施授权于2026-10-07取得；发布授权未取得。
Implementation review: 首次真实 upgrade 在停止 API 前发现 baseline release 参数被错误路由，安全拒绝且未运行 PostgreSQL migration；稳定 API 仍为 `733b074`，持久数据未修改。现已显式区分 baseline / active 参数并增加回归测试；以 `e7100d9` 为基线的当前实现 Review PASS，local release/state 测试45项、Ruff、Bash语法和Diff检查通过。修复候选 C `9ae32ef6900030af15c38ac9a059e3086b5dde1c` 本地构建成功（API `sha256:2f7258763e7464efafadaf587bef9cb63e0de6bc1bf259254988604605bdf22c`；PostgreSQL `sha256:e41b6f0a804e5515fb92d165762f9708c25cf11adab66243b75a7dcab1629631`），对稳定持久状态的只读兼容检查通过，尚未切换服务。候选往返验收仍待完成。


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
