# R4 Ticket 草案

Status: 六项拆分与整体本地实施已于 2026-10-05 获用户确认；六份正式 Ticket 已建立，01 正在实施；远端发布未授权。
Canonical Source: [已确认 Spec](spec.md)、[Design](design.md)、[最终 Design Review PASS](design-review.md)。
Baseline: `2019443020bb7a20a8c3d1a578a613544ad8148b`
Owner: 当前主 Agent；六项连续实施由同一主Agent维护，不委派独立Agent。

## 切片与依赖

| 草案 | 可观察交付 | 直接依赖 |
| --- | --- | --- |
| 01 | 后台受理、操作查回与最终结果 | None |
| 02 | 网页真实阶段、SSE观察与重连 | 01 |
| 03 | 主动取消、超时与授权失效停止 | 02 |
| 04 | 状态 /最终结果阶段的真实链路验收 | 03 |
| 05 | 模型报告文字真实流式与草稿校验 | 04 |
| 06 | 最终候选完整验收、回归与事实源同步 | 05 |

直接依赖组成单链，无循环。04是已确认的状态阶段验收门槛，不用“稍后全量验证”跨过它进入05。每项包含适用测试 /Review /本地Commit；06独立收敛最终clean候选与正式Evaluation，不把测试拖到最后。

共同边界：只实现R4；旧同步API正常请求 /响应兼容；单进程；不引入队列 /新SDK /模型替换；所有用户动作遵守owner /权限 /CSRF。改变Spec、设计核心决定或验证方式时返回相应门禁。

## 01 后台受理、稳定操作查回与最终结果

Change Profile: 持续维护 /中偏大 /高风险事务与生命周期 /软件+真实PG+API /本地candidate。
Owner: 当前主Agent；迁移与运行状态由本项建立，后续切片维护其接口。
Blocked by: None (can start immediately)

### What to build / Scope

- 显式v4 migration、execution身份 /状态Store与Port，受理同事务关联原history turn，不复制成功snapshot /上下文。
- POST新执行 /恢复 /历史与成果重查、GET执行 /操作编号查回，后台worker使用同一查询 /分析链并返回受理身份。
- admission先查原operation再看revision /额度；相同请求去重、内容冲突拒绝；每账号1 /全局4，配置校验、不排队，worker真正结束才释放。
- history活跃登记与可转交analysis run lease覆盖受理→worker窗口，原同步入口不能抢同run或回收已受理执行。
- 结果 /成功指针 /execution成功同事务；失败与存储未知保持原上下文和受理唯一身份；初始化、shutdown signal /drain /部分装配失败清理按Design顺序。

Out of Scope: SSE网页反馈、用户取消 /文字流式、生产发布；本项暂由新API查状态 /最终turn完成纵向闭环。

Owned files: `database/control/006_execution_streaming.sql`、`src/chatbi_control/execution.py` /history.py /database.py /必要初始化映射；`src/query_api/execution_contracts.py` /execution.py /execution_runtime.py /execution_api.py、history.py /history_contracts.py /history_runtime.py /runtime.py /app.py；`src/business_analysis/run_execution.py`；`src/bootstrap/runtime.py` /必要生命周期；`.env.example`；对应 `tests/query_api/` /`tests/chatbi_control/` /`tests/bootstrap/` 和数据库验证入口；本项相关正式Contract /Runbook章节。

### Acceptance criteria / Evidence

1. 受理202后即使请求连接关闭，执行可继续；GET或原turn读取最终持久化结果，成功上下文与execution状态一致。
2. 重复 /并发同operation在同账号下只有一个turn /worker；不同内容409；响应丢失查回原身份；暂查不到无隐式重执行；跨账号不可查，未知字段 /非法UUID等受控拒绝。
3. busy /额度 /stale在适用位置拒绝，不多占额度；同run旧同步入口竞争受控；调度失败 /受理失败 /提交未知的故障seam有状态和资源证据。
4. 真实PG证明fresh /v3升级 /重复migration、事务与fencing，旧历史 /成果与marker保留；FK cascade不损独立成果。
5. 可阻塞worker证明shutdown先signal/drain后关Provider /DB /checkpointer，结束前不释放，部分装配失败无运行资源泄漏。

