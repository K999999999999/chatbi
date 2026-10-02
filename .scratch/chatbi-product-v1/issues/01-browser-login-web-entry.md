# 01. 浏览器登录与可运行网页入口

Status: done
Owner: 当前主 Agent
Canonical Source: ../r1-spec.md、../r1-design.md、../r1-design-review.md、../r1-ticket-readiness.md


**Change Profile**：长期；中等跨模块切片；高身份风险；后端确定性 / 集成 + 桌面浏览器基础验证；本地逻辑 Commit。

**Blocked by**：None (can start immediately)。

### What to build

- 建立 `frontend/` React / TypeScript / Vite 与锁定 npm 依赖，网页提供登录、首次改密、退出与默认问数页面外壳。
- 新增 Design 的四个浏览器认证路由、业务 Cookie、精确 Origin / 自定义头 CSRF 门禁与 Cookie / Bearer 身份提取；旧 Bearer 路由保持兼容。
- 增加同源开发代理、显式网页 Origin / dist 配置和打包页面入口；保留 Streamlit。
- 统一身份清理、epoch / 请求编号、退出待确认 fragment、跨标签页通知；保护迟到响应和错账号发送。

### Acceptance criteria

- 新 clone 的 npm lock / 类型检查 / 构建可重现；登录 → 强制改密 → 重新登录 → 空白问数闭环可用，改密前业务访问拒绝。
- Cookie HttpOnly / SameSite / Secure / Path 属性正确；新浏览器 JSON 不含原始 Token；原 Bearer 登录响应及 SQLAdmin 兼容测试继续通过。
- 30 分钟 Idle、8 小时 Absolute、禁用 / 撤销 / 错误凭证均遵循原规则，无周期保活；错误 CSRF / Origin / 混合凭证 / 用户 ID 不匹配在业务前拒绝。
- 网页仅通过 HTTP，未知 API / 静态资源 404，缺失 dist / 非法配置按 Design 失败；API-only 不被新增前端要求破坏。
- 退出失败清空私有内容并保持待确认状态，刷新不自动进入；迟到响应 / 其他标签换号不能写回旧身份。

### Owned files 与证据

- `frontend/package.json` / lock / 配置 / 登录与状态基础组件 / CSS；`src/query_api/` 的浏览器 / 静态 Adapter 与装配 seam；`src/authorization/auth_service.py` 的身份 Adapter（必要部分）；`src/bootstrap/` 配置传递。
- `tests/query_api/`、`tests/authorization/`、前端基础检查；`.env.example`、README / Runbook 的新增开发入口、`docs/specs/web-dialogue-v1.md` / Query API 认证部分、`docs/designs/web-dialogue-v1.md`。
- CI 中增加 Node / npm lock / 类型 / 构建检查，沿用原 required check 名称；不修改远端 ruleset。
- 验证：现有认证 / 授权 / API 回归、浏览器认证 / CSRF / 配置 / 静态资源测试、npm ci / 类型 / 构建 / 依赖检查、真实 HTTP 基础登录与改密。

**Migration / Rollback**：Expand，新旧入口并存；无数据库迁移，回退新增 Adapter / 前端 / 对应依赖与配置即可，保留现有账号及审计。失败停止后续切片。

**Done When**：以上行为、兼容、验证和新增入口文档到位，Review 通过，本地 Commit；不声称 R1 查询已完成。


## Result

浏览器身份 Adapter、登录 / 改密 / 退出页面、同源开发代理和打包静态入口已实现；保留旧 Bearer / SQLAdmin / Streamlit。

- RED：浏览器登录路由缺失，预期 503 实际 404，测试按预期失败。
- GREEN：`uv run --locked pytest tests/query_api tests/authorization`：116 passed / 19 subtests；新增退出数据库失败、8 小时上限、静态资源检查后相关 19 项通过。
- `npm run build`、模块边界、Markdown 链接、Ruff 与 diff 空白检查通过；桌面 Chrome 154.0.8037.92 的登录刷新 / 退出和首次改密两条真实 HTTP 用例通过（最后重跑 2 passed）。浏览器业务服务是确定性替身，不能代替真实 AI 验收。
- 本机浏览器及缺失动态库放在用户 cache，无系统修改；CI 浏览器覆盖将在 Ticket 04 补齐。
- 当前上下文 Code Review：PASS。范围为 d790317 至 Ticket 01 未提交 Diff；检查 Cookie / CSRF、会话复用与失效、迟到身份响应、运行时清理、API-only / Bearer 兼容、私密响应 no-store。修复 HTTPException 被转为 503 和身份清理后 busy / epoch 状态问题，受影响验证通过。
- 正式行为 / 设计、README / Runbook / Query API 认证文档与路线图同步。问数 / 分析仍待后续切片，不声称 R1 完成。

## Comments

2026-10-03 用户确认五项拆分并授权完整 R1 实施；不包含 Push / PR 发布。
