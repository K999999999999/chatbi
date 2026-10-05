# R3 Ticket 草案

Status: 草案，[当前上下文Readiness](ticket-readiness.md) READY；用户已确认拆分及整体本地实施；正式Tickets见issues/。
Canonical Source: [已确认Spec](spec.md)、[实施设计](design.md)、[完整恢复语义](restoration-semantics.md)、[最终Design Review PASS](design-review-final.md)。上位行为优先；Ticket不另建口径。
Owner: 当前主Agent；持续维护的代码 /migration /测试 /文档由本目标维护者负责。当前同一仓库 /单Agent，无虚构Backup Owner；跨业务 /运行边界问题升级用户，实现不得猜测。
Change Profile: 持续维护 /整体较大 /状态与公共接口高风险；每项是完整行为切片。Delivery同一feat/history-results-v1、同一worktree，按直接依赖连续推进，Review及适用检查通过后本地逻辑Commit。一个目标一个候选 /PR；发布授权独立取得。

六项拆分把完整语义随首个持久成功行为交付，不能先保存无上下文快照再称历史已完成。管理和成果各有独立完成条件；最终验收只核对完整目标，不替代前面每项的测试 /文档 /Review。

## 01 问数自动保存与刷新重开

Change Profile: 持续维护 /较大 /高风险（成功一致提交、认证状态、新Schema与兼容）；Evidence为确定性、API、真实PG及桌面Chrome；Delivery为一个纵向行为，可用多个相关逻辑Commit完成，不拆出独立DB /服务 /UI目标。
Owner: 当前主Agent。
Blocked by: None (can start immediately)

### What to build / Scope

- 首个网页问数从明确发送→私人history受理→既有授权 /Online Query执行→完整认证state与快照一致提交→页面显示；刷新 /退出后重登录从基础列表重开仅读快照。完整恢复state在首个成功轮次存在，续聊交互在02接入。
- 实现Restoration§1–§3 /§5首轮history profile、完整Candidate /Validated条件 /certification /codec、程序批准的semantic binding及当前发布资产闭包；R2引用同一维度映射，旧Bearer /分析任务默认profile保持。
- 实现Design§2 /§4 /§5 /§9：005 /v3对象、Store Port /PG Adapter、begin /finish、5MiB与失败状态、revision /epoch /generation /ExecutionRegistry、单API guard及停止后重启恢复，不把核心一致性推迟到最终验收。
- 新API创建 /执行问数 /header /turn详情 /基础分页列表，严格字段与owner /permission /CSRF；前端URL定位、身份清理、懒加载、旧ResultView /精度 /图表复用。

Out of Scope: 追问 /显式重查、分析history执行、改名 /搜索 /删除交互、成果管理（后续Tickets）；R4–R7、任何新依赖或业务指标。

### Owned files

新增`database/control/005_history_results.sql`、`src/chatbi_control/history.py`、`src/query_api/history.py` / `history_contracts.py` / `history_codec.py` / `history_api.py` / `history_runtime.py`、`src/online_query/semantic_state.py`、`src/semantic/query_bindings.json`及其校验加载；必要修改`src/chatbi_control/database.py`、`src/bootstrap/runtime.py`、`src/query_api/app.py` /响应与身份适配、`src/online_query/contracts.py` / `query_understanding.py` / `query_understanding_llm.py` / `prompt.py` / `service.py` / `service_execution.py` / `retrieval/retrieval_context.py` / SQL Guard、R2 mapping loader /display配置；frontend App /Chat /api /历史基础组件 /snapshot解码与样式。相关`tests/query_api`、`tests/chatbi_control`、`tests/online_query` /semantic、`frontend/tests`。

### Acceptance criteria /验证证据

