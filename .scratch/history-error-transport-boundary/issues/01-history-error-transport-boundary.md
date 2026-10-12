# 历史错误边界与 HTTP 映射解耦

Status: done
Owner: Query API 历史 / 执行模块维护者
Blocked by: None (can start immediately)

## Change Profile

- Lifetime: 短期局部改动；交付后长期维护错误 Contract、接口映射与回归测试。
- Size: 中小；涉及 Application 错误 Contract、HTTP Adapter、持久化适配器、测试和两份 Spec / 两份 Design 文档。
- Risk: 中；错误映射变化会影响 API 可观察行为，须保持现有错误码、消息、响应体和 status。
- Evidence: Application 单元测试、HTTP API 测试、边界回归检查、静态检查和 Code Review。
- Delivery: 本地实现、验证和 Review；本 Ticket 不授权 Push、PR 或部署。

## Canonical Source

- 行为与范围：[Spec](../spec.md)
- 架构依赖方向：[架构](../../../docs/architecture.md)
- 历史行为：[历史与成果 Spec](../../../docs/specs/history-results-v1.md)
- 执行行为：[执行 Spec](../../../docs/specs/execution-streaming-v1.md)

## What to build

- 将 `HistoryError` 改为传输无关的 Application 错误 Contract：保留既有错误码、公开消息及对象标识，不携带 HTTP status。
- 增加内部 `failure_kind`，仅为确有同码异状态的业务情形分类；该字段不进入客户端响应。
- 将错误码 / `failure_kind` 到 HTTP status 的映射收敛在 HTTP Adapter；直接抛出的 `HistoryError` 与持久化 `public_error` 分别映射，未知组合 fail closed。
- 移除 `ExecutionApplication` 根据 `exc.status == 404` 分支的逻辑，以错误语义表达执行记录不可用。
- 更新所有生产代码中的 `HistoryError` 构造点，以及受影响的 Application / API 测试和测试辅助代码。
- 补充错误 Contract 与映射的回归保护，防止 Application 或存储适配器重新依赖 HTTP status。
- 按实际客户端响应路径保持 `CONTEXT_ERROR` 为 503；不要把其构造点传入的 422 误认为 HTTP 响应。两组真实多状态映射为：`EXECUTION_UNAVAILABLE` 缺省 / `EXECUTION_RUNTIME_UNAVAILABLE` → 404 / 503；`HISTORY_RESULT_NOT_SAVABLE` 缺省 / `ANALYSIS_ALREADY_COMPLETED` → 422 / 409。
- 覆盖 `history_codec` 与 `chatbi_control.execution` 中的错误构造点；全量生产调用点以移除 `HistoryError.status` 后的静态搜索结果为准。
- 更新正式文档，准确写明 `HISTORY_RESULT_NOT_SAVABLE` 的 409 / 422 情形和 `EXECUTION_UNAVAILABLE` 的 404 / 503 情形。
- 在两个正式 Spec 中维护当前错误响应 Contract；对应两个 Design 文档链接到权威 Spec，并只保留内部分类 / 映射机制说明。

## Out of scope

- 不迁移 `HistoryStore`、`ExecutionRecord`、`ExecutionAcceptance` 等 Port / DTO。
- 不新增顶层模块或重排目录；不拆分大文件。
- 不改 API 错误码、消息、响应字段 / 响应体、HTTP status、权限、数据隔离、数据库 Schema 或持久化格式。
- 不修改 Roadmap，不发布、不创建远端 PR。

## Acceptance criteria

- 生产代码与测试辅助中的 `HistoryError` 构造不再接收 HTTP status；HTTP status 由接口层确定。
- Application 与持久化适配器不读取 HTTP status，执行 Application 的 not-found 控制分支改用错误语义。
- 所有现存 HistoryError 的直接异常路径和持久化 `public_error` 路径均有显式映射；上述两组同码异状态组合由 `failure_kind` 唯一区分，`CONTEXT_ERROR` 对客户端维持 503；未知分类 fail closed。
- API 错误码、公开消息、响应 JSON、对象标识、request_id 和 HTTP status 与改动前一致。
- 测试分别验证 Application 错误语义、所有多状态映射及未知分类的 fail-closed 行为；边界回归检查能阻止 status 耦合复发。
- 两份正式 Spec 准确记录行为映射；对应 Design 链接到权威 Spec，只说明内部机制，链接有效且没有竞争的行为定义。
- 无数据库或历史快照格式变更。

## Owned files

- `src/query_api/history_contracts.py`
- `src/query_api/history.py`
- `src/query_api/history_codec.py`
- `src/query_api/execution.py`
- `src/query_api/history_api.py`
- `src/query_api/execution_api.py`
- `src/chatbi_control/history.py`
- `src/chatbi_control/execution.py`
- `tests/query_api/test_history_application.py`
- `tests/query_api/test_execution_application.py`
- `tests/query_api/test_history_api.py`
- `tests/query_api/test_execution_api.py`
- `tests/query_api/test_result_export_api.py`
- `tests/chatbi_control/test_history_postgres.py`
- `tests/chatbi_control/test_execution_postgres.py`
- `tests/history_support.py` 及必要的新边界测试
- `docs/specs/history-results-v1.md`
- `docs/specs/execution-streaming-v1.md`
- `docs/designs/history-results-v1.md`
- `docs/designs/execution-streaming-v1.md`

## Verification evidence

- 运行受影响的 History / Execution Application 与 API Software Tests，覆盖两组同码异状态映射、持久化 `public_error` 映射、对象标识与未知分类 fail closed。
- 运行边界回归检查、项目静态检查、文档检查，以及仓库要求的 Review / diff 检查。
- 记录命令、候选提交、覆盖范围、结果与未运行项；没有执行的验证不得报告为通过。

## Migration / Rollback

不涉及数据迁移、Schema、历史快照或运行时部署。出现映射回归时回滚本 Ticket 的代码与文档提交；不执行数据库操作。

## Done When

- 所有验收条件满足，适用验证与 Review 证据已关联候选提交。
- 正式 Spec / Design 描述现存行为，文档链接检查通过。
- Roadmap 经检查确认不需更新，理由是本 Ticket 仅整理既有错误边界与行为说明，不改变已确认产品目标、依赖或验收承诺。
- 本地 Diff 仅包含本 Ticket 范围；未授权发布操作未发生。

## Result

实施与验证完成，已生成本地提交候选。

## Comments

- 该 Ticket 由用户确认的 `history-error-transport-boundary` Spec 派生；Spec 已通过 Design Review，Ticket Readiness 为 READY。
- 用户已于 2026-10-12 确认该 Ticket 的单一切片及实施范围。远端发布操作仍未授权。
- 验证：Query API 软件测试 209 passed、2 skipped、14 subtests；隔离 PostgreSQL 5 passed；Python quality、文档检查、`git diff --check` 通过。
- Code Review：PASS；无遗留发现。
- 全仓 Roadmap 检查后不需修改：本 Ticket 只澄清既有错误边界和当前行为映射，没有改变已确认产品目标、依赖或验收承诺。