验证：对应Python /API /Runtime /migration targeted tests；真实隔离PG入口；旧API /R3受影响回归，锁文件 /模块边界 /静态 /Diff /文档检查。测试验证状态与结果，不能仅看submit调用次数。启动新存储实际失败与关键数据只读校验必须有证据。

Migration / Rollback: v4只增对象 /grant /marker，v2/v3保留，执行FK cascade仅元数据；显式初始化，不在请求DDL；停止worker后v3保留数据恢复将在04 /06完整验收。
Done When: 1–5通过、API /存储 /生命周期契约与适用文档完整，当前上下文Code Review PASS、Diff与本地Commit完成。
Result: 尚未实施。
Comments: 中间切片结果不冒称整个R4验收完成。

## 02 网页真实阶段、SSE观察与快照重连

Change Profile: 持续维护 /中 /高风险身份与传输 /软件+HTTP浏览器 /本地candidate。
Owner: 当前主Agent。
Blocked by: 01

### What to build / Scope

- 在实际语义理解 /retrieval /生成 /Guard /DB /存储与analysis节点添加可选阶段反馈Port；旧调用默认行为保持，不把阶段从Trace exporter推断。
- 当前执行快照 /计数 /序号、SSE订阅 /心跳 /有界ring与慢订阅重同步，fetch保留X-user-ID /Cookie，版本化DTO /decoder /reducer。
- 网页发送 /恢复 /重查改为受理→GET/SSE观察→读取正式turn；刷新 /关闭 /断连重开原执行，网络重连只GET；当前阶段与实际task count可见。
- 原Session只读鉴权能力与每帧 /心跳检查，新路径来源校验 /CSRF /no-store /Trace，失败关闭观察并清私有内容；不把请求对象交给worker、不续期。

Out of Scope: 报告文字草稿 /流式、用户取消按钮与执行停止策略（03）；真实Provider验收（04）。

Owned files: 01的execution Application /runtime /API与所需history DTO；`src/authorization/auth_service.py`、browser.py /app.py；`src/online_query/contracts.py` /service.py /service_execution.py /`src/authorization/query_entry.py` 的可选Control传递；`src/business_analysis/application.py` /contracts.py /execution.py；`frontend/src/execution.ts` /executionStream.ts /Chat.tsx /api.ts /history.ts /App.tsx /style.css；对应Python、授权、前端纯函数 /浏览器tests；Web /Query API /R4传输事实文档。

### Acceptance criteria / Evidence

1. 实际阶段 /恢复跳步 /真实唯一task计数正确，不模拟百分比 /计数；表格图表只展示正式有效结果，内部Prompt /JSON /分析SQL不泄漏。
2. HTTP /浏览器刷新、断连、重复事件、乱序 /缺口、终态事件丢失、多页与用户切换不会重执行、串任务、状态倒退或复用旧身份。
3. 首snapshot与增量无丢失窗口；ring64帧 /1MiB、每execution8订阅、文字帧16KiB与浏览器6MiB边界有确定性证据；慢读恢复snapshot，无无界队列或worker阻塞。
4. read鉴权不改变Session的idle /absolute期限；401/403或无法验证时停止推送 /清私有内容；缺X-user-ID /跨owner /跨来源 /CSRF /cache策略一致。
5. legacy正常同步输出与R2/R3最终结果组件回归通过；无stream订阅也能查询原执行终态，取消观察只断连接。

验证：执行observer /runtime /SSE解析与reducer定向测试、真实HTTP/Cookie桌面浏览器；必要PG授权 /Session测试；types /build /静态 /links /Diff；不以Mock chunk证明实际模型流式。
Migration / Rollback: 无新技术产品 /Schema决定，复用01存储；网页新流程与旧API兼容回归，保留数据回滚按04 /06执行。
Done When: 1–5与适用检查通过、Review PASS、文档同步、本地Commit完成。
Result: 尚未实施。
Comments: Phase观察不得改变business result，业务停止Port的实际传播由03补全。

## 03 主动取消、总时限与授权失效停止

Change Profile: 持续维护 /中偏大 /高风险竞态 /软件+真实PG+浏览器 /本地candidate。
Owner: 当前主Agent。
Blocked by: 02

### What to build / Scope

