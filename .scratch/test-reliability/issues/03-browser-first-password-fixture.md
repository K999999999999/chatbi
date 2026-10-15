# 03 首次改密浏览器用例使用独立账号

Status: open
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

Pending.

## Comments

调查证据为同服务 `--repeat-each=2` 一过一败，第二次仍复用第一次改密后的账号状态。
