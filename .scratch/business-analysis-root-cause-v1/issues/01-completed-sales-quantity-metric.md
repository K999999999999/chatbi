# 01 添加已完成销售数量语义指标

Status: done

## Owner

ChatBI Engine 实施 Agent

## Blocked by

None (can start immediately)

## What to build

- 在 `src/semantic/metrics.json` 登记“已完成销售数量”，公式为 `SUM(f.quantity)`，只统计 `order_status = 'completed'`，按完成日期 `completion_date_key -> dim_date.full_date` 过滤。
- 配置“销售数量”“销量”等已确认别名，使指标可被普通 Natural Query 使用。
- 更新相应确定性语义测试；按现有 RAG Offline Build 流程构建并发布包含新指标的资产。

## Acceptance criteria

- 加载后的语义目录能解析“已完成销售数量”及其别名，公式、过滤和时间字段与 Spec 一致。
- 普通 Natural Query 可按完成日期查询数量，并可将数量与净销售额、销售成本一同用于产品分组查询。
- RAG 构建包含该指标，固定检索和在线自然查询评估通过。
- 现有已发布资产仅在新资产构建成功后替换；种子数据和事实表不修改。

## Change Profile

- Lifetime: 长期语义 Contract。
- Size: 小到中。
- Risk: 高；扩展所有普通自然查询可用的指标目录，并影响在线 RAG。
- Evidence: 指标目录软件测试、RAG 离线构建与固定检索评测、真实在线 Natural Query 评估。
- Delivery: 本地 Feature branch；不直接修改生产资产。

## Canonical Source

`.scratch/business-analysis-root-cause-v1/spec.md`；`src/semantic/metrics.json` 是实现映射事实。

## Owned files

- `src/semantic/metrics.json`
- `tests/online_query/`、`tests/rag_offline/` 中直接相关测试
- 如 RAG 评测需要固定案例，只修改对应案例文件

## Migration / Rollback

- 不迁移业务数据。
- 如构建或在线评估失败，保留当前已发布 RAG 版本，恢复指标 JSON 后继续使用原资产版本。

## Verification evidence

- 指标记录 schema 和公式测试。
- 新资产版本、指标检索结果和固定检索报告。
- 使用真实 LLM 和在线 RAG 的 Natural Query 结果，与独立只读 PostgreSQL 结果核对。

## Done When

指标目录与已发布 RAG 资产包含该指标，所需确定性及在线查询证据通过，并能供 Ticket 02 的正常查询 Task 使用。

## Result

已登记“已完成销售数量”正式指标，并发布 RAG 资产 `20260928-ba-sales-quantity-v1`。数量按 `SUM(f.quantity)`、已完成状态和完成日期口径统计。增加了销售数量检索案例及 2 条普通 Natural Query 评测案例；确定性测试 66 项通过，真实 Online RAG / Natural Query 评测 2/2 通过。数据库 Seed 和事实表未修改。

## Comments

- 不在本 Ticket 中增加实际成交单价或单位成本指标。
