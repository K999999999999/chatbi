# 浏览器身份与状态隔离

本文说明维护当前实现所需的机制；功能行为见 [Web交互Spec](../specs/web-dialogue-v1.md)。开发方案比较、任务和历次验收保存在工作记录。

## 浏览器接口与兼容

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

## Cookie 与 CSRF

- 业务 Cookie 名 `chatbi_web_session`，与 SQLAdmin Cookie 分开；HttpOnly、SameSite=Strict、Path=/、不设置 Domain。
- 不设置长期记住登录的 expiry；服务器数据库仍是 TTL 与撤销的权威。生产 / staging 使用 Secure；仅显式 development / test 且网页地址为回环 HTTP 时允许非 Secure Cookie。
- `CHATBI_WEB_ORIGIN` 表示唯一允许的网页 Origin：协议 + 主机 + 端口，无用户信息、路径、query、fragment 或 wildcard。开发为 `http://127.0.0.1:5173`，打包验收使用其实际网页地址；生产 / staging 要求 HTTPS。
- 未配置网页 Origin 时浏览器能力关闭并返回受控不可用，不削弱既有 Bearer / API-only 运行；显式配置但非法时启动失败。配置解析不能从请求头补齐缺失值。
- 有 Origin 的 Cookie 请求须与配置精确匹配；所有浏览器 POST 必须同时满足匹配 Origin、`X-ChatBI-Request: browser`、JSON Content-Type（无正文的退出请求也设置），拒绝缺失 / `null` / 其他来源。检查在登录 / 改密 / 退出 / 下游查询副作用前执行。
- 对 `Sec-Fetch-Site` 明确 cross-site / same-site 的浏览器 POST 拒绝；缺少该头也必须通过上述精确 Origin 门禁。不能从可伪造的 Host / Forwarded Host 自动放宽配置。
- 同源 GET me 返回安全身份信息；存在非匹配 Origin 或明确 cross-site 的 Fetch Metadata 时拒绝。没有 Origin 的同源浏览器 GET 可使用正常 Cookie 身份校验。
- 不启用跨站凭证 CORS、不接受表单或 text/plain 请求作为 JSON 的替代，不从输入或 URL 选择任意请求目标。
- 该 JSON API 使用来源校验与自定义头组合，不引入第二套 CSRF Session / Token 存储。[OWASP 对 API 自定义头与来源校验的说明](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)。SameSite / Secure 属性是配套措施，不代替上述门禁。

## 前端状态与安全展示

- `Chat`按问数、经营分析分别维护历史选择、时间线和输入草稿；服务端 `history_id` / `turn_id` 关联持久记录，`execution_id` 标识一次后台执行。提交和恢复的完整行为见[执行规则](../specs/execution-streaming-v1.md)与[历史与成果](../specs/history-results-v1.md)。
- 每次执行先创建明确的历史或操作，再观察已受理执行。状态与SSE只恢复观察；刷新或断连后重开历史连接现有执行，不自动重发问题。受理结果不确定时展示明确状态，只有用户选择重试才继续同一操作身份。
- 执行 reducer 按执行身份、序号和草稿代次接收快照与增量；终态和正式结果以服务端历史快照为准。分析生成中的文字以未校验草稿展示，只有正式结果校验并保存后才替换草稿。断连时暂留页面已有草稿，重连后同步服务端当前状态。
- 身份退出、失效或切换时使旧页面响应失效，清除两种模式的私有内容并中止客户端观察。中止浏览器请求本身不代表后台执行已取消；服务端取消按[执行规则](../specs/execution-streaming-v1.md)裁决。
- 表格按二维数组和列顺序展示；`null`、零与空字符串保持不同，不推测指标单位。报告字段用结构化组件或纯文本展示，不执行 HTML / Markdown HTML。
