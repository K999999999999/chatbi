# R7 本机运行保障实现设计

Status: 已确认Spec的Contract内实现设计；Design复审PASS，见 [复审](design-review-2.md)；未实施。Canonical Source: 行为以 [Spec](spec.md) 为准；本文仅固化Contract内实施机制。Owner: 本目标实施维护者。Baseline: 0c77d80。

## 1. 边界与变更轴

不新增一级业务模块。运行状态快照与共享额度属于现有query_api Application；HTTP/前端展示留在Adapter；依赖探测与模型调用观察在bootstrap/Infrastructure装配。业务Domain、模型Prompt、SemanticQuery、Certified Physical Mapping与SQL Guard不变。

备份/恢复属于scripts和local运维边界，用独立工具容器承载age/PostgreSQL客户端。工具具有受限主机目录和必要数据库管理权限；业务API只读安全状态投影，无迁移凭据/私钥/Docker socket。阿里云通过现有TraceRecorder/OTLP Adapter，不在业务Core引用云SDK。

不为每个状态创建Service/Repository层。最低边界是一个可注入clock/probe的状态快照、一个现有runtime内共享额度租约，以及运维文件/进程Adapter。真实网络/数据库/文件交由Adapter，纯状态规则用确定性测试。

## 2. 公共状态与60秒预算

- `/health`完全兼容。
- 新增`GET /ready`，公开最小`status=ready|not_ready|unknown`与checked_at；ready返回200，其余503；没有依赖细节、额度、模型错误和备份内容。公开返回不执行实时重型探测。
- 新增`GET /api/v1/operations/status`，仅已认证账号。返回version=1、status、checked_at、query_available及安全message；管理员额外获得details，普通账号无details内容（不包含路径/用户ID/错误原文）。备份details包含最近成功时间/逾期/安全失败码，模型details仅安全最近结果/时间；Control DB不可用不能依赖缓存身份暴露管理员内容。
- 状态HTTP显式复用`reject_browser_request(write=False)`与Cookie/Bearer冲突、expected-user校验；该新路径不假定现有业务Trace middleware会覆盖。使用`authenticate_readonly`并检查当前账号/role，不能fallback到会滑动TTL的认证。无身份401、非管理员只获得普通投影；禁用/撤销即时拒绝。缓存身份不作为权限真相。no-store，不新增Cookie，不更新last_seen。
- 每15秒发起一轮后台依赖检查，单轮最多10秒、单个探测有更短connect/read/statement timeout；不重叠、不无界排队。状态超过30秒未更新则unknown。网页每10秒刷新；最坏检查调度+执行+显示35秒，给60秒目标留裕量。
- 检查有有界worker和shutdown；超时中止探测、丢弃迟到结果（generation/epoch），不能由一次挂住的探测阻止下一轮恢复检查；不在API事件循环执行长阻塞。
- 轻量检查验证业务/Control schema marker与catalog、Qdrant必需集合、RAG current/manifest、发布/模型配置来源。首次启动用既有完整门禁；固定只读资产未变化可复用已认证结果，内容/身份/来源变化后重新认证。不能因减少开销取消Spec要求的资产正确性。
- `unknown/not_ready`阻止新的业务受理，格式/认证检查在保护入口之前，HTTP503与稳定`SERVICE_NOT_READY`；字段按既有QueryFailure或HistoryError外壳映射。正常成功/拒绝DTO不变。已持久受理的幂等重放先返回既有状态，不被就绪失败改写成新任务失败。
- LLM最近结果在实际LLM Adapter调用结束处更新（不是HTTP总结果）；只记timestamp/success/安全分类，无原文；超过15分钟显示unknown，进程重启从unknown开始。经销商API错/网络错可记录模型调用失败，后续SQL/保存失败不误报模型失败。
- `./local status`在明确stable API容器内读取600权限的Unix socket安全快照；socket仅容器同UID可读，随API生命周期回收，不创建账号/Session或公开诊断HTTP。复用状态快照，不另建健康真相。容器未运行或旧版本无socket明确未知。
- 网页只在已加载且登录的页面轮询；401停止，后台状态请求不保持登录。API/网络无法访问时显示服务连接不可用而非成功快照；现有历史UI保留，不修改已完成结果。
- 非稳定测试装配可注入ready provider与clock，但稳定运行必须启用，缺少装配fail closed；不以测试分支跳过权限/就绪。

