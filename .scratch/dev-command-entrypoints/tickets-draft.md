# Ticket 草案

Status: 用户已确认七项拆分及全部本地实施；正式Tickets保存在issues/，本文保留拆分依据。
Canonical Source: [Spec](spec.md)定义行为；[设计](design.md)定义机制；[Design Review](design-review.md)为PASS。
Owner: 全部切片由当前主 Agent连续负责，实现后的维护归所属模块；不新增跨团队Owner。Contract、安全或目标变化返回用户，局部实现失败由Owner修复；不通过弱化验收推进。
Delivery: 同一目标、同一branch/worktree，默认本地Commit；远端发布未授权。先按依赖完成全部，再给整体候选。每项有独立回归与Review，不逐项要求用户继续。

## 共用Done When与证据要求

每项完成行为、失败分支和适用正式文档更新；测试结果关联实际候选/未提交范围和基线；主上下文Code Review、Diff及相关链接检查完成才提交。未运行或不适用验证明确记录。共享dev/Runbook文件按顺序编辑，不并行写入。Roadmap不得把草案或局部通过写成已完成。

所有新入口先Expand再迁移调用者；旧入口删除须有消费者检索和独有能力去向，证明不足保留非推荐入口并记录原因。普通工具/测试不取得Docker socket，不调用真实LLM；真容器验收的路由测试用替身。运行实验只使用专属临时项目/账号；真实日常环境不做删除或改密。无依赖升级、无Schema迁移，无日常部署/Feature Flag。

## T01 分类帮助、统一目标与标准应用运行

- Change Profile: 短期CLI扩展；中等切片；配置与资源选择风险；路由回归+真实Compose；本地交付。
- Owner: 当前主 Agent；长期归开发/部署工具。
- Blocked by: None (can start immediately)。
- What to build: 八类根帮助和分组帮助；共享Bash目标解析；保留现有dev根命令；app build/up/down/status/logs/infra/migrate/create-admin/prepare-model/build-rag/check，沿用标准初始化及就绪顺序。
- owned files: dev、共享scripts环境辅助文件、tests/scripts容器命令测试；docs/specs/container-dev-environment.md、container-deployment.md与Runbook所属章节。
- Acceptance Criteria: 所有帮助无.env/Docker且无副作用；错误参数先拒绝；dev/app项目/env/override/端口/UID/host路径正确且互不影响；app up不隐式初始化；down保留卷；app check只读verify；旧命令失败退出不退化。
- 验证证据: Docker替身检查参数与退出码；真实Compose config覆盖默认/定制/override；专属临时dev/app项目验证启停保留与初始化顺序，模型/LLM使用替身，不声称真实业务ready。
- Migration / Rollback: 先增入口再改推荐文档，原Compose直接调用保留；回滚CLI切片不改变卷。未知目标结构拒绝。
- Done When: 全部app操作及已有根操作完成兼容回归，目标解析成为后续唯一装配来源，正式文档说明环境选择。

## T02 定向检查、测试与评测报告校验

- Change Profile: 短期验证CLI扩展与旧runner迁移；中等；验证身份/漏测风险；确定性测试+隔离PG；本地交付。
- Owner: 当前主 Agent；长期归container_tasks/测试与evaluation。
- Blocked by: T01。
- What to build: check docs/python/boundaries、固定Ruff入口、evaluate validate；保持test各suite及all；核对旧run_database_tests独有profile/失败清理/路径能力并迁移引用。
- owned files: dev、scripts/container_tasks.sh、scripts/run_database_tests.py、对应tests/scripts/evaluation；Runbook与容器开发Contract。不改模型/案例口径。
- Acceptance Criteria: 完整check保留全部范围；定向结果不能混报；数据库ci/development覆盖及隔离清理保持；软件测试不真实问LLM；报告commit/RAG/cases不匹配拒绝，无DB/LLM调用；linked worktree提交和dirty不失真。
- 验证证据: 路由/无调用回归、报告校验回归、实际普通clone和linked worktree Git可见性；隔离数据库两profile；旧runner与新链能力逐项对照，覆盖不足保留并注明。
- Migration / Rollback: Expand新子命令，证明coverage后迁移旧runner；原参数保留；代码回滚不影响业务数据，保留迁移台账。
- Done When: check/test/evaluate公开入口完整，旧runner处置有证据，CI可直接复用；定向及完整验证各自如实记录。

