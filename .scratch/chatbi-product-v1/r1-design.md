# R1 实现设计

依据：[已确认 R1 Spec](r1-spec.md)。状态：编码前技术设计，非已实现功能；审查见 [Design Review](r1-design-review.md)。Owner：当前主 Agent。

## 1. 最小结构与运行入口

- `frontend/` 保存 React + TypeScript 页面、原生 CSS、原生 `fetch`、Vite 配置及 npm lockfile。R1 不增加路由框架、全局状态平台、图表库或 Markdown / HTML 渲染依赖。
- 前端分为浏览器 API 客户端、页面状态转换、登录 / 改密视图、问数 / 分析视图与结果展示。划分按知识职责，不能建立只透传调用的多层 Service。
- FastAPI 只新增浏览器身份 / CSRF Adapter 和打包文件入口；复用 `AuthService`、现有 `AuthorizedQueryService`、Conversation Store 与 Business Analysis。Domain 不新增前端依赖。
- 开发：Vite 监听 `127.0.0.1:5173`，将 `/api`、`/auth`、`/health` 代理到回环 FastAPI。浏览器始终使用相对 URL；Vite 不改写真实 `Origin` 来绕过来源校验。
- 打包：Vite 生成 `frontend/dist`；FastAPI 提供 `/` 与 `/assets`，只有配置目录中的构建文件可被读取，不能暴露源码、`.env` 或任意路径。
- API / 认证 / 管理后台 / health 路由优先，未知 API 和未知静态资源保持 404，不将 API 错误改成 HTML。R1 仅一个聊天页面，不需要全局 SPA fallback。
- 显式 `CHATBI_WEB_DIST_DIR` 配置构建目录；未配置则保留 API-only 能力，配置但没有有效构建时启动报错，避免把缺失前端当成功应用启动。
- 单实例单 worker 运行；前端打包入口不宣称已经完成 R6 的公网 HTTPS / 升级 / 回滚验收。

## 2. 浏览器接口与兼容

现有 `/auth/login`、`/auth/me`、`/auth/logout`、`/auth/change-password` 保持 Bearer-only 行为；不让这些旧路由隐式接收 Cookie。

新增路由：

| 路由 | 成功响应与职责 |
| --- | --- |
| `POST /auth/browser/login` | 校验用户名 / 密码，设置 HttpOnly Cookie；返回用户名、用户 ID、权限与 `must_change_password`，不返回原始 Token |
| `GET /auth/browser/me` | 校验 Cookie Session，返回上述身份快照，不返回 Token |
| `POST /auth/browser/logout` | 撤销当前 Cookie Session，删除 Cookie，204；不存在 / 已撤销 Session 可幂等清理，但审计 / 数据库失败返回 503，不能声称撤销成功 |
| `POST /auth/browser/change-password` | 现有改密规则；成功撤销账号全部 Session、删除 Cookie，204，前端要求重新登录 |

- 查询保持 `POST /api/v1/query` 的原请求体、响应体、状态映射；通过统一身份 Adapter 支持 Cookie 或 Bearer。
- 浏览器专用路由不得接受 Bearer 作为 Cookie 回退；共用查询路由同时出现业务 Session Cookie 和任何显式 Authorization 时拒绝，返回现有 401 / `AUTHENTICATION_REQUIRED`；SQLAdmin 的 Cookie 不参与该判断。
- 没有业务 Cookie 的 Bearer 调用继续保持原行为，不要求浏览器 Origin 或自定义头；显式错误 Bearer 不回退 Cookie。
- Cookie 请求使用 `X-ChatBI-User-ID` 提交页面当前经 `me` 核实的用户 ID。它不是身份凭证：服务器先验证 Cookie 得到可信身份，再比对；缺失、格式错误或不匹配返回 401，不进入业务链路。
- `GET me` 不需已知用户 ID；登录不需要该头；改密和业务查询需要。退出待确认期间保留非凭证的目标用户 ID，避免旧页面撤销另一账号刚创建的 Session。
- 认证 / 用户比对只执行一次，并将可信上下文在当前请求内复用；不为匹配两种凭证重复滑动 TTL。
- 浏览器认证错误沿用安全 `detail`，查询仍沿用 `QueryFailure`。CSRF 拒绝在浏览器认证路由返回 403 / 安全说明，在查询返回 403 / `AUTHORIZATION_DENIED`；身份过期 / 不匹配返回 401。所有返回不暴露堆栈、连接信息或另一个账号信息。
- 登录 / 身份 / 查询 / 分析响应使用 `Cache-Control: no-store`；浏览器新接口的 Token 禁止进入 JSON、日志、Trace、截图 / 测试报告。

