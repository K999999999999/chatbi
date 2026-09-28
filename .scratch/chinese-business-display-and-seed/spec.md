# 中文经营分析展示与演示数据本地化

## Problem Statement

ChatBI 当前有三处影响中文演示和结果可读性的问题：

1. Business Analysis Summary 的 Prompt 使用中文，但没有要求报告内容使用中文，LLM 因此可能返回英文报告。
2. Streamlit 普通查询只按少数列名格式化数值；Business Analysis 的 Task 结果表格直接展示 API 原始值，金额可能没有逗号分组或单位。
3. 本地 Sales Mart 开发 Seed 中，客户名、产品名、客户类型、行业和国家包含英文样例，不利于中文演示。

Business Analysis 黄金案例中的固定变化金额不是随机数据库值。当前开发 Seed 使用确定性公式生成，评测也会执行参考 SQL 核对当前数据库结果；本次不改变这些数值断言。

## Solution

### 总结语言

- Business Analysis 的面向用户报告使用简体中文，包括标题、摘要、趋势判断、发现、原因和建议。
- 结构化字段、证据引用、数值方向和归因事实保持现有 Contract；不得为实现翻译而修改数据事实。
- 作为数据内容引用的专有名称或原始值可以保留其权威写法；本地演示 Seed 将同步使用中文业务名称。

### 数值展示

- 普通查询和 Business Analysis Task 结果表格均使用千分位分组：整数部分从右向左每三位使用半角逗号，例如 `12,345,678.90`。
- 金额保持原人民币元，不换算为万元；已确认的人民币金额列在列名或表格单位标识中注明“元”。不为未知指标推测单位。
- 数值格式化只发生在 Streamlit 展示层。HTTP API / JSON 仍返回原始数值，不把逗号或单位写入数据库、SQL 结果或 API 数值字段。
- 数值型标识、日期键、枚举码和状态码不作为度量值格式化。金额、计数、数量、比率按已知语义和现有精度规则呈现；不得仅凭“是数字”就把所有数值字段当金额。

### 开发 Seed 本地化

- 本地演示 Seed 的用户可见文本使用中文：客户名称、产品名称、客户类型、行业、国家，以及对应的字段值示例。
- 保留数据库 Schema / 表 / 列标识、SQL 使用的订单状态机器码（`pending`、`confirmed`、`completed`、`cancelled`）、币种代码、区域代码、来源系统标识等技术值为英文。
- 保持所有数值事实、键值、日期、金额、数量、状态分布和业务计算不变；翻译不得改变固定评测案例的数值结果。
- Seed 版本从 `chatbi-sales-mart-dev-v2` 提升到新版本；新空数据库初始化直接使用新 Seed。
- 已有本地开发环境使用仓库既有的 PostgreSQL 开发环境重置流程全量重建，不增加 v2→v3 定向迁移。重置会清空 `chatbi_mvp` 与 `chatbi_control` 中的本地数据、管理员、账号、Session 和审计记录；重置后按 Runbook 重新创建管理员。此方案只适用于可丢弃的本地开发 / 演示数据，不适用于共享环境或任何需要保留的数据。
- 既有重置命令只重置 PostgreSQL，不删除 Qdrant。Seed / metadata 变化后，必须按 Runbook 重建并发布与新数据匹配的 RAG 检索资产，避免旧索引继续提供旧英文演示名称。
- 数据 Seed 版本、当前结构 `columns.json` 中已有 `value_examples` 和相关 Runbook 同步更新。历史 `column_values.json` 不恢复为活动事实源。
- Seed 文本变更会改变数据指纹；已有 Baseline 评测报告应按不可直接比较处理，并在新数据上产生新报告。数值参考 SQL 结果应保持一致。若当前发布的 RAG 资产包含旧演示名称，更新后需按仓库工作流重建 / 发布并验证检索资产。

## User Stories

- 作为中文业务用户，我希望经营分析报告以简体中文呈现，便于理解结论和建议。
- 作为查看查询结果的用户，我希望大数使用三位千分位逗号、金额单位清楚，且不会把元误读成万元。
- 作为演示人员，我希望客户、产品及业务分类样例是中文，同时保留 SQL 和机器接口所依赖的稳定代码。
- 作为本地开发 / 演示环境使用者，我可以在已知 PostgreSQL 开发数据、管理员及控制记录会清空的前提下，全量重置数据库并按 Runbook 重建管理员和检索索引。

## Implementation Decisions

- 当前 UI 为 Streamlit；格式化属于展示职责，API Contract 与数据库数值类型不变。
- 不将千分位逗号存入 PostgreSQL，不改变金额 / 数量列的数据类型。
- 只本地化开发演示数据，不改 CI-only Fixture、外部真实数据或历史报告文件。
- 现有业务层按当前 Seed 计算的黄金数值仍是回归断言；数据指纹变化通过新 Evaluation 报告记录，不静默覆盖旧报告。
- 现存 `.scratch` Spec 是工作规划记录；正式稳定行为若后续确认需要长期固化，再更新对应正式 Spec。

## Testing Decisions

- 确定性测试覆盖简体中文 Summary 指令和报告字段 Contract。
- Streamlit 测试覆盖普通查询与 Business Analysis 表格的三位分组、货币单位、原始 JSON 数值不变、负数 / 小数 / 空值，以及 ID / 日期 / 状态码不被错误格式化。
- 人民币金额展示为元并保留两位小数；不改变数据库/API 精度，也不把金额缩写成万元。
- Seed / metadata 测试覆盖中英文范围、机器码保留，以及数值事实和固定 BA 案例期望值保持一致；新空库初始化应带有新 Seed 版本。
- Runbook 验收覆盖 PostgreSQL 全量重置会清除两个开发数据库并重新初始化 Seed，管理员需显式重建；Qdrant 不随 PostgreSQL 重置而清除，需独立重建并发布匹配的新检索资产。
- 按仓库风险规则，Summary Prompt、Retrieval 元数据 / RAG 资产受影响时，在确认 candidate 后执行对应真实 Evaluation；若本地真实链路失败，不宣称验收通过。
- 只有用户确认 Spec、设计审查通过、Ticket Readiness 为 READY 并确认 Ticket 后才进入实现。

## Out of Scope

- 将表名、列名、Schema 名、API 字段、SQL 标识、枚举机器码或币种代码翻译为中文。
- 把人民币金额自动缩写成万元 / 亿元，或改动底层金额、数量、汇率计算和列类型。
- 改变 Business Analysis Golden Case 的问题、参考 SQL、期望方向或数值。
- 为共享环境、生产环境或需要保留的 PostgreSQL 数据提供自动迁移；本次只支持本地可丢弃开发 / 演示环境的全量重置。
- 将当前演示数据替换成生产数据，或改变真实客户 / 产品权威名称。
- 修改 CI fixture、其他评测集或过往验收报告，除非实现时发现它们是当前 Contract 的必要验证边界。

## Further Notes

- 当前历史提交 `bfdf422` 已将旧 `column_values.json` 合并进 `columns.json` 的 `value_examples`；不应把历史导出物恢复成并列事实源。
- 当前 metadata export 会保留 `columns.json` 中已有的 `value_examples`，不会自动从数据库实时采集；修改 Seed 值时必须显式同步这些示例。
- 当前工作区已有密码重置 CLI 的未提交修改，后续实现必须保留且不能把该功能并入本 Spec。