1. 首次发送成功后刷新、重新登录重开，可读原问题 /表格 /SQL /图表 /说明且理解、模型、业务数据库调用次数不增加；空页面不建记录、登录默认空白问数、身份切换 /迟到响应不泄露。
2. 单值、时间 /分类、实体distinct、1至5指标、过滤、排序 /Top-N /nulls /平局、既有合法单指标聚合筛选完整认证并codec往返。前200项保留业务200而最多返回100且截断，旧相对时间持久化绝对值不跨天漂移。
3. 漏排序 /wrong LIMIT /额外WHERE /HAVING /错误公式或grouping等SQL拒绝，业务数据库0次；不能保存“成功但不可恢复”。旧Candidate六字段 /Prompt /Guard、API请求响应 /默认会话与静态替身构造回归保持。
4. begin写失败业务调用0次；finish回滚 /commit未知不返回成功、不推进已提交context；响应丢失后仅读已提交事实；精确5MiB等于通过 /多1字节拒绝，十进制字符串 /NULL /空值 /日期不丢类型 /精度。
5. 真实PG两连接同history只能受理一个attempt；当前epoch任务运行保持busy，restart旧epoch未确认 /最后成功保持，旧generation不能写回。guard失效拒绝新history执行，无任意TTL提前释放。
6. 真实PG fresh /v2 upgrade /repeat migration、必要权限与缺对象startup拒绝、资源关闭 /持锁连接不回池；同owner operation dedup，跨owner /禁用 /撤权 /CSRF /unknown字段受控无越权。

Evidence: 纯seam与httpx测试、真实PG事务 /初始化报告、确定性桌面Chrome测试；模型输出用替身证明调用边界。真实模型及整体clean报告在06。每份记录关联当前候选 /基线 /覆盖 /结果，失败保留证据并修复。

### Migration / Rollback / Done When

增加型005保留v2标记与数据，不修改用户 /RBAC /业务 /RAG内容，不从旧内存造历史。旧版回滚停止新API、保留v3表 /字节，重新升级仍读。无生产发布 /feature flag承诺；兼容或Schema验证失败停止该切片。
Done When: 上述可观察闭环与适用软件 /PG /Chrome通过；当前上下文Code Review /Diff检查通过；同步正式R3 /Query API /Web及恢复语义说明、Design和Runbook初始化 /单进程恢复规则、roadmap进度或不适用理由；本地逻辑Commit及Ticket Result记载完成，整体R3仍未验收完成。
Result: 未实施。
Comments: 首个切片较大是因为网页成功必须同时满足执行 /认证 /持久化 /恢复，不能横向拆出无完整成功条件的交付。

## 02 历史续聊与完整条件重新查询

Change Profile: 持续维护 /中 /高风险（条件继承、当前定义与多页面冲突）；Evidence为delta /API、真实PG /桌面Chrome；Delivery本地逻辑提交。
Owner: 当前主Agent。
Blocked by: 01（使用持久成功state与当前认证执行 /受理机制）。

### What to build / Scope

- 接入历史追问与Restoration§4严格delta keep /set /clear，基础同槽位替换 /不同槽位叠加 /明确维度替换 /歧义澄清；排序 /业务数量 /聚合过滤 /selection保留或明确更改，不存最新短delta当完整state。
- 先当前相关定义认证比较，再合并 /重新认证。定义真实变更拒绝，相关RAG读取技术失败与定义不兼容区分，无关资产 /显示格式 /build ID变化不误拒。
- 接入所选成功turn的显式requery：同一事务复制来源私有条件并受理新header /turn；创建operation唯一性定位同一目标，生成当前SQL并Guard，原快照不改；不再次理解旧问题 /执行旧SQL。
- stale context提示刷新且不排队、active busy、断连期间占用保持；刷新新revision与对应结果同时加载才可续聊，无自动重发。

Out of Scope: 跨查询比较 /经营分析路由、成果来源重查（05）、新的指标 /SQL功能。

### Owned files

`src/query_api/semantic_revision.py`及history Application /Store /API /codec /runtime、`src/chatbi_control/history.py`、Online Query语义profile /认证 /Prompt /Guard /相关权威mapping、frontend Chat /History /api /解码与状态；`tests/query_api/test_multi_turn_revision.py`及新增history /state /PG测试、`frontend/tests`。不修改旧Bearer默认处理。

### Acceptance criteria /验证证据

