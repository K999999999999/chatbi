# MVP 生产基线一致性与资源可追溯

Status: confirmed
Last updated: 2026-09-29

## Problem Statement

ChatBI 已进入 MVP 向生产演进阶段。当前仓库存在几类可能影响系统正确性或基线判断的一致性风险：PostgreSQL Schema、Structure Metadata 与 Qdrant 发布资产之间缺少可验证的版本关联；空环境初始化路径可能没有安装 Business Analysis 所需的 LangGraph checkpoint 表；历史 Evaluation 报告来自旧提交，不能代表当前 HEAD；部分当前状态、指标数量和验收说明仍沿用旧事实。

此前的 `.scratch/reproducible-local-dev-environment/spec.md` 及其 Ticket 记录了开发环境建设和当时的验收结果，属于历史交付证据。本 Spec 不覆盖或删除这些记录；本轮必须以当前 HEAD 和实际初始化路径重新核实，不把历史结果视为当前验收。

## Solution

建立一个可复核的 MVP 基线，使数据库结构、仓库中的 Structure Metadata、Semantic Metrics、Qdrant 索引资产、全新环境初始化行为和当前 Evaluation 结果能够追溯到同一份当前代码状态。

发生已发布 RAG 资产与当前 Schema / Structure Metadata / Metrics 不一致时，生产路径停止使用该资产并明确失败；不得静默继续使用旧索引或静态回退。Baseline 验收使用当前 HEAD 重新生成的 Evaluation 报告。相关文档应反映当前已实现的 MVP 能力和生产准备状态，并清楚标记历史报告。

本 Spec 只固化一致性与基线 Contract，不要求一次性完成所有生产化能力。

## User Stories

- 作为部署与维护者，我能判断当前 Qdrant 发布资产是由哪些 Schema、Structure Metadata、Metrics 和 Embedding 配置构建的。
- 作为系统维护者，若运行时资源与已发布索引不一致，系统会拒绝使用该索引，并提供可定位的失败信息。
- 作为新开发者，我能从空环境按仓库入口初始化完整的 Control DB，包括 Business Analysis 运行所需的 checkpoint 表，并通过健康检查确认初始化完成。
- 作为项目维护者，我能从当前 HEAD 获得明确标识提交和工作区状态的 Evaluation 基线，不会把旧报告误当成当前结果。
- 作为维护者，我能从文档识别当前 MVP 已实现能力、暂缓事项和历史验收证据。

## Change Profile

- Lifetime: 长期维护的运行时资源校验、初始化流程、Evaluation 证据和项目文档。
- Size: 跨 RAG / Bootstrap / Evaluation / 文档的多阶段工程目标。
- Risk: 高；涉及在线 Retrieval 使用的索引、Business Analysis 状态持久化和 AI Evaluation 基线。
- Evidence: 确定性测试、空环境初始化验证、Qdrant 资产指纹验证，以及当前 HEAD 的 AI Evaluation。
- Delivery: 先通过 Spec 与设计审查，再拆为同一目标下可独立验收的 Tickets；不在本 Spec 阶段实施。

## Implementation Decisions

### 已确认的 Contract

1. 结构 Schema 的维护顺序是：修改 `database/` 中的 DDL → 更新实际 PostgreSQL 数据库 → 从实际数据库导出 Structure JSON。DDL 是期望的结构定义，运行中的 PostgreSQL catalog 是该环境实际生效结构的事实；Structure JSON 是从数据库导出的 RAG 结构输入，不反向覆盖 DDL。
2. `src/semantic/metrics.json` 是指标定义和业务口径的事实源；Golden Set 是正确性证据，不得反向定义或修改业务指标口径；Qdrant 文档、向量和关系图均为派生产物。
3. RAG 资产需要记录足以识别其源输入和构建配置的指纹。生产服务进入 Ready（可服务）状态前，必须核验实际 PostgreSQL Schema、Structure Metadata、Semantic Metrics 与已发布索引对应一致；无法核验或不一致时必须 fail closed（不进入可服务状态 / 拒绝在线查询），不得使用陈旧索引或静态回退。Schema 结构变更后需重新导出 Metadata 并构建匹配索引，再允许服务就绪。
4. 建立当前 HEAD 的评估基线，包含：Single-turn 29 cases、Multi-Turn 7 conversations、Business Analysis 10 cases。Query Understanding 6 cases 作为辅助证据。三个必需套件各自要求 `0 FAIL`、`0 INVALID_CASE`。
5. 建立当前 HEAD 基线前，必须核对 Golden Set 中的指标、预期结果类型、过滤条件和行为断言仍符合当前产品 Contract 及 `metrics.json`。发现实质不一致时停止该基线验收并报告；本 Spec 不授权自行修改案例或业务口径。
6. 产品当前定位按“MVP 向生产演进”表述；文档需区分已实现的 MVP 能力与尚未完成的生产准备工作。
7. `src/semantic/dimensions.json` 的职责和是否保留本轮暂缓，不纳入本 Spec 的行为变更范围。

### 实现设计阶段决定

