# 审计修复 Ticket 草案

Status: 已确认并已正式化。本文保留草案与拆分依据；执行状态以对应[issues](issues/)记录为准。

Canonical Source: [已确认Spec](spec.md)定义行为；[设计审查](design-review.md)定义已核对的实施约束。本文不覆盖它们，也不新增业务或权限决定。

全部Ticket的Owner为当前主Agent，后续维护归各现有模块；不委派独立Agent、不新增跨团队Owner。Backup Owner不适用；事实源、公共Contract、数据/权限范围或依赖需改变时，返回Spec/设计审查并向用户报告。

共同Change Profile：长期维护的缺陷修复，单一工作项/branch/worktree，多次相关本地Commit形成一个candidate；无新依赖、无破坏性Schema迁移、无实际生产发布。各项定向验证通过即记录切片结果，整体只在全部适用验收完成后关闭。

共同Out of Scope：AUD014、无关重构、新功能、模型/Provider替换、日常数据修复、远端写入。测试只用合成数据和独立资源，不打印/提交Secret。

实施准备：当前Docker及Compose可用；隔离worktree尚无.env与模型缓存。获得整体实施授权后，按已确认范围准备0600独立配置，程序复用原有配置但不打印/记录值；确认Compose project、卷、端口和RAG输出均独立。固定revision模型缓存按既有流程复用或显式下载；不能把原工作区的日常配置路径/项目名/输出指针直接沿用为隔离目标。准备失败先报告事实，不使用日常资源替代。各项实现前运行定向测试的基础配置准备不等于提前完成AUD015防护。

## 拆分总览

| Ticket | 目标 | AUD | 直接依赖 |
| --- | --- | --- | --- |
| 01 | 查询安全裁决与授权拒绝保护 | AUD001、AUD002 | None |
| 02 | 兼容历史入口的共享保护与准确终态 | AUD003、AUD004、AUD005 | None |
| 03 | 删除分析历史后的checkpoint回收 | AUD006 | None |
| 04 | 归因分类与PDF证据列的一致展示 | AUD007、AUD008 | None |
| 05 | 重查受理不确定时保留同一操作 | AUD009 | None |
| 06 | 检索模型首次加载与安全故障诊断 | AUD010、AUD018 | None |
| 07 | 审计与分析快照的嵌套安全边界 | AUD016、AUD019 | None |
| 08 | 本机配置权限及读入前保护 | AUD015 | None |
| 09 | 首个管理员事务并发互斥 | AUD017 | None |
| 10 | 真实评测与兼容验收入口修复 | AUD011、AUD012、AUD020 | None |
| 11 | 隔离容器热更新与验收账号异常清理 | AUD013、AUD021 | None |
| 12 | 文档状态修正与完整候选验收 | AUD022、AUD023 | 01–11 |

01–11没有互相阻塞的行为依赖；同文件重叠按编号顺序在同一branch修改并复核，不为共享文件制造虚假依赖。12负责全部修复后的最终候选验证，直接依赖01–11。没有逐Ticket发布或长期独立集成分支。

## Ticket 01：查询安全裁决与授权拒绝保护

- Change Profile: 高风险；局部Guard与授权测试；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD001、AUD002。
- Blocked by: None (can start immediately)。
- owned files: src/online_query/sql_guard/sql_guard_multi_metric.py；src/online_query/semantic_state.py（仅必要的分组语义校验）；tests/online_query/test_multi_metric.py；tests/online_query/test_sql_guard.py；tests/authorization/test_authorization_core.py；docs/specs/online-query.md。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

拒绝多指标GROUPING SETS/ROLLUP/CUBE及组合AST形式；修正授权拒绝测试观察的真实下游方法，保留合法查询路径。

### Acceptance criteria

1. 非法扩展分组在数据库执行前返回SQL_REJECTED；普通多指标分组仍可执行并保持结果形状。
2. 有/无普通分组表达式和组合扩展都覆盖；合法时间分组、单指标及历史条件不回归。
3. 无身份/无权限时实际执行路径零调用；合法对照能命中同一个执行替身，不以未用mock断言冒充保护。