1. 过短期TTL /API进程停止后重启，“按销售额降序前10产品”再“改成毛利”保留绝对时期 /筛选 /分组 /direction /10，唯一排序指标同步替换；歧义多目标澄清不推进。
2. keep /set /clear、取消Top-N、维度替换导致悬空排序、聚合筛选指标更换歧义有确定性证据；失败 /拒绝 /澄清后从最后成功继续。
3. 相关口径 /映射 /类型 /Join变化拒绝，无自动指标替换；无关定义、build ID、R2显示修改不误拒；技术不可用CONTEXT_ERROR安全提示。
4. 显式重查产生新history /新真实执行，完整条件同源、旧记录 /快照固定；重复相同operation不多建 /执行，hash不符409，来源删除竞争按受理事务先后裁决。
5. 同context两个页面只一个成功，另一个busy或stale且下游调用0次；未确认页面必须读取新事实，迟到旧请求不能覆盖。API与桌面Chrome验证刷新无执行 /不默默换上下文。

Evidence: 纯delta /认证、API invoke计数、PG竞争与operation /sourcecopy事务、Chrome两页面 /恢复用例；真实当前数据对照在06。
Migration / Rollback: 使用01新增对象，无破坏迁移；失败保持原context，回滚保留快照 /state版本，未知版本不能执行。不改变旧接口生命周期。
Done When: 所有适用检查 /Code Review /Diff通过；同步正式恢复条件 /续聊 /requery Contract和Acceptance证据 /roadmap事实；本地Commit完成，Result记录候选与未验证范围。
Result: 未实施。
Comments: 当前数据重查是明确的新执行，原记录始终只读历史事实。

## 03 独立分析历史、原任务恢复与新任务重查

Change Profile: 持续维护 /中 /高风险（checkpoint与history独立事务协调）；Evidence为Business Analysis /API /真实PG /Chrome；Delivery本地逻辑提交。
Owner: 当前主Agent。
Blocked by: 01（复用完整history生命周期 /codec /runtime /基础列表，不依赖02的问数修订）。

### What to build / Scope

- 网页analysis首次明确发送创建history /服务端run UUID并受理；沿用原问题 /独立业务链，不继承query条件；报告与公开task证据经大小检查持久化后才成功。
- 重开仅读保存状态；原24h checkpoint有效可手动同问题 /原ID新attempt恢复；completed checkpoint但history未提交时仅读原completed结果，不graph.invoke。过期不续用原ID，显式新任务才新history /run。
- 旧Bearer analysis与Web共享owner /run Guard，覆盖graph执行至网页finish，保留内部任务受控重试；runtime失效 /线程未结束不放行同ID。让既有run登记expired接口供04原子删除使用。
- 报告快照独立于checkpoint，既有分析不公开SQL边界保持；未经完成 /有效归因校验的报告不是成功可保存结果。

Out of Scope: 延长checkpoint、问数路由 /共享条件、SSE /取消 /队列、多进程failover、新归因场景。

### Owned files

history Application /analysis snapshot codec /API /Store /runtime、`src/business_analysis/run_execution.py`、原Application /RunStore /contracts必要最小协作、`src/query_api/app.py`旧analysis入口共享guard、`src/bootstrap/analysis.py` /runtime注入、frontend analysis History /Chat /报告解码；`tests/business_analysis` /`tests/query_api` /PG /`frontend/tests`及正式分析 /历史文档。

### Acceptance criteria /验证证据

1. 分析成功→刷新 /重开仅读长期报告 /证据 /图表，不再次执行且不带问数context，清理checkpoint后仍可查看。
2. 未完成重开无invoke；有效期手动恢复原问题 /原ID，completed但history保存失败恢复无graph.invoke；非retryable失败依原Contract受控拒绝、不编造报告。
3. 原ID跨owner /不同问题 /24h过期 /runtime invalid均拒绝；同ID旧API与Web并发只一执行，断连仍busy至真实线程结束，不提前释放。
4. 显式分析重查新history /run，原报告固定；5MiB超限 /finish失败不网页成功，completed事实保留可在期限内明确恢复。
5. HTTP /旧analysis回归、实际PG RunStore和checkpoint生命周期、桌面Chrome状态 /恢复 /新任务交互通过；真实模型对账在06。

