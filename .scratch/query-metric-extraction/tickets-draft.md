# 实施项草案

状态：草案，尚未写入正式 Ticket。依据：[Spec](spec.md)、[实施设计](design.md)、[设计审查 PASS](design-review.md)。

采用一个完整纵向实施项：提示词、修订及认证对同一身份语义相互依赖，分别交付会制造可被运行的半成品。此项自带适用软件测试、AI Evaluation、历史入口验收和文档，不另拆“只改代码 / 再补测试”的水平任务。

## Ticket 01：指标原话提取贯通单轮、多轮与历史认证

### Change Profile

- Lifetime：一次目标内完成候选及适用验证；长期维护归现有 Online Query / Query API / Evaluation 模块。
- Size：单一业务规则，中等改动；涉及已有 Prompt、认证、修订及其测试 / 评测，不新增运行组件。
- Risk：指标别名与规范身份衔接、已有排序 / 聚合筛选和历史状态兼容；保持 Guard 和失败关闭。
- Evidence：确定性软件回归、真实解析 / 正式单多轮评测、完整历史 profile 与网页验收、文档检查、只读 Code Review。
- Delivery：独立本地原子候选及中文 Commit；不含 Push、PR、Merge 或对旧验证分支的整合授权。

### Owner

当前主 Agent 负责实施、验证和文档；不涉及独立团队或需新增 Backup Owner 的运行职责。

### Blocked by

None（设计审查已 PASS；开始前仍需用户确认本草案及实施授权）。

### What to build

1. 单轮、多轮 delta、历史首轮及历史修订保留指标原话，既有词汇供给与受控歧义澄清仍可用；排序 / 聚合引用遵守同一规则。
2. 复用现有检索结果和认证边界，统一指标及引用的权威身份；所有校验只授权本次已选指标；普通在线与历史入口均保持正确。
3. 历史修订将依赖指标身份的字符串成员检查与认证衔接；同指标别名保留等价条件，真实替换造成旧条件含义不明仍澄清，失败不更新状态。
4. 对齐查询理解评测，保留原六例原话期望，兼容地补充规范名、别名、多指标、受控澄清和多轮案例；报告能判定解析阶段，不用最终成功掩盖解析错误。
5. 更新当前正式查询 / 检索 / 恢复文档和必要评测操作说明，纠正文档与实现的已查实检索次数差异；检查路线图适用性并记录理由。

### Owned files

- 主要实现：`src/online_query/query_understanding_llm.py`、`src/online_query/semantic_state.py`、`src/online_query/service_execution.py`、`src/query_api/semantic_revision.py`；仅在复用比较逻辑所需时局部调整现有 `src/online_query/retrieval/multi_metric.py`，不改检索策略。
- 软件验证：`tests/online_query/test_query_understanding_llm.py`、`test_query_understanding_service.py`、`test_retrieval.py`、`test_history_query_execution.py`、`test_history_calendar_guard.py`，`tests/query_api/test_history_revision.py`、`test_history_application.py`、`test_multi_turn_revision.py` 及直接相关测试。
- 评测：`evaluation/suites/query_understanding/`、对应 `tests/evaluation/query_understanding/`；必要的正式单多轮 / 历史验收案例及本目标报告目录。
- 文档：`docs/specs/online-query.md`、`online-retrieval.md`、`query-restoration.md`，必要的 `docs/runbook.md` / `docs/roadmap.md`，本工作项验证和 Review 记录。
- 不拥有：旧验证 worktree、模型及真实配置、指标目录业务定义、历史数据与账号、无关测试整理。若需触及已确认边界以外的文件或行为，先依据 Design Review 规则检查是否需要回到设计阶段。

### Acceptance criteria

- “人民币销售额”“营收”“毛利”分别以原话进入解析候选和检索，认证身份及最终结果正确；客户明确说规范名时也正确。
- “毛利和毛利率”等多指标完整有序，不能混淆、丢项或暗中增加指标；METRIC 未命中或歧义继续拒绝，Provider / 资产技术故障不冒充澄清。
- “利润”等解析歧义得到现有澄清，后续检索 / SQL / 数据库调用数为零；输出结构错误仍为技术解析错误。
- 排序 / Top-N 和既有合法聚合筛选在指标引用认证后仍正确；旧历史续聊使用另一登记别名不误改条件，真正指标替换时旧聚合条件仍需澄清。
- 非法目标、候选外指标、认证后冲突条件安全拒绝；不会执行 SQL，也不会推进历史成功状态。
- 已有规范身份历史快照可重开、重查和续聊，状态版本、旧时间及旧结果不变。
- 真实模型及正式入口证据关联同一候选及明确案例 / 资源；软件回归、静态检查、文档检查和只读 Code Review 均满足目标；不能用旧候选的规范名 `6/6` 声称本次通过。

### 验证证据

- 软件：先覆盖解析 → 检索 → 认证 / 修订 → Prompt / Guard → 状态提交的受影响用例；按 Runbook 使用 `./dev test python` 或该入口支持的定向参数、`./dev check`，必要数据库 / Web 用例使用对应正式容器入口。记录精确命令、候选身份和结果；不因历史全绿跳过受影响断言。
- 模型：`./dev evaluate --query-understanding`、`./dev evaluate --online-retrieval`、`./dev evaluate --multi-turn --online-retrieval`。案例数量以本次确认的集合为准，报告分开保留解析输出、权威指标认证与执行结论，不固定为历史数字。
- 历史 / 网页：通过正式 history profile 覆盖原话指标 + 排序 / Top-N、合法单指标聚合筛选、旧规范状态恢复，以及同指标别名修订；优先扩展已有验收 seam，保存可审核的业务条件和结果证据，不新建产品入口。
- 边界回归：复用查询入口的经营分析确定性测试；本次未改其独立解析规则，不无依据扩大真实经营分析基线。
- 真实评测使用已有本地配置且会调用已配置模型 / 检索服务；不输出 Secret、不更换模型或重建资产掩盖结果。若资源不可用，保留可继续的候选及明确缺失证据，不伪造验收。

### Migration / Rollback

无数据表或状态版本迁移。一个候选原子交付及完整代码版本回滚；已持久化规范身份继续兼容。保留原问题和旧报告。原验证分支保持原样，后续交付需独立核对整合方式。

### Done When

验收条件和适用验证完成，真实外部检查无未说明缺口，文档及路线图处置有据，候选 Diff 和只读 Review 通过后本地提交并更新实时进度。测试不通过先定位，若必须改变已确认指标语义、架构、错误 Contract 或安全边界，回到 Spec / Design Review；不弱化断言、Guard 或直接改期望凑分数。远端发布等待另行授权。