## 3. Cookie 与 CSRF

- 业务 Cookie 名 `chatbi_web_session`，与 SQLAdmin Cookie 分开；HttpOnly、SameSite=Strict、Path=/、不设置 Domain。
- 不设置长期记住登录的 expiry；服务器数据库仍是 TTL 与撤销的权威。生产 / staging 使用 Secure；仅显式 development / test 且网页地址为回环 HTTP 时允许非 Secure Cookie。
- `CHATBI_WEB_ORIGIN` 表示唯一允许的网页 Origin：协议 + 主机 + 端口，无用户信息、路径、query、fragment 或 wildcard。开发为 `http://127.0.0.1:5173`，打包验收使用其实际网页地址；生产 / staging 要求 HTTPS。
- 未配置网页 Origin 时浏览器能力关闭并返回受控不可用，不削弱既有 Bearer / API-only 运行；显式配置但非法时启动失败。配置解析不能从请求头补齐缺失值。
- 有 Origin 的 Cookie 请求须与配置精确匹配；所有浏览器 POST 必须同时满足匹配 Origin、`X-ChatBI-Request: browser`、JSON Content-Type（无正文的退出请求也设置），拒绝缺失 / `null` / 其他来源。检查在登录 / 改密 / 退出 / 下游查询副作用前执行。
- 对 `Sec-Fetch-Site` 明确 cross-site / same-site 的浏览器 POST 拒绝；缺少该头也必须通过上述精确 Origin 门禁。不能从可伪造的 Host / Forwarded Host 自动放宽配置。
- 同源 GET me 返回安全身份信息；存在非匹配 Origin 或明确 cross-site 的 Fetch Metadata 时拒绝。没有 Origin 的同源浏览器 GET 可使用正常 Cookie 身份校验。
- 不启用跨站凭证 CORS、不接受表单或 text/plain 请求作为 JSON 的替代，不从输入或 URL 选择任意请求目标。
- 该 JSON API 使用来源校验与自定义头组合，不引入第二套 CSRF Session / Token 存储。[OWASP 对 API 自定义头与来源校验的说明](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)。SameSite / Secure 属性是配套措施，不代替上述门禁。

## 4. 前端状态与安全展示

- 页面状态包含 `auth`、`identityEpoch`、`mode`、两份独立时间线 / 草稿、当前 query 编号 / 是否可追问、当前 analysis 运行编号 / 原问题，以及最多一份进行中请求。
- 开始请求时捕获 epoch、用户 ID、原问题、模式、业务编号与客户端请求编号。草稿在发送后与进行中原问题分离。
- 任何响应只有 epoch、用户 ID 和当前请求编号仍匹配才可写入。退出 / 失效 / 换号时先提升 epoch、abort 客户端请求、清空两种模式的全部私有内容；abort 不宣称服务端任务取消。
- 同源页面以 BroadcastChannel 发送不含问题 / 数据 / Token 的身份变更通知；其他标签页只清理本页状态，不自动续发旧请求。浏览器 API 的用户 ID 比对防止 Cookie 跨标签变更导致的错账号提交。
- 退出前在当前网页 URL fragment 写入仅含退出待确认标志 / 目标用户 ID 的标记，不保存凭证或业务数据，也不将 fragment 发给服务器。退出失败保持标记，刷新不自动进入业务页，只显示重试 / 明确重新登录入口；初始化必须先解析该标记，再决定是否调用 me。
- 退出成功清标记；明确重新登录成功后清标记并初始化新身份。收到其他标签页退出通知时同步清理并设置待确认标记，不能因共享 Cookie 撤销失败而在刷新后自动进入业务页。标记只限制自动登录，不作为认证或撤销凭证。
- `CONVERSATION_UNAVAILABLE` 或问数结果未确认后，保留已显示结果，但禁用继续追问，只允许新对话。HTTP 受控失败保留上一成功状态。
- 分析重试使用原 ID / 原问题，草稿修改只影响下一个新任务；过期 / 不匹配明确提示不可恢复，不能静默重建 ID。
- 表格按二维数组和列顺序展示，`null` 显示明确空值标记、零保持零、空串保持空串；不推测指标单位。报告字段通过结构化组件 / 文本展示，HTML / Markdown HTML 不执行。
- 页面包含账号 / 退出、问数 / 分析切换、输入与发送、问数新对话、两份独立展示和错误提示；SQL 与分析任务证据可展开。仅桌面布局。

## 5. 有限等待与错误分类