Evidence: 原completed branch调用计数、时钟 /归属 /互斥测试、PG run /checkpoint集成、Chrome；软件替身不得宣称真实模型报告通过。
Migration / Rollback: 复用01新表、原analysis run /checkpointSchema不破坏；runtime关闭先停执行。旧API默认不产history，旧版回滚保留长期报告且不延长原run期限。
Done When: 适用验证 /Review /Diff、本地提交、正式分析 /历史恢复Contract /Design /Runbook同步与候选证据记录完成。
Result: 未实施。
Comments: 恢复analysis与重新问数是不同Use Case；两个ID生命周期不混用。

## 04 历史分类管理、搜索、重命名与删除

Change Profile: 持续维护 /中 /高风险（删除防重放、并发 /隐私）；Evidence为API /PG /Chrome；Delivery本地逻辑提交。
Owner: 当前主Agent。
Blocked by: 03（需要两类完整history和analysis run失效能力；01为传递依赖）。

### What to build / Scope

- 统一两类列表按最近更新排序，默认20最多100、kind筛选、字面标题搜索、keyset分页 /筛选hash、详情懒加载；默认首问题截取标题不调用模型。
- PATCH标题 /record revision；DELETE期望revision、active拒绝；清敏感轮次 /state、保留最小tombstone，analysis run登记同Control事务expired，无checkpoint恢复入口复活。
- UI列表 /管理、刷新URL记录删除 /无权访问退回新问数，已打开其他页面迟到响应不重填。

Out of Scope: 全文问题搜索 /文件夹 /分享 /年龄清理 /移动端；独立成果UI在05。

### Owned files

history API /Application /contracts /PG Adapter /必要约束、Business Analysis RunStore同事务失效协作、frontend History /App /api /样式与状态，相关API /PG竞争 /Chrome测试；正式历史管理 /隐私 /删除文档。

### Acceptance criteria /验证证据

1. 两类混合 /分类、默认标题、literal % / _ /反斜杠搜索、排序与分页界限、非法cursor /筛选不符 /长度 /UUID /unknown字段一致错误；无列表下载全量快照。
2. 重命名只影响标题，不改变state /快照 /context revision；旧record revision拒绝，不静默覆盖另一页面修改；恶意标题以文本呈现。
3. begin /delete竞争锁定明确，只能一方先成立；active不能删除，结束后删除旧ID详情 /续聊 /resume全404，原analysis ID旧入口不能复活。
4. 跨owner存在 /不存在 /deleted统一404，撤权 /禁用 /CSRF保持；成功删除后迟到finish或UI响应不能恢复数据。
5. 真实PG删除 /runexpired事务、Chrome两页面 /被删URL /退出换号管理闭环通过。

Evidence: 严格API、真实PG两连接竞争 /同事务回滚、桌面Chrome；无随机sleep作为竞争正确证据。
Migration / Rollback: 沿用01Schema，必要约束只增加。用户主动删除内容不可还原，保留原有独立数据 /业务卷；代码回滚不能复活tombstone。不通过批量删除开发数据验证。
Done When: 正常 /失败 /安全证据、Code Review /Diff、本地提交、正式Contract /隐私边界 /Runbook及roadmap适用事实同步完成。
Result: 未实施。
Comments: 删除历史与删除analysis checkpoint不是同一行为，checkpoint仅沿用既有期限清理。

## 05 具名独立成果与来源删除后的重查

Change Profile: 持续维护 /中 /高风险（独立生命周期与来源 /内容防变）；Evidence为快照 /API /PG /Chrome；Delivery本地逻辑提交。
Owner: 当前主Agent。
Blocked by: 02、04（02提供完整条件requery；04提供两类管理组件与来源删除语义，03为传递依赖）。

### What to build / Scope

- 从成功query turn /完成有效analysis report命名另存，保存相同versioned envelope的独立副本与必要来源说明；名称允许重复、只可改名不能改结果。
- 成果列表 /kind /字面标题搜索 /分页 /懒详情 /重命名 /删除，复用04的输入 /分页和页面规则，保留新的独立owner核验。
- 来源删除不级联、成果删除不影响历史；成果显式requery从自己私有完整条件 /原分析问题受理新history /run，operation去重保持来源独立。
- 正在执行时可另存来源既有成功turn，copy /delete短事务先后裁决；失败 /澄清 /未确认 /无效报告不能另存。