## T03 Hook与Harness协作入口

- Change Profile: 短期CLI扩展；小切片；Git本机身份风险；临时clone/worktree；本地交付。
- Owner: 当前主 Agent；长期归本机Harness/Hook工具。
- Blocked by: T01。
- What to build: hooks install直接委派既有安装器；harness check容器内只读执行，真实Git目录挂载复用T01目标/路径能力；报告本机ERROR/REVIEW原语义。
- owned files: dev、scripts/container_tasks.sh或共享辅助文件、tests/scripts Hook/Harness路由测试；Runbook。既有Python检查规则尽量不修改。
- Acceptance Criteria: 无业务.env；Hook无需Docker并拒绝其他有效hooksPath；Harness不访问远端或写状态；共享common-dir/指定repo及普通clone/linked worktree正确；退出码原样。
- 验证证据: 临时clone和linked worktree的测试记录，不改日常其他clone配置；只读元数据前后对比、未知参数及缺镜像分支。
- Migration / Rollback: 保留既有脚本直调；回滚入口不自动回写hooksPath，本切片仅测试临时clone。
- Done When: 两个协作操作无业务环境依赖，真实Git身份与只读边界有证据。

## T04 只读诊断与结构导出

- Change Profile: 短期维护CLI；中等；诊断误报/源文件权限风险；安全探针+隔离catalog；本地交付。
- Owner: 当前主 Agent；长期归operations和metadata。
- Blocked by: T01。
- What to build: doctor dev/app安全状态汇总与超时；metadata export容器执行，继承现有结构范围/参数/输出。
- owned files: dev、scripts诊断装配/现有check_dev_qdrant及metadata入口适配、tests/scripts及metadata测试；Runbook、所属正式Contract。
- Acceptance Criteria: doctor不启动/修复、无LLM调用、不改账号；失败/未知不ready、不泄密；两目标资产路径准确；export只catalog SELECT、宿主UID输出三份结构投影、不修改Semantic或隐式build-rag。
- 验证证据: 成功/缺失/故障/超时/脱敏回归；临时项目只读检查前后状态；隔离catalog与临时输出目录权限、结构Contract回归。
- Migration / Rollback: 保留metadata内部模块调用；原Qdrant脚本适用直调能力先兼容；回滚CLI不能替用户恢复已经导出的源文件，测试只写临时目录。
- Done When: 正确诊断与导出闭环，包括只读和显式源文件写入边界。

## T05 开发项目数据重置

- Change Profile: 短期维护入口迁移；中等；高风险不可逆删除；纯校验+真实专属临时资源；本地交付。
- Owner: 当前主 Agent；长期归dev维护。归属或停止验证失败立即停止，不扩大删除集合。
- Blocked by: T01。
- What to build: reset postgres/qdrant宿主编排与容器内校验/迁移；复用现有卷验证和删除确认；迁移旧宿主执行边界。
- owned files: dev、scripts/reset_dev_postgres.py、reset_dev_qdrant.py、compose_volume_reset.py及必要Bash编排、tests/scripts重置回归；Runbook与容器开发Contract。
- Acceptance Criteria: 仅dev；明确目标和范围；取消/EOF/标签错/外部卷/停止失败不删除；先停止API/Web及目标服务并复核归属；仅删目标卷；PG基础Seed+完整迁移、无管理员；QD无索引；API/Web保持停止，其他资源不变。
- 验证证据: 拒绝路径确定性回归；真实临时项目删除确认、卷身份、停止保护、权限与重新迁移；保留另一卷内容与其他项目身份对照。测试资源带专属标签，清理也验证归属。
- Migration / Rollback: 先提供新入口再迁移旧CLI消费者；代码可回滚，卷删除不可回滚，不承诺自动恢复；测试失败只清理有归属证明的测试资源。
- Done When: 两种重置完整闭环及安全拒绝证据，旧调用处置明确，无Docker socket扩权。

