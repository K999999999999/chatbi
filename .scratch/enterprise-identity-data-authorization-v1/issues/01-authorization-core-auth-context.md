# 01: 建立授权核心与 AuthContext Application Entry

**What to build:**

建立 provider-neutral 的身份与授权核心，提供：

- AuthContext，只包含 subject_id 和 identity_provider。
- Identity Provider Adapter Contract。
- AuthorizationPolicyStore Contract 和静态策略实现。
- mart_sales:query:read_only 的确定性授权决策。
- 401、403、503 对应的应用层失败语义。
- AuditSink 事件 Contract。
- Demo/Test IdentityProvider 的测试实现。
- 一个要求可信 AuthContext 的 Application-level Query Entry。
- 授权检查位于 LLM、Retrieval、SQL 和数据库之前。

为保留现有调用方可运行，暂时保留旧查询入口，但只作为迁移期间的内部过渡入口，不接入正式 API。

**Blocked by:**

None (can start immediately)

**Status:** done

## Acceptance criteria

- [ ] 已授权 AuthContext 可以查询 mart_sales。
- [ ] 缺少身份、身份无效或未授权时，查询下游不会被调用。
- [ ] 其他资源、Schema、字段和写操作默认拒绝。
- [ ] 客户端无法通过身份字段改变服务端的 AuthContext。
- [ ] 授权决策不依赖 LLM、用户问题或 SQL。
- [ ] Application-level 测试能够观察授权结果和下游调用是否被抑制。
- [ ] Domain 不依赖具体 Provider SDK、Token 格式或平台对象。

## Result

已完成 Ticket 01 的授权核心最小闭环：

- 新增 provider-neutral AuthContext、Identity Provider Adapter Contract、AuthorizationPolicyStore 和 StaticAuthorizationPolicyStore。
- 新增 AuthorizedQueryService，在 LLM、Retrieval、SQL 和数据库之前执行 mart_sales:query:read_only 授权。
- 新增 Demo/Test 场景使用的 StaticIdentityProviderAdapter。
- 增加认证缺失、授权拒绝和策略不可用的 QueryErrorCode。
- 保留旧查询入口供后续 02、03 迁移，待 06 收口。

验证证据：

- `uv run --with pytest python -m pytest -q tests/authorization tests/online_query tests/query_api`：199 passed，6 skipped，95 subtests passed。
- `uv run python -m compileall -q src tests`：通过。
- `uv run --python 3.11 --with ruff==0.16.8 ruff format --check src tests`：通过。
- `uv run --python 3.11 --with ruff==0.16.8 ruff check --select E4,E7,E9,F src tests`：通过。
- `git diff --check`：通过。

## Comments

这是 Expand 阶段。旧查询入口只允许作为迁移期间的内部过渡路径，不能被正式 Query API 使用。后续由 02、03 完成调用方迁移，再由 06 收口旧 Contract。
