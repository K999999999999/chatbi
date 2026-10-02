# 02. 问数、连续追问与查询失败恢复

Status: open
Owner: 当前主 Agent
Canonical Source: ../r1-spec.md、../r1-design.md、../r1-design-review.md、../r1-ticket-readiness.md


**Change Profile**：长期；中等切片；状态 / 隐私风险；前端确定性 + API / 浏览器闭环；本地逻辑 Commit。

**Blocked by**：01。

### What to build

- 当前问数时间线、输入 / 发送 / 新对话、结果表格、SQL 展开、空结果 / null / 截断提示。
- 首轮和追问只提交现有问题 / 模式 / 会话编号；成功才更新会话，失败与澄清沿用原 Contract。
- 进行中操作限制、输入草稿与请求原问题分离、有限等待、响应形状校验与 query 结果未确认后的新对话提示。
- 刷新保持登录但问数展示 / 编号清空，页面说明阶段边界；无浏览器历史持久化。

### Acceptance criteria

- 登录后完整问题返回表格 / 经校验 SQL，追问使用服务端成功编号；前端不能直接提交语义状态 / SQL。
- 空输入不发送、空结果仍可继续追问；null / 0 / 空串分开，截断提示不误称完整数据。
- 受控失败 / 澄清不改变成功状态；会话不可用不自动把片段追问当首轮执行。
- 重复发送 / 模式切换 / 新对话在等待时禁用，草稿仍能编辑；网络失联 / 客户端超时 / 畸形响应显示结果未确认，不自动重发，不允许基于不确定状态继续追问。
- 退出 / 过期 / 账号变化后查询内容和迟到响应被清理；刷新进入空白问数。

### Owned files 与证据

- `frontend/` 查询 API 客户端、状态转换、问数 / 表格 / SQL 组件及对应检查；已存在的业务 API body / 结果语义不改变。
- `docs/specs/web-dialogue-v1.md` 查询章节、Runbook 查询示例；必要的 `tests/query_api/` 浏览器请求 seam。
- 验证：前端状态 / 请求形状 / 受控错误 / 超时测试，真实 HTTP 身份 + 假查询服务的桌面浏览器问数与追问；既有会话 / Query API 回归。

**Migration / Rollback**：Migrate 普通问数，Streamlit 保留；回退本切片不影响登录及后端状态 Contract，无数据迁移。

**Done When**：查询闭环与全部边界有可复现证据、文档同步、Review / 本地 Commit 完成；不加入图表或历史。


## Result

尚未实施。

## Comments

2026-10-03 用户确认五项拆分并授权完整 R1 实施；不包含 Push / PR 发布。
