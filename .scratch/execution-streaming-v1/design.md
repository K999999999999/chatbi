# R4 实施设计

Status: [最终 Design Review](design-review.md) PASS；首轮发现已修订；Ticket 01 实施中。
Owner: 当前主 Agent
Baseline: `2019443020bb7a20a8c3d1a578a613544ad8148b`
Canonical Contract: [已整体确认 Spec](spec.md)；设计只细化其行为；实施授权依据见 Spec Decision Record 与实时工作状态。

## 1. 当前事实与方案比较

当前 `HistoryApplication` 在 `HistoryRuntime.executing()` 中同步受理 / 执行 / 提交。`PostgresHistoryStore` 以 history 行锁、active turn、epoch / generation 和成功快照事务保证单一成功上下文；`AnalysisExecutionGuard` 已供旧 API 与历史共享。保持这些机制，增加执行尝试的可观察状态。

| 方案 | 成本与边界 | 选择 |
| --- | --- | --- |
| 请求内生成 SSE 并同时执行 | 接入较短，但连接取消可能取消生成器，无法证明关闭页面后继续；受理丢失与跨页查看难协调 | 不采用 |
| 独立队列 / 执行进程与持久事件流水 | 可支持分布式，但增加队列、调度、故障恢复与部署 Contract，超出单进程目标 | 不采用 |
| 单进程受控 worker + 原历史事务 + 共享当前快照 | HTTP 受理后与连接解耦，明确占用 / 取消 / 提交，重连恢复当前快照；资源生命周期在 bootstrap 统一持有 | 采用 |

没有新数据库、框架、SDK 或一级业务模块。现有 `src/query_api/` Application 隐藏执行生命周期，Infrastructure 仍只实现 Port。模型 / SQL 业务不进入 HTTP / worker 调度器。

## 2. 模块与依赖

| 位置 | 职责与最小新增 seam |
| --- | --- |
| `src/query_api/execution_contracts.py`、`execution.py` | DTO、状态及完整受理 / 查回 / 停止 / 观察 Use Case；复用 HistoryStore 的受理和提交，不引入第二份成功状态 |
| `src/query_api/execution_runtime.py` | 单进程额度、worker 所有权、时钟 / 停止信号、活跃执行快照、订阅与资源回收；可注入调度器 / 时钟验证，不依赖 HTTP |
| `src/query_api/execution_api.py` | 仅 DTO 校验、CSRF / 身份、状态 JSON / SSE；无 SQL / Prompt / 业务步骤 |
| `src/query_api/history.py`、`history_contracts.py` | 抽出可复用受理与执行已受理尝试；执行执行期间的成功 / 失败提交继续由 History Application 裁决 |
| `src/chatbi_control/history.py`、拟新增 `execution.py` | 同一 Control DB 短事务内受理、停止标记、历史快照与执行终态提交，隐藏行锁 / CAS；Store 不裁决权限或公式 |
| `src/authorization/auth_service.py` | 验证原 Session 的只读检查能力，复用用户 / Session / 权限规则，不通过请求对象保活 |
| `src/online_query/` 既有 Application / Adapter | 可选停止 / 阶段反馈 Port，保持语义→物理映射→SQL Guard；SQL Adapter 隐藏连接中断细节 |
| `src/business_analysis/` | 节点 / 查询任务反馈、停止传播、报告流式解码；状态图与原 checkpoint 流程保持 |
| bootstrap / API lifespan | 装配、停止新受理、停止观察、drain workers 后释放业务资源 |
| `frontend/src/` | 执行 DTO / SSE 解码与 reducer；Chat 的发送 / 重查 / 恢复切换为受理与观察，复用既有最终结果组件 |

在线查询不得 import `query_api`、HTTP 或 Control DB。通用停止 Port 放在既有 Online Query contracts，只有 checkpoint / 受控停止和阶段反馈；分析文字 Observer 放在 Business Analysis contracts / reporting 所属边界，不让 Online Query 认识报告字段。回调 / Control 作为可选执行参数传递，不存入 QueryState、快照或 LangGraph checkpoint；旧调用默认无 Control，返回 DTO 不变。

