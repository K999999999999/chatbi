# ChatBI 全仓项目审计报告

审计台账日期：2026-10-16；报告保存日期：2026-10-17  
审计基线：master，commit 8d01740474b2c727131e54a70a2f186713b306ad，工作区 clean  
覆盖：928 / 928 个 Git 跟踪文件完成阅读与语义审查  
结论：22 项已确认问题；P1 4 项、P2 12 项、P3 6 项。未在本报告中实施修复。

## 范围与证据边界

本次审计逐项核对仓库中的源码、测试、配置、正式文档及工作记录，并结合 Contract、实现和测试证据评估问题。审计期间仓库保持只读。Harness 检查读取了 49 份本机当前记录；该检查只反映本机状态，不证明远端 CI 或产品验收结果。

证据包括静态调用链检查，以及隔离的合成输入或假服务复现。没有重跑完整测试套件，也没有运行真实 PostgreSQL 并发测试、真实 LLM 业务链路或完整容器验收。各条问题注明了相应的限制。审计没有读取或写入真实 Secret 值；报告不包含凭证内容。

## P1

### AUD001：多指标 SQL Guard 未拒绝 GROUPING SETS / ROLLUP

位置：[sql_guard_multi_metric.py:197](../../src/online_query/sql_guard/sql_guard_multi_metric.py#L197)、[semantic_state.py:352](../../src/online_query/semantic_state.py#L352)。

多指标校验检查了聚合表达式和普通 GROUP BY 输出对应关系，但没有拒绝 GROUPING SETS / ROLLUP 等分组扩展。确定性服务复现中，一个通过候选认证且包含 GROUPING SETS 的查询到达数据库执行器并被包装为 QuerySuccess。额外汇总行可能突破原先的结果形状与语义校验边界。

### AUD003：历史兼容写路由绕过就绪检查和共享执行额度

位置：[history_api.py:286](../../src/query_api/history_api.py#L286)，以及同文件的 requery、resume 和 saved-results requery 路由。

这些兼容路由直接调用 HistoryApplication；写入路径使用单个 history_id 的锁，但没有经过 operations.ready 和共享 admission / reserve_owner 限额。ready=False 的假服务复现仍调用了应用；不同 history_id 也可并发执行。这样会绕过 Contract 要求的未就绪拒绝及同步/后台共享资源额度。

### AUD008：经营分析产品分类的后端和前端 Contract 不一致

位置：[attribution.py:343](../../src/business_analysis/attribution.py#L343)、[Analysis.tsx:32](../../frontend/src/Analysis.tsx#L32)。

后端对新增、退出产品输出 new_product / exited_product，前端解析器只接受 continuing / new / discontinued。全仓没有转换层。涉及新增或退出产品时，前端会把有效分析响应判为无效，可能导致归因图表和相关结果无法展示。

### AUD011：Real E2E 工作流未准备本地 BGE 模型快照

位置：[real-e2e.yml:141](../../.github/workflows/real-e2e.yml#L141)、[embedding.py:155](../../src/rag_offline/embedding.py#L155)。

工作流直接运行 build-rag，没有先执行 prepare-model；配置中的模型名不是本地快照目录。Embedding 加载器只接受已存在的本地目录，因此工作流会在正式 Evaluation suites 开始前报模型快照不存在。该结论来自加载器检查和本机路径复现，未启动 GitHub runner。

## P2

### AUD004：授权撤销被归类为错误的执行终态

位置：[execution_runtime.py:550](../../src/query_api/execution_runtime.py#L550)、[history_contracts.py:18](../../src/query_api/history_contracts.py#L18)。

Worker 鉴权拒绝通过 HistoryError 的 AUTHORIZATION_DENIED / AUTHENTICATION_REQUIRED 代码传递，而终止原因分类只识别 HTTP status 401 / 403。撤销授权仍会 Fail Closed，但会被归类为 AUTHORIZATION_UNAVAILABLE，公开终态也因此给出错误原因。

### AUD005：Trace 把 succeeded 轮次记为技术失败

位置：[execution.py:43](../../src/query_api/execution.py#L43)、[execution.py:408](../../src/query_api/execution.py#L408)、[execution_api.py:163](../../src/query_api/execution_api.py#L163)。

真实 Worker 和 API 使用 succeeded 表示成功，Trace 分类只把 completed 作为 SUCCESS。当前成功分支因此可能记录成 TECHNICAL_FAILURE / UNKNOWN。现有成功测试只用 completed，未覆盖实际的 succeeded 状态。

### AUD006：删除历史后分析 checkpoint 不进入 TTL 清理

位置：[history.py:1068](../../src/chatbi_control/history.py#L1068)、[run_store.py:115](../../src/business_analysis/run_store.py#L115)。

删除历史会把分析 run 标为 expired 并设置 expires_at 为当前时间，但不会同步删除 checkpoints、checkpoint_blobs 和 checkpoint_writes。过期清理只选 status 不等于 expired 的记录，所以这些 checkpoint 不再进入清理流程，可能长期保留分析状态及查询结果。

### AUD007：PDF 分页后的列标题与列值错配

位置：[pdfReport.tsx:281](../../frontend/src/export/pdfReport.tsx#L281)。

每个两列分块的标题名称仍从 task.columns 的开头映射，但列索引和值从当前分块偏移。第二组及后续分块会显示错误的列名。现有 8 列 fixture 只检查末列数据存在，没有验证标题和列索引一致；该缺陷已通过代码和 fixture 对照确认。

### AUD009：requery 的不确定提交重试会换 operation ID

位置：[Chat.tsx:308](../../frontend/src/Chat.tsx#L308)、[Chat.tsx:313](../../frontend/src/Chat.tsx#L313)、[Chat.tsx:316](../../frontend/src/Chat.tsx#L316)。

每次 requery 点击都会创建新 UUID。非确定性提交失败后仅查询一次原 operation；如果查询也失败，状态会终止而不保留 uncertainExecution。用户再次尝试时会换新 ID，服务端可能把它作为另一项操作执行，造成重复提交风险。

### AUD010：BGE 模型并发首次加载可能创建多个实例

位置：[embedding.py:162](../../src/rag_offline/embedding.py#L162)、[rag_runtime.py:88](../../src/online_query/retrieval/rag_runtime.py#L88)。

共享 provider 的 _load_model 对 _model 只进行无锁检查和赋值。RagRuntime 的锁没有覆盖快照返回后的并发 embed_query 首次调用。四线程假构造器复现创建了四个不同实例；真实大模型首次加载可能造成内存峰值或 OOM。

### AUD012：Real Playwright host 报告目录变量不匹配

位置：[playwright.real.config.ts:18](../../frontend/playwright.real.config.ts#L18)、[report-path.ts:7](../../frontend/test-support/report-path.ts#L7)、[real.spec.ts:13](../../frontend/tests/real.spec.ts#L13)。

host 配置写入 CHATBI_REAL_E2E_REPORT_DIR 下的 start.json，但 reportPath 只读取 CHATBI_CONTAINER_REPORT_DIR 或默认 /reports。路径 helper 复现返回 /reports/start.json，而 host 文件在 runs/<id> 目录中；因此 host 入口会在业务验证前找不到报告起始文件。未运行真实模型验收。

### AUD013：容器热更新验收向只读挂载写文件

位置：[verify_container_dev.sh:258](../../scripts/verify_container_dev.sh#L258)、[container-real.spec.ts:275](../../frontend/tests/container-real.spec.ts#L275)。

浏览器容器把后端源码挂载为只读，热更新用例却先对挂载目录中的 app.py 执行 writeFileSync。首次验收阶段 restart phase 默认值不会跳过该用例，按当前挂载配置会触发 EROFS，并阻断后续真实验收。此项基于脚本和测试的静态路径核对，没有运行真实 Compose / LLM 流程。

### AUD015：本机 .env 权限为 0644

位置：本机忽略文件 .env；相关启动说明见 [runbook.md](../../docs/runbook.md) 和 [dev_environment.sh:10](../../scripts/dev_environment.sh#L10)。

审计只核对变量是否非空和文件权限，没有读取或保存值。该文件含非空凭证变量且模式为 0644；在多用户机器上，其他本机用户可能读取这些凭证。Runbook 只要求复制模板，启动脚本也没有收紧或拒绝宽松权限的检查。

### AUD017：并发首次管理员初始化存在事务竞态

位置：[bootstrap.py:62](../../src/chatbi_control/bootstrap.py#L62)、[bootstrap.py:53](../../src/bootstrap/control.py#L53)。

create_first_admin 在事务内普通查询当前管理员，没有锁定固定角色或使用 advisory lock。在 PostgreSQL 默认 READ COMMITTED 下，两个并发事务可能都读到尚无管理员，再以不同用户名关联同一个预置 admin 角色并提交，违反仅在尚无管理员时允许初始化的 Contract。当前测试是串行场景；没有做真实 PostgreSQL 并发复现。

### AUD018：Qdrant 故障日志可能包含 URL 凭证

位置：[qdrant_store.py:62](../../src/rag_offline/qdrant_store.py#L62)、[retrieval_resource_stage.py:76](../../src/online_query/retrieval/retrieval_resource_stage.py#L76)、[service.py:345](../../src/online_query/service.py#L345)。

连接失败时原始 URL 和异常会进入 QdrantStoreError，之后被作为 retrieval warning 写入服务日志。使用带合成认证信息的 URL 和假客户端复现，日志含有合成凭证内容。未连接真实 Qdrant，也未读取或打印任何真实 Secret。

### AUD020：旧 PostgreSQL 测试入口可能把初始化临时实例当成正式服务

位置：[run_database_tests.py:192](../../scripts/run_database_tests.py#L192)、[run_database_tests.py:422](../../scripts/run_database_tests.py#L422)、[container_tasks.sh:315](../../scripts/container_tasks.sh#L315)。

旧入口的 pg_isready 没有指定 host，会通过 Unix socket 探测。postgres:16-alpine 初始化期间会先启动仅供 init scripts 使用的临时 Postgres 实例，再停止并启动正式服务；旧入口可能在正式 TCP 服务就绪前继续执行 fixture。相邻的新容器入口已用 127.0.0.1 避免该情况。旧入口为兼容路径，当前 CI 使用新入口；没有运行该容器时序复现。

## P3

### AUD002：授权拒绝测试断言了未使用的 mock 方法

位置：[test_authorization_core.py:117](../../tests/authorization/test_authorization_core.py#L117)、[query_entry.py:218](../../src/authorization/query_entry.py#L218)。

拒绝场景断言 mock.query 未调用，但当前实际下游方法是 execute_authorized。错误码断言验证了拒绝响应，却不能发现未来出现“调用下游产生副作用后仍返回拒绝”的回归。当前实现先授权、后执行，尚未发现授权绕过；这是测试保护缺口。

### AUD016：审计详情的敏感字段检查不递归

位置：[audit_service.py:35](../../src/authorization/audit_service.py#L35)。

AuditRecord 只检查 details 顶层键。合成对象中嵌套的 metadata.password 可通过构造并被 PersistentAuditSink 原样持久化。当前仓库调用点使用扁平详情，没有发现实际 Secret 写入；风险在未来扩展嵌套详情时绕过检查。

### AUD019：持久化快照公开校验没有递归检查嵌套字段

位置：[history_codec.py:159](../../src/query_api/history_codec.py#L159)、[query-api.md](../../docs/specs/query-api.md)。

public_snapshot 只检查最外层 allowed / required 字段。对合成的异常或旧格式分析快照，task_results 内嵌的 SQL 和 connection_info 会原样返回，违反公开 Contract 对 SQL / 连接信息的排除要求。当前合法 encode_snapshot 调用使用显式字段投影；未发现受支持客户端能直接写入此类快照，因此这是条件性持久化边界缺口，不是已确认的请求注入路径。

### AUD021：容器验收异常时可能遗留专用测试账号

位置：[container_dev_support.py:32](../../tests/container_dev_support.py#L32)、[verify_container_dev.sh:142](../../scripts/verify_container_dev.sh#L142)。

prepare 会先提交随机专用用户，再写 account.json；退出清理只在 account.json 存在时调用 cleanup。如果用户已提交而报告文件写入失败，Control DB 中可能留下无法由该钩子定位的用户。此路径由代码时序确认，未实际制造容器文件系统故障；主要影响是孤儿测试账号及清理不完整。

### AUD022：R1 Spec 首部状态未随交付回填

位置：[r1-spec.md](../../.scratch/chatbi-product-v1/r1-spec.md)。

首部仍写“不是已实现或已验收的功能”，文末的 dated 回填则记载五项 Ticket 已完成、最终候选本地验收通过且 Streamlit 已移除。读者从 Spec 首屏会看到与其后实施结果冲突的状态。

### AUD023：项目导航 Spec 首部仍称非作者走查待完成

位置：[project-navigation Spec](../../.scratch/project-navigation/spec.md)、[status.md](../../.scratch/project-navigation/status.md)。

Spec 首部写 Ticket 03 等待非作者新人走查；同工作项的状态和结果记录则说明非作者走查及全部三个 Ticket 已完成。首部状态未随交付收尾更新。

## 排除项与后续

AUD014 曾作为候选检查：双阶段容器验收中的 intentional skips 会让报告状态为 incomplete。正式容器 Contract 明确规定任何 skipped 都使报告 incomplete，当前实现符合 Contract，因此不计为缺陷。

本报告记录审计基线上的发现，不代表修复已授权或已完成。后续如要处理，应按仓库工作流为选定范围建立工作记录、核对当前代码与 Contract，并分别运行适用验证。