### 验证证据

容器内定向运行上述Guard/授权测试；保留失败前/修复后的结果；最终test python及三套Evaluation验证正式链路。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

草案，未实施，未运行修复验证。正式Ticket确认后才以Status: open写入issues目录。

## Ticket 02：兼容历史入口的共享保护与准确终态

- Change Profile: 高风险；跨Application/Store内部协作，公开HTTP Contract保持；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD003、AUD004、AUD005。
- Blocked by: None (can start immediately)。
- owned files: src/query_api/history.py；src/query_api/history_api.py；src/query_api/history_contracts.py；src/chatbi_control/history.py；src/query_api/admission.py；src/query_api/execution.py；src/query_api/execution_runtime.py；src/query_api/app.py；tests/history_support.py；tests/query_api/test_history_api.py；tests/query_api/test_history_application.py；tests/query_api/test_execution_application.py；tests/query_api/test_execution_runtime.py；tests/chatbi_control/test_history_postgres.py；对应readiness/history/execution Specs。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

按Spec设计约束复用就绪/owner额度和同步control，在幂等校验后、新attempt写入前受理；业务层授权拒绝映射revoked；真实succeeded轮次正确记录SUCCESS。

### Acceptance criteria

1. 四类兼容写入口未就绪503、超额429，拒绝无新attempt/history及下游调用；错误外壳兼容。
2. 同账号跨history、同步/后台及不同账号全局额度共享；幂等成功/失败重放在未就绪或额度已满时仍不重复占额；请求摘要冲突仍拒绝。
3. 事务/执行/持久化异常释放同一租约；断开或停止等待不能提前释放真实工作；180秒/1200秒控制下传，analysis guard不双重取得。
4. HistoryError授权错误与HTTP401/403均为AUTHORIZATION_REVOKED，其他鉴权依赖故障为UNAVAILABLE；真实worker succeeded trace为SUCCESS，既有失败分类保持。

### 验证证据

Application/API可控替身与事件同步并发测试；PG验证受理前拒绝、事务回滚、幂等及历史状态；容器test database覆盖CI/development。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

草案，未实施，未运行修复验证。正式Ticket确认后才以Status: open写入issues目录。

## Ticket 03：删除分析历史后的checkpoint回收

- Change Profile: 高风险；Control DB数据生命周期，保留tombstone；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD006。
- Blocked by: None (can start immediately)。
- owned files: src/business_analysis/run_store.py；src/chatbi_control/history.py（仅必要删除标记配合）；tests/business_analysis/test_run_execution.py；tests/chatbi_control/test_history_postgres.py；tests/chatbi_control/test_postgres_dev_environment.py；docs/specs/business-analysis.md；docs/specs/history-results-v1.md。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

让到期清理覆盖已标expired但仍有checkpoint的运行，不引入新清理器或Schema；保留失效ID。

### Acceptance criteria

1. 主动删除分析历史后，checkpoints/checkpoint_blobs/checkpoint_writes均在既有清理周期内被回收。
2. 已expired遗留run同样回收；重复清理幂等且不反复无差别更新全部expired行。
3. 其他有效run和独立成果保持；原run不能claim/resume；清理失败事务回滚，不出现仅部分子表已删的成功。

### 验证证据

真实PG建立三类子表记录，执行删除+清理及遗留/重复/失败路径；明确证明保留记录及原ID失效。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

草案，未实施，未运行修复验证。正式Ticket确认后才以Status: open写入issues目录。

## Ticket 04：归因分类与PDF证据列的一致展示

- Change Profile: 中高风险；页面/快照/文件结果表达；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD007、AUD008。
- Blocked by: None (can start immediately)。
- owned files: frontend/src/Analysis.tsx；frontend/src/export/pdfReport.tsx；frontend/src/（必要的轻量共用分类函数）；frontend/tests/result-export.spec.ts；frontend/tests/history.spec.ts；tests/query_api/test_result_export_pdf.py；tests/query_api/test_result_export_pdf_renderer.py；相关fixture；docs/specs/result-visualization-v1.md；docs/specs/result-export-v1.md。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