取消 / 超时是专门的受控停止信号，所有已有 broad `except Exception`、Task 错误转换、LLM retry 和 Graph Adapter 必须先识别并传播，不能吞成普通失败后再继续 / 重试。LangGraph context 放运行期 Control / Observer，state 只放原可序列化业务值。Trace 继续做可观测性，不承担执行状态裁决。

## 3. 数据、身份与兼容迁移

使用 `database/control/006_execution_streaming.sql`，新增 `chatbi-control-v4`，保留 v2 / v3 标记与全部旧表。复用 `history_turns.id` 作为 execution_id：一次受理就是一个 turn / 执行尝试，分析 run 与恢复后的新 turn 仍是独立身份。

新增 `history_executions`：`turn_id` PK / FK、history_id（复合 FK 校验归属）、owner_user_id、operation_id、request_hash（UNIQUE owner / operation）、mode、operation_kind、status、stop_reason、stop_requested_at、started_at、deadline_at、finished_at、epoch / generation。FK 使用 ON DELETE CASCADE，只清除随历史删除的执行元数据；owner /operation和turn内受理身份必须一致，Store事务检验。执行状态为 accepted / running / stopping / succeeded / failed / cancelled / timed_out / unconfirmed；stopping 由 reason 区分用户取消、超时、授权失效和进程停止。只保存最小生命周期元数据，不复制正式结果、问题、凭证、AuthContext、草稿或完整事件。

原 history turn 状态保持 accepted / succeeded / failed / unconfirmed：运行 / 停止中映射 accepted；cancelled / timed_out 映射 failed + 专用公开 error；执行状态行提供细分原因。成功快照与 last_success 指针仍只在原事务提交。旧历史无 execution 行，读取 / 保存 / 续聊按 R3；R4 列表 / 详情 DTO 以可选 execution 身份关联当前 active turn。

迁移只创建新表 / 约束 / 索引 / grant 与 v4 marker，不改原 turn / run 的 CHECK。取消分析用现有运行登记的 expired 状态阻止原 run 再 claim，明确是取消封锁而非延长 / 重新计算 24h TTL；R4 的 cancelled 原因在 execution 行中保存，旧分析入口也会被 registry 拒绝。原 checkpoint 不作为新执行的成功证明。

执行行和其历史生命周期一致：历史删除仍先排除活跃 worker，清除 turn / snapshot 时先清除 execution 行；成果保持独立。已保存正式结果不依赖进程内 registry。Terminal 内存快照在 worker 与订阅退出后回收，后续查状态由 PG 还原，无永久内存执行表。

启动 verifier 检查 v4、对象、关键列 / 约束 / 权限；初始化入口显式迁移，新请求不执行 DDL。旧 v3 二进制在保留 v3 marker 的 v4 数据库上需有实际兼容证据；不能因为新增表就猜测 verifier 一定兼容。

## 4. 受理、去重、额度与 worker 交接

1. Interface 验证当前身份与写操作，取得不含 Request 的运行期 Session 校验引用；Application 完成初始授权 / 审计。
2. 先按 owner / history / operation 查询已有受理身份并核对完整请求 hash；重复返回原 execution 状态，即使其占额度或 revision 已前进也不再次受理。新创建 / 重查按原 owner / creation_operation 唯一键查回新历史。
3. Runtime 在短 admission gate 中检查可用额度并暂时保留；analysis还须先取得共享 AnalysisExecutionGuard 的 run lease，再执行原 HistoryStore 受理并同事务插入 execution 行。新/旧API共用 acquire/release，原 executing上下文只包装同一lease；lease可在受理线程获取、由worker finally释放，只有Runtime能转交。Guard忙则受理前返回busy。临界区不持有模型、RAG 或 SQL 调用。history 行锁 / 唯一键负责存储正确性，内存 gate 只管理单进程额度与 worker 交接。
4. 将受理身份、已认证输入和 session checker 交给受控 worker，成功调度后返回 202 + 身份。worker 数等于配置的全局执行额度；进入 scheduler 前已保留额度，不向 executor 填入超过额度的待执行请求，不建立业务排队功能。
5. DB 受理失败回收预留额度 /run lease，不调度；受理已提交但调度失败，持久化受控失败后释放，原操作仍可查回，不能再次受理。若写失败也不确定，则保持 fail closed / 未确认并协调原受理身份，不删除幂等键再试。
6. worker 使用已转交run lease，不二次获取共享Guard；重复受理不重新获取lease。worker 进入 HistoryRuntime 的活跃登记必须覆盖“已经受理、尚未开始业务”的窗口，避免 GET reconcile 把待启动尝试标为未确认；注册 / 调度 / 去注册由 Runtime 原子交接。旧历史同步入口访问同 active turn 返回 busy，不绕过后台执行。

