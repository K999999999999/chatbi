# 私人历史与成果：整理前的过程记录

来源：`docs/specs/history-results-v1.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 整理前入口说明

# R3 历史与成果管理

状态：已确认行为 Contract；当前本地候选及验收状态见 Git 公共目录的本机实时工作状态，尚未发布。来源为用户确认的六项整体目标；过程记录保留于 `.scratch/history-results-v1/`。

## Problem Statement

R1 / R2 已交付电脑端问数、独立经营分析、可信结果说明和图表，但网页刷新仍清空临时记录。普通问数仅有进程内短期会话，分析 checkpoint 仅支持限时恢复。用户不能在重新登录或服务重启后重开长期历史、继续问数，或保存独立成果。

本目标为产品 V1 已确认路线中的 R3。R4 的执行状态、取消、恢复与流式观察由 [R4 Spec](../../../docs/specs/execution-streaming-v1.md) 独立定义；R3 的快照读取、续聊和成果生命周期 Contract 仍适用。R5 导出、R6 / R7 生产运行验收也独立推进。

事实源：[路线图](../../../docs/roadmap.md)、[产品范围](../../../docs/product-scope.md)、[架构](../../../docs/architecture.md)、[历史领域上下文快照](../../context-file-removal/history/domain-context-snapshot.md)、[Web Spec](../../../docs/specs/web-dialogue-v1.md)、[Query API](../../../docs/specs/query-api.md)、[R2 Spec](../../../docs/specs/result-visualization-v1.md)、[多轮原 Contract](../../multi-turn-conversation-v1/spec.md)、[分析原 Contract](../../business-analysis-root-cause-v1/spec.md)、[Evaluation Contract](../../../docs/specs/evaluation.md)。历史阶段约束不反向否定本轮确认的网页历史恢复行为；本 Spec 整体确认后明确其与旧短期接口的适用边界。

## Implementation Decisions / Decision Record

| 决定 | 依据与取舍 | Revisit Trigger |
| --- | --- | --- |
| 快照重开、显式重查生成新记录 | 用户逐项确认；可核对原结果且避免打开历史隐式产生执行成本 | 明确的新版本对比需求 |
| 持久结构化状态恢复问数 | 用户确认过期 / 重启后续聊；旧快照不成为当前业务真相 | 当前语义或映射不兼容 |
| 自动历史与手动独立成果 | 用户确认；原历史删除不损坏已保存成果 | 明确共享 / 导出需求 |
| PostgreSQL Control DB 专用表 | 复用已核实的账号 / checkpoint基础设施与迁移入口；不将状态写入销售只读库 | 经确认的规模或部署变化 |
| 网页持久化成功门槛 | 用户确认；快照及续聊上下文一致，失败不暗中推进 | 已确认的新可用性取舍 |
| 旧 Bearer 接口维持短期行为 | 用户确认；兼容现有客户端、测试与评测入口 | 显式向外部调用方提供长期历史 |
| 单进程运行边界内验证 | 延续已确认初始运行边界；持久历史不等同于多副本能力 | R6 / R7 新运行 Contract |

职责边界：Interface 处理 HTTP / Cookie / 输入输出，Application 裁决历史归属、轮次受理、成功提交和恢复；通过 Port 使用 Control DB Adapter，Domain 与业务语义仍拥有业务真相。Online Query 不承担历史、账号或成果管理；Infrastructure 不定义指标和权限。具体模块组织由设计审查明确，不能新增第二条生成 / 执行链路。

## Compatibility / Migration / Documentation / Done When

- 旧 Bearer Query API / Evaluation 默认行为保持；网页持久历史是显式的新 Contract，具体路由 / 参数兼容通过设计固化，不能按客户端输入身份决定权限。
- 通过现有 `src.bootstrap migrate` 入口显式安装新增Control DB对象 / 权限，纳入启动完整性检查；不在普通查询请求中建表，不从旧短期内存 / checkpoint伪造不存在的完整历史。
- 已有账号、Session、RBAC、审计、RAG、业务数据及旧checkpoint保持；migration可重复且新clone可初始化。旧网页未持久化记录不承诺补回。
- 回滚以发布版本 / 应用迁移兼容为单位，由设计明确；保留历史 / 成果数据，不以删除开发卷 / 业务数据回滚。本目标验收本地部署，不替代R6生产升级 / 恢复承诺。
- 交付同步正式 `docs/specs/` 的R3及Query API / Web变化、适用Design、Architecture职责说明、产品范围、领域版本边界、Runbook / README、日期化Acceptance和路线图；过程记录位于本目录。
- 核对受影响能力的需求状态 / 当前能力 / 不包含范围一致，按已合并事实同步主与关联实时字段；计划状态不能写成已实现。每项事实源维护位置或不适用理由记录在验收。
- Done When：确认后的全部Tickets完成，适用软件 / 集成 / 浏览器 / 三套Evaluation / R3真实闭环通过，Code Review / Diff / 事实源同步及本地Commit完成；远端发布另须明确授权，并按实际required checks / Auto-merge收尾。
