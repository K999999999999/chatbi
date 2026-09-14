# ChatBI 开发流程导航

## 用途

本文档只负责 ChatBI 的阶段导航、事实源索引和当前项目状态。具体的通用工作方法由已安装的 Matt Engineering Skills 负责，不在本文档重复展开。

## 默认流程

```text
/ask-matt
    ↓ 判断当前阶段
/grill-with-docs
    ↓ 需求、术语、范围明确后
/domain-modeling       ← 仅在领域术语或不可逆决策需要时
    ↓
/to-spec               ← 用户确认 Spec
    ↓
/to-tickets            ← 用户确认 Ticket 拆分
    ↓
/implement
    ├── /tdd
    └── /code-review
```

不是每个任务都需要完整流程：

- 小范围且目标明确的修改可以直接进入 `/implement`；
- 只写行为测试时使用 `/tdd`；
- 只审查本地 Diff、Commit 或 Branch 时使用 `/code-review`；
- Bug 诊断、外部资料研究、架构接口设计和大型路线规划分别使用对应的 `diagnosing-bugs`、`research`、`codebase-design` 和 `wayfinder`。

## ChatBI 特有的前置门槛

以下内容不是通用 Skill 的替代品，而是 ChatBI 的事实和确认边界：

- Architecture（架构）决定模块职责、主链路、依赖方向和稳定边界；
- Feature / Module Spec（功能 / 模块规格）决定输入、输出、规则、错误、不负责范围和验收标准；
- Implementation Design（实现设计）只决定已确认 Contract 的落地方式；
- 发生系统边界、模块一级职责、公共 Contract、数据所有权、权限或状态不变量变化时，必须先完成设计确认；
- Software Test、AI Evaluation 和 Business Acceptance 必须分别保留证据。

Matt Skills 应先读取这些项目事实源，不能用通用模板覆盖它们。

## 思路混乱时

1. 暂停新增代码和技术选型。
2. 通过 `/ask-matt` 判断最早仍未完成的阶段。
3. 读取 `AGENTS.md`、产品范围、架构和相关 Spec / Design。
4. 只解决当前阶段，不提前创建后续产物。
5. 会改变范围、行为或架构的待定问题先确认；否则采用最简单可验证的方案。

`Module` 是完整业务能力，`Node` 是模块内部链路的一步，`Task` 是一次可以独立完成和验证的工作。不要按数据库、服务、接口等水平层机械拆分 Ticket；优先拆分可观察的纵向行为。

## 当前项目位置

更新时间：2026-09-12

| 阶段 | 状态 | 依据 |
|---|---|---|
| Requirement（需求确认） | 已完成 | `docs/product-scope.md` |
| Architecture（架构设计） | 已完成 | `docs/architecture.md` |
| Online Query Module Spec（在线查询模块规格） | 已完成 | `docs/specs/online-query.md` |
| Online Query Implementation（在线查询实现） | 已完成 | Query API、Streamlit POC 和基础 Multi-Metric T1～T4 已实现；主验收问题 C05 已通过真实在线 RAG 链路 |
| Observability V1 Module Spec（可观测性规格） | 已完成 | `docs/specs/observability.md`；行为、数据安全、降级和验收边界已确认 |
| Observability V1 Implementation Design（可观测性实现设计） | T1～T4C 已完成并通过各自测试；本地验收完成，T5 外部 Gate 待补 | `docs/designs/observability.md`；T1～T4C 均有独立提交，`.env` 未配置 OTLP/Langfuse Endpoint，不能记为 T5 PASS 或 Production Ready |
| RAG Offline Build Module Spec（RAG 离线构建模块规格） | 已完成 | `docs/specs/rag-offline-build.md` |
| RAG Offline Implementation Design（RAG 离线构建实现设计） | 已完成 | `docs/designs/rag-offline-build.md` |
| RAG Offline Task Split（RAG 离线构建任务拆分） | 已完成 | T1 至 T9 均已完成 |
| RAG Offline Implementation（RAG 离线构建实现） | 已完成 | TABLE / COLUMN / METRIC 文档、BGE-M3 dense+sparse、Qdrant 版本集合、关系图和原子发布均已实现 |
| Test / Evaluation（测试与评估） | 已完成（T5 外部 Langfuse Gate 待补） | 当前全量确定性测试 230 passed、6 skipped、79 subtests；真实 Online RAG Evaluation 报告 `reports/evaluation/20260912T145505Z-c60e073.json` 为 20/20，C05 PASS，并记录 Evaluation 的 `request_id`/`trace_id`；本地 API C05 成功和空问题受控失败均已验证 `X-Trace-ID` |
| Code Review（代码审查） | 已完成 | Contract、范围、失败保护、Secret、依赖锁和差异检查均已复核 |
| Integration / Release（集成与发布） | 本地 POC 资产已发布 | 应用仍为 `0.1.0`（POC）；RAG Offline 资产 `20260906-bge-m3-v2` 已发布到本地持久化 Qdrant 和 `data/rag`；单指标 Online Retrieval V1、基础多指标真实评测和 C05 业务验收均已完成；生成资产不进入 Git，未 Push（推送）远程 |

当前下一步：

> T1～T4C 已完成并通过各自测试，当前本地验收已完成；下一步仅补 T5 Langfuse / Business Acceptance Gate。由于 `.env` 没有 OTLP/Langfuse Endpoint，外部 Langfuse Gate 待补，不能写 T5 PASS，也不把 `0.1.0` POC 描述为 Production Ready（生产可用）。

## 维护规则

- 阶段发生变化时，只更新“当前项目位置”。
- 需求或架构改变时，先更新对应事实文档，再更新当前状态。
- 新需求的 Spec 和 Ticket 使用 `.scratch/<feature>/`；已有 `docs/specs/`、`docs/designs/` 和历史验收记录不迁移、不覆盖。
- 不为每个小节点创建长文档；只有稳定 Contract、关键决定和验证结果需要保留。
- 文档状态必须以真实代码、测试和评测结果为准，不能把计划写成已经完成。