配置 `CHATBI_EXECUTION_MAX_PER_USER=1`、`CHATBI_EXECUTION_MAX_TOTAL=4`，要求正整数且 per-user ≤ total；错误启动失败。时限固定为已确认 query180s / analysis1200s，从受理时间计入 worker 交接，monotonic clock 裁决当前进程 deadline，PG 时间用于重开说明，不用于接管旧进程。

取消 / 停止中占额度；同操作重发不再占额度。worker finally 真正结束后一次释放；成功 / 失败 / 未确认处理不重复释放。旧同步 `/api/v1/query` 不新增 R4 额度承诺，但同 analysis run 仍受已有共享 Guard 和 registry 封锁，不绕过已取消运行。

## 5. 停止、提交与分析 checkpoint 协调

采用 PG 行锁与条件提交；统一锁顺序 history → execution → analysis registry，epoch / generation 校验在同事务。Runtime signal / 内存快照有自己的短锁，不在持锁时调用 Provider / SSE；callbacks 复制后出锁调用。

| 操作 | 原子裁决 |
| --- | --- |
| request_stop | 锁 history / execution；成功已提交则返回 succeeded；已有 stop reason 不重复改变；否则持久化 stopping / reason。用户取消分析时同时把原 run 置 expired，使历史和旧接口均不能恢复。提交后才 ACK / 发停止信号 |
| finish_success | 编码 / 5MiB 检查与重新鉴权后，事务校验 epoch / generation / active turn / 无 stop；snapshot、success pointer、revision 与 execution succeeded 同事务；已有 stop 则拒绝成功提交 |
| finish_stopped | worker 已退出所有下游调用后，同事务提交相应非成功 history error 与 execution终态，清 active turn，成功指针不变；再释放 Runtime额度 |
| DB 提交结果未知 | 不把内存状态猜成成功；当前身份查询原 execution / turn，以持久化结果为准；无法查证则 unconfirmed，不能自动重执行；本进程worker已退出后的reconcile同事务更新execution /turn为unconfirmed并清active，不能只改turn留下running执行行 |

成功和停止以获取存储裁决锁的顺序决定；取消已受理后不得提交成功。完成事务提交后取消只能读到 succeeded。结果准备、内存未来状态或 checkpoint 完成都不占先。

定时监视器检查总时限、只读原 Session / 当前权限与 HistoryRuntime guard；signal 至少在每业务步骤前后、每重试前、每流式增量处理前后检查。SQL Adapter 注册当前连接的 best-effort cancel；旧数据库端 statement_timeout 继续生效。SQL 取消回执不等于服务器已停止，只在执行函数返回后 finish_stopped。

模型调用没有可靠的通用立即中断能力：非流式 invoke 等待现有单调用 timeout / 返回；流式在迭代边界观察停止并在同 worker 关闭 iterator / 响应；不从其他线程对正在运行的 generator 调用 close，不把取消 Future 当作取消调用。即使下游迟到返回，停止 signal 与 PG stop 条件都阻止后续步骤和成功提交。

