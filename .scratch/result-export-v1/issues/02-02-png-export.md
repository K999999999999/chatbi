# 完整 PNG 导出与离线渲染

Status: open
Owner: 当前主 Agent
Blocked by: 01-xlsx-export

## What to build

从当前结果、历史和成果完整下载图表 PNG，使用与网页一致的认证图形事实。

## Acceptance criteria

共享纯 chart plan / renderer options；支持全部类目、图表类型、产品 / 因素与查询任务图；离线 bundle、manifest、本地字体、Playwright + Chromium 隔离；容器装配与开发源 hash 检查。

## Verification

独立检查 PNG 内容覆盖全部 series / categories / label；15+分类、缩放与页面折叠、产品选择、截断说明、字形 / 超像素限制、缺资源、sandbox 与断连清理；浏览器下载与隔离 Compose 真实 snapshot。既有网页图表和 Ticket 01 回归通过；Runbook 更新。

## Result

待实施。

## Comments

本 Ticket owns vertical PNG slice of tickets-draft.md §02. Canonical Contract: ../spec.md; mechanism: ../design.md. User-confirmed XlsxWriter / Playwright + Chromium direction; use assets offline.

Migration / Rollback: 无数据迁移。依赖资源缺失时 PNG fail closed、01 XLSX 保持有效。若 Chrome sandbox / offline asset constraints infeasible，返回 Design Review，不禁用 sandbox 绕过。
