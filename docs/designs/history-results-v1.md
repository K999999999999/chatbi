# R3 历史与成果实施设计

Contract：[History Spec](../specs/history-results-v1.md)。已确认设计的本地实现；验收见 [Acceptance](../acceptance/history-results-v1.md)。

## 1. 方案与边界

网页长期状态由PostgreSQL历史记录唯一裁决，旧Bearer `/api/v1/query` 保持原请求 / 响应和默认短期状态。新增历史接口不调用旧 `_authorized_query` 的内存create / commit：复用现有授权服务、语义修订、OnlineQueryService及BusinessAnalysisApplication，只把网页状态提交替换为历史事务。

| 边界 | 职责 / owned files |
| --- | --- |
| History Application / Contract | `src/query_api/history.py`、`history_contracts.py`、`history_codec.py`：当前身份、受理、成功 /失败提交、来源及恢复策略；独立DTO与一个HistoryStore Port，不依赖FastAPI / ORM |
| History API Adapter | `src/query_api/history_api.py`、现有app / browser / response：HTTP、当前Cookie或显式Bearer身份、CSRF、输入 /响应；不生成SQL或定义指标 |
| PostgreSQL Adapter | `src/chatbi_control/history.py`：事务、行锁、约束、版本 /占用及快照存取；没有业务公式或权限策略 |
| 当前语义认证 | `src/online_query/semantic_state.py`、query_understanding / revision / prompt / Guard及必要contracts / service_execution / RetrievalContext改动：结构化语义的严格codec和当前业务定义 /认证映射比较；不存储历史、不依赖Control DB |
| 执行资源 | `src/query_api/history_runtime.py`、bootstrap runtime / lifecycle：单API进程启动归属、在执行请求登记、重启恢复和资源释放 |
| 分析运行互斥 | `src/business_analysis/run_execution.py`：当前进程同owner / analysis_run_id执行互斥；旧analysis入口与历史入口共享Guard，保持原图与checkpoint类型 |
| Web | 新History / SavedResults组件与解码器，修改Chat / App / api / styles；复用ResultView / AnalysisReport，清除身份私有状态 |

这些是现有Application与Adapter职责内的文件，不新增一级业务模块、第二条执行链路、数据库产品或依赖。HistoryStore的方法围绕完整操作（begin_attempt / finish_attempt / copy_result / delete_history等），不暴露任意SQL、ORM Row或“先调用A再B”的隐式事务。

### 方案比较

| 方案 | 成本与问题 | 决定 |
| --- | --- | --- |
| 保留网页内存状态，执行后另写历史 | 改动少，但保存失败时内存已前进；重启后需协调两个真相；不能满足F1 | 不采用 |
| 长事务从受理到模型结束，锁整段对话 | 数据提交直观，但模型执行期间持有PG事务 /锁，断连恢复难，读取 /另存 /关闭成本增大 | 不采用 |
| 持久历史真相，短事务受理与完成，条件提交 | 一次明确的Store边界管理版本与执行身份；模型期间释放行锁；可确定性证明失败 /删除 /迟到行为 | 采用 |