Graph 的停止不进入普通失败的 mark_completed 路径；用户取消的 expired registry 保持，不清成新 run。取消与 registry 初次 claim 有竞争时，受理 / request_stop 同事务先为原 run 建立 owner / question / 原期限一致的注册，再把它置 expired；未进入 Graph 的取消也不能被旧接口作为新 run 创建。非取消的超时 / 授权失败保留既有 TTL / 手动恢复边界，不自动续跑。

分析完成 checkpoint 后、历史提交前收到取消，仍由 stop / success 原子裁决；若 stop 赢则封锁该 run，不从 completed checkpoint 另行读成网页成功。旧入口共享 AnalysisExecutionGuard，worker 真正退出前不解锁；页面执行终态不能提前释放 run Guard。

## 6. 原 Session 检查与事件安全

已核实 `AuthService.authenticate_session()` 更新 last_seen_at / expires_at，`BrowserIdentityProvider` 调用它并强制 `X-ChatBI-User-ID`。新增 AuthService 的只读 Session 校验 seam，复用同一有效性 / 用户 / RBAC规则，不更新或撤销 DB Session。提交 / 取消这样的用户写操作仍使用现有滑动认证。

提交时将原 cookie凭证转为不输出 / 不持久化的私有校验引用，闭包只由 Runtime 持有，不捕获 FastAPI Request；观察接口读验证传入 cookie，worker读验证原提交登录。原始凭证 / hash 不进入 DTO、PG execution 行、logs 或 checkpoint；reader 结束后释放引用。

每个 SSE 业务帧发送前读验证订阅身份 / owner / query.execute；状态 / SSE重连不续期。业务 worker 在步骤与定时检测、成功提交前读验证原登录；授权依赖不可用 fail closed，不发送数据或假称授权继续有效。鉴权通过复用策略规则，正常业务受理 / Task /提交继续记录适用审计；不为每个 token 伪造查询执行审计。

没有新文字时按连接控制周期检查授权，不能只有 token 到达才发现禁用。授权失效使用不含业务载荷的 auth_lost 控制帧后关闭；前端清私有内容，若连接异常没有该帧，则状态 / 当前身份查询确认。数据库不可用视为未能验证，停止数据输出；不以异常文本泄露内部信息。

## 7. HTTP 与事件 Contract

全部 `/api/v1` 前缀，新增独立接口，已有 R3 同步路径保留作为兼容入口，网页迁移到新执行接口。DTO extra forbid，沿用 UUID、8192问题字符、revision / 来源校验，不接受客户端指定 owner、deadline、SQL 或模型参数。

| 接口 | 输入 / 输出 |
| --- | --- |
| POST `/histories/{id}/executions` | query: question / operation_id / expected_context_revision；analysis: operation_id / expected_record_revision；202 execution身份 / 状态 / history header（重复可返回原终态，不执行） |
| POST `/histories/{id}/requery-executions` | operation_id、query 来源 turn；原条件复制后新history + 新execution，返回202 |
| POST `/saved-results/{id}/requery-executions` | operation_id，来源成果当前鉴权 /复制，返回新history + execution |
| GET `/executions/by-operation/{operation_id}` | 当前账号下查原受理（包含普通提交 / 创建重查）；不带业务执行副作用；查不到404 / 可观察受理未确认，不自动重发 |
| GET `/executions/{id}` | 当前身份 + owner下的持久状态、history / turn / run、stop reason、deadline与可公开错误 /最终结果定位，不下发私有续聊条件 |
| GET `/executions/{id}/events` | 当前 snapshot + SSE帧，终态发最终定位后结束；不用 Last-Event-ID 推定持久日志存在 |
| POST `/executions/{id}/cancel` | 空JSON body；202 stopping 或200已存在终态，幂等；成功终态不被改写 |

操作编号查回要求 owner级唯一定位：新R4 executions在同owner operation_id空间唯一；原R3 turn内相同编号允许历史重复不能导致模糊查回，查回仅查询R4受理表。使用§3已定义的owner /operation /request_hash，复合FK与事务检验保证history/turn一致，仍不保存凭证。重查与普通请求共用新R4唯一空间；creation hash与受理hash包含操作类别 /来源 /问题 /revision，不混淆旧creation空间。