Out of Scope: 分享 /公开链接 /导出 /编辑数据 /图表配置保存 /仪表板；不以来源引用替代必要条件副本。

### Owned files

history与saved-results Application /API /contracts /snapshot codec /PG Adapter、frontend SavedResults /History /Chat /api /解码与样式、相关query_api /PG /Chrome测试、正式成果 /独立生命周期 /重查Contract与Design。

### Acceptance criteria /验证证据

1. 保存成功query和analysis成果内容与所选成功轮次一致、保留原始值 /说明 /截断 /图表 /完成证据；追问、来源改名 /删除、checkpoint清理均不改变成果。
2. 来源删除后从成果完整条件query重查 /原问题新analysis run仍可当前认证执行，新record不覆盖原成果；定义不兼容明确拒绝不改原内容。
3. 不成功turn /未知损坏snapshot /未完成报告拒绝；成果名1–120、同名允许、恶意名文本、跨owner /撤权 /CSRF /revision拒绝保持。
4. active时另存之前成功turn允许且不清busy；copy先完成则删来源仍读，delete先完成则保存404，真实PG两连接无半份成果。
5. 删成果原history仍读，重复 /跨owner统一不可用；详情只公开result不暴露私有state、执行token、AuthContext或checkpoint对象；Chrome双向独立删除 /重查闭环通过。

Evidence: 快照字节 /语义相等、API调用边界、PG copy /delete /dedup竞争、Chrome流程；当前模型 /业务数据验收在06。
Migration / Rollback: 使用01saved_results独立副本Schema，无来源级联FK；回滚保留表 /字节，用户主动删成果不可还原。外部分享 /公开scope变更需重新确认。
Done When: 全部适用检查 /Review /Diff、本地逻辑Commit及正式成果 /历史 /API /Web文档、证据 /roadmap事实同步完成。
Result: 未实施。
Comments: 来源标识只作说明，删除来源不使成果变为失效引用。

## 06 最终候选真实闭环验收与事实源同步

Change Profile: 收敛型一次验收 /中 /高风险证据与交付；维护报告 /Runbook长期保留；Evidence为clean候选 /真实PG /Chrome /三套正式Evaluation与R3真实链路；Delivery本地candidate，远端另授权。
Owner: 当前主Agent。
Blocked by: 05（其依赖覆盖01–04，不能在全部行为完成前声称整体R3通过）。

### What to build / Scope

- 使用既有真实验收入口及安全临时账号扩展R3模型 /检索 /只读DB桌面Chrome：查询 /追问 /排序Top-N /刷新 /重登录 /历史与成果 /独立删除 /重查 /API停止重启；analysis原任务恢复与过期 /完成快照保持。用独立参考SQL /确定性归因核对业务结果。
- 汇总01–05证据，受影响行为 /基线变动重跑；完成失败注入 /真实PG初始化升级重复、运行资源释放 /旧版保留数据回滚、安全与旧API完整回归。
- 最终clean候选运行三套正式Evaluation与统一real_e2e_acceptance；不以小范围R3浏览器闭环替代三套。正式失败报告保留，修复后形成新候选再验收，不挑选成功报告。
- 正式Spec /Design /适用Architecture /产品范围 /README /Runbook /日期化Acceptance /roadmap完成一致性核对，区分需求状态 /当前能力 /不包含范围；后续R4–R7保持实际未交付。逐一记录维护位置或不适用理由。

Out of Scope: Push /PR /Merge /生产部署、R4流式 /R5导出 /R6–R7容量与多副本；未经授权新技术或真实业务数据写入。

### Owned files

`scripts/verify_container_dev.sh`及其现有helper /真实验收入口、`frontend/tests/container-real.spec.ts` /real配置与必要R3用例、受影响软件 /PG /API tests、`reports/evaluation/` /Acceptance报告、`docs/specs/history-results-v1.md` /Query API /Web /相关恢复语义Contract、`docs/designs/`、`docs/acceptance/`、`docs/runbook.md` /`docs/product-scope.md` /`docs/architecture.md` /`docs/roadmap.md` /README、本目录Ticket与Review证据。若验收发现缺陷，仅修复01–05既定owned files和范围并重新Review /检查，不加新承诺。

