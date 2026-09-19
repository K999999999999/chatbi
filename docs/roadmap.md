# ChatBI 项目路线图

本路线图只用于确认产品当前处于哪个阶段，以及后续可能开发什么功能。

具体需求、边界、技术设计、Ticket、测试和发布条件，分别记录在对应的 Feature Spec、Ticket、验收记录和发布文档中，不在本路线图展开。

## 产品方向

- 目标用户：公司内部员工。
- 首期用户：销售 / 经营分析人员。
- 首期数据域：`mart_sales`。
- 产品方向：先做好单业务域的自然语言查询，再逐步增加受控的分析能力和生产能力。

## 当前阶段

### Query Product V1：内部查询体验闭环

状态：`current`

当前 V1 基线已经具备单轮查询、受控多轮查询、基础授权、Query API 和内部 Streamlit 入口。

当前下一功能：`Conversation Timeline V1`

目标：让用户能够在当前会话中回看连续提问、结果和失败信息，而不只是看到最后一次查询结果。

## 后续阶段

| 阶段 | 状态 | 方向 |
| --- | --- | --- |
| Query Product V1 | `current` | 完成内部查询体验闭环 |
| Internal Pilot | `planned` | 让有限范围的内部员工受控试用并收集反馈 |
| Production V1 | `planned` | 在明确的内部用户和 `mart_sales` 范围内稳定运行 |
| Business Analysis V1 | `planned` | 增加有边界的经营分析能力 |
| Platform Evolution | `conditional` | 根据真实规模和需求演进到多业务域、异步或平台化能力 |

## 未来功能方向

以下是方向，不代表已经进入开发：

- `Conversation Timeline V1`：当前会话记录和查询过程回看；
- `Internal Pilot` 相关能力：内部用户使用、反馈和问题追踪；
- `Business Analysis V1`：有限范围的拆解、对比和结果汇总；
- 平台演进：多业务域、多数据源、异步任务和规模化运行。

## 当前决定

- 当前阶段：`Query Product V1`。
- 下一功能：`Conversation Timeline V1`。
- `Production V1` 的发布条件：在进入内部试点和正式生产准备时再单独确认。
- 详细内容：不写入路线图，以对应 Feature Spec、Ticket 和验收文档为准。
