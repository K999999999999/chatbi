# R5 Design Review 复审

Review: PASS
Review Target: 用户整体确认的 [Spec](spec.md) 与 [实现设计](design.md)，baseline `ee92acaa7998749d46b57d85611ec69ab14948b1`。

## 结论与边界

初审 [NEED FIX](design-review-initial.md) 的四项机制缺口已由主 Agent 在独立设计阶段补齐。本次复审只读，不修改 Spec、Design、代码或测试。需求、格式、技术方向、历史状态语义与权限边界保持用户已确认范围。PASS 表示机制和验证计划足以拆分实施 Ticket，不表示运行正确性已验证，也不授予实施 / 发布授权。

## Findings / 修订核对

| Signal | Evidence | Impact | Recommendation / 结果 |
| --- | --- | --- | --- |
| DR-01 完整图形和资产路径 | Design §5 / §7，Chart.tsx 与 python-dev.Dockerfile | 避免图形遗漏、语义重复与开发 / 容器不一致 | 共享纯图形规则、完整 export profile、自包含 bundle、独立安装路径、源 hash 比对与缺失失败；已落实 |
| DR-02 单元格保真 | Design §4，numberFormat.ts、XlsxWriter 官方文档 | 避免空值混淆、精度损失与公式执行 | 显式类型 writer、特殊 / 转换单元格坐标类型与原值记录、独立解析 oracle、格式超限明确失败；已落实 |
| DR-03 原完成时间 | Design §2，HistoryTurn、copy_result / saved_result 与 Codec | 避免以保存时间冒充原结果时间、删除历史导致成果不可导出 | 独立只读投影，旧成果缺原时间如实未知，不强制迁移；已落实 |
| DR-04 竞态与进程清理 | Design §3 / §6，HistoryApplication authorize / Store owner 查找 | 避免越权交付、孤儿进程与额度泄漏 | 交付前重鉴权 / 重查源，明确响应首字节前裁决点，独立进程组 watchdog、断连 / 重启回收；已落实 |
| 慢下载产物堆积 | Design §6 的最终修订 | 提前释放额度会让临时文件数量失去界限 | lease 保留至发送 / 清理结束，只在 worker 退出且文件清理后释放；已落实，不提高容量承诺 |
| 源码热更新与资产漂移 | Design §7 的最终修订 | API 容器仅有 bundle 时不能发现 frontend/src 已变化 | 专用只读校验挂载、构建 manifest 比对，未重建只拒绝导出；已落实 |

## Architecture / Contract / Testability

- Application 留在既有 query_api 边界；Control DB 只读来源与文件生成 Adapter 分别隐藏存储 / 渲染知识；不新增业务模块、远端服务、队列或数据 migration。
- 单 POST、严格 source 联合 / 图形选择、既有身份 / CSRF / owner 与受控错误；不接收业务数据、SQL、HTML 或路径。
- 原始值、快照、业务权限和状态不变量由既有确定性代码与权威数据裁决；LLM 不参与导出。
- XLSX / PNG / PDF 各有独立解析证据；核心 Application 可用假生成器 / SourceReader 测试；PG、worker、浏览器、真实 Compose 分别证明存储隔离、生命周期和运行装配。
- 比较客户端生成、Python 重建全部图形与已确认 Chromium 方案；选择依据与复查条件见 Design §8，不增加未来插件系统。
- Linux sandbox、中文字体、长标签、分页、实际超时终止与 clean candidate 验收属于实施必须验证的运行条件；当前未运行实验、测试或真实模型，不标为已通过。若无法满足须回到设计审查，不绕过边界。

Reference: Architecture Knowledge Core 全文；重点 §3–9，覆盖用例 / 变化轴、依赖、信息隐藏、边界、失败、可测试性、替代方案和复杂度约束。
Evidence Sources: 已读取的 Spec / Design、Architecture、R2–R4 Contract、History DTO / Store / Codec / Application、前端图形 / 数字规则、Compose / Dockerfile、现有历史 Regression 与官方依赖文档。
Next: workflow-to-tickets 形成草案，并在当前上下文执行 workflow-ticket-readiness；用户确认拆分及整体实施授权前不建立正式 Ticket 或编码。