页面和PDF识别后端真实新增/退出产品分类及旧兼容值；PDF分块按同一源列取得名称、索引和值。

### Acceptance criteria

1. continuing/new_product/exited_product可在首次结果、历史重开、归因图表和PDF正常展示；旧new/discontinued仍识别，未知值不猜语义。
2. 归因金额/方向/因素与后端一致，不重算业务公式。
3. 8列、奇数列、空行、长中文名称与多分块的标题/序号/值精确对应；实际PDF文本可核验，coverage检查不能仅证明数量。

### 验证证据

确定性浏览器从真实后端payload形状渲染；解析实际PDF的分块文本与原值，运行web及renderer相关测试。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

草案，未实施，未运行修复验证。正式Ticket确认后才以Status: open写入issues目录。

## Ticket 05：重查受理不确定时保留同一操作

- Change Profile: 高风险；前端状态与服务端幂等；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD009。
- Blocked by: None (can start immediately)。
- owned files: frontend/src/Chat.tsx；frontend/tests/execution.spec.ts；frontend/tests/history.spec.ts；docs/specs/execution-streaming-v1.md（若需补充现有验收）。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

复用已有uncertainExecution恢复流程，保留requery原path/body/operationId和来源；原请求显式恢复不生成新UUID。

### Acceptance criteria

1. 服务端已受理但提交响应丢失、首次by-operation查询又失败时，页面进入未确认且保留原请求。
2. 显式恢复/重试复用同一ID；迟到受理只观察同一execution；确定拒绝允许按既有语义新请求，不自动重发。
3. 问数历史、分析历史及saved-result来源都覆盖；401/403、退出、切换账号清理私有状态；原成果和快照不被失败改写。

### 验证证据

浏览器故障注入提交/查找双失败与迟到响应，核对实际请求ID、路径、body和执行次数，运行execution/history测试。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

草案，未实施，未运行修复验证。正式Ticket确认后才以Status: open写入issues目录。

## Ticket 06：检索模型首次加载与安全故障诊断

- Change Profile: 中高风险；模型资源与第三方错误边界；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD010、AUD018。
- Blocked by: None (can start immediately)。
- owned files: src/rag_offline/embedding.py；src/rag_offline/qdrant_store.py；src/online_query/retrieval/retrieval_resource_stage.py；src/online_query/service.py（仅必要错误传播收口）；tests/rag_offline/test_embedding.py；tests/rag_offline/test_qdrant_store.py；相关retrieval/service测试；docs/designs/rag-offline-build.md（同步本地快照规则）。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

在provider内保护首次加载并保留重试能力；Qdrant异常输出只含安全阶段/类型，不拼接原URL或敏感异常。

### Acceptance criteria

1. 同provider多线程同步首次调用只构造一个成功实例，已加载路径复用；构造失败释放锁，后续调用可恢复。
2. 不对所有推理强加全局串行锁，不改变模型配置、revision或RAG身份。
3. 带合成userinfo、敏感查询参数、API Key和异常canary的故障在最终服务日志和公开错误中均不含canary；安全诊断仍可识别阶段/类别。

### 验证证据

Barrier/Event控制构造并发计数及失败恢复；捕获最终日志链核对合成canary；真实BGE加载由后续隔离评测验证。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

草案，未实施，未运行修复验证。正式Ticket确认后才以Status: open写入issues目录。

## Ticket 07：审计与分析快照的嵌套安全边界

- Change Profile: 高风险；持久化/公开数据兼容；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD016、AUD019。
- Blocked by: None (can start immediately)。
- owned files: src/authorization/audit_service.py；src/query_api/history_codec.py；tests/authorization/test_audit_service.py；tests/query_api/test_history_codec.py；tests/query_api/test_history_application.py；tests/query_api/test_result_export_api.py；docs/specs/query-api.md；docs/specs/history-results-v1.md。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

递归审计dict/list敏感键校验；分析快照按report/task/error/attribution/metadata公开结构逐层验证，复用现有DTO语义而非新建通用脱敏框架。

### Acceptance criteria