### Acceptance criteria /验证证据

1. `uv run --python 3.11 --locked python -m pytest -q`、Runbook数据库测试入口、frontend `npm ci` /typecheck /build /Playwright、适用锁检查 /安全检查 /静态检查通过；环境缺失或未运行明确记录，不能以skip称通过。
2. 实际fresh /v2 upgrade /repeat migration、restart /旧generation /checkpointTTL /回滚保留数据、故障保存 /超限 /多页面 /stale /跨owner /撤权等矩阵有当前适用证据；软件seam与真实PG /浏览器证据类型分清。
3. R3真实浏览器完整行为在最终clean候选通过，真实结果与独立业务参考一致；正式报告关联commit、git_dirty=false、RAG /案例集 /数据库身份 /配置边界，临时账号 /Session /凭证清理不伤原用户 /卷 /业务数据。
4. 三套single_turn /multi_turn /business_analysis正式Evaluation按Runbook§9、同一最终clean候选与资源身份全部通过，并由统一acceptance入口核对；另做三次完整多轮稳定性诊断并保留全部结果，诊断不替代正式基线。R3history profile另有真实闭环证据，旧套件不能代替它。
5. 当前上下文workflow-code-review、Diff /Secret /文档链接及roadmap内容一致性核对通过；所有正式事实源与各Ticket Result同步，有适用范围 /剩余风险 /未运行项目的准确报告。

Evidence /候选流程: 先完成实现、Contract、Review及适用事实文档 /确定性证据提交，再固定clean候选运行真实验收。若预验收后回填tracked Acceptance /Ticket结果形成新提交，必须再次固定最终clean HEAD并运行最终三套正式Evaluation /统一acceptance和R3真实闭环，让最终报告严格绑定该HEAD；原预验收仅保留自己的身份，不冒称新HEAD成绩。生成报告使用既有.gitignore下reports/evaluation与reports/browser-real位置；最终验收后不再修改tracked文件补写“当前通过”，实时结果原子记录于Git公共目录。若代码 /Contract /基线改变则修复、Review并形成新候选后重跑受影响检查。最终commit不因只加证据而绕过正式报告expected-commit核对。
Migration / Rollback: 使用隔离fresh /升级测试库和原有明确入口，保留开发卷 /账号 /RAG；旧版兼容演练停止API后切换版本、保留v3数据，恢复当前候选。无实际生产Rollout /feature flag门禁；一旦需要真实用户部署返回发布授权与R6边界。
Done When: 全部01–05与上述适用门禁 /真实验收通过，正式证据身份 /维护位置完整、所有Ticket结果与当前候选可追溯、Code Review /Diff /本地Commit完成，形成唯一clean本地candidate。报告发布目标 /风险 /验证 /实际Auto-merge规则后才能请求PR发布授权；本Ticket完成不授权发布。
Result: 未实施 /未运行验收。
Comments: 真实API凭证与.env只在本地，报告不得泄露Secret；失败必须保留并修复，不通过回退验收门槛完成。

## 依赖与范围检查

直接依赖：01→02；01→03→04；02与04→05→06。无循环；同一主Agent按编号连续执行，不创建额外branch /worktree或独立Agent。六项覆盖Spec全部正常 /失败 /安全 /持久化 /兼容 /验收行为；管理从基础重开到完整管理是同一新Contract内的增量，不删除旧API。

## 确认边界

本文件只供Readiness和用户确认粒度 /依赖；正式issues在拆分确认后生成。拆分确认与完整本地实施授权分别记录，可一次回复同时确认两者。授权完整本地实施后按依赖连续完成全部Tickets、适用真实验收与本地Commit，不逐项询问继续；Push /PR仍另取明确发布授权。

用户本轮确认六项拆分与完整本地实施，包括适用真实验收、Review及Commit；按依赖连续推进，Push /PR另授权。当前正式Tickets见issues/，01实施中。
