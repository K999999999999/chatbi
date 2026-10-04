# R3 首轮 Design Review

Review: NEED FIX
Review Target: 已获用户整体确认的 [R3 Spec](spec.md)
Baseline: `afad5ac18452566199bfcfdcceb1585115576a77`
Mode: 当前主 Agent 只读审查；无独立 Agent、代码 / 测试 / 配置修改或自动修复。

## 结论

产品目标、核心成功 / 失败行为、技术方向与验收已明确，不存在需要重新访谈的目标歧义。当前 Spec 有意将关键实现内容交给 Design，但尚无实现设计文件；这些内容改变持久状态及公开 Contract，不能直接交给 Tickets 编码时决定。本结论不否定已确认需求，不代表功能实现失败。

必须先完成实施设计并针对以下发现复审，通过后再拆分。未执行任何R3软件测试、技术实验、真实模型调用或发布；不能把计划检查写成可运行 / PASS证据。

## Findings

### F1：快照与续聊状态的一致提交未有机制（高）

Signal: 同一成功语义跨越当前内存状态提交和新数据库快照写入，不能靠外层追加保存保证一致。
Evidence: Spec §7 / Design清单要求快照与状态一致保存；`src/query_api/app.py:747–765` 在成功后直接调用 ConversationStore.create / commit，再返回；响应序列化在 `_query_result_response` 中进行。`src/query_api/conversation.py` Store只有create / acquire / commit / abort，没有快照事务。
Impact: 调用旧链路之后再写历史，写失败时短期状态已经前进，违反用户确认的保存失败不推进续聊；在执行前 / 执行后 / 响应失败边界难以预测恢复行为。
Recommendation: 在实现设计明确网页长期状态的唯一权威、受理 / 执行 / 序列化 / 原子成功提交顺序，以及失败和提交结果不确定时的处理。复用业务执行链路，不能直接包住旧会话提交然后另写历史。将“提交前失败保留旧状态 / 提交后响应丢失读取已提交快照”分别测试，不能混为保存失败。

### F2：并发、删除和重启回收缺少统一所有权（高）

Signal: 当前的进程内租约不能证明新增数据库历史在多页面、重启和迟到提交下的安全状态转换。
Evidence: Spec §8 / §9承诺执行与删除互斥、旧上下文拒绝、重启未确认回收、迟到写保护；InMemoryConversationStore仅有进程内Lock与token，重启失效；本目标新Design未定义持久轮次状态、版本 / 执行归属及其校验。
Impact: 可能永久保留执行中、浏览器断连后提前放行新请求，或删除后迟到回写复活历史；未知影响无法由独立的UI按钮禁用消除。
Recommendation: 明确同一历史的受理 / 完成 / 删除原子条件、预期成功版本、执行身份及回收条件。回收前证明旧执行已不再拥有提交权；单API进程边界须真实可执行，不能用任意超时释放仍在执行的任务。设计对应真实PG竞争与确定性迟到提交seam；不扩张多副本承诺。

### F3：分析checkpoint与历史完成协调未定义（高）

Signal: 现有分析执行包含独立持久化，不能假设历史保存失败等于分析未执行。
Evidence: `src/business_analysis/application.py:178–199` 登记 / 读取已完成任务，`241–255` mark_completed后返回结果；`src/business_analysis/run_store.py` 使用自己的engine.begin事务，checkpoint由LangGraph管理。Spec §6 / §7要求原任务手动恢复、长期快照独立以及历史写失败不返回成功。
Impact: 保存失败后恢复可能重复执行、错误更换run ID、在checkpoint已完成时永久停留未确认；旧任务迟到写还可能影响同ID恢复。
Recommendation: 定义history identity / analysis_run_id / 本次执行身份的关系和手动恢复状态表；已完成checkpoint且历史未提交时复用已有结果的明确路径；原ID过期 / 问题不符 / 删除 / 当前权限变化均不得自动新建运行。证明历史删除和checkpoint清理不损坏独立成果。

### F4：公开接口与网页 / 旧API选择尚未固化（高）