- 客户端等待：认证 / 改密 / 退出 30 秒，普通问数 180 秒，经营分析 1200 秒；使用 AbortController，结束后根据已确认恢复规则处理。
- 预算依据是现有单次 LLM 最多 30 秒、Qdrant 默认 30 秒、四个顺序查询 Task 及既有重试。它是有限客户端等待选择，不是形式化服务器上限或生产 SLA；多个检索 / 本地处理 / 不同配置仍可能超预算。
- 后端合法成功 / 受控失败按原 Contract 显示；没有合法受控结果、网络错误或客户端超时均视为结果未确认。HTML 代理报错、畸形 JSON、错误模式结果、错误 ID、列 / 行形状不匹配不能当成成功。
- Cookie CSRF / 身份错误不做匿名回退；401 清理私有状态，403 显示拒绝并停止本次发送。不存在自动业务重发。
- 不增加后台轮询、保活、任务查询、取消协议或服务器总运行时限；这些改变需回到对应需求。

## 6. 工具与验证

本机已核实 Node `24.21.0` / npm `11.19.0`。npm 元数据核实的实施候选：React / React DOM `19.3.0`、Vite `8.3.2`、TypeScript `7.0.2`、`@vitejs/plugin-react` `6.1.1`、`@playwright/test` `1.63.0`。新依赖在实施时精确锁定，包含 plugin peer dependency 解析；如不兼容不得自动跨大版本升级，先重新审查。当前未安装或验证这些组合。

- `package-lock.json` + `npm ci` 作为可复现入口；Node 使用 24 系列，CI 固定实际兼容版本。Vite 的 Node 要求已经核对。[Vite 官方文档](https://vite.dev/guide/)。
- TypeScript 类型检查、Vite 构建、前端状态 / 客户端确定性检查；后端现有 pytest seam 验证 Cookie / Bearer / CSRF / 配置 / 静态入口。
- Playwright 驱动桌面浏览器；最终 Chrome 验收必须使用 `channel: chrome`，不能把默认 Chromium 结果改称 Chrome。记录浏览器实际版本、OS、提交与构建身份。[Playwright 官方浏览器说明](https://playwright.dev/docs/browsers)。
- 确定性浏览器检查使用真实 HTTP / 账号 Session 和假的查询服务；真实 AI 浏览器验收使用同一页面与真实模型 / RAG / PostgreSQL，两者报告明确区分。
- 在现有 CI 的必需检查中加入 npm lock / 类型 / 构建 / 依赖审计 / 浏览器链路，保留既有 required check 名称，不调整远端 ruleset。现有 Python 和 Secret / Security 检查继续运行。
- 真正高风险的身份 / 查询 / 分析 HTTP 路径需真实闭环证据；正式 AI Evaluation 是否重跑按最终 Diff 与仓库基线规则判断，不继承新提交通过身份。
- 浏览器报告默认不保存带真实登录凭证、问题或结果的网络 Trace / 视频；验收记录只保留安全字段，真实业务截图另按数据范围确认。

## 7. Streamlit 替换闭包与回滚

Owner 为同一主 Agent。Expand：新增 Cookie 支持和网页，保留 Streamlit / Bearer；Migrate：查询 / 分析及浏览器验收覆盖旧核心入口；Contract：新入口 smoke 通过后删除 Streamlit。

已查到的消费者：`src/streamlit_app.py`、`tests/streamlit/`、`pyproject.toml` / `uv.lock`、README、Runbook、Architecture、Product Scope、Query API 文档、`.github/workflows/ci.yml`、`scripts/start-dev.ps1`、`scripts/check_module_boundaries.py` 及其测试。实施时再用 rg 核对全仓库，区分历史记录 / 验收与活动入口，不删除历史 Spec 或证据。

- 启动脚本与文档切换至 Vite / FastAPI；CI smoke 切换至构建后的网页 / API，并添加浏览器登录闭环，不仅验证 `/health`。
- 更新模块检查以覆盖新增 HTTP Adapter，并移除对被删除 Streamlit 文件的硬编码读取；不能为删旧文件而削弱查询 / Domain 依赖门禁。
- CI / 文档禁止新增 Streamlit 活动入口；历史文件允许注明“历史入口”。
- 无数据库业务数据迁移。Cookie / 页面层新增能力可回滚；完整发布回退到 known-good 版本及对应 lockfile / 启动入口，不删除数据库 volume / 账号 / 审计 / checkpoint。
- 删除阶段若新入口或兼容测试失败，停止删除 / 交付，修复新入口或恢复仍在迁移中的旧入口；不把带缺陷的替换标记为完成。

Revisit Trigger：真实需求要求跨站部署、多实例、移动端、历史续聊、通用恢复或更高访问规模时重新审查对应设计；不能直接加 worker 或拉长 TTL 代替新 Contract。
