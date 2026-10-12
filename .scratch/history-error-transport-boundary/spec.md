# 历史错误与 HTTP 状态映射边界

状态：修订版，用户已确认方向及实施范围；Design Review PASS

## 问题

`src/query_api/history_contracts.py` 中的 `HistoryError` 同时承载稳定错误码、公开消息、对象标识和 HTTP status。该类型既由 Query API Application 使用，也由 `src/chatbi_control` 持久化适配器构造；HTTP 层直接读取 `HistoryError.status` 返回响应。这样存储错误 Contract 带有传输层状态语义。

`HistoryStore` Protocol、历史与执行 DTO 属于 Application 与适配器之间的稳定 Contract。它们的当前位置和适配器对这些类型的依赖不属于本 Spec 的迁移范围。

## 目标与预期结果

- 将历史操作错误表达为与 HTTP 无关的 Application Contract：保留错误码、公开消息及可选历史 / 轮次 / 执行标识，不再携带 HTTP status。
- 增加可选的内部 `failure_kind`，只用于区分同一个错误码在不同业务结果下的状态语义；它不是 HTTP 状态码，也不进入响应 JSON。已存在且一对一的错误码可沿用 HTTP Adapter 的显式错误码映射；同码多状态错误必须附带 `failure_kind`，由 Adapter 使用错误码与分类共同映射。
- HTTP Adapter 是唯一把错误 Contract 映射为 HTTP status 的边界。Application 控制流根据错误码 / `failure_kind` 判断，不读取 status。
- 对现有客户端保持可观察行为不变：错误码、消息、响应字段、响应体和 HTTP status 均保持当前结果。
- 保持数据库事务、owner 隔离、重试 / 幂等和历史状态行为不变。

按实际 HTTP 路径盘点后，当前需保留的同码多状态情形如下。仅在异常直接到达 HTTP Adapter 时，Adapter 才能看到 `failure_kind`；执行结果持久化时仍只存既有错误码和消息，由现有公开错误码映射决定 status，不扩展持久化格式。

| 错误码 | 当前 HTTP status | 业务情形 / `failure_kind` |
| --- | --- | --- |
| `EXECUTION_UNAVAILABLE` | 404 / 503 | 执行记录不存在或对当前 owner 不可见（`failure_kind` 缺省映射 404） / 执行 Runtime 关闭或受理后 worker 调度失败（`EXECUTION_RUNTIME_UNAVAILABLE` 映射 503） |
| `HISTORY_RESULT_NOT_SAVABLE` | 409 / 422 | 已完成的分析无需恢复（`ANALYSIS_ALREADY_COMPLETED` 映射 409） / 保存来源结果不是可另存的成功结果（持久化错误按错误码映射 422） |

`CONTEXT_ERROR` 构造点虽曾传入 422 或 503，但历史 Application 会将可保存错误降为仅含错误码 / 消息的 `public_error`，再由 Query API 的固定错误码映射返回 503；这不构成两个当前 HTTP status。移除构造参数时统一按实际接口行为映射为 503。上述两组真实 status 差异属于需保留的当前 API 行为。正式文档目前未覆盖所有情形；交付时须修正文档以准确表达按业务情形区分的映射，不以当前文档遗漏推导为统一 status，也不改变现有客户端响应。

## 实施边界

- 只调整历史 / 执行相关错误 Contract 及 HTTP 映射调用点；所有 `HistoryError` 构造点必须移除 HTTP status 参数。
- 正式文档按职责同步 Contract 与实现说明：在 `docs/specs/history-results-v1.md` 和 `docs/specs/execution-streaming-v1.md` 明确两组同码异状态及当前 status；两个对应 `docs/designs/` 文档链接到权威 Spec 并说明内部映射机制，不复制行为表。
- 保留现有错误码和响应 JSON；完整盘点直接抛出的 HistoryError 与已持久化 public_error 两条响应路径，确保错误码 / failure_kind / HTTP status 映射穷尽、同码多状态可区分且未知组合 fail closed。
- 将 `ExecutionApplication` 中依赖 `exc.status == 404` 的控制判断改为检查错误语义，不以 HTTP status 驱动 Application 行为。
- 更新现有软件测试，使 Application 错误语义与 HTTP 映射分别可验证；不得更改数据库 Schema 或历史记录格式。
- 保留 `HistoryStore`、`ExecutionRecord`、`ExecutionAcceptance` 等 DTO / Port 的现有归属，不新增顶层业务模块。

## 非目标

- 不迁移整个 `HistoryStore` 或 DTO 契约，不重排 `backend/`、`src/`、`frontend/` 目录。
- 不拆分 `app.py`、`history.py`、`Chat.tsx` 或部署脚本。
- 不改变 Query API / History API、错误码、错误文本、HTTP 状态、授权、数据隔离、数据库结构或当前产品范围。
- 不修改 Roadmap；该工作属于已报告的局部架构边界整理，不新增产品承诺。

## 验收与验证

- 非 HTTP Application 与持久化代码不再读取或构造 HTTP status；Application 分支不再依赖 status。
- HTTP 层对直接抛出的 HistoryError 与 public_error 分别有明确映射；当前所有客户端可见状态映射与修改前一致，包括表中两组同码多状态错误。不得将 HistoryError 构造点的 status 误作当前 HTTP 行为。
- 既有 API 响应体、公开消息、状态码、request_id 和对象标识保持兼容。
- 正式文档准确区分表中同码异状态的业务情形，并维持 Spec 与 Design 各自的职责。
- Application 单元测试覆盖错误码 / 对象标识；API 测试覆盖错误码至 HTTP status 的映射；相关模块边界检查保护职责归属。
- 按仓库流程执行受影响 Software Test、静态检查、Code Review 和 diff 检查。验证未执行时不得报告为通过。

## 授权依据

用户在全面审查后确认优先处理 P2 Contract 边界问题；之后确认在错误 Contract 中增加 HTTP 无关的失败分类，以维持同码多状态的现有 API 行为，并确认单一 Ticket 粒度及按该 Ticket 实施。本 Spec 不授权后续大文件拆分、发布或远端操作。