Signal: 新长期历史请求需要编号、预期状态版本、重查 / 恢复操作，而旧接口拒绝未知字段。
Evidence: `docs/specs/query-api.md` 请求只接受既定question / mode / conversation_id / analysis_run_id，未知字段INVALID_REQUEST；Spec要求新增公开接口同时旧Bearer默认短期行为，Design清单明确接口结构待定；`frontend/src/Chat.tsx` 只维护临时conversation与analysis_run_id。
Impact: 若Ticket各自猜路由 / 字段，可能改变旧调用默认值，或把客户端结构化条件 / 用户ID作为权威；浏览器刷新定位和失败后操作也难以验收。
Recommendation: 先列API路径、身份选择、请求 / 响应 /错误 / HTTP映射、编号含义、版本和分页规则，以及刷新 /重登录 /恢复入口。客户端只能提交问题、服务端历史标识和期望版本，不提交SQL或恢复状态真相。给旧API消费者发现与兼容回归范围，不复制查询链路。

### F5：快照与结构化状态的版本 / 兼容认证未落地（中）

Signal: 进程内已校验对象跨持久化后不再自动保持其认证身份，查询结果也包含需安全编码的数值 / 时间等类型。
Evidence: QuerySuccess.semantic_query为ValidatedSemanticQuery，ConversationRecord.structured_query_state为object；`src/query_api/semantic_revision.py` 要求已校验结构化对象；Spec §4 / §10要求业务定义变化拒绝、原始值保留、UTF-8 JSON 5MiB限制。尚无快照 / 上下文codec和当前语义比较Contract。
Impact: 直接JSON重建对象可能误认已认证语义，或用全局版本替代具体业务兼容判定；精度、空值、证据公开范围与超限恢复可能分散在多处。
Recommendation: 定义可版本化的安全快照codec、续聊状态codec及与当前权威定义 / 映射比较的输入来源；复用既有公开响应序列化。未知 / 不兼容结构不得继续执行。单条快照大小检查范围、独立成果复制和无Secret约束应集中且有边界测试。

### F6：迁移、启动检查与可回滚数据边界未固化（中）

Signal: 新表依赖需进入既有显式初始化和资源生命周期，而当前只验证已登记schema / checkpoint对象。
Evidence: `src/chatbi_control/database.py:136–200` 验证CONTROL_SCHEMA_VERSION及checkpoint对象 / 权限；`204–218`扫描有序SQL迁移；`src/bootstrap/runtime.py`装配资源与启动检查。Spec列出新环境 / 旧库升级 / 可重复迁移 / 回滚验收，但无新对象和权限清单。
Impact: 开发旧库可能能运行而新clone缺对象，或新版startup错误通过；回滚删除新表会损失已确认需长期保留的历史 /成果。
Recommendation: 明确表、约束、权限、版本升级 / 幂等规则、启动完整性检查、资源关闭和保留数据的旧版回滚边界；已有账号、审计、checkpoint与业务库保持。真实PG新建 /升级测试分别提供证据。

## Reference / Evidence Sources

已读取workflow-design-review的Architecture Knowledge Core：§2复杂度、§3变化轴、§4依赖方向、§5跨边界Contract、§6避免过度拆分、§7可测试性 /状态、§8替代方案 /迁移和§9Overengineering Guard。

已核对：AGENTS.md、Harness / Git流程、architecture / product-scope / roadmap、CONTEXT.md、R3已确认Spec、Query API / Web / R2 / Evaluation Contract、现有query_api会话 / 语义修订 / 执行与响应、business_analysis Application / RunStore、Control DB migration、bootstrap runtime、网页API与结果解码。

正向结论：业务链路与业务真相边界正确；PostgreSQL Control DB是已确认且已存在的基础设施；没有新增Provider、传输协议或生产多副本承诺；测试分层和三套正式Evaluation / R3真实链路的证据身份明确。

## Next

返回实施设计阶段，围绕F1–F6完成最小充分设计，并至少比较一个真正不同的状态提交方案；保持已确认目标、范围和技术方向。当前无需用户重选产品行为。设计若需要改变公共行为、一级职责、关键技术 /依赖或授权不变量，说明影响并重新确认；否则完成后复审。复审PASS后进入Ticket草案与当前上下文Readiness；没有实施 /Commit /Push授权。
