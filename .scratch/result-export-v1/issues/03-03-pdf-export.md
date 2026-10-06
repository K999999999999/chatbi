# 完整分析报告 PDF 下载

Status: in-progress
Owner: 当前主 Agent
Blocked by: 02-png-export

## What to build

从完成分析结果、历史与成果下载完整 PDF，含正文、归因、引用任务和限制说明。

## Acceptance criteria

专用 HTML + Chromium PDF；复用权限与独立 renderer；A4 中文分页 / 可选取文本、长表和标签布局完整；全部已返回产品因素，不受折叠状态影响。

## Verification

独立 PDF parser 抽取正文 / 证据完整性；无归因与完整归因、失败 / 缺失 evidence、截断 / 旧成果时间；多页中文与图表人工检查；browser 实际下载。权限、renderer、Ticket 01/02回归和 docs 更新通过。

## Result

原 PDF renderer 通过视觉 / 页数检查，但真实文件独立提取发现 Noto 将“民”“长”映射为部首码位。用户确认仅将 PDF 字体改为 WenQuanYi Zen Hei；字体包版本锁定、运行清单（包版本 / fontconfig 路径 / SHA-256）和 PDF 字体应用已实现。字体清单单测 3 passed，PDF renderer 独立文件回归 2 passed（含“居民消费和民生数据”）；完整 Query API 181 passed、2 skipped、14 subtests；前端 typecheck / Ruff 通过。Review PASS：确认 PNG 字体未变，PDF 字体独立且运行资源按精确 family / 包版本 / 文件 hash fail closed；未发现实现缺陷。待最终 clean candidate Compose 验收。

## Comments

本 Ticket owns vertical PDF slice of tickets-draft.md §03. Canonical Contract: ../spec.md; mechanism: ../design.md. Do not alter report generation or attribution logic.

Migration / Rollback: 无 migration，可回退至 PNG/XLSX 不改变历史。禁止草稿 / 部分 PDF。
