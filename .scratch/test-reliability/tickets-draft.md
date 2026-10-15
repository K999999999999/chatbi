# 测试可靠性：实施 Ticket 草案

Status: confirmed；用户已确认七项拆分，并授权全部本地实施、验证和 Commit。正式 Ticket 见 [issues](issues/)；本草案阶段尚未取得 Push / PR 授权，后续汇总交付见 [PR #86](https://github.com/K999999999999/chatbi/pull/86)。

## 共同约束

- Owner：当前主 Agent；范围 / Contract 变化升级给用户，不启动独立 Agent。
- Canonical Source：[Spec](spec.md) 定义行为，[Design](design.md) 细化实现，[Design Review](design-review.md) 为已通过门禁；本文件只安排切片。
- Change Profile：本机源码作品的持续维护；七个有界切片、同一目标 branch / worktree、本地候选；各项代码 / 测试 / 正式文档一起交付，不另建水平文档 Ticket。
- 不改产品业务、首次改密、账号权限、SQL Guard 或模型答案；不自动操作日常环境或收费调用；旧验证候选保留。
- 每项按 TDD / 最小适用验证、当前上下文 Code Review、Diff 检查和本地提交执行；草案阶段未有 Push / PR 授权，故当时托管 CI 尚未运行。后续 PR / CI 结果记录于 Ticket 07。
- 所有 owned files 的新增标记为“新”；发现未列出的业务边界或关键设计变更时先返回 Spec / Design，不借实现扩张。
- 前四项和第五项可独立开始；主 Agent 按编号串行推进。共享文件由同一 Owner 顺序维护，不据此制造额外技术依赖。

## 01. 移除独立 APP 路线，保留 dev 与资源保护

Change Profile: 单次退役；中等范围 / 中等风险；CLI、装配、专属构建、测试与文档闭环；无真实数据迁移。

Blocked by: None (can start immediately)

What to build:

- 移除 app 正向命令 / 目标、专属 Compose / Dockerfile / 验收器和配置；无效调用在资源操作前失败。
- 保留 dev 开发与测试镜像、前端静态构建 / startup smoke、公共 Python app、数据库角色；保留拒绝旧 APP 容器的目标校验。
- 同步当前支持范围、恢复 / 容器 Contract、README / Runbook / Roadmap，归档独有历史内容并修复引用。

Owned files: `dev`、`.env.example`、`scripts/dev_environment.sh`、`scripts/dev_maintenance.sh`、`scripts/dev_compose.py`、`scripts/verify_container_app.sh`（删）、根 `Dockerfile`（删）、`docker-compose.app.yml`（删）、`src/bootstrap/commands.py`、`src/bootstrap/doctor.py`、`src/bootstrap/admin_recovery.py`、`src/bootstrap/verification.py`（删）、`src/authorization/auth_service.py` 的恢复环境限制、`tests/scripts/test_container_application.py`（删）、`tests/scripts/test_container_dev.py`、`tests/scripts/test_dev_maintenance.py`、Bootstrap / Authorization 对应测试；README、`docs/agents/documentation.md`、docs 的架构 / 产品 / 路线图 / Runbook / Bootstrap / 容器 / 恢复 Contract、APP Contract 历史归档及受影响历史 Markdown。

Acceptance Criteria / Evidence:

1. 帮助只宣传支持路线；`app`、`verify app`、`doctor app`、`recover-admin app` 及相应底层新请求拒绝，不触发 Docker / SQL / 账号操作；既有历史审计不改写。
2. dev 对旧 APP / Stable 或未知资源仍拒绝；合法开发目标、元数据 / 诊断 / 恢复选择回归通过，不修改实际账号。
3. Compose 实际解析、定向 scripts / bootstrap / authorization 回归及保留的构建入口检查通过；消费者检索解释所有残留 app 字符串。
4. 正式事实源同步、历史归档和链接检查通过。本机旧资源原样保留。

Migration / Rollback: 退役替代入口为 dev；仓库切片可用 Git 恢复，真实卷 / 配置 / 资产不迁移或删除；失败暂停依赖切片，不能把旧调用悄悄导向 dev。

Done When: 以上证据、Review、相关文档与 Diff 通过，结果记录对应候选；本地提交完成。

## 02. 修复数据库并发测试的失败退出与清理

Change Profile: 小范围测试修复；并发 / 退出风险中等；真实隔离 PostgreSQL 与有界故障注入证据。

Blocked by: None (can start immediately)

What to build: worker 独立连接与 backend PID 可识别；观察精确等待；释放锁早于 join；测试连接 / SQL / 观察 / join 有限时，失败保留原始原因并清理自己拥有的资源。

Owned files: `tests/chatbi_control/test_history_postgres.py`、必要的 `tests/history_support.py` 测试辅助或本文件内局部 fixture、`tests/scripts/` 下进程有界失败验证（新文件仅如必需）、Runbook 的相关诊断说明及本目标验收记录；不改生产 HistoryStore / HistoryRuntime 业务行为。

Acceptance Criteria / Evidence:

1. 正常用例确实观察到自身 worker 等锁，释放后成功保存；重复隔离执行通过。
2. 未观察到等待、worker 抛错、等待超时或断言失败时有上限退出，非零且能定位原因；没有等待线程阻止解释器退出。
3. 只取消 / 关闭本用例拥有的连接；测试结束锁、连接和资源释放，不触及日常库；完整 database 两 profile 回归通过。

Migration / Rollback: 无生产 / 数据迁移；测试切片可独立恢复；不以跳过断言、仅加长超时或取消其他会话作为修复。

Done When: 正常与失败证据、数据库回归、Review、Diff 通过并本地提交。

## 03. 首次改密浏览器用例使用独立账号

Change Profile: 小范围 fixture 生命周期修复；中低风险；真实浏览器 / HTTP、隔离 SQLite 支持应用。

Blocked by: None (can start immediately)

What to build: 用例级唯一测试账号准备 / 清理；失败也清理会话和账号；正式登录 / 首次改密规则不变；测试辅助仅注册在隔离支持应用中，生产应用无测试后门。

Owned files: `tests/browser_support.py`、`frontend/tests/auth.spec.ts`、`frontend/tests/helpers.ts` 或新的仅测试 fixture 文件、必要的浏览器支持隔离回归；现行 Web 测试说明及本目标验收记录。

Acceptance Criteria / Evidence:

1. 同一支持服务上 `./dev test web auth.spec.ts --grep 'first password change' --repeat-each=2` 至少两次通过，记录不同账号身份与清理证据，不靠每次重启服务重置状态。
2. 故意中断或断言失败时执行清理；清理失败不能记通过，不留下可复用 Session。
3. 完整浏览器与 Vite 代理回归通过；定向验证测试 fixture 管理能力未注册到正式应用，且无法修改固定 / 非本次测试身份。

Migration / Rollback: 无真实账号迁移；仅测试装配切片可独立恢复，日常账号不读写。

Done When: 重复 / 失败 / 完整浏览器证据、Review、Diff 通过并本地提交。

## 04. 修正无序结果的容差匹配

Change Profile: 小范围评测算法修复；评分影响中等；纯确定性测试，不调用模型 / 数据库。

Blocked by: None (can start immediately)

What to build: 复用现有值比较，用多项式增广路径判断完整一一配对；有序模式和原容差、NULL、列顺序、重复行、截断规则保持。

Owned files: `evaluation/suites/single_turn/evaluator.py`、`tests/evaluation/single_turn/test_evaluator.py`、受影响的 `tests/evaluation/single_turn/test_runner.py` / `tests/evaluation/multi_turn/test_evaluation.py`、`docs/specs/evaluation.md` 的比较规则及本目标验收记录。

Acceptance Criteria / Evidence:

1. 原重叠容差反例与行置换通过；存在完整匹配时通过，不存在时失败。
2. 重复行不足、NULL 与零、多个列、边界误差、数字字符串可选归一化、截断和有序比较均有回归。
3. 接近有界最大行数的密集候选可确定性完成，不使用全排列或脆弱的计时断言；Evaluation 全部确定性测试通过。

Migration / Rollback: 不改题集、标准 SQL、误差门槛；旧报告不回算；本切片可独立恢复，后续评分依据记录候选版本。

Done When: 比较器与调用者回归、正式规则、Review、Diff 通过并本地提交。

## 05. 四套 AI 评测统一追溯、防覆盖与正式验收

Change Profile: 中等跨套件改动；证据格式 / 兼容风险中等；不改业务执行与评分；纯工具 + 原有报告适配。

Blocked by: None (can start immediately)

What to build:

- 建立 Design 定义的标准库报告小工具，四套入口均从运行开始采集身份，结束核对；旧 git 字段表示起点。
- 补齐语义题集 / 模型设置及经营分析 Judge 的有效配置；适用数据库 / RAG 指纹继续由原 collector 提供。
- 版本化 provenance、独立 run ID、排他保存 JSON / Markdown、部分写入失败；正式验收拒绝 changed / unverified / 缺证明的新报告，历史报告继续可读。
- 修正文档语义案例数量，保留当前标准集内容与原话提取 Contract。

Owned files: `scripts/verification_report.py`（新）、`evaluation/__main__.py`、`evaluation/common/reporting.py` / `reporting_markdown.py` / `real_e2e_acceptance.py`、四套各自报告模块（包括语义 `semantic_evaluation.py`）、`tests/scripts/test_verification_report.py`（新）、`tests/evaluation/test_entrypoint.py`、`tests/evaluation/common/` 与各套件报告测试、`docs/specs/evaluation.md` / `docs/designs/evaluation.md` 及相关 Runbook。

Acceptance Criteria / Evidence:

1. 固定时间 / 提交重复生成仍有唯一 ID；强制重名时旧文件字节不变、返回失败；JSON 与 Markdown 对应同一 run，任一保存失败不能报告完整成功。
2. 四套起止采集顺序经公共入口验证；HEAD / dirty / tracked 变更或输入身份变化、Git 读取失败有明确结果；clean 正式验收只接受 stable / 完整身份。
3. 修改题目内容或实际模型设置能区分；纯语义不连接数据库；Judge temperature 0 单独记录；报告无 Secret / 完整端点 / 连接串。
4. 老报告可读、既有基线比较可用，新增字段不被默认补造成历史证明；正式三套目录不混入辅助 summary JSON。
5. 完整 Evaluation 确定性测试通过，不把不变业务链重新跑付费 LLM 作为本 Ticket 必需证据。

Migration / Rollback: 只增量修改新报告，不重写历史；回退切片仍保留新产物原件；新身份缺失时读取允许、正式资格拒绝。涉及超出 Design 的报告格式破坏时返回 Design Review。

Done When: 全四套生成 / 验收 / 渲染及失败路径闭环，正式 Contract / 文档、Review、Diff 通过并本地提交。

## 06. 本地软件检查与保留的业务验收补齐运行证据

Change Profile: 中等入口 / 报告适配；失败与退出语义风险中等；复用现有执行器，不新增测试平台。

Blocked by: 01, 05

What to build:

- dev test / check 以子任务记录 Design 的命令级 summary，适配 pytest JUnit / Playwright 机器结果和构建检查，不从控制台文字推算成绩。
- 捕获起止身份、实际环境、作用范围、安全参数、退出 / 清理结果与 skipped / 未执行；test all / check 不吞失败。
- 保留 dev 验收与旧宿主真实浏览器兼容入口的独立运行身份；中间状态允许同次更新，最终证据排他发布；共享 RAG 身份按实际配置读取。
- 仅本次资源清理；报告 / 临时目录映射兼容普通 clone、linked worktree、Dev Container；无宿主 Python / Node 新要求。

Owned files: `dev`、`scripts/container_tasks.sh`、`scripts/verification_report.py`、`scripts/verify_container_dev.sh`、`scripts/run_database_tests.py`、`scripts/smoke_web.py` 的证据接入（不扩充用途）、`tests/container_dev_support.py`、`tests/browser_real_reference.py`、`tests/browser_real_support.py`、`frontend/playwright*.ts`、`frontend/test-support/`、`frontend/tests/real.spec.ts` / `container-real.spec.ts` 与必要报告测试、`tests/scripts/` 对应入口测试、`docs/runbook.md` / `docs/specs/container-dev-environment.md`。

Acceptance Criteria / Evidence:

1. test 四类与 check 代表性入口能生成正确 summary；实际无用例计数时 counts null，执行范围准确，失败 / skipped / 未执行不会变成通过。
2. 参数与环境白名单不泄漏凭据；只读源码挂载、无 Docker socket 测试容器、临时资源归属保护保持；缺配置 / 工具 / 写入失败有明确失败证据或未确认提示。
3. test all / check 子步骤失败、进程中断、清理失败与报告冲突均不报告完整成功；故障注入只使用伪命令 / 隔离资源。
4. 业务验收中间 browser.json 仍可按重启 / 清理阶段更新；最终 run 报告不可覆盖，缺 RAG 身份明确未确认而非读取另一位置的旧资产；safe-reporter 不再改写已发布最终证据。
5. clone / linked / Dev Container 路径映射的确定性回归、完整软件 test / check 通过。真实 LLM / 日常环境验收不自动执行，未跑明确标记。

Migration / Rollback: 新证据写 ignored 独立路径，旧报告与兼容入口独有能力保留；APP 已退役路径不重新加入；可回退本切片而不修改历史或日常卷。

Done When: 命令 / 文件可观察行为、失败保存、路径与 Secret 回归、正式说明、Review、Diff 通过并本地提交。

## 07. CI 接入关键数据库与 PDF 检查及证据

Change Profile: 小至中等 workflow 改动；自动门禁风险中等；复用原 job 身份、本地相同软件套件与新 summary。

Blocked by: 02, 06

What to build:

- 在现有 PostgreSQL integration job 内接入 development 数据库套件和真实 renderer，共用必要开发测试环境；保留现有 job 名称和其他检查。
- 使用与本地一致的 fixture / migration / 测试选择及开关；失败非零、有界 job、可得 JUnit / summary 在失败时仍上传。
- 不打包 / 上传业务 APP 镜像、不调用真实 LLM、不修改远端保护规则；保留来源码 API smoke / 前端 build。

Owned files: `.github/workflows/ci.yml`、必要的 `tests/scripts/test_ci_verification.py`（新）、`scripts/container_tasks.sh` 的已有可复用入口（仅如适配确需）、`docs/runbook.md` 与本目标验收记录；不改托管仓库设置。

Acceptance Criteria / Evidence:

1. workflow 结构验证真实调用 development 数据库套件与 renderer，启用正确开关；不是仅 collect 或默认 skip，必要检查失败会使 job 失败。
2. 同一实际执行命令已在本地隔离运行验证；CI 使用临时资源，无日常环境 / 模型密钥；依赖锁、固定工具版本和镜像身份可追溯。
3. artifact 兼容成功 / 失败 / 未完成，缺计数不虚构；正式三套 AI 报告目录不被软件产物污染。
4. 既有 job 名称不变，无应用镜像发布；本地结构 / 脚本 / 全量软件 / 文档检查通过。未获发布授权时托管 CI 明确未执行。

Migration / Rollback: 同 job 内增加步骤，不改变远端门禁身份；workflow 切片可 Git 恢复；失败暂停候选交付，不删除测试换取通过。

Done When: 本地等价命令、workflow / 失败证据、最终交叉文档 / 全量软件检查、Code Review 和 Diff 通过，形成干净本地 candidate；Push / PR 另行授权。
