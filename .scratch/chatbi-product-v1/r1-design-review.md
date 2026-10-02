# R1 编码前设计审查

日期：2026-10-03。Owner：当前主 Agent；只读审查，未启动独立 Agent，未运行测试。

## 首轮：已确认 Spec

Review: PASS WITH MINOR FIXES

Review Target: `r1-spec.md`（用户本轮整体确认）。

Findings:

1. **Signal**：浏览器凭证不可见的验证语句容易误伤既有 Bearer 登录。
   **Evidence**：Spec 的兼容要求保留 Bearer；`src/query_api/app.py` 的 `/auth/login` 返回 `access_token`，`tests/query_api/test_auth_api.py` 直接消费该字段。
   **Impact**：如统一修改响应，会破坏现有调用方并引入不必要迁移。
   **Recommendation**：明确只要求浏览器登录响应不返回原始 Session Token；新增独立浏览器认证路由，旧路由保持兼容。
2. **Signal**：Cookie、CSRF 与混合凭证规则必须在 Ticket 前形成可测试的具体边缘 Contract。
   **Evidence**：现有 `LocalSessionIdentityProvider` 和认证路由只读 Bearer，SQLAdmin 有自己的签名 Session Cookie；Spec 允许技术细化但禁止身份回退。
   **Impact**：若各路由自行处理凭证，可能重复认证、滑动 TTL 或混用用户；来源校验若依赖不可信 Host，反向代理部署会出现隐患。
   **Recommendation**：独立浏览器 Cookie 命名；统一边缘凭证提取及来源校验，核心 Session / RBAC 复用。配置准确网页 Origin；明确缺失 / null / 非同源拒绝、混合凭证拒绝与测试 seam。
3. **Signal**：退出失败及账号切换需要清理展示和防止迟到响应的联合设计。
   **Evidence**：Spec 禁止退出未确认后自动重新进入；HttpOnly Cookie 无法由页面脚本直接删除；现有 Streamlit 退出仅清理认证键。
   **Impact**：仅清消息会在刷新后自动登录；仅 abort HTTP 不能保证服务端未执行或迟到响应不会回填。
   **Recommendation**：前端身份 epoch、私有状态统一清理与不含凭证 / 业务内容的退出待确认标记；服务器核对浏览器当前期待的用户，拒绝跨账号竞态。
4. **Signal**：同步分析等待预算与 Streamlit 删除的影响闭包需要提前明确。
   **Evidence**：`src/business_analysis/planning.py` 固定四个查询 Task，Task 可重试一次；提取 / 总结模型各可调用两次，单次 LLM 30 秒，Qdrant 默认 30 秒，SQL 10 秒。CI smoke、启动脚本及模块边界检查仍直接引用 Streamlit。
   **Impact**：过短 HTTP 超时会人为制造结果不确定；直接删文件会破坏 CI / 新 clone 启动与模块检查。
   **Recommendation**：为普通查询和分析设置分别的有限客户端等待预算，明确不构成服务器总时限 / SLA；删除前建立新入口 smoke，覆盖启动、依赖、边界检查和正式文档。

Reference：已读取 Architecture Knowledge Core，应用 §2 复杂度、§4 依赖方向、§5 Contract、§7 状态 / 测试、§8 替代方案 / 迁移及 §9 简化原则。

Evidence Sources：已确认 Spec、Architecture / Product Scope / Query API Spec；AuthService / API / SQLAdmin、分析执行 / 计划 / 模型、SQL Executor、RAG 配置；现有测试、CI、README / Runbook、启动脚本、模块检查。读取官方 OWASP CSRF、Vite 与 Playwright 文档；只查询 npm 包元数据和本机 Node / npm 版本，未安装依赖。

Next：由主 Agent 在审查结束后补充局部技术设计并核对修订；不改变已确认产品行为，核对前不进入 Ticket。

## 修订核对与第二轮：Spec + Design

修订位置：`r1-spec.md` 区分浏览器 / Bearer Token 验证范围；`r1-design.md` 固化浏览器路由、来源 / 凭证门禁、身份 epoch / 退出标记、同步等待预算及替换闭包。

Review: PASS

Review Target: `r1-spec.md` + `r1-design.md`。

- 四项修订均已落实，未新增产品能力、业务规则或部署服务；原查询 / 归因 / 授权核心不变。
- 新认证支持位于 HTTP / 身份 Adapter，数据库 Session、RBAC 与审计仍由现有 Application / Infrastructure 持有，不把 React / Cookie 类型下沉到 Domain。
- 比较了直接 Cookie 扩展、额外 BFF 和可读 Token 存储；选择已确认的直接 Cookie 扩展，影响范围最小。比较静态文件由 FastAPI 提供与额外独立静态服务，前者作为 R1 最小打包入口，完整生产入口仍由 R6 验收。
- 浏览器身份、失败恢复、同源 Origin 配置、静态资源与未知路由边界、迁移 / 回滚均有客观可验收规则。
- 浏览器集成验证与 AI 真实闭环分别提供证据；本次 PASS 是设计判断，不代表任何测试或生产验收已经通过。

Findings: 无剩余阻止 Ticket 拆分的设计问题。

Next: `workflow-to-tickets` 草案 → 当前上下文 `workflow-ticket-readiness` → 用户确认拆分与整体 R1 实施范围。
