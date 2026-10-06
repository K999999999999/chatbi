# R5 初次 Design Review

Review: NEED FIX
Review Target: 已由用户整体确认的 [Spec](spec.md)，baseline `ee92acaa7998749d46b57d85611ec69ab14948b1`。

本次只读审查，不修改目标 Spec、代码、测试或配置。需求和技术方向明确，但以下机制需要在设计阶段落实后复审，不能直接拆实施 Ticket。

## Findings

### DR-01：完整图形与资源交付路径未定义

- Signal: 复用现有组件会遗漏完整分类与标签；API 镜像尚无导出前端资源。
- Evidence: `frontend/src/Chart.tsx` 对超过 15 个标签启用初始缩放、限制图高且截断分类名称；`docker/python-dev.Dockerfile` 仅安装 Python 依赖，Compose 只挂载 src / scripts，`CHATBI_WEB_DIST_DIR` 为空。
- Impact: PNG 不满足全部数据和可读标签；即使浏览器开发页面可用，API 容器仍不能离线渲染。
- Recommendation: 在 Design 明确共享图形规则和独立完整导出布局、单独静态 bundle、API 镜像 / 本地运行路径、中文字体及缺失资源失败；不得依赖 Vite 服务或运行时 CDN。

### DR-02：XLSX 原值类型与空值保真没有编码规则

- Signal: Excel 单元格无法直接表达全部 JSON 类型差异；默认库行为可能执行公式或截断文本。
- Evidence: Spec §2 要求 NULL / 空字符串 / 零与精度可还原；`frontend/src/numberFormat.ts` 明确区分 NULL 与空字符串；XlsxWriter Worksheet / Workbook 官方文档说明字符串长度和自动公式 / URL 行为。
- Impact: 同一数据可能在导出后被错误解释，不能仅凭表格看起来一致判定成功。
- Recommendation: 定义确定性数值安全规则和说明表的单元格类型 / 原值记录；显式写文本、禁公式 / URL 自动转换、检查格式边界与写入返回结果。

### DR-03：完成时间与独立成果来源不能从当前公开 DTO 保证

- Signal: 原历史删除后，成果来源时间不能重新从历史查取。
- Evidence: `HistoryTurn` 只有 created_at，没有 completed_at；底层 history_turns 保存 completed_at；`copy_result` 复制 snapshot，既有成果 envelope 没有原完成时间；独立成果必须在原历史删除后仍可导出。
- Impact: 把成果创建时间冒充报告完成时间会误导用户；强制读取已删除历史会破坏独立成果语义。
- Recommendation: 设计只读导出来源 DTO，历史可读取真实完成时间；独立成果缺失原完成时间时明确未知，不替换为成果保存时间；无需强制历史迁移。

### DR-04：权限裁决与工作进程终止机制未定义

- Signal: 只检查受理身份或使用线程等待超时，不能满足生成期间访问变化与真正回收。
- Evidence: Spec §5–6 明确生成 / 交付竞态、60 秒总时限与清理；现有 HistoryApplication authorize / turn 和 Store owner 读取可复用，但没有文件交付裁决或导出 runtime。
- Impact: 越权交付或生成进程遗留，导致额度泄漏和查询服务受阻。
- Recommendation: 明确交付前重鉴权 / 重新查源的裁决点、独立进程组与 watchdog、断连 / 重启清理、有界数据传递、只有确认进程结束才释放生成额度；避免长数据库事务。

Reference: 已读取 Architecture Knowledge Core 全文，重点应用 §3–7（变化轴、依赖、信息隐藏、边界、可测试性）、§8（替代方案）和 §9（过度设计约束）。
Evidence Sources: Spec、Architecture、R2–R4 Contract、History Application / Store / Codec / DTO、Chart / numberFormat、Vite 与 Compose / Dockerfile、XlsxWriter 与 Playwright 官方文档。
Next: 返回设计阶段，补充实现设计后复审；不改变已确认需求，不编码，不启动独立 Agent。
