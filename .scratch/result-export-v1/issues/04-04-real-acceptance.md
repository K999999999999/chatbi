# R5 隔离真实闭环验收与候选收口

Status: in-progress
Owner: 当前主 Agent
Blocked by: 03-pdf-export

## What to build

在 clean 最终候选上证明三类文件能从真实持久化来源下载且与快照一致。

## Acceptance criteria

扩展隔离 Compose / 浏览器闭环：登录、问数与追问、完成分析，导出当前 / 历史 / 成果；覆盖重启、删除 / 权限、额度 / timeout 与 resource cleanup。锁定身份与证据，更新最终 R5 Acceptance 和全部正式文档。

## Verification

clean candidate、文件 hash / 大小 / content 与快照、模型 / 数据 / RAG 身份，browser / file parser / compose runtime 全部通过。正式 Evaluation 是否复用按 Contract 判断；生成链路变动重跑适用 Evaluation。临时账号、凭证和隔离资源清理已核实。

## Result

上一 clean candidate `89bc7a6` 的隔离 Compose 浏览器流程、当前 / 历史 / 成果导出、API 重启恢复与资源清理均通过；12 个文件捕获、导出期间没有 executions POST，独立 PDF 文本解析因 Noto ToUnicode 把“民”“长”变成部首而失败。字体修正候选已本地渲染回归通过；需绑定新的 clean candidate 重跑全部真实验收和内容解析。

## Comments

本 Ticket owns final validation / docs of tickets-draft.md §04. Canonical Contract: ../spec.md; design: ../design.md. Local completion only; publication authorization unknown.

Migration / Rollback: 无生产 rollout / R6、R7 scope。失败保留报告并重跑受影响检查；不覆盖历史证据或声称 PR 已发布。