1. 嵌套字典、列表内字典不能携带现有敏感键持久化；错误不回显原载荷；合法结构保留。
2. 异常旧分析快照在历史重开、另存及导出边界受控拒绝HISTORY_SNAPSHOT_UNAVAILABLE，不静默删除内部字段后当成功。
3. 合法旧缺少可选result_metadata的快照保持可读；query合法sql不被误拒；表格单元格中的普通文本不按字段名过滤。
4. 未知/不支持结构受控失败；不扫描或改写日常数据库，不扩大当前数据保留范围。

### 验证证据

用合成嵌套SQL/connection_info/Secret canary验证公开返回与持久化失败；对合法旧/新query与analysis fixtures做兼容回归。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

草案，未实施，未运行修复验证。正式Ticket确认后才以Status: open写入issues目录。

## Ticket 08：本机配置权限及读入前保护

- Change Profile: 中风险；本机文件与开发CLI可观察失败；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD015。
- Blocked by: None (can start immediately)。
- owned files: scripts/dev_environment.sh；相关配置读取宿主入口；tests/scripts/test_container_dev.py；tests/scripts/test_dev.py（如不存在则新增）；docs/runbook.md；本机原worktree .env（仅权限、不入Git）。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

在Linux配置交给Compose/读入前检查属主与group/other权限；明确拒绝和安全修复指令；新建配置说明使用安全权限，并收紧本机已识别.env。

### Acceptance criteria

1. 受控临时配置0644拒绝、0600正常；可读但非所有者等不安全情况安全拒绝；错误不打印内容；不自动递归改权限。
2. dev help及参数拒绝仍不读取.env、不调用Docker；所有配置加载调用点已盘点，不只保护日常up。
3. 原工作区.env仅chmod600，不改值；用权限元数据核验，不输出或保存Secret；不要求宿主安装Python/Node。

### 验证证据

shell/假Docker记录验证拒绝发生在配置使用前；安全模板检查；本机处置仅记录stat元数据，不记录内容Hash或值。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

草案，未实施，未运行修复验证。正式Ticket确认后才以Status: open写入issues目录。

## Ticket 09：首个管理员事务并发互斥

- Change Profile: 高风险；账号初始化不变量；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD017。
- Blocked by: None (can start immediately)。
- owned files: src/chatbi_control/bootstrap.py；tests/chatbi_control/test_bootstrap.py；tests/chatbi_control/test_postgres_dev_environment.py；tests/bootstrap/test_control_commands.py；docs/specs/bootstrap.md。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

按Spec以专用PG事务advisory lock保护先查后建，覆盖有预置角色和空初始化路径；保留原CLI与强制改密。

### Acceptance criteria

1. 真实PG两个不同用户名在无管理员时同步初始化，只能一个提交成功，另一个明确已有管理员且无额外用户。
2. 预置admin角色存在和首次seed场景均覆盖；失败回滚释放锁，后续合法初始化可成功。
3. 锁身份不与HistoryRuntime/其他用途共用；SQLite仅验证串行；普通管理后台、恢复管理员、密码与审计语义不变。

### 验证证据

PG线程/独立事务配合屏障和有界超时，观察目标事务互斥；检查最终用户/角色关系；不依赖sleep碰运气或串行mock。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

草案，未实施，未运行修复验证。正式Ticket确认后才以Status: open写入issues目录。

## Ticket 10：真实评测与兼容验收入口修复

- Change Profile: 中风险；CI/host验证入口，不触发远端写入；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD011、AUD012、AUD020。
- Blocked by: None (can start immediately)。
- owned files: .github/workflows/real-e2e.yml；frontend/test-support/report-path.ts；frontend/playwright.real.config.ts（仅必要对齐）；scripts/run_database_tests.py；tests/scripts/test_real_e2e_workflow.py；tests/scripts/test_run_database_tests.py；frontend/tests/report-path.spec.ts；docs/runbook.md。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

Real E2E在build-rag前prepare-model并使用同revision本地路径；报告helper兼容host run目录；旧PG测试入口使用正式TCP探测/查询。

### Acceptance criteria

