# 03 首次改密浏览器用例使用独立账号

Status: ready-to-commit
Canonical Source: [Spec](../spec.md)、[Design](../design.md)、[草案](../tickets-draft.md#03-首次改密浏览器用例使用独立账号)
Owner: 当前主 Agent
Change Profile: 小范围测试 fixture 生命周期修复；中低风险；浏览器 / HTTP 与隔离 SQLite 支持应用。
Blocked by: None (can start immediately)

## What to build

为首次改密浏览器用例准备唯一测试账号，并在成功或失败时清理会话和账号。保持正式登录与首次改密规则不变；账号管理能力仅装配在隔离测试支持应用，生产应用不增加测试后门。

Owned files: `tests/browser_support.py`、`frontend/tests/auth.spec.ts`、必要的前端测试 helper / fixture、对应隔离测试和 Web 测试说明。

Out of Scope: 改变首次改密业务流程、共用固定账号状态，或在正式应用注册测试账号管理接口。

## Acceptance criteria

- 同一支持服务上 `./dev test web auth.spec.ts --grep 'first password change' --repeat-each=2` 连续通过，使用不同账号且清理完成。
- 断言失败 / 测试中断时仍清理账号和会话；清理失败不能记为通过。
- 完整浏览器与 Vite 代理回归通过；测试 fixture 管理能力不会进入正式应用，也不能修改固定 / 非本次测试身份。

Migration / Rollback: 无真实账号迁移；仅回退测试装配，不读写日常账号。

## Result

Code Review: PASS；未修改 `src.query_api` 或首次改密业务逻辑。测试支持应用为每次创建随机账号并签发不透明句柄，删除只能操作本进程签发且名称仍在测试命名空间内的账号；SQLAlchemy 删除级联清理 Session。生产 `create_app` 未装配该 Router，定向 404 检查通过；没有发现需修改的问题。

TDD: Red 阶段支持应用账号创建请求返回 404；新增测试固定这一行为目标。实现后测试创建两个不同账号、验证初始首次改密状态、清理目标及其 Session、拒绝伪造句柄且保留 analyst。Playwright 用例在 `finally` 删除自己账号，清理失败会导致测试失败。

Verification: `uv run --locked pytest -q tests/query_api/test_browser_auth.py`（22 passed）；`./dev test web auth.spec.ts --grep 'first password change' --repeat-each=2`（首次改密 2 passed，Vite dev 代理 1 passed）；完整 `./dev test web`（浏览器 67 passed，Vite dev 代理 1 passed）。Ruff format / check、文档链接检查、TypeScript typecheck 均通过。浏览器 runner 构建的是 `chatbi-browser-dev:local` 测试环境，不构建业务 APP 镜像；临时测试容器和网络由 runner 清理。

Commit: 本地提交待执行；没有 Push / PR。

## Comments

调查证据为同服务 `--repeat-each=2` 一过一败，第二次仍复用第一次改密后的账号状态。
