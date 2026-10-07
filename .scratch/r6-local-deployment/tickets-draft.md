# R6 本地稳定交付 Ticket 草案

Status: 草案；非正式Ticket，待用户确认粒度和整体实施范围。
Canonical Source: [已确认Spec](spec.md)、[设计](design.md)、[Design Review PASS](design-review.md)。
全体Owner: 当前主Agent；持续维护Owner为交付配置与所属模块维护者。无跨团队变更，不设虚构Backup Owner；涉及安全/Contract变更返回用户澄清与Design Review。
Delivery: 同一目标分支/worktree，按直接依赖连续实施，每项包含验证/Review/文档并按仓库规则本地提交；无Push/PR授权。

## Ticket 01：固定版本镜像承载完整应用

Change Profile: 持续维护 / 中 / 构建与运行资产风险 / 构建检查+容器浏览器导出证据 / 本地Commit。
Owner: 当前主Agent；后续Docker构建/导出资产维护者。
Blocked by: None。
What to build: 多阶段本地交付Dockerfile，打包网页、Python源码/事实资产、R5导出bundle/Chromium/字体和数据库初始化镜像；基础digest/依赖锁定；非root、单worker、无reload；发布描述记录commit和实际image ID及初始兼容声明。
Owned files: docker/local.Dockerfile、.dockerignore、发布描述格式及构建支持（scripts/local_release.py相关部分）、必要构建配置、安全模板骨架；对应测试与镜像说明文档。不得混入业务改动或锁文件无关升级。
Acceptance Criteria:
- clean指定版本容器构建成功，镜像包含有效网页与导出manifest、所需初始化/迁移文件；无.env/真实凭据/开发挂载依赖。
- 内嵌源commit与发布描述一致，镜像实际ID记录；不依赖可变标签识别版本。
- API默认非root、单worker且没有reload；字体/Chromium既有验证机制可运行，导出不依赖宿主源码。
Evidence: 构建定义确定性检查、镜像内容/启动命令检查、导出资产校验及受影响R5回归；容器帮助入口运行不需要宿主Python/Node。
Migration / Rollback: 不修改DB Schema；不替换开发镜像或开发入口。失败只保留本目标构建诊断，不自动prune镜像。
Done When: 构建证据关联clean候选与image ID，软件/资产检查和Code Review完成；Runbook打包入口说明同步，未执行项如实记录。

## Ticket 02：独立环境安装与日常启停闭环

Change Profile: 持续维护 / 中 / 初始化、资源归属与Secret风险 / 命令软件测试+空卷集成+浏览器 / 本地Commit。
Owner: 当前主Agent；后续交付/bootstrap维护者。
Blocked by: Ticket 01。
What to build: 独立docker-compose.local.yml、安全配置模板、./local安装/初始化/启动/停止/状态/日志入口；配置和卷/项目labels隔离、API/工具/migrator最小权限、模型缓存与独立RAG资产装配；交付启动显式复用既有catalog/RAG门禁。
Owned files: docker-compose.local.yml、.env.local.example、local、scripts/local_release.py、必要bootstrap装配适配及对应tests；部署正式Spec初稿/Runbook安装配置启停章节。若需改变bootstrap公共行为返回审查。
Acceptance Criteria:
- 空验收环境显式完成基础初始化→migrate→模型/索引→隐藏密码创建管理员→up；up缺少条件拒绝且不自动初始化。
- 仅API发布回环端口；无开发代码bind/迁移凭据进入API，所有服务手动启动；secret与静态身份检查生效。
- Windows浏览器同源登录并完成至少一次真实问数；关闭终端继续运行，down保留数据，再up历史可读。
- 索引指纹不匹配/配置缺失/端口冲突给出阶段诊断与非零结果；不杀进程/重置数据/影响开发环境。
Evidence: 命令分支/权限/挂载确定性检查，独立真实PG/Qdrant初始化与重试集成，真实LLM浏览器登录问数；记录环境/提交/镜像/资产身份。
Migration / Rollback: 只在新独立实例应用现有migration，不导入开发数据；失败保留稳定数据，恢复按显式初始化步骤重试。工具锁阻止并发写操作。
Done When: 已确认安装/启停边界全部有证据，正式行为说明与Runbook同步，Code Review完成；形成可用于后续真实升级对的clean release候选。

## Ticket 03：指定版本升级与兼容回滚

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

## Ticket 04：目标环境完整验收与交付证据

Change Profile: 本轮验收+持续维护文档入口 / 中 / 证据身份与清理影响风险 / 软件回归+真实浏览器+运行验收 / 本地Commit。
Owner: 当前主Agent；后续验收脚本与Runbook维护者。
Blocked by: Ticket 03。
What to build: 可重复隔离验收入口、完整业务与失败场景证据、目标机重启验收计划、正式Acceptance与文档状态收尾。前述Tickets的测试不推迟到本项。
Owned files: scripts/verify_local_deployment*、受影响tests、docs/specs/local-deployment-v1.md、docs/designs/local-deployment-v1.md、docs/acceptance/local-deployment-v1.md、docs/runbook.md、docs/product-scope.md、docs/roadmap.md及本目标scratch记录。
Acceptance Criteria:
- 同一最终clean候选完成空环境安装与Windows浏览器登录/问数/追问/经营分析/历史/保存成果/XLSX PNG PDF下载并独立检查内容。
- 停止/重启/手动恢复后账号、历史和成果可用，Seed不重播；电脑或Docker重启验证安排维护窗口，不擅自重启共享服务。
- 真实升级回滚与不兼容拒绝、配置/端口/索引/启动失败、资源隔离/安全日志均有证据；清理仅限身份已确认验收资源。
- 记录候选commit、dirty状态、镜像与模型/Seed/RAG身份，历史R1–R5报告保持原身份。根据最终Diff说明AI Evaluation复用适用性或重跑受影响正式套件。
Evidence: 最终受影响软件回归、容器集成、真实模型Windows浏览器/Business Acceptance、目标机运行证据及资源清理核对；报告绑定最终候选，无结果预填。
Migration / Rollback: 只在专用验收资源构造失败状态，不写开发数据；稳定环境重启需维护窗口。已有长期记录保留，验收结束只清理临时项目。
Done When: 正式Contract/Design/Runbook/Acceptance/产品范围/路线图全部一致，最终Code Review与Diff检查完成，未运行项与限制明确；产品/R6实时状态同步，无远端发布。发布另需明确授权。


## 拆分确认与正式登记（2026-10-07）

用户确认四项拆分并授权按依赖连续完成全部本地实施与验证。四项正式本地Ticket分别登记于`issues/`。授权覆盖本地实现、目标电脑验收及仓库默认本地提交；不包含Push、PR、合并或云部署。