- 采用稳定、可复算的 Schema / Metadata / Metrics / Embedding 指纹格式，以及实际 PostgreSQL catalog 与 Metadata 的规范化比较方式。
- 将一致性核验接入生产服务 Ready 门禁的具体代码边界、运行时装配和可诊断错误呈现。核验失败时的外部行为仍必须满足 fail closed Contract。
- 如何把首次 Control DB 初始化纳入仓库入口：初始化过程须建立当前 migration、LangGraph checkpoint 表与权限；健康检查缺失任一关键对象时不得报告健康。具体调用现有 migration CLI 的编排方式留给设计。
- 首次初始化编排必须避免健康检查等待 checkpoint migration、而 migration 命令又等待数据库健康的启动死锁；Runbook 中从 clean clone 开始的完整命令路径必须能到达数据库健康且应用可启动。
- DDL、初始化 SQL、Structure JSON 和导出流程通过何种检查避免日后漂移；至少要能在基线验收中验证实际数据库结构与导出 Metadata 一致。是否增加 CI 自动检查由设计阶段根据现有入口选择最小实现。
- 当前 HEAD Evaluation 报告明确记录 commit、工作区状态、案例集和相关资源指纹。历史报告保留为历史证据，不得被标记或展示为当前 HEAD 基线。
- 文档中关于产品能力、指标数量、Golden Set 数量、初始化命令和 Evaluation 状态的陈述与当前实现和报告一致；不同文件不得保留互相冲突的当前事实。

## Testing Decisions

- 对 RAG 指纹执行确定性测试：任一纳入指纹的源资产或关键 Embedding 配置变化都会改变指纹；相同输入可复算出相同指纹。
- 对在线 Retrieval / Ready 门禁执行通过与失败边界验证：实际 PostgreSQL Schema、Structure Metadata、Metrics 与已发布资产一致时可就绪；任一缺失、无法验证或不匹配时生产服务不可就绪且不接受在线查询，不走旧索引或静态回退。
- 验证 DDL 所定义的结构、全新数据库初始化后的 catalog、导出的 tables / columns / relationships Metadata 在结构投影上相符；描述和 `value_examples` 等非 catalog 属性按其各自来源核对，不要求从 DDL 推导。
- 使用全新 PostgreSQL / Control DB 环境验证 migrations、checkpoint 表、运行账号权限和初始化健康检查；删除或缺失 checkpoint 表时健康检查必须失败。
- 从 clean clone 按 Runbook 完整执行首次初始化，不得发生服务健康等待与 checkpoint migration 相互阻塞；初始化完成后 Postgres 健康状态、API 启动条件和 Business Analysis checkpoint 写入均可验证。
- 在最终当前 HEAD 上，先完成 Golden Set 与当前产品 Contract / `metrics.json` 的一致性核对，再分别运行 Single-turn、Multi-Turn、Business Analysis 三个必需 Evaluation 套件，并核对报告提交、dirty 状态、案例集版本及 `FAIL` / `INVALID_CASE` 计数。每个套件须满足已确认的零失败门槛；实质案例冲突未解决时不得签发通过的当前基线。
- 验收时 Query Understanding 套件作为辅助证据运行或记录；它不替代上述三个必需套件。
- 更新文档后做交叉核对：案例数量、指标数量、功能支持状态、初始化步骤和报告身份均能对应到当前仓库证据。纯文档交叉核对不替代运行时测试或 AI Evaluation。

## Out of Scope

- 修改业务指标定义、SQL 计算口径、授权规则、Query / Business Analysis 产品 Contract 或 Golden Set 期望答案。
- 决定或重构 `dimensions.json` 的业务语义；该话题暂缓。
- 迁移生产数据、部署生产服务、管理生产 Secret、制定流量 Rollout 或建设新的运维平台。
- 为开发环境引入新的数据库、Qdrant 或 Evaluation 报告系统。
- 删除、重写或伪装历史 Evaluation、Acceptance、Ticket 或 `.scratch` 记录。
- 在 Spec 阶段创建实现 Tickets、修改代码或运行会产生外部 LLM 请求并写入新报告的 Evaluation。

## Further Notes

- 当前本地数据库的 Schema 与导出 JSON 曾被只读比较为一致；该事实只代表检查时的本地实例，不代表所有环境或未来提交始终一致。DDL 负责期望结构，实际数据库负责当前环境生效结构，JSON 负责给 RAG 构建消费的结构化投影；三者职责不能混写为互相替代的事实源。
- 当前 Qdrant 集合数量与当前源资产数量相符，但仅凭数量无法证明索引内容对应当前源文件。需要实现 / 验证内容级 provenance（来源可追溯性）。
- 现有 Runbook 描述显式执行 `src.chatbi_control migrate` 的条件，与 clean clone 首次初始化是否自动建立 checkpoint 表之间存在明确差异；本 Spec 要求首次初始化完成后 checkpoint 表和权限已就绪。
- 当前存在已确认的旧报告和旧文档数量陈述；旧报告应继续保留并明确标成历史结果。
- 本 Spec 已由用户确认；通过只读 `design-review` 后，方可拆分并审查实现 Tickets。Spec 与 Ticket 确认均不自动授权实现、Commit、Push 或 PR。