并发控制依赖PG实际事务和行锁：[PostgreSQL 16 Explicit Locking](https://www.postgresql.org/docs/16/explicit-locking.html)、[Transaction Isolation](https://www.postgresql.org/docs/16/transaction-iso.html)。选择已确认的现有数据库；不引入Redis、后台队列、分布式锁服务或通用工作流引擎。

## 2. 数据模型与唯一权威

新增 `database/control/005_history_results.sql`，新Schema标记 `chatbi-control-v3`，保留v2。表名与下列逻辑字段为实施Contract：

| 表 | 内容与关键约束 |
| --- | --- |
| `history_records` | UUID id、owner_user_id FK users、kind(query / analysis)、title、first_question、created_at / updated_at、creation_operation_id / creation_operation_hash（UNIQUE owner / operation）、context_revision(从0开始)、record_revision、next_ordinal、last_success_turn_id、active_turn_id、execution_generation、analysis_run_id(analysis唯一)、deleted_at；kind /非负revision CHECK |
| `history_turns` | UUID id、history_id FK、ordinal、operation_id、operation_hash、question、request_id、attempt_input（重查受理时复制的私有来源条件，不作为成功state）、status(accepted / succeeded / failed / unconfirmed)、runtime_epoch、execution_generation、时间、public_error、snapshot_version / snapshot JSONB；UNIQUE(history_id,ordinal)、UNIQUE(history_id,operation_id) |
| `saved_results` | UUID id、owner_user_id FK、kind、title、record_revision、时间、snapshot_version、来源history /turn标识（纯说明，无级联FK）、snapshot独立JSONB副本；内容不随重命名变化 |
| `history_runtime` | 固定单行key、runtime_epoch UUID；启动恢复与完成条件引用当前epoch，无不断积累的每次启动记录 |

历史header不再复制一份last_success_state：last_success_turn_id指向不可变成功轮次快照中的私有query_state；成功快照与指针在同一事务提交。外键在所有表创建后添加，last_success指针先清空再删除轮次，避免删除循环；跨历史指针通过复合(history_id,turn_id)约束 /Store校验拒绝。active_turn与last_success不能指向其他历史。

索引：owner /kind /updated_at /id支持列表；history_id /ordinal支持轮次分页；analysis_run_id唯一；来源用户与operation唯一性由Store和上述约束共同检查。业务数据行不写入销售只读库。

删除采用短事务清除标题、first_question、成功指针及所有轮次快照 /问题，保留最小已删除header（id、owner、kind、analysis_run_id、deleted_at及防重放版本）。列表 /详情 /续聊一致排除deleted。analysis运行登记在同一Control DB事务标记expired，原ID不能被旧分析接口当成新任务或重开已删除历史；不改动与网页历史无关的旧运行。成果没有级联引用，已独立复制的内容保留；删成果物理删除该成果行。

## 3. Codec、5MiB与当前业务兼容

`snapshot_version=1`持久化envelope包含kind、公开result及私有query_state /语义认证来源与来源轮次问题（问数）或原分析问题（分析）。问数来源问题取成功轮次自身，不取历史第一轮；成果复制保留它，独立重查从完整条件和该轮问题重新认证。旧版v1查询快照即使缺少可选来源问题仍可展示；另存成果重查时使用中性提示，并以私有结构化条件作为唯一业务依据。只有经过程序白名单编码的公开字段进入result；不保存AuthContext、凭证、异常堆栈、模型Prompt或完整checkpoint对象。

问数公开result沿用request_id / sql / columns / rows / row_count / truncated /可选result_metadata，但不使用旧conversation_id作为长期编号。分析公开result沿用analysis_run_id / mode / report / task_results，继续不公开SQL。抽取纯payload构造函数供旧响应与新codec共用，旧接口输出字段 /默认null省略行为不变。

应用先完成全部payload编码，再以UTF-8、ensure_ascii=False、紧凑JSON、拒绝NaN /Infinity计算整个持久化envelope大小；允许大小等于5×1024×1024，超过拒绝。成果复制同一envelope，名称 /来源索引列不改变其数据。Decimal /日期沿用现有Pydantic JSON公开编码，不先转JS浮点；结构化时间额外保存原时区与绝对start /end，不在重开时重新解释“昨天”等相对文本。

私有state为state_version=1的CertifiedQueryState，含经程序认证的完整结构化业务条件、绝对时间及相关定义来源。排序、业务row_limit、实体distinct /选择、既有合法聚合过滤不可遗漏；[完整结构化恢复Contract](history-query-restoration.md)明确profile兼容、字段 /delta、当前发布资产认证、SQL Guard和覆盖证据。网页成功须证明完整状态与执行SQL一致，不能以“成功但不可恢复”作为实现降级。旧Bearer与分析内部任务默认profile保持，R2 result_metadata只作展示，不能充当恢复证书。

当前定义比较由Online Query所属语义认证规则负责，仅核对相关已发布事实，不使用旧SQL、未发布metrics.json、模型解释或全局mtime /build ID替代。认证发生于生成SQL前；旧状态在续聊 /重查前与当前认证定义比较，执行SQL逐项检查完整条件，程序认证的状态与公开结果一起提交。

codec未知版本 /损坏：安全提示不可用，仍能管理 /删除，不执行未知状态、不产生成果。相关业务定义 /认证映射实际改变时HISTORY_CONTEXT_INCOMPATIBLE；技术性资产不可用沿用CONTEXT_ERROR，不混淆原因。R2缺可选展示元数据可表格降级，不使已认证恢复状态失效。所有已支持业务请求必须覆盖完整恢复，不得因设计省事缩减正常合法范围。

## 4. 两阶段短事务与失败窗口（F1）

网页第一次明确发送时先创建私人history（记录first_question、确定性标题，analysis由服务端生成run UUID），得到history_id后更新页面URL；创建不是模型执行。新对话空页面不创建DB记录。若创建响应丢失，用户可在列表找到“尚未提交”的记录；不会自动重发。客户端creation operation_id保证同一明确创建请求不会产生多份记录，不用它决定归属。

一次执行步骤：

1. 当前认证 /query.execute /历史归属校验；Runtime有效性与本进程ExecutionRegistry登记。分析额外获取共享run Guard。
2. `begin_attempt`短事务以 `FOR UPDATE NOWAIT`锁header，排除deleted；校验expected_context_revision、当前无active_turn；插入accepted轮次并写active_turn /新generation /runtime_epoch。提交失败或提交结果未确认均不进入模型执行；不自动重做begin。
3. 查询读取header的最后成功state并校验当前业务定义，调用既有revise_semantic_query（有上下文）或首轮理解；现有AuthorizedQueryService.authorize /execute_authorized与OnlineQueryService完成当前数据查询；内部require_restorable=True全程保留，旧入口默认False。分析调用原analyze。期间无PG行锁 /长事务。
4. 完整编码公开result、state和认证来源，校验5MiB；在 `finish_attempt`短事务锁header并核对active_turn、epoch、generation、当前归属、非deleted以及最新权限是否仍允许交付。
5. 成功：写succeeded快照，更新last_success指针 /context_revision并清active；失败：写受控failed状态，保持last_success /context_revision并清active；一起提交后才返回对应响应。公共payload只在当前合法身份下发出。
6. 在整个begin→finish区间的finally中结束本地Registry与分析Guard；前端断连不会在业务线程仍执行时释放。

`context_revision`仅成功轮次递增，作为追问基础版本；`record_revision`用于元数据修改 /删除的乐观冲突，重命名不改变续聊语义。固定锁序header→turn→run登记，避免删除 /完成 /成果复制反序。

| 失败窗口 | 行为 |
| --- | --- |
| begin提交前 /提交结果不明 | 不执行下游；恢复读取accepted记录，再按无本地执行者标记unconfirmed，不假定请求曾执行 |
| 下游明确失败且history可写 | failed快照，最后成功state保持；HTTP沿用该业务错误 |
| 编码失败 /快照超限 | 明确错误，原成功指针保持；用小型失败状态结束attempt；不返回业务成功 |
| finish明确回滚 | 返回HISTORY_SAVE_UNCONFIRMED；保留原state，本地attempt结束后恢复时标记unconfirmed |
| finish提交结果不明 | 返回HISTORY_SAVE_UNCONFIRMED，不自动重试业务 /重做提交；后续只读若发现succeeded则展示已提交结果，否则按unconfirmed恢复 |
| finish已提交，HTTP响应丢失 | 历史succeeded与新state已成立；重开只读恢复，不回退已提交成功，不再次执行 |

前端收到未确认错误先阻止基于旧页面提交，再由用户刷新history确认最新state /revision；不能只看HTTP失败就认定数据库一定没提交。

## 5. 执行占用、重启与恢复（F2）

`execution_generation`单调增加，attempt UUID加runtime_epoch确定唯一提交者。active字段只是持久事实，不依赖浏览器等待状态。NOWAIT锁竞争、active占用和旧context版本统一拒绝，调用方显式刷新；不自动排队执行。

Runtime在单API进程启动时持有专用PG会话advisory guard（独立psycopg连接，不借出连接池），固定key由实现常量唯一保留。使用try-lock，已有owner时拒绝第二个API进程启动；不改造成多worker方案。取得guard后以事务更新runtime_epoch，将前epoch的accepted轮次标unconfirmed、清active并递增generation；last_success不变。

正常受支持的重启须先停止原API进程（包括原分析 /checkpoint执行），再启动新进程；Compose重启 /开发reload及Runbook验收核实这个顺序。advisory guard只阻止常规重叠启动，不能把数据库连接断开当成旧进程 /工作已停止的证明，不承诺故障切换或多进程并行可用性。

guard连接失效时Runtime永久标为无提交权，拒绝新的历史执行与分析恢复，不自动换epoch /重连后清占用；当前本地任务仍登记至实际线程完成。恢复需停止旧进程并正常启动，不能任意TTL到期放行旧执行仍活着的同ID分析。服务仍运行但history写失败：Store恢复后对当前epoch的accepted轮次只在本地Registry确认任务已结束时标unconfirmed，旧generation作废；仍执行的任务保持active。

所有完成更新同时校验数据库epoch /generation /active UUID。旧回调更新0行即无提交权，不插新history或新turn补救。history已deleted同样拒绝；前端账号epoch与URL定位变化阻止迟到响应回填。

## 6. 分析checkpoint协调（F3）

history_id /analysis_run_id /turn_id（attempt）为不同概念；一个分析history绑定一个服务端run UUID及不可变原问题。每次手动恢复新attempt，不创建新analysis_run_id。

| 历史状态 /原run | 手动恢复 |
| --- | --- |
| active且本地工作未结束 | 409 HISTORY_BUSY，不调用原analyze |
| unconfirmed /可重试failed，原run未过期 | 当前身份核验后新attempt，原问题 /原ID调用原analyze |
| run已完成但history未成功 | 原analyze的COMPLETED路径读取已有checkpoint结果，编码并提交history；不得重新graph.invoke |
| 原run过期 /问题不符 /归属不符 | 受控拒绝，无自动生成新ID |
| history已成功 | 只读成功快照，不恢复模型；显式重查才新history /新run |
| history已删除 | 404；同事务run登记expired阻止原ID恢复；独立成果仍读 |

旧Bearer分析入口与网页入口共享当前进程AnalysisExecutionGuard，key为服务端owner subject /run UUID；Guard覆盖整个执行及网页finish，不能仅在graph.invoke返回后提前释放。Guard在旧 `_authorized_analysis` 与HistoryApplication执行边界获取，原analyze内部不二次获取；归属不同的owner key不冲突，后续原RunStore仍拒绝跨owner，不因观察busy而得知他人任务信息。此互斥不改变旧请求字段 /TTL；旧API不会自动产生history。

原BusinessAnalysis内部受控Task重试保持；新的Guard不对失败自动重做请求。当前单进程下不允许同ID的旧API与历史恢复并发修改checkpoint。Runtime失效后不恢复同ID，直到旧进程已停止；epoch验证保护网页state，单进程生命周期保护checkpointwriter，不能用仅history CAS声称保护checkpoint。

历史删除清除自己的报告及state；最小run登记用于防重放，原checkpoint按24小时既有机制清理。完成历史 /成果读取完全不查询checkpoint，因此过期清理不丢已保存报告。

## 7. 公开API与兼容（F4）

新增 `/api/v1/histories`、`/api/v1/saved-results`命名空间。旧 `/api/v1/query`及其严格未知字段规则保持，网页迁移到新接口；不会以是否Cookie登录暗中改变旧接口语义。新接口允许当前本地账号Cookie或显式Bearer认证，默认行为改变仅发生在显式调用新接口时。

所有写操作经现有CSRF /same-origin校验，所有操作核验当前有效账号、query.execute及owner；owner_user_id只取AuthContext.user_id，客户端user_id /SQL /state /analysis_run_id不接受。跨owner /已删除 /不存在统一404 HISTORY_UNAVAILABLE；认证401、权限403、CSRF错误沿用原Contract。新history管理错误由Application自己的枚举表示，不塞入SQL Guard业务错误定义。

| Method /Path | 严格输入 | 输出 /语义 |
| --- | --- | --- |
| POST `/histories` | kind、first_question、operation_id(UUID) | 201 header；只建记录，analysis生成run ID；同owner相同operation /内容重复返回同header，不执行 |
| GET `/histories` | kind可选、q标题可选、limit默认20 /1–100、cursor可选 | 200 items /next_cursor；无快照；只当前owner |
| GET `/histories/{id}` | 无body | 200 header，包括context_revision、record_revision、active状态、最后成功turn、can_continue /can_resume；无整个聊天快照 |
| GET `/histories/{id}/turns` | limit /cursor | 200轮次摘要分页，按ordinal升序；明确next_cursor，不附大快照 |
| GET `/histories/{id}/turns/{turn}` | 无body | 200安全轮次详情，公开snapshot /error；不返回私有query_state |
| POST `/histories/{id}/turns` | question、operation_id、expected_context_revision | 同步执行问数；200本次turn /当前revision /公开snapshot，失败对应HTTP+history /turn标识 |
| POST `/histories/{id}/resume` | operation_id、expected_record_revision | 同步原分析手动恢复；首次分析也使用此执行入口（服务端原问题 /run ID） |
| POST `/histories/{id}/requery` | query须source_turn_id；operation_id | 新建history并同步显式重查；query取服务端完整条件，analysis取原问题 /新ID；返回新history身份 |
| PATCH `/histories/{id}` | title、expected_record_revision | 200新header；只改标题 |
| DELETE `/histories/{id}` | expected_record_revision | 204已删除；执行中409，重复访问404 |
| POST `/saved-results` | history_id、turn_id、title | 201独立成果；只成功turn /完成报告 |
| GET `/saved-results` | kind可选、q /limit /cursor | 200成果摘要分页，无快照 |
| GET `/saved-results/{id}` | 无body | 200公开成果snapshot /来源说明 |
| PATCH `/saved-results/{id}` | title、expected_record_revision | 200新摘要；结果不可改 |
| DELETE `/saved-results/{id}` | expected_record_revision | 204；不影响history |
| POST `/saved-results/{id}/requery` | operation_id | 新建history并显式执行，原成果固定 |

上述路径均带`/api/v1`前缀。history创建operation_id存入header并加(owner,operation_id)唯一约束；执行operation_id存入turn，hash包含mode /问题 /原成功版本 /动作 /来源。重复已完成operation只返回已提交状态，不再次执行；accepted返回busy，unconfirmed要求读history后由用户明确创建新operation，hash不匹配409。客户端只在明确点击发送 /恢复 /重查时生成operation_id，网络层不自动重试；X-Request-ID仍只是追踪标识。

重查使用独立的 `begin_requery` Store操作：当前身份下锁定来源并复制完整envelope中的私有条件，在同一受理事务创建新header及accepted turn；creation hash含来源类别 /来源ID /source_turn_id。新header的last_success为空、context_revision=0；来源条件仅放在attempt_input，不冒充新历史的已成功状态。由(owner,creation_operation_id)唯一约束定位重复请求的同一新history；完成重复返回同一结果，未确认不再次执行。来源随后删除不影响已受理副本；首次受理前来源已删除则404。来源历史行锁只覆盖复制受理，不覆盖新模型执行；lock顺序按来源→新header→turn，复制后不再锁回来源。普通POST创建与重查共享creation唯一空间，hash不匹配返回409。

稳定分页使用owner过滤后的keyset cursor，history /成果按(updated_at DESC,id DESC)，turn按ordinal ASC；cursor包含排序键和筛选hash，改变kind /q后重新开始。q为trim后最长200字符、标题按字面子串搜索并转义SQL wildcard；cursor严格编码，非法400。移动记录导致下一次完整刷新重新排序，不承诺跨更新分页的永久快照隔离。

标题trim后1–120字符，历史默认first_question前120字符，不调用模型；first_question /question沿用既有有效非空语义，新增接口上限8192字符。非法unknown字段 /enum /UUID /长度 /分页统一400 INVALID_REQUEST。新Web输入也标明限制；旧API长度默认不变。成果同名允许，record_revision用于避免静默覆盖其他页面改名 /删除。

错误envelope沿用request_id /error_code /error_message，加可选history_id /turn_id；不含snapshot或内部reason。补充映射：HISTORY_BUSY /HISTORY_STALE /HISTORY_OPERATION_CONFLICT→409；HISTORY_UNAVAILABLE→404；HISTORY_CONTEXT_INCOMPATIBLE /HISTORY_SNAPSHOT_UNAVAILABLE /HISTORY_RESULT_NOT_SAVABLE→422；HISTORY_SNAPSHOT_TOO_LARGE→413；HISTORY_STORAGE_UNAVAILABLE /HISTORY_SAVE_UNCONFIRMED→503。业务失败沿用原error_code /HTTP，新接口envelope附服务端标识便于读取；不返回成功数据同时声称保存失败。

## 8. 管理与Web状态

更新request helper支持GET /POST /PATCH /DELETE，写操作保留browser标识 /用户匹配header；不能把helper的userId当归属。旧GET /POST调用默认不变，已有R1 tests保留。

网页问数 /分析沿用独立模式；history /成果列表入口均为当前账号私人。URL只定位当前history或成果ID，刷新先验证身份再取header /分页turn；不在localStorage /sessionStorage存私有聊天或凭证。重新登录清除历史定位、默认空白问数。打开history根据kind选择展示，不把analysis当query续聊。

query Entry展示使用新QuerySnapshot（不要求旧conversation_id），ResultView仍消费TableData；AnalysisReport复用原解码与校验。header /turn列表 /单条快照分别加载，服务端当前revision与已显示快照一同保存；不会默默刷新revision后仍让用户在旧结果上追问。

执行期间禁用发送、模式切换、新对话及删除当前history；已完成结果仍可展开 /另存。失败后明确区分failed与unconfirmed；busy提示等待，stale提示刷新，context incompatible提示新对话，无自动新ID /重发。刷新不会自动轮询恢复模型执行；用户手动刷新读取状态（R4负责更细进度）。

成果复制短事务锁来源header、确认归属与成功turn，复制immutable envelope到独立行，允许active期间复制既有成功turn；删除与复制竞争以事务先后裁决：复制先完成则成果保留，删除先完成则来源404。删除不会通过迟到UI响应重新填充记录。

## 9. Migration /启动 /回滚（F6）

005使用IF NOT EXISTS或等价幂等约束检查，migration由既有有序 `src.bootstrap migrate`执行；不在业务请求建表。新表grant最小SELECT /INSERT /UPDATE /DELETE，history_runtime相应SELECT /INSERT /UPDATE；FK /唯一 /CHECK约束完整；schema_migrations只由迁移账号写版本。`chatbi_app`不获Control DB权限。

verify_control_schema新增v3及新表 /索引约束 /运行账号权限检查，旧checkpoint检查保持；缺任一关键对象startup拒绝。bootstrap构造Store /runtime guard /shared analysis Guard，注入API与Application；失败按ExitStack逆序清理；正常关闭先停止新请求并结束业务线程，再unlock /关闭专用连接、关闭Store资源 /existing engines。不能把持有session advisory lock的连接直接返回通用池。

已有库升级只新增对象，账号 /RBAC /Session /审计 /业务数据 /RAG不改；不从旧内存或checkpoint伪造历史。旧v2记录保留，新clone直接安装v2+v3；重复migration不丢历史 /成果 /旧运行。

本地版本回滚：停止新API后运行旧版本，保留v3表 /数据；旧版本仍看得到v2标记且只访问其原对象，不降级或删表。旧网页不提供R3，但重新升级后数据可再读；这是本地兼容验收，不宣称生产R6完成。无真实流量发布 /feature flag /分批生产切换承诺。

## 10. 可测试性与受影响边界

| F项 | 确定性seam /实际证据 |
| --- | --- |
| F1 | HistoryApplication注入Store与下游：begin失败无execute、finish回滚旧state、commit后响应丢失只读成功、大小 /编码失败、无双重truth |
| F2 | 真实PG两个连接竞争begin /delete /copy、epoch /generation旧token拒绝；注入本地Registry仍running /已结束 /guard失效；实际单API进程停止再启动 |
| F3 | 同run旧API /Web Guard竞争、completed→无graph.invoke、未完成原ID恢复、删除标expired、过期拒绝、checkpoint清理后成果仍读 |
| F4 | httpx公开API：严格字段、状态版本、统一跨账号404、permission撤销 /CSRF、分页 /字面搜索 /操作ID复用、旧API字段与默认行为 |
| F5 / F7 | 完整恢复语义的字段 /delta /当前资产 /SQL条件一致性及排序 /Top-N /entity /既有聚合筛选；原始数值 /绝对时区 /相对时间跨天codec roundtrip；来源定义变化拒绝、无关定义不误拒、未知version不执行，未知展示说明原表格降级 |
| F6 | fresh PG与v2已有库升级、重复migration、权限 /缺对象启动拒绝、回滚旧版保留数据、关闭guard连接 |

每个ticket包含纵向API /UI或状态行为，不先完成所有DB再接所有业务。无新依赖 /lockfile版本，无新增真实业务指标。最终按Spec完成桌面Chrome、真实模型 /数据库R3闭环、三套正式Evaluation与统一身份验收；设计复审不代替这些实际结果。