- POST取消 /网页按钮、stopping /cancelled /timed_out /授权失败状态、stop signal与1秒monitor，query180s /analysis1200s，共享deadline /quota。
- 全业务边界 /retry /stream前后识别专门停止信号，防broad catch吞掉；SQL Adapter best-effort cancel、模型停止边界，实际函数结束才释放。
- request_stop /finish_success同PG裁决；取消分析同事务封锁原run，旧API /checkpoint不能复活已取消运行；checkpoint完成不是网页成功。
- 原登录失效 /禁用 /撤权后台检测，不依赖SSE在线；成功提交前再鉴权；故障 /unconfirmed /restart与原TTL恢复规则一致。

Out of Scope: 改成立即强杀 /多进程、导出、文字流式；不延长checkpoint TTL。

Owned files: execution API /Application /runtime、History Application /Store /reconcile；`src/authorization/auth_service.py` /必要策略绑定；`src/online_query/contracts.py` /service.py /service_execution.py /llm.py /query_understanding_llm.py /database.py及实际下游停止传播；`src/business_analysis/application.py` /execution.py /run_store.py /run_execution.py /reporting.py /decomposer.py；bootstrap资源关闭；frontend execution /Chat /状态解码；对应软件 /真实PG /浏览器tests，R4 /Web /History恢复文档。

### Acceptance criteria / Evidence

1. 取消请求ACK之后不能成功回写；成功已提交之后取消读到成功。双连接 /可控barrier覆盖两种先后与重复取消 /超时竞争，历史snapshot /指针不被取消更新。
2. 停止中quota /run lease保留，迟到调用返回仍不继续或提交；真正结束才显示终态 /释放一次；超时重试不重置计时，不以Future.cancel或PG cancel回执证明停止。
3. 无业务帧期间撤权 /过期 /账号禁用也能停止后续步骤；同一原Session校验不续期，权限恢复不自动续跑；授权依赖不可用fail closed。
4. 未进入graph的取消、graph执行中、checkpoint completed但history未提交的取消都封锁原run；旧API /R3恢复路径不可重新claim；已完成正式结果不被取消撤销。
5. 服务重启未完成标unconfirmed、旧epoch /generation迟到写拒绝，问数按上一成功续聊、分析有效期内显式恢复，cancelled原run拒绝；存储失效 /关闭流程没有隐式接管或提前释放。

验证：全风险控制的确定性回归、真实PG stop/commit /registry /TTL，浏览器取消 /超时 /撤权。实际Provider不能立刻中断的限制准确报告。用户已确认的手动重试 /新任务行为须有浏览器证据。
Migration / Rollback: 使用01最小execution状态，cancelled run写旧版可识别expired；停止旧worker后回滚，不通过删数据解锁。
Done When: 1–5通过、Code Review PASS、相关安全 /状态Contract同步、本地Commit完成，可进入状态阶段真实验收。
Result: 尚未实施。
Comments: 验收deadline用可控clock与barrier，不长时间真实sleep。

## 04 状态与最终结果阶段真实链路验收

Change Profile: 收敛型阶段验收 /中 /高风险证据 /真实Compose+浏览器+PG /本地状态阶段candidate。
Owner: 当前主Agent。
Blocked by: 03

### What to build / Scope

- 扩展既有container真实验收profile，固定01–03的clean候选验证问数 /追问 /analysis真实阶段、正式结果、刷新 /多页 /断连重连 /取消与重新操作。
- 核对真实模型 /RAG /只读Sales DB与独立业务参考，实际PG重启 /cancelrun封锁 /v3保留数据回滚；不可立即中断Provider的表现如实记录。
- 若发现缺陷，只修复01–03已确认范围，Review并新候选复验；通过后才进入文字流式切片。

Out of Scope: 文字真实stream证据、全产品生产验收 /容量、R4最终三套正式基线（06）。

Owned files: `scripts/verify_container_dev.sh` /既有helpers /真实验收入口、`frontend/tests/container-real.spec.ts` /real配置、受影响PG /checkpoint验收辅助、`.scratch/execution-streaming-v1/`阶段证据 /正式Acceptance入口；发现缺陷仅01–03 owned files。

### Acceptance criteria / Evidence