## 3. 同步与后台共享额度

现有ExecutionRuntime内计数逻辑拆为同一最小capacity lease：reserve_owner(owner)/release幂等一次、关闭后不新受理。R4原reserve在容量租约上组合history/analysis lease，原stop controls/events/threads保留。

同步API完成认证后取得同一owner/API租约，原同步分析guard只取一次、不新建持久history/execution、不制造伪history_id；普通同步会话仍沿原ConversationStore。使用原query/analysis执行上下文与总deadline，保留既有单次LLM/SQL timeout与停止语义。若连接断开/外层等待停止，真实调用未结束仍持有额度；不能用future timeout释放活工作。后台也不因为SSE/取消正在停止提前释放。

所有路径finally释放，异常/授权拒绝/调用前失败无泄漏；同步与后台合计每owner1/总4。超额使用现有R4 HTTP429 `EXECUTION_LIMIT_REACHED`，同步QueryFailure错误码扩展同名值并保持原失败外壳，不自动重发/排队。观察与operation重放不加额度。导出维持原runtime与配额，状态仅安全汇总。

Alternative: 给同步单独建Semaphore不能保护跨入口合计，拒绝；把同步改成持久R4 execution会改变旧API生命周期，拒绝。共享容量租约保留两种入口原行为。

## 4. 文件、工具与操作互斥

- age固定v1.3.2 Linux amd64包及SHA-256按Spec；工具镜像内安装age/age-keygen、与现有PG16匹配的pg_dump/pg_restore，构建供应链验证，不在宿主下载/安装新依赖。
- `.local/backup-keys/`700、私钥600；`.local/backups/`700存加密副本；`.local/operations/`700存安全状态/已知副本目录；不写Secret到目录索引。显式`./local init-backup`只在key不存在时生成并从私钥核对公钥，不覆盖已有key；失败/缺key在status显示未初始化。公钥文件和key fingerprint不是凭证。
- 新CLI：`init-backup`、`backup`、`backup-list`、`restore <backup-id>`、`restore-activate <restore-id>`、`restore-recover <restore-id> --previous|--candidate`。backup/restore-id只选可信登记对象，不接受任意archive路径或任意Dockerproject；read-only list/status不取写锁。
- 自动备份由stable `backup`工具服务驱动，无Docker socket；只在stable runtime启动后运行，`restart:no`随local up/down管理，API整体故障也不能自行重新启动API。具体Docker服务是运维Adapter，不是业务模块。
- 手工命令与工具共享同一`.local/operation.lock` inode（flock，对shell与Python fcntl兼容），所有local写操作/新备份/恢复/切换统一互斥，读状态无需锁。工具取锁后捕获实际active binding/release并核对API来源，不以最新build指针冒称当前受保护运行版本。
- 调度以最近成功时间为准，每6小时尝试一次；失败记录下一尝试时刻，最多按6小时重试，启动无副本或超过24小时立即补备份；不会每秒循环真实备份。状态投影在秒级刷新失败/过期，由网页轮询显示。
- 备份作业读取最小credentials/env文件仅在容器内传入客户端，不输出Compose展开配置，不把password放argv/命令日志；工具临时输出受限且进程/退出/信号清理可靠。业务API仅挂`.local/operations/public/`安全投影目录只读（工具所有者，目录755/文件644，仅安全状态，无catalog/配置/路径/Secret），不挂其700父目录；目录挂载保证原子替换文件可见。备份、known catalog、journal、binding及keys均不可读取。

## 5. 在线备份快照与产物有效性

本项目运行期Sales Mart是只读，checkpoint/execution/history/审计在同一Control DB。全局操作锁防升级、migration、恢复和发布配置切换；业务数据库仍使用独立只读快照并核对Seed/catalog/内容指纹前后，不能声称跨库共享同一PostgreSQL snapshot。未知写入或身份改变使备份失败。两库各自一致且只读业务身份固定，保证Control里保存的业务快照对应同一业务资源。

Control DB保持REPEATABLE READ只读exported snapshot，在持有导出事务期间`pg_dump --snapshot`与证据指纹读取使用同一snapshot；dump custom格式，禁止stdout经过可记录日志的通路。业务库以同类独立snapshot dump。数据库roles不由pg_dump默认覆盖：从既有批准角色/grants和加密配置恢复固定角色，记录必要role/schema授权身份；不恢复任意陌生超级用户。