事件 version=1；统一 envelope：execution_id、history_id、turn_id、sequence、draft_generation、type、payload。sequence在同进程同execution中单调递增；generation在报告重新生成时递增，快照给出已覆盖的sequence与完整当前草稿。旧事件可忽略，未来 / 缺口必须重取snapshot，不能盲目append。

| type | payload / 行为 |
| --- | --- |
| snapshot | status / stage / counters / stop_reason / draft六字段 / final定位；覆盖≤sequence的增量，原子取当前版本 |
| progress | 真实阶段 / 已完成唯一 task数 / total，报告内子查询细阶段不污染顶层进度 |
| text_delta | field（六类白名单）、列表项index或null、offset、text；只追加到同generation指定位置，不允许通用对象路径 |
| draft_reset | 新generation及原因model_retry；清前次草稿，原execution不变 |
| terminal | 持久状态及公开结果定位 /受控错误；清草稿的非成功类型，持久查询仍是最终依据 |
| auth_lost | 无业务载荷，停止连接、清页面私有状态 |

所有新增 /api/v1/executions 路径明确纳入app浏览器来源校验、request_id /Trace与no-store中间件；事件Adapter同时处理只读身份检查，不能因为已有histories路径获保护就省略新路由。SSE响应设置Content-Type: text/event-stream、Cache-Control: no-store、X-Accel-Buffering: no；此header不代替目标环境真实代理验收。

错误envelope沿用request_id /error_code /error_message，加公开history_id /turn_id /execution_id定位：EXECUTION_BUSY /HISTORY_STALE /HISTORY_OPERATION_CONFLICT→409；EXECUTION_LIMIT_REACHED /EXECUTION_SUBSCRIBER_LIMIT→429；EXECUTION_UNAVAILABLE→404；INVALID_REQUEST→400；鉴权沿用401 /403；未能验证或存储不确定沿用503。已受理执行的cancelled /timed_out /业务失败由GET/SSE状态返回200与终态错误，不假装新的POST请求失败或自动重发。业务终态error沿用现有受控码，额外EXECUTION_CANCELLED /EXECUTION_TIMEOUT只用于R4，旧QueryFailure公开枚举不为取消扩张。

心跳每15秒用SSE comment；后台停止 /deadline /原Session检查每1秒一次并在业务边界再检查，SSE每业务帧及每心跳检查订阅授权，不作为业务进度或期限续期。UTF-8解码与SSE解析覆盖chunk任意分割 / CRLF / 多行data，未知版本 / malformed事件不当作成功，关闭并查询原状态。事件不传未验证SQL、原始JSON、分析底层SQL、内部reason或快照private state。

前端用 `fetch` + ReadableStream 解析 SSE，保持现有 `X-ChatBI-User-ID` 与 same-origin cookie。原生 EventSource 无自定义header接口，不能直接套用现有身份校验，也不把用户ID或cookie塞到URL替代认证。浏览器 abort只终止观察fetch，取消执行必须走POST。

## 8. 快照衔接、有界缓冲与网页

Runtime给每个active execution一份快照，阶段 / task counters / draft generation /当前文字由单writer在短锁内更新。订阅初始化在同锁注册游标与取snapshot；订阅方不持锁等待网络。

每execution共享一个ring，最多64帧 /1MiB，文字单帧最多16KiB按Unicode边界拆分；订阅者仅保存游标，不各自复制无界队列。游标落后ring时发送最新snapshot替换积压，原子快照衔接按§7；不无限queue /静默丢字。服务端批合并文字片段后发送仍是真实增量；慢读不阻塞模型线程。停止 /终态同样以完整snapshot可恢复，不要求保留全部历史event。只缓存active execution草稿，受现有快照5MiB上限约束；超限按结果过大受控失败，不截断。

