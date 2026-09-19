# ChatBI 项目路线图

本路线图确定 ChatBI 从当前 V1 基线走向公司内部员工 Production V1（受控生产版）的产品与发布方向。它负责回答“为什么做、先做什么、什么条件下可以进入下一阶段”，不替代 Feature Spec、Ticket、Module Contract、测试、Evaluation 或 Business Acceptance。

具体 Feature 进入实现前，仍必须按仓库的工程流程确认 Scope、Contract、验证证据和交付边界。

## 1. 已确认的产品目标

### 1.1 目标用户

- 首要用户：公司内部员工。
- 首批用户组：尚待 Phase 0 确认；销售或经营分析相关人员是当前默认候选。
- 首要使用方式：在受控身份和数据范围内，通过 ChatBI 查询业务数据。
- 默认首期数据域：PostgreSQL `mart_sales` 单一业务域；正式发布范围仍需在 Phase 0 确认。
- 首要数据权限：只读查询；用户只能访问当前身份被授予的数据范围。

### 1.2 Production V1 边界

Production V1 的目标不是一次建设一个面向外部客户的通用 AI 平台，而是交付一个范围明确、可审计、可监控、可回滚的内部生产查询产品：

```text
自然语言问题
→ 业务语义解析
→ 已认证的 Retrieval Context
→ LLM SQL Candidate
→ 确定性 SQL Guard
→ 只读数据库执行
→ 可追踪的结果与错误
```

Production V1 允许保持以下限制：

- 单一业务域 `mart_sales`；
- 受控内部用户；
- 同步查询；
- 只读 SQL；
- 受控 Multi-Turn Query；
- Streamlit 作为当前内部入口；
- 明确拒绝无法确认口径、数据范围或 SQL 安全性的请求。

以下能力不属于当前 Production V1 的前置条件，除非真实业务场景证明需要：

- 外部客户访问；
- 多租户平台；
- 多数据源和多 Schema；
- 公开 API Gateway；
- 无限范围的 Autonomous Agent；
- 集群化平台和大规模异步任务。

## 2. 当前基线

状态基线以当前 Git checkout、对应测试和验收证据为准；历史 Acceptance 文档是当时运行时的证据快照，不能单独代表当前代码状态。

| 能力 | 当前状态 | 证据与边界 |
| --- | --- | --- |
| Online Query | 已完成 V1 | `src/online_query/`、对应 Module Spec 和确定性测试 |
| Online Retrieval / RAG Offline Build | 已完成 V1 | 已发布资产、Relationship Graph、Online Retrieval 测试和验收记录 |
| User / Data Authorization | 已完成 V1 Contract | 已有身份、策略和数据范围边界；企业 SSO 集成、生产策略和持久化审计仍需完成 |
| Multi-Turn Query | 已完成 V1 | 用户隔离、结构化状态、每轮重新授权、失败回滚和当前 Streamlit 会话；当前不承诺跨重启恢复 |
| Observability | 已完成 V1 Contract | Trace、No-op、OTLP 和安全属性处理已实现；生产告警、值班和故障响应仍需完成 |
| Query API | 已完成 V1 | `POST /api/v1/query`、`GET /health` 和稳定错误 Contract |
| Streamlit | 当前内部验证入口 | 可以完成查询和受控多轮交互；当前页面只展示最后一次结果，下一阶段补齐会话体验 |
| Software Test / AI Evaluation / Business Acceptance | 已有分层证据 | 当前多轮验收记录包含全量确定性测试、`21/21` 真实 AI Evaluation 和三轮真实 HTTP E2E |
| Production Readiness | 未完成 | 企业身份、持久化审计、Secret、限流 / 配额、性能 / 负载、部署、监控 / 告警、回滚和运维流程仍需按发布范围完成 |

## 3. 确定的阶段路线

路线不是单纯的功能清单。每个重要产品能力都必须经过确定性验证、受控试用和适用的 Production Gate（生产门禁）。

```text
当前 V1 基线
  ↓
Query Product V1：内部查询体验闭环
  ↓
Internal Pilot：内部受控试点
  ↓
Production V1：单业务域正式生产
  ↓
Business Analysis V1：受控经营分析
  ↓
Platform Evolution：按真实规模演进
```

### Phase 0：Production V1 发布契约

状态：当前阶段，方向已确认，发布契约待形成。

目标：在继续增加功能前，明确“公司内部正式使用”具体指什么。

必须确认：

- 首批用户组和业务 Owner；
- 首个正式业务场景；
- 允许访问的数据范围；
- 结果错误的可接受程度和人工兜底；
- 是否需要跨页面 / 跨重启恢复会话；
- 目标 SLO、响应时间和并发范围；
- 数据、问题、SQL、结果和审计记录的保留策略；
- Pilot、Production V1 和后续能力的发布门槛。

Done When：形成可确认的 Production V1 Release Contract（发布契约），但不提前扩大到外部客户、多租户或平台化范围。

### Phase 1：Query Product V1——内部查询体验闭环

状态：下一阶段；下一 Feature 默认是 `Conversation Timeline V1`。

目标：让内部员工能够理解并回看连续查询过程，而不只是得到最后一张结果表。

范围：

- 展示当前页面会话中的问题、成功结果和失败事件；
- 保留 Multi-Turn Query 的 `conversation_id` 和失败不提交状态语义；
- 展示结果行数、截断状态、SQL、Request ID 和 Trace ID；
- 对查询口径、指标、时间范围和维度提供可理解的结果说明；
- 点击“新建会话”后清理当前页面记录和会话引用；
- 只保留当前页面会话，不在本阶段建设持久化历史、分享或复杂分析。

不在范围内：多查询聚合、趋势 / 同比 / 环比、自动任务拆解、Agent、SQL 自动修复和多模型投票。