清单format=1包含run/backup-id、实际API/数据库image ID/revision、schema/snapshot/Seed/业务catalog指纹、模型revision与RAG来源、dump/config/发布资产摘要及备份capture时刻。敏感完整指纹/配置在加密包内，public index仅id/time/status/size/hash与安全失败码。

采用受限staging完成dump/manifest/config验证，age用公钥加密；仅工具挂私钥用于**完整解密校验**，临时解密输出不能挂给API。解密后检查固定成员白名单/总大小/路径、manifest摘要与dump TOC可解析；不得先执行任意archive脚本。校验成功后原子rename artifact并写known catalog（目录记录artifact SHA-256/大小/identity），最后更新last_success并清理已登记且超过7天副本；中途失败不登记、不删除旧副本。

age的加密可验证损坏，但不能把公钥加密等同于备份来自授权发送者。只接受本机受限known catalog登记且hash一致的副本，路径/owner/权限/manifest/release身份同样校验；不宣称抵御已经拥有主机操作者/私钥权限的攻击者。不新增自行设计签名/加密协议。

备份校验不等于每6小时都新建数据库做完整恢复；可解析+完整性成功与实际恢复演练证据分开。首次发布必须通过真实空环境恢复演练。磁盘不足、超时、key错误、锁冲突、PGdump或解析失败均有安全状态，不留下公开明文。

升级门禁在停止旧API/migrate之前备份**旧active**，不能因目标image配置已加载备份错误版本；备份失败API保持运行。备份成功也不代表目标版本兼容，仍沿R6兼容检查。Rollback的原兼容门禁保持。