允许多个页面观察同一执行。连接管理每active execution最多8个订阅，连接结束finally解除；全局active execution仍受配置额度保护。终态事件查询直接读取PG，不保留终态订阅或新永久cache。超过订阅上限429，仅拒绝该观察请求，不终止任务。快照最大为5MiB草稿+元数据，浏览器单SSE data帧解析上限6MiB，越界终止观察并查询状态；生产性能不据此承诺。观测连接的资源拒绝只停止该订阅，显示连接不可用 /重试查看，不终止业务执行或释放执行额度。

网页新增单一执行reducer负责身份 /sequence /generation /阶段 /草稿 /终态，现有Chat继续负责模式 /历史定位和最终结果组件。发送 /恢复 /重查返回受理后进入观察，取消按钮保持到确认停止；相同账号执行占用仍限制发送 /切换等现有等待交互，草稿可编辑，既有结果可看 /保存。

切换身份、退出或清页面时abort观察并清除所有私有草稿 /URL状态；退出导致原Session撤销，worker随后按原授权失效规则停止。重登录默认新问数，可从私人历史重开；不在localStorage /sessionStorage写草稿或凭证。已受理operation ID只作页面内恢复提示，失去页面内编号后仍可从后端history关联找回，不保存私人问题到浏览器持久存储。

重新连接先状态 / snapshot，不重新POST。失败重连按有限等待间隔更新连接中断提示；任何自动重连都只访问read接口。terminal成功再读现有turn公开快照并按R2 /R3解码，读不到显示结果未确认不重新执行。UI generation不能拼接两次模型输出，auth_lost /明确失败 /确认取消清本次draft。

## 9. 真实模型流式与结构解码

已核实锁定 `langchain-openai=1.6.0` 有stream迭代与响应上下文，`psycopg=3.3.4` 有cancel_safe；本机代码不是实际Provider支持流式的验收证明。保持现有Prompt、model /endpoint、max_tokens、temperature、max_retries=0与use_responses_api=False；不新增依赖或默默更换模型。

报告summarizer新增可选Observer路径：有R4 observer才调用model.stream，同一尝试逐chunk收集完整原始JSON并增量解码六类文字；无observer使用原invoke。最终两条路径共享原JSON对象 /字段 /引用校验和BusinessAnalysisReport构造，不建立弱校验的第二报告入口。

原始JSON累积缓冲最大5MiB，公开草稿同样最大5MiB；超过受控结果过大失败，不截断继续成功。增量JSON字符串解码器仅识别顶层允许字段 /列表项，处理跨chunk引号、反斜杠、unicode surrogate、空项、列表顺序和字符串边界；不得用regex截取原始字符串、eval或把模型key变成任意对象路径。已解码且完整的Unicode文字可提前展示，JSON结构仍是未验证candidate。完整输出再经严格解析：重复key /字段歧义不得让草稿与最终对象静默使用不同值；无法安全解码则受控失败并清draft，而非回放invoke结果伪造stream。

每次provider exception的重试前发送draft_reset /generation增长；累计attempt仍同deadline，校验失败无重试。stop信号不被provider retry catch吞掉。Provider不支持stream时受控失败，记录实际风险，不偷偷调用invoke再打字展示。真实验收需记录首段文字先于最终成功事件，不以网络chunk数量冒充模型增量。

## 10. 生命周期、重启与回滚

bootstrap持有ExecutionRuntime：成功装配后开放受理。API lifespan的finally在现有 analysis_guard.drain() 之前先调用execution_runtime.close_admission、signal_shutdown、stop_observers、drain；monitor在drain期间继续处理已有worker的停止与只读鉴权，全部结束后才join monitor并shutdown worker pool。随后HistoryRuntime /AnalysisGuard drain，才清app引用、退出runtime资源context并关闭checkpointer、Control DB、RAG、HTTP客户端与Trace。直接资源注入分支同序；未完成装配时也按已取得资源注册的清理闭包执行，不能等到只进入analysis_factory才有执行清理。失败装配按同样逆序清理。进程停止属于结果未确认恢复边界，不伪称用户取消或擅自延长checkpoint。

