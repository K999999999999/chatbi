# 03. 经营分析与模式切换

Status: done
Owner: 当前主 Agent
Canonical Source: ../r1-spec.md、../r1-design.md、../r1-design-review.md、../r1-ticket-readiness.md


**Change Profile**：长期；中等切片；任务重试 / 模式隔离风险；前端 / API / 桌面浏览器验证；本地逻辑 Commit。

**Blocked by**：02（在已有单请求状态机与聊天页面上接入模式切换）。

### What to build

- 同页问数 / 经营分析手动切换、独立输入草稿 / 展示记录；默认问数，切回保留原有效 query 编号。
- 自然语言分析输入、支持边界提示、报告 / 任务证据组件、原 UUID / 问题的手动重试。
- 分析 1200 秒有限等待及结果未确认提示；改变问题创建新 ID，重试不能静默新建 ID。

### Acceptance criteria

- 支持既有两个时期的人民币净销售额 / 毛利产品归因；不自动继承查询条件或增加区域 / 客户分析。
- analysis 请求不含 conversation_id；每个新问题独立 ID，重试同用户 / 原问题 / 原 ID，过期 / 不匹配显示受控拒绝。
- 报告及证据展示与返回内容一致，不补写原因、不重算指标，不执行模型输出 HTML。
- query → analysis → query 的记录和上下文不串用；等待时切换禁用；失败保留上一个 query 成功状态。
- 分析重试草稿编辑不改变原任务问题；新分析成功与旧任务重试结果按请求身份归属正确展示，迟到响应受 epoch 门禁保护。

### Owned files 与证据

- `frontend/` 模式 / 分析客户端、状态、报告 / 证据组件与对应检查；`tests/query_api/` 分析请求兼容 seam；正式 Web Spec / Design 的分析章节。
- 后端 `src/business_analysis/`、指标 / Prompt / Golden Cases 默认不改；发现核心问题应记录独立问题，不以 UI 接入改写业务事实。
- 验证：模式分离 / ID / 原问题锁定 / 重试 / 拒绝 / 安全展示检查、桌面浏览器确定性分析闭环、现有 analysis API 回归。

**Migration / Rollback**：Migrate 分析；不删除 checkpoint / run registry；回退本切片保留 query 和旧 Streamlit 分析入口。

**Done When**：经营分析和模式切换的正常 / 边界证据、文档、Review / 本地 Commit 完成。


## Result

已接入手动双模式、独立草稿 / 时间线、分析 UUID、原问题手动重试、报告 / 归因 / 任务证据展示；后端业务模块、指标与 Prompt 未改。

- RED：分析两条新用例因缺少模式按钮失败。
- GREEN：类型 / 构建、Chrome 全部 9 项通过；新增 3 项分析覆盖模式隔离 / 原成功编号保留、断网后同 ID / 问题重试且下一任务使用新 ID、受控拒绝不提供静默重建。API analysis / browser 回归 20 passed。
- Code Review：PASS；BASE 395a979，范围前端分析接入 / HTTP fixture / 测试 / Runbook。检查 1200 秒上限、报告任务 ID 比对、允许重试错误集、首轮分析不含 conversation_id、React 文本转义、按后端数值展示。共享表格允许被截断证据的原始 row_count，普通 query 仍严格验证实际行数。
- 正式 Spec / Design 已定义本次行为，无 Contract 变更；Runbook 同步分析操作。真实 AI 验收仍待 04，历史 AI 基线未改称当前结果。

## Comments

2026-10-03 用户确认五项拆分并授权完整 R1 实施；不包含 Push / PR 发布。