官方依据：[PostgreSQL16 pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html)、[snapshot export](https://www.postgresql.org/docs/16/functions-admin.html)、[age](https://github.com/FiloSottile/age)。

## 6. 隔离恢复、资源绑定与显式切换

扩展既有local工具的资源选择，而不是新增发布平台。版本化`.local/runtime-binding.json`描述active environment id、已登记PG/Qdrant卷、RAG目录、受限配置引用及active release；文件600、原子写入。缺文件默认兼容原R6固定卷/目录/config；严格schema、固定可接受根目录/标签/卷清单，不执行文件中的shell内容。

Compose从该绑定选择外部卷名/RAG与受限env文件，默认仍原名称。local status/down/up/upgrade/rollback/backup全部使用同一解析后的binding，不能只有restore命令知道新卷。volume create/inspect必须核对本目标environment label/id；unknown resource拒绝，不改global Compose identity。

`restore`解密登记副本并核对版本/来源/权限，建立restore-id专用project、空PG/Qdrant卷、RAG目录和独立受限配置；只暴露随机回环临时端口。新PG初始化批准角色/空库后以安全restore mode（不执行archive创建陌生role、owner等越界逻辑）恢复schema/data并重施批准grants，核验完整指纹和权限。恢复不改变稳定环境或开发资源。

撤销恢复出的所有Session；备份中accepted/running执行沿现有epoch/fencing恢复到unconfirmed，历史成功快照/成果保持；不修改完成值/checkpoint原日期。用于恢复核验的临时账号/Session身份独立且尾部清理，不能在指纹证据里把允许的撤销操作误报数据丢失。

固定model缓存只读复用；从备份发布源码/资产身份重建Qdrant/RAG。比较业务/语义/模型来源身份与逻辑结果，不强求重建后的时间戳/物理index字节完全相同。就绪检查/登录/历史成果读取通过后登记candidate verified；未满足30分钟条件或超时不能伪报RTO通过。

`restore-activate`重新核对verified candidate未变化、目标资源归属/port、原stable binding和单写者，记录切换journal（previous/candidate/config/release/阶段）。停止candidate API并确认PG/Qdrant也停，避免两个容器同时挂相同PG卷；再停止原stable API/依赖，原卷/RAG/config保留。原子切换binding后由chatbi-stable Compose附着候选卷/资产/配置，运行既有门禁并启动；稳定HTTP/readiness和数据核验成功才提交journal完成。

中断/失败时journal保留last_success和阶段，状态为恢复切换未完成而非running；不得自动删除卷/配置、自动反向migration或偷偷改回。`restore-recover --previous|--candidate`在锁内由操作者显式选择，确认当前writer停止后再绑定/启动已核验资源。完成切换前后的完整资源清单保存，恢复后两边未完成任务均由各自DB epoch处理，不能共用控制库writer。

保留原环境用于回退，不纳入7天备份自动清理。清理原环境未来单独授权，此目标不提供自动销毁原数据命令。实际稳定activate需要该次资源操作授权，验收只在专用隔离stable clone上演练。

Alternative: 原卷原地DROP/restore恢复简单但无法保护原数据且切换失败无回退，拒绝；把隔离project直接宣称新stable会与固定local命令失配，拒绝。固定stable项目+显式资源binding维持一个用户入口和最小可逆状态。

## 7. Trace边界与云配置

复用TraceRecorder；HTTP admission scope继续产生request trace。后台work另建生命周期覆盖实际执行的scope，用不可变安全trace carrier/Link关联受理trace，而非跨线程复用已关闭HTTP root对象。一次业务尝试/恢复有新trace，operation/execution/run通过批准属性关联；观察SSE不提交新业务。Adapter层处理OTelContext，不向Domain传SDK对象。

分析/LLM/导出span仅记录实际步骤；导出独立worker的创建/生成/回收由父进程受控span覆盖，不把独立worker完整异常加入Trace。扩展安全span/属性白名单，不放raw strings、SQL、密钥或内容。

Compose传递明确的OTel配置白名单：enable、HTTPS OTLP endpoint、service version/revision、资源environment、受限headers；在local清理shell环境覆盖后读取稳定配置，不能继承开发endpoint/headers。Trace内容采集硬关闭；状态refresh/probes不调用LLM、不产生大量请求链路污染用户业务性能基线。

Batch exporter队列/timeout/shutdown有界，失败警告只有安全分类；云状态并非readiness业务门槛。初始软件用in-memory exporter验证真实span生命周期；最后用户配置的阿里云实际接入才能记云验收PASS，不依赖历史截图。

## 8. 验证与交付边界

沿Spec测试矩阵，每个纵向切片都有对应软件/隔离集成/文档门禁，不能把所有安全验证留到尾部。clock/probe/snapshot/transporter/资源命令提供真实边界可注入seam，避免测试专用业务分支。

最后clean image执行Windows真实入口、备份/恢复/切换/回退、60秒故障/恢复、权限与无保活、Secret与资源归属、阿里云Trace及单用户容量/RTO报告；选择多个代表用例记逐次耗时和CPU/内存峰值，不在少量样本上声称可靠p95/SLA。

正式Spec/Design/API/Architecture/Runbook/Observability/Acceptance/Product Scope/roadmap按适用范围同步；最初只保留scratch规划，不提前改正式Contract。未授权主机重启/永久IDM/稳定数据切换，不在验收中执行。

无需新增业务migration即可保存运行/备份绑定状态到本机受限文件。若实施证据要求改变schema/权限或稳定一级边界，返回Spec/Design审查。实验若需要真实资源/配置变更，先定义实验及授权，不以Design写入代替验证。

## 9. 实施细化：实际来源与锁的交接

手工/升级前备份由已持有operation.lock的local进程核对实际运行API/PG的Docker image ID、revision、内嵌compatibility与配置快照，写入受限source目录，再调用工具的host-locked入口；该入口不重复获取同inode的flock。自动调度自行取得同一锁，并通过同UID600的共享Unix socket核对API仍在运行及source_commit；它不能使用首次R6兼容的离线来源。工具没有Docker socket。local持锁进程和拥有受限目录的工具均属于已有本机操作者信任边界。

API仅新增一个独立700运行socket目录的挂载；安全public投影仍单独只读挂载，API无keys/catalog/source目录。socket的来源字段仅供本机诊断，HTTP投影不新增发布详情。R6首次备份允许local在锁内直接核验旧API身份；自动备份要求新socket证据且不得重用R6离线捕获。

配置/发布资产在dump前后摘要核对；手工修改导致漂移时拒绝登记。source记录实际运行release，不读取latest build作为实际版本。固定成员、完整解密校验、known catalog与密文原子发布维持原设计。

共享socket同时给出当前RAG pointer/manifest安全摘要；R7手工与自动路径核对live来源及资产一致，R6离线兼容仅首次显式备份。
