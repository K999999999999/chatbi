# 03: 迁移 Evaluation 与内部调用到显式 Test Identity

**What to build:**

将 Evaluation、Online Query 测试和其他直接调用查询服务的内部调用迁移到统一授权入口：

- 使用显式 Test IdentityProvider 或授权测试身份。
- 不再通过缺少 AuthContext 的方式执行完整查询。
- 保持既有 Evaluation、PostgreSQL 集成和确定性测试的业务行为。
- 将测试中的授权身份、拒绝身份和下游 Spy 固定为可观察 Fixture。
- 不改变指标、Retrieval、Prompt、SQL Guard 或 Evaluation 业务规则。

**Blocked by:**

01: 建立授权核心与 AuthContext Application Entry

**Status:** done

## Acceptance criteria

- [x] Evaluation 在显式测试身份下可以复用正式 Online Query 链路。
- [x] 现有确定性测试和 PostgreSQL 集成测试保持通过。
- [x] 缺少 AuthContext 的非测试查询调用不能绕过授权。
- [x] 测试能够覆盖允许、未授权和基础设施失败路径。
- [x] 既有 AI Evaluation 的查询语义和结果比较行为不被改变。
- [x] 内部测试调用使用统一 Application-level Query Entry，而不是保留另一套授权逻辑。

## Result

已完成 Evaluation 与内部评测链路迁移：

- 新增 `BoundAuthorizedQueryService`，把显式 `AuthContext` 绑定到既有 `AuthorizedQueryService`，内部调用不复制授权规则。
- `src.evaluation.__main__.run_cli` 使用显式 `test/evaluation-test` Identity 和静态策略，再把绑定后的 Query Entry 传给 `run_evaluation`。
- `run_evaluation` 依赖通用已装配 Query Entry Contract；V1 Acceptance 和共享 Trace 测试使用同一授权入口，低层 Online Query 单元测试仍只验证自身业务语义。
- 授权核心覆盖允许、缺失身份、未授权、策略不可用和非法策略决策的下游抑制；既有 Evaluation 结果比较、Trace 关联和 Retrieval/SQL 行为保持不变。

验证证据：

- `uv run --with pytest python -m pytest -q tests/evaluation tests/authorization tests/query_api`：83 passed，12 subtests passed。
- `uv run python -m compileall -q src tests`：通过。
- `uv run --python 3.11 --with ruff==0.16.8 ruff format --check src tests`：通过。
- `uv run --python 3.11 --with ruff==0.16.8 ruff check --select E4,E7,E9,F src tests`：通过。
- `git diff --check`：通过。

## Comments

这是迁移阶段。它覆盖 Evaluation、Online Query 测试和其他已确认的内部直接调用，不引入生产身份 Provider。