Done When：Streamlit 确定性测试、相关 API 行为测试和本地页面烟测通过；既有 Query API、Authorization、Multi-Turn 和 SQL Contract 不被改变。

### Phase 2：Internal Pilot——内部受控试点

状态：后续阶段；依赖 Phase 0 和 Phase 1。

目标：让有限范围的内部员工真实使用，并能追踪风险和问题。

范围：

- 企业身份 Provider / SSO 集成；
- 角色、用户组和数据范围授权；
- 持久化审计，至少可回答谁、何时、查询了什么、结果如何、是否被拒绝；
- Secret 管理、环境隔离和配置边界；
- 请求超时、限流、并发上限和成本控制；
- Health / Readiness、Trace、日志、指标和告警；
- 试点用户反馈、Bad Case Regression 和人工兜底流程；
- 部署、故障处理和回滚演练。

Done When：安全评审、试点业务验收、关键失败场景验证和运维 Runbook 评审通过；试点范围、责任人和升级路径明确。

### Phase 3：Production V1——单业务域正式生产

状态：后续阶段；依赖 Phase 2 的试点证据。

目标：在明确的内部用户和 `mart_sales` 范围内，提供可持续运行的正式服务。

范围：

- 明确 SLO / SLI、容量上限和支持时间；
- 性能、并发、超时、下游不可用和资源耗尽验证；
- CI / CD 或等价的可审查发布流程；
- Code、Prompt、Model、Metric Catalog、RAG Asset 和配置的版本管理；
- 发布前 Regression、AI Evaluation 和 Business Acceptance；
- 生产监控、告警、值班和事故响应；
- 数据、配置和已发布资产备份；
- 失败发布、模型变更、资产变更和配置变更的回滚；
- 对用户可见的错误、人工兜底和服务降级路径。

Production V1 不要求一次完成多租户、集群化或所有未来平台能力，但必须对已承诺的单业务域和内部用户范围负责。

Done When：Production Acceptance（生产验收）通过，关键告警有效，回滚演练完成，支持团队能够依据 Runbook 处理常见故障。

### Phase 4：Business Analysis V1——受控经营分析

状态：Production V1 稳定后再启动；不是当前 Production V1 的隐含前置条件。

目标：在稳定的单条查询和多轮查询之上，增加有限范围的经营分析能力。

范围方向：

- 有边界的分析任务拆解；
- 有上限的多查询执行；
- 结果和证据汇总；
- 业务口径和数据来源解释；
- 明确的无法回答、数据不足和权限拒答；
- 针对多查询结果的 AI Evaluation、Business Acceptance 和成本控制。

不直接建设无限制的 Autonomous Agent；复杂分析必须有可追踪的计划、查询、证据和失败状态。

### Phase 5：Platform Evolution——按真实规模演进

状态：条件触发，不预先建设。

只有在内部使用规模、业务域数量或运行约束证明需要时，才考虑：

- 多业务域和多数据源；
- 多租户和更细的隔离；
- AI Gateway、Provider Routing 和统一成本治理；
- 异步分析任务、队列和缓存；
- 集群、高可用和跨环境平台化；
- 面向外部客户的开放能力。

## 4. 阶段门禁

每个 Phase 的实现仍遵循以下顺序：

```text
明确 Scope / Release Contract
  → Feature Spec
  → Design Review
  → Ticket Readiness
  → TDD / 实现
  → 确定性测试
  → Code Review
  → 本地 Commit
  → Candidate / PR 交付
```

不同证据不能相互替代：

- Software Test 证明确定性软件行为；
- AI Evaluation 证明标准案例下的模型链路表现；
- Business Acceptance 证明目标业务场景可用；
- Runtime / Integration 证明真实服务、数据库、Qdrant、模型和发布入口；
- Security / Production Acceptance 证明身份、数据范围、审计、监控、发布和回滚满足正式环境要求。

## 5. 如何查询当前状态

以后询问“当前状态”“做到哪了”“下一步做什么”时，按以下事实来源回答：

1. 本文件：确认长期产品路线和各 Phase 的目标；
2. 当前 Git branch、HEAD、Git status：确认实际 checkout 是否与路线一致；
3. `.scratch/<feature>/spec.md` 和 `issues/`：确认正在执行的 Feature / Ticket；
4. `src/` 与 `tests/`：确认实现和确定性测试；
5. `reports/`、`docs/acceptance/` 和运行记录：确认 AI Evaluation、Integration、Business Acceptance 和 Runtime 证据；
6. 只有证据满足对应 Done When，才能把 Phase 标为 `done`。

状态使用以下含义：

- `done`：Contract、实现和适用证据均已完成；
- `current`：当前正在澄清或实施；
- `next`：已确定方向，但尚未开始；
- `planned`：路线中已确认，但依赖前置阶段；
- `conditional`：只有真实需求或规模证明后才启动；
- `blocked`：存在已确认且无法在当前范围内解决的阻塞条件。

路线图中的“规划”不等于“已经实现”，历史验收记录也不自动覆盖当前 checkout。

## 6. 当前决定

截至本路线图确认：

- 产品目标：公司内部员工使用 ChatBI；
- 默认首期范围：单一业务域 `mart_sales`，但首批用户组、业务 Owner 和首个正式场景仍需在 Phase 0 确认；
- 当前系统定位：内部验证 / 受控生产演进，不是外部通用平台；
- 当前下一阶段：Phase 0，形成 Production V1 发布契约；
- 当前下一 Feature 默认候选：Phase 1 的 `Conversation Timeline V1`；
- Business Analysis：保留为 Production V1 稳定后的后续能力；
- 平台化：仅在真实规模和需求出现后建设。