1. 工作流步骤顺序、空缓存/复用缓存、失败传播有回归；不以移除本地快照校验修复；普通CI不新增真实LLM调用。
2. 报告helper变量优先级为非空container、real、/reports，空值与文件名穿越校验保持；实际能读取本次host start.json。
3. pg_isready与fixture readiness查询均指定正式TCP host；临时socket实例不能放行，超时和错误保持；CI/development两profile保留。
4. 未在GitHub runner或Windows执行的范围如实记录，不冒称托管工作流已通过。

### 验证证据

工作流测试核验prepare/build配置；报告helper实际文件读写夹具；旧脚本subprocess探测回归，真实临时PG验证由最终数据库套件/兼容定向入口提供。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

草案，未实施，未运行修复验证。正式Ticket确认后才以Status: open写入issues目录。

## Ticket 11：隔离容器热更新与验收账号异常清理

- Change Profile: 高风险；测试写入、账号和临时资源生命周期；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD013、AUD021。
- Blocked by: None (can start immediately)。
- owned files: scripts/verify_container_dev.sh；tests/container_dev_support.py；frontend/tests/container-real.spec.ts；tests/scripts/test_container_dev.py及必要独立故障注入测试；docs/specs/container-dev-environment.md；docs/runbook.md。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

仅隔离验收提供受控热更新写入路径与源码恢复；为prepare账号创建建立无身份丢失窗口的记录/异常补偿；独立模型缓存显式准备。

### Acceptance criteria

1. 默认初始阶段实际观测Python和Vite热更新；不将用例skip或把原日常源码目录整体改为可写。
2. 成功、write失败、浏览器失败、prepare失败及可处理的INT/TERM都恢复原源码，最终Hash一致，报告记录失败不伪装成功；不可处理强杀保留可恢复证据，不承诺捕获SIGKILL。
3. 模拟账号提交前后account.json写入失败仍能精确识别本次账号并禁用、撤销Session；不得前缀批量操作；cleanup失败要保留证据和非成功状态。
4. 不对日常项目执行restart/kill/down；临时project/volume明确标签；prepare-model/build-rag先后关系正确，日常RAG指针不被覆盖。

### 验证证据

脚本/工具故障注入验证挂载范围、信号恢复、精确账号清理；真实完整isolated验收在最终候选执行，原intentional skip计数规则保持。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

草案，未实施，未运行修复验证。正式Ticket确认后才以Status: open写入issues目录。

## Ticket 12：文档状态修正与完整候选验收

- Change Profile: 中高风险；收尾文档和本目标有界完整验收；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD022、AUD023。
- Blocked by: 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11。
- owned files: .scratch/chatbi-product-v1/r1-spec.md；.scratch/project-navigation/spec.md；docs/roadmap.md；README.md（仅本目标入口）；本工作项记录；必要现有验证编排入口（仅运行，不新增通用平台）。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

按历史证据修正两份Spec首部；完成22项映射台账、全量软件检查与三套真实AI评测/隔离业务验收，形成一个本地candidate。

### Acceptance criteria

1. R1和导航Spec首部与已有交付/非作者走查证据一致，保留原日期和历史记录；路线图准确记录本目标，适用正式文档已由各Ticket更新。
2. 22项均有修复、regression、候选SHA和结果，不漏AUD002，不把AUD014作为缺陷；审计报告副本与原件一致。
3. dev check及python/database/web/renderer完整执行，记录真实计数/skip/未运行；Code Review与Diff Review通过；形成clean代码candidate后才做正式真实验收。
4. 同candidate与资源身份的三套正式Evaluation完成并按现有标准校验；首轮失败保留、不挑选成功替换；隔离业务报告依Contract判定，skipped仍incomplete。
5. 验证之后源码、专用账号和临时资源已恢复/清理；任何失败或环境限制保留未完成项。仅本地Commit，不Push/PR、不直接Merge；原工作区修改保持。

### 验证证据

完整./dev check、./dev test all；三套./dev evaluate与evaluate validate；./dev verify dev isolated；安全验收摘要、provenance与清理结果；不触发远端workflow。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

草案，未实施，未运行修复验证。正式Ticket确认后才以Status: open写入issues目录。
