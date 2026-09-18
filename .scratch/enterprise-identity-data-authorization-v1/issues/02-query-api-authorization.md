# 02: 接入 Query API 服务端身份授权

**What to build:**

将 FastAPI Query API 迁移到授权入口：

- 由服务端 Identity Provider Adapter 生成 AuthContext。
- 请求体继续只接收查询问题，不能接收 subject_id、角色或数据范围。
- 接入静态授权策略。
- 将身份失败、授权失败和认证基础设施故障映射为 401、403、503。
- 显式选择 Demo/Test Provider。
- 生产环境启用 Demo/Test Provider 时拒绝启动或拒绝请求。
- 保留现有受控错误响应和 request_id 关联。
- 保持健康检查等不执行用户数据查询的运维端点不进入用户查询授权链路。

**Blocked by:**

01: 建立授权核心与 AuthContext Application Entry

**Status:** done

## Acceptance criteria

- [x] 已授权 HTTP 请求能够得到原有只读查询结果。
- [x] 未认证请求返回 401，且不调用查询服务。
- [x] 已认证但未授权请求返回 403，且不调用查询服务。
- [x] Provider 或策略存储不可用时 Fail Closed，并返回 503 或统一服务错误。
- [x] 伪造请求体身份字段不能冒用其他用户。
- [x] 生产配置不能自动回退到 Demo 身份。
- [x] 现有 request_id 和受控错误响应 Contract 保持可观察一致。
- [x] Query API 不复制 Online Query、SQL Guard 或数据库执行逻辑。

## Result

已完成 Query API 的服务端身份与静态授权接入：

- `create_app` 通过服务端 `IdentityProviderAdapter` 生成 `AuthContext`，再经 `AuthorizedQueryService` 执行 `mart_sales:query:read_only` 授权；未提供依赖时默认 Fail Closed。
- Query body 继续只接受 `question`；Pydantic `extra="forbid"` 和确定性 400 校验阻断客户端提交身份字段，非法请求不进入下游查询服务。
- 增加 401、403、503 的受控 HTTP 映射，并保留 `request_id`、`X-Trace-ID` 和既有错误响应字段边界；`/health` 不进入查询授权链路。
- 增加显式 development/test 环境、`demo` / `test` Provider 与外部 JSON 静态策略文件配置；缺失或未知环境、`production` / `prod` 环境都会拒绝静态 Provider，不自动回退到 Demo 身份。
- 增加 `.env.example`、`config/authorization-policy.example.json` 和 Runbook 配置说明；未接入具体企业 SSO。

验证证据：

- `uv run --with pytest python -m pytest -q tests/query_api tests/authorization tests/online_query`：211 passed，6 skipped，95 subtests passed。
- `uv run --with pytest python -m pytest -q`：320 passed，6 skipped，107 subtests passed。
- `uv run python -m compileall -q src tests`：通过。
- `uv run --python 3.11 --with ruff==0.16.8 ruff format --check src tests`：通过。
- `uv run --python 3.11 --with ruff==0.16.8 ruff check --select E4,E7,E9,F src tests`：通过。
- `git diff --check`：通过。

## Comments

本 Ticket 负责正式 HTTP 用户入口的安全接入，不接入具体企业 SSO。真实 Provider 仍由后续独立 Feature 通过 Adapter 提供。

Ticket 02 固定的最小策略文件格式为：`policy_version` 字符串和 `allowed_subjects` 字符串数组；策略挂载、热更新和真实企业 Provider 仍不在本 Feature 内。
