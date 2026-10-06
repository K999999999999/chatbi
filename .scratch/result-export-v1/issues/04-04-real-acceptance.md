# R5 隔离真实闭环验收与候选收口

Status: completed
Owner: 当前主 Agent
Blocked by: 03-pdf-export

## What to build

在 clean 最终候选上证明三类文件能从真实持久化来源下载且与快照一致。

## Acceptance criteria

扩展隔离 Compose / 浏览器闭环：登录、问数与追问、完成分析，导出当前 / 历史 / 成果；覆盖重启、删除 / 权限、额度 / timeout 与 resource cleanup。锁定身份与证据，更新最终 R5 Acceptance 和全部正式文档。

## Verification

clean candidate、文件 hash / 大小 / content 与快照、模型 / 数据 / RAG 身份，browser / file parser / compose runtime 全部通过。正式 Evaluation 是否复用按 Contract 判断；生成链路变动重跑适用 Evaluation。临时账号、凭证和隔离资源清理已核实。

## Result

最终 clean candidate `71d72d2585306dc50a0b9ecca9ac1679d7ab45ff`：隔离 Compose 真实登录 / 问数 / 追问 / 分析、API/Web 重启恢复、12 个 XLSX / PNG / PDF 下载和独立解析全部 PASS；export execution POST=0。临时账号禁用、active sessions=0、无 worker，隔离容器/卷/网络已清除。Runtime 的 API/Web image ID、模型配置、RAG manifest、PDF 五份 hash 与字体 hash 见 [最终验收](../../../docs/acceptance/result-export-v1.md)。AI Evaluation 未重跑，因导出不改变生成 / Retrieval / Guard；未授权 Push / PR / 部署。

## Comments

本 Ticket owns final validation / docs of tickets-draft.md §04. Canonical Contract: ../spec.md; design: ../design.md. 本地完成，不包含发布或部署授权。

Migration / Rollback: 无生产 rollout / R6、R7 scope。失败保留报告并重跑受影响检查；不覆盖历史证据或声称 PR 已发布。