HistoryRuntime仍持原单进程advisory guard，不用总超时回收另一进程。重启必须证明原API进程已停止；新epoch中将未确认active turn /execution按原规则标unconfirmed，清活动指针 /更新generation。不恢复草稿或自动启动worker；原cancelled run registry始终expired，仍拒绝恢复。completed历史 /独立成果正常读取。

运行guard失效停止新受理，活跃worker禁止成功提交并请求停止，未确认状态保持；不在相同进程透明重建guard接管旧任务。

回滚演练：先停止v4 API与全部worker，再运行v3基线；保留v4表 /marker、R3历史 /成果 /原卷；cancelled run已用v3可识别expired封锁。v4新增FK明确级联清除最小execution元数据，因此v3删除历史不被新表阻断；演练必须验证原历史/turn与execution同时消失、独立成果保留；v4重启将缺失原history的execution视为不可用，不能复活。回滚不需要DROP数据，不回退模型 /业务数据 /RAG。

## 11. 验证 seam、文档与交付

- Runtime独立时钟 /可阻塞worker /可控停止适配器验证受理交接、stop /success先后、真正结束才释放额度；不以真实sleep或Future.cancel推断安全。
- Store真实PG双连接 /可控barrier验证同operation并发、跨账号、revision、停止提交事务、registry封锁、初始化 /升级 /重复、旧版保留数据回滚和迟到CAS。
- 字符串解码与reducer按实际不同chunk拆分、escape /Unicode /字段 /重试 /旧generation /序号缺口验证，断言可观察文字与最终对象，不测试私有调用次数代替行为。
- HTTP /浏览器模拟真实网络、响应丢失、并发页面、断连 /重连、无token时撤权、终态丢失；验证X-user-ID、Cookie /CSRF与只读Session期限不变化。各Profile真实/替身证据分别记录。
- 最终clean候选跑已确认全部Python /真实PG /桌面浏览器 /静态检查、R4真实模型和业务参考闭环、三套正式Evaluation统一身份与三次诊断；不增加生产容量或多副本结果。
- 维护正式R4 Spec /Design /Acceptance、Web /Query API /History受影响说明、Architecture /Product Scope /Runbook /README /Roadmap；移除与已交付R4矛盾的未来描述，R5–R7保持真实未交付。
- 一目标一active branch /worktree；当前R3文档候选独立保留，R4从master基线设计，不合入无关Commit。发布仍需独立授权，未准备真实生产rollout，无额外feature flag流程。

## 12. 证据与重审触发

已读取本机锁定SDK源码、API /browser /auth、history受理 /finish /runtime、analysis graph /run_store /shared guard、bootstrap生命周期、Control DB migration/verifier、frontend api /Chat、现有测试入口。未执行实验或软件 /PG /Provider验证，计划不写成PASS。

协议和API能力参考：[SSE 标准](https://html.spec.whatwg.org/multipage/server-sent-events.html)、[Fetch response streaming](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch#streaming_the_response_body)、[Psycopg cancel_safe](https://www.psycopg.org/psycopg3/docs/api/connections.html#psycopg.Connection.cancel_safe)、[PostgreSQL 行锁](https://www.postgresql.org/docs/16/explicit-locking.html)。实际Provider /libpq中断能力以验收为准。

Owner为当前主Agent；需要新依赖、改变旧API响应、将历史成功与execution成功拆成两次提交、扩大单进程边界、修改取消 /恢复或授权策略时返回Spec /Design Review。内部文件划分、纯函数命名和测试辅助属于既有Contract内局部选择。

## 首轮修订核对

[首轮 Review](design-review-initial.md) F1：§4明确admission获取可转交分析run lease；F2：§10明确实际API finally→worker drain→Guard drain→资源context顺序；F3：§3/§8/§10明确级联FK、ring/订阅/帧上限及回滚验证；F4：§7明确middleware前缀、Header与统一错误映射。未改变已确认行为、范围或单进程边界，最终只读复审已 PASS。