1. clean候选真实桌面浏览器 /HTTP /实际模型 /RAG /DB完成已确认阶段链、问数 /分析最终结果与参考一致；记录候选、RAG /模型 /数据身份与退出状态。
2. 断连 /刷新 /多页同execution无重复业务执行、取消前后状态与额度真实表现可观测；故障竞态的替身 /PG证据与真实Provider证据分开，不能将不可立即中断写为已立即停止。
3. 实际停止原进程再重启，unconfirmed /原TTL /迟到fencing正确；保留数据切换v3 /回到v4，既有结果 /独立成果可用、cancelled原run不恢复、旧版删除不被新FK阻断。
4. 临时账号 /Session /凭证清理完成，业务DB /原账号 /开发卷 /RAG不受破坏；无secret进报告。状态阶段证据不改称05或最终R4成绩。

验证：Runbook中既有真实验收方式、独立SQL /归因参考、真实PG进程 /migration回滚检查；文档identity /links /Diff核对。原报告保留身份。
Migration / Rollback: 验收只使用已确认隔离资源和本地开发实例；回滚明确停止worker，不DROP业务数据，不做生产rollout。
Done When: 1–4通过、Code Review /证据核对PASS；固定clean阶段候选并在Git公共目录记录报告，tracked入口不预写“新HEAD通过”；才能启动05。
Result: 尚未实施。
Comments: 若tracked证据回填产生新阶段提交，受影响真实证据按新clean身份复验，不改原report SHA。

## 05 分析文字真实流式、草稿重置与最终校验

Change Profile: 持续维护 /中偏大 /高风险模型不可信输出 /纯decoder+软件+浏览器 /本地candidate。
Owner: 当前主Agent。
Blocked by: 04

### What to build / Scope

- summarizer可选R4 observer路径调用锁定SDK stream，六类报告文字增量严格解码 /公开；原invoke路径和最终结构 /引用校验复用，不伪造打字。
- 草稿generation /field /index /offset、snapshot /delta /reset处理；原JSON与草稿5MiB限制，escape /Unicode /重复key等异常受控失败，不公开JSON /任意对象路径。
- 同execution /deadline最多一次Provider异常内部重试，清旧draft；取消 /超时 /授权失效不重试，校验失败不自动重试。
- UI生成中不可另存，成功校验保存后替换成正式报告，数值 /图表 /证据此时展示；非成功清草稿、断连保留提示 /重连取当前generation。

Out of Scope: 新模型 /依赖 /业务指标、改变report结构、伪流式降级、token前公开数值图表。

Owned files: `src/business_analysis/reporting.py` /contracts.py /application.py /runtime.py及单一增量JSON decoder；execution runtime /event DTO /API的文字映射；`frontend/src/execution.ts` /executionStream.ts /Analysis.tsx /Chat.tsx /style.css；analysis /decoder /event /reducer /浏览器tests；正式R4 /Web /Analysis文档。

### Acceptance criteria / Evidence

1. 六类文字来自实际stream，合法chunk分割、CRLF /多行data、转义 /surrogate /空列表均得到正确纯文本；未知字段不任意写路径，重复key /不安全结构不制造草稿与最终结果分歧。
2. Provider异常重试保留execution /deadline、draft_reset正确；旧generation /重复offset /序号缺口 /多页 /重连不拼接两次输出；不可安全解析的内容不自动重试 /回放invoke。
3. 成功报告沿原结构 /引用 /业务校验及快照保存门槛，失败 /取消 /超时 /撤权无成功提交或可保存draft；既有成功结果保留。
4. 无observer的旧同步API /分析Evaluation正常行为兼容；停止信号在stream /retry /graph路径不被吞，Provider不支持stream给受控错误。
5. targeted software /浏览器通过且至少一次实际模型有完成前文字增量的开发证据；正式clean真实stream验收仍由06统一完成，不冒称样例为全套基线。

验证：单一decoder纯函数边界与生成器stop、Runtime /PG提交行为、HTTP/Cookie浏览器草稿测试；frontend types /build /静态 /文档链接；原analysis /query受影响回归，新增bad case加入regression。
Migration / Rollback: 无新SDK /存储选择，保持现有model /endpoint /temperature /max_tokens /max_retries=0；依赖无需升级，若确需新版本先回设计。
Done When: 1–5及Review PASS、本地Commit完成，可形成完整R4最终候选。
Result: 尚未实施。
Comments: 不能以完成报告字符分割或HTTP chunk数充当真实模型流式证明。

