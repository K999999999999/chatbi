# 完整分析报告 PDF 下载

Status: completed
Owner: 当前主 Agent
Blocked by: 02-png-export

## What to build

从完成分析结果、历史与成果下载完整 PDF，含正文、归因、引用任务和限制说明。

## Acceptance criteria

专用 HTML + Chromium PDF；复用权限与独立 renderer；A4 中文分页 / 可选取文本、长表和标签布局完整；全部已返回产品因素，不受折叠状态影响。

## Verification

独立 PDF parser 抽取正文 / 证据完整性；无归因与完整归因、失败 / 缺失 evidence、截断 / 旧成果时间；多页中文与图表人工检查；browser 实际下载。权限、renderer、Ticket 01/02回归和 docs 更新通过。

## Result

Review PASS。PDF renderer 回归 2 passed；Query API 181 passed、2 skipped、14 subtests；完整 Compose 的 5 份 PDF 均为 6 页，可抽取“民”“长”且不含错误部首码位。Noto / WenQuanYi 包版本、许可、字体路径和 SHA-256 见 [最终验收](../../../docs/acceptance/result-export-v1.md)。

## Comments

本 Ticket owns vertical PDF slice of tickets-draft.md §03. Canonical Contract: ../spec.md; mechanism: ../design.md. Do not alter report generation or attribution logic.

Migration / Rollback: 无 migration，可回退至 PNG/XLSX 不改变历史。禁止草稿 / 部分 PDF。
