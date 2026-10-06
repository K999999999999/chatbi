# 成功快照 XLSX 导出闭环

Status: 已完成；本地候选提交 `111980d`
Owner: 当前主 Agent
Blocked by: None (can start immediately)

## What to build

当前成功问数、历史和保存成果支持当前登录用户安全下载真实 XLSX 快照；内容可还原，失败不改业务状态。

## Acceptance criteria

来源 reader / API / runtime / XLSX adapter / 网页入口形成完整闭环。服务端 owner 与权限检查；只读既有成功快照；原始值、NULL / 空字符串 / 0、公式文本、精度与格式上限满足 Spec。实现隔离 worker、并发额度、超时、下载与断连清理。

## Verification

`uv run --group dev pytest tests/query_api -q`：171 passed、14 subtests passed。`uv run --locked python scripts/run_database_tests.py --profile development`：43 passed。`frontend` 的 `npm run typecheck` / `npm run build` 通过；导出模块与专用测试 Ruff、`uv lock --check`、`git diff --check` 通过。

## Result

验证与 Code Review PASS。独立 XLSX 解析覆盖历史轮次和另存成果真实浏览器下载、值与类型、NULL / 空字符串 / 零、公式 / URL 文本、前导零、精度边界、空结果、截断、空列名和标记同名文本；独立 PostgreSQL 验证 owner 隔离及删除历史后成果仍可导出。Runtime 覆盖 5 MiB / 20 MiB、额度、60 秒 watchdog、超时 / 断连 / shutdown 整组进程回收、符号链接拒绝、清理失败保留 quota 与再次使用。

Review 修复了保留标记同名文本缺少原值注记、分析成果误进入 XLSX serializer、Excel 数值范围、输出符号链接 chmod 顺序、worker 子进程组残留以及导出 runtime 启动故障影响 Query API 的风险；当前无未解决发现。Playwright Chromium 容器未关闭 sandbox；真实浏览器下载两种来源均通过并由 openpyxl 独立解析。本 Ticket 的验证候选为本地 commit `111980d`（`feat(result-export): 增加成功快照 XLSX 导出`）；未授权 Push / PR / 部署。

## Comments

本 Ticket owns first vertical slice of .scratch/result-export-v1/tickets-draft.md §01. Canonical Contract: ../spec.md; mechanism: ../design.md. Spec, Design, Design Review and Ticket Readiness passed; user confirmed 01–04 split and continuous local implementation on 2026-10-06. No Push / PR / deploy authorization.

Migration / Rollback: 源码 / 公开 Contract / 精度 / UI 只读变更都做最小改动；无 DB migration。失败升级：若必须改业务 Contract、权限不变量或 renderer 方向，暂停并返回 Design Review。