## 06 最终clean候选验收、回归与事实源同步

Change Profile: 收敛型交付验收 /中 /高风险证据 /软件+真实PG+桌面Chrome+AI Evaluation /本地最终candidate。
Owner: 当前主Agent。
Blocked by: 05

### What to build / Scope

- 汇总全部Ticket与受影响Regression，完整确定性 /真实PG /浏览器 /安全与静态检查，R4真实模型与DB闭环、独立业务参考。
- 正式R4 Spec /Design /Acceptance、Query API /Web /History受影响说明、Architecture /Product Scope /Runbook /README /Roadmap与各Ticket Result一致更新。
- 固定最终clean候选运行三套正式Evaluation /统一report身份 /三次完整多轮诊断，以及R4真实SSE /文字 /取消恢复链路；完整保留失败报告。
- 在当前上下文Code Review /Diff检查并形成本地最终candidate；报告发布范围 /风险 /验证 /真实auto-merge行为后另行请求发布授权。

Out of Scope: Push /PR /人工Merge /生产部署、R5–R7、扩大模型或业务数据范围。

Owned files: R4真实profile /验收scripts与frontend真实tests、既有Evaluation验收入口（仅必要受影响适配，案例集不无理由改口径）、相关Software /PG tests；`docs/specs/` /`docs/designs/` /`docs/acceptance/`正式R4与受影响Web /Query /History、architecture /product-scope /runbook /roadmap、README；本目录Ticket /Review /规划证据；故障修复仅01–05范围。

### Acceptance criteria / Evidence

1. Python全量、Runbook隔离DB、npm ci /types /build /Playwright、锁 /模块边界 /Ruff /安全 /Markdown /Diff等适用门禁通过；skip /未运行 /环境阻塞明确记录，不能视为通过。
2. R4真实桌面Chrome /Cookie /SSE /模型 /RAG /DB证明真实阶段与模型增量、最终结果 /图表 /报告参考一致、断连重连 /刷新 /多页 /取消 /草稿重试 /重启恢复正确；04只复用仍适用证据，相关行为 /基线改变重跑。
3. 受理幂等、并发 /额度、stop-success竞态、撤权 /保存失败、registry封锁、旧API /R2 /R3、安全 /SQL Guard、初始化 /升级 /重复 /旧版保留数据回滚有适用软件 /真实PG /浏览器证据；报告分清真实与替身范围。
4. 同一最终clean提交的single_turn /multi_turn /business_analysis正式三套均0 FAIL /0 INVALID_CASE，统一身份检查验证commit /git_dirty=false /案例hash /RAG /数据 /模型一致；另三次完整多轮诊断分别保留，不替代正式报告。
5. 临时账号禁用、活跃Session=0、临时凭证清理、原用户 /业务DB /开发卷 /RAG保留；正式事实源 /Roadmap与当前能力一致，R5–R7不假称已交付。
6. Code Review PASS，only相关Diff /Secret /文档检查完成，本地candidate唯一 /clean；未获发布授权不Push /创建PR。

Evidence / Candidate流程：实现、Contract、Review和适用tracked维护先Commit，再固定clean身份运行真实门禁。若回填tracked结果形成新candidate，重跑受影响真实门禁并按本项最终三套身份要求接受新报告；原报告不改SHA。最终即时结果原子写Git公共目录，tracked验收入口保存可复现门禁与历史身份，不循环回填“当前HEAD已通过”。

Migration / Rollback: 复用已确认的v4 /v3保留数据方案与04证据，基线变动重验；无实际生产rollout，发布另授权。
Done When: 1–6全部适用检查达到可报告终态，正式事实源维护完整、最终clean候选与报告可追溯；准确报告未运行 /剩余问题。仅本地交付完成不授权远端发布。
Result: 尚未实施。
Comments: 全量验证的适用范围 /命令在当前实施上下文根据实际Diff确定，不用过期报告数量推定通过。

## 授权与下一步

用户于 2026-10-05 确认六项拆分及整体本地实施范围，包含编码、适用测试 / 真实验收、当前上下文 Code Review 与本地 Commit。正式 Ticket 01–06 已写入 issues/，依赖顺序为 01→02→03→04→05→06；Ticket 01 已开始，按依赖连续实施，不逐项等待选择。Push / PR / 部署没有获得授权。