## T06 dev/app管理员紧急恢复

- Change Profile: 新本机安全Contract；中等纵向切片；高风险认证/事务；Service/TTY+真实PG竞争+两目标装配；本地交付。
- Owner: 当前主 Agent；长期规则归authorization，配置装配归Bootstrap/operations；未决安全问题返回设计审查。
- Blocked by: T01。
- What to build: recover-admin显式环境/用户名、最小容器装配、交互CLI、专用AuthService原子恢复及强制审计；相关已有用户写路径统一User锁/刷新，仅服务并发保护。
- owned files: dev及目标辅助、src/bootstrap/commands.py与恢复装配、src/authorization/auth_service.py、src/chatbi_control/admin.py及对应tests/bootstrap/authorization/chatbi_control/scripts；Dockerfile仅如打包所需；Bootstrap/认证/容器Contract、产品范围/架构及Runbook适用段落。
- Acceptance Criteria: 只已有active admin，角色/其他用户/历史不变；Hash+必须改密+清锁+撤销全部Session+独立审计同事务；审计失败全回滚；现有登录/角色/改密/禁用竞争有序；actor非被恢复用户；运行DB身份、不依赖API/LLM/QD/RAG；已有匹配镜像/初始化PG要求，无隐式build/start/migrate；TTY和0/1/2、敏感输入及提交失败安全。
- 验证证据: Service状态与审计回归、真实PG双连接屏障竞争及权限测试；真实伪终端验证回显拒绝/输入中断；临时dev/app专用管理员互不影响、缺无关LLM配置仍可恢复、错误目标与缺镜像拒绝。不能用SQLite或Docker替身替代行锁和最终容器证据。
- Migration / Rollback: 无Schema迁移；原create-admin/Web重置职责保持；新CLI代码可回滚，已恢复密码/撤销Session不可靠代码回滚复原；只操作测试账号。任一原子性/身份测试失败停止交付。
- Done When: 安全恢复完整闭环、并发回归无旧Session逃逸、两目标真实证据与正式本机信任边界文档齐全。

## T07 容器验收入口与旧操作最终归档

- Change Profile: 短期验收入口与已盘点迁移收尾；中等；错误环境/丢失验收风险；路由与断言对照；本地交付。
- Owner: 当前主 Agent；长期归验收脚本与Runbook。
- Blocked by: T01。T02–T06不是开工依赖；全目标Done需全部完成。
- What to build: verify dev默认isolated、显式real与verify app委派现有脚本；核对前端test:real断言与现行验收覆盖，处理start-dev.ps1及旧推荐引用；完成24/24台账和总帮助/README导航。
- owned files: dev、tests/scripts验收路由、frontend/package.json/real配置与断言（仅迁移需要时）、start-dev.ps1、必要验收脚本兼容点；README、Runbook、inventory与适用container Contract。成熟验收脚本不重写。
- Acceptance Criteria: 原报告/退出/clean要求/费用/专用账号清理保持；错误目标/多余参数不启动；直接脚本可用；独立SQL、追问、分析断言有明确去向，覆盖不足保留非推荐入口；内部/CI专用脚本均注明原因；不新增日常Smoke改密。
- 验证证据: 路由替身与费用说明、旧新能力逐项对照、消费者rg检索；对应确定性回归、文档/链接检查。此次不自动真实LLM验收，未运行须明确，不套用历史报告。
- Migration / Rollback: 新入口Expand→引用Migrate→证明后Contract；原断言及历史证据保留。可回滚入口和迁移引用；无日常数据操作。
- Done When: 验收命令可用、全部脚本归属与旧能力去向齐全；全部切片完成后整体Code Review与适用回归、Roadmap事实核对，形成本地候选。

## 依赖与执行顺序

T01 → T02、T03、T04、T05、T06、T07。实际由同一Owner按T01至T07顺序连续实施，共享文件顺序写入。没有循环，没有外部发布依赖；前一container-auto-restart候选不混入本目标。
