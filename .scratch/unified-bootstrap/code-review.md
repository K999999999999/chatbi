# 实现 Review

Review: PASS
Clean Code: PASS
Scope: 基线 `08c632e01baae62e161f3eec69993d56a3f441c3`；三项正式 Tickets 的 owned files，以及被迁移装配函数的 Evaluation 调用和旧命令的 Embedding 错误提示。
Reviewer: 当前主 Agent，未启动独立 Agent

## Change Description

将运行资源装配、production 就绪门禁与四类显式命令集中到 bootstrap；真实应用改用 lifespan 创建和绑定资源，统一处理失败与关闭。移除旧入口，同步调用、文档和回归证据。沿用业务、权限、数据、模型参数与依赖版本。

## Findings / 核对

- Correctness: HTTP 闭包引用在启动阶段更新，SQLAdmin 挂载在就绪后完成，关闭解除本轮引用与挂载。重复启动使用新资源，启动失败保持原始原因。
- Resource ownership: 根应用持有自己的 engine、RAG、模型同步 / 异步 HTTP clients、Tracing 和分析应用；builder 先登记 engine / pool 再 open，构造失败清理局部资源。直接注入与 runtime_factory 混用被拒绝，避免两套管理员资源或不明确所有权。
- Failure: 清理按依赖逆序，单个 cleanup 失败继续其余清理，诊断只记录阶段 / 异常类型。RAG 意外构造异常也释放 store；多 client 关闭失败仍清理剩余 clients；关闭保持幂等。
- Security: migration 与运行身份隔离，首个管理员隐藏密码和重复拒绝，production 来源 / catalog 门禁保留。HTTP、Authorization、SQL Guard、Semantic、Schema / Seed 与 Prompt 无改动；RuntimeDependencies repr 隐藏 admin secret。
- Migration: 四类 CLI 按需导入，无旧入口转发；数据库 runner、reset、CI、Real E2E workflow、README / Runbook 和 Embedding 错误提示迁移。历史证据保留。
- Scope: 隔离数据库验证暴露 runner 旧测试路径失效，已在受影响 runner 内最小修正，并加入目标存在性回归；不改变测试数据或环境操作。
- Maintainability: 单一 FastAPI、标准资源 stack 与所属模块实现；无 DI 容器、注册框架、第二条查询链路或额外依赖。Adapter 的服务接口移入 runtime.py，保留原 import 名称。
- Testing: 软件、隔离数据库和 API startup smoke 分开记录；RAG / 模型命令用替身验证操作分发与失败，不将这些证据表述为真实 AI Evaluation 或生产部署通过。

发现的资源所有权混用、意外构造异常和清理失败中断问题均已在本目标内修复并复验，无待修复项。后续启动测试显式禁用外部 Trace exporter，4 项真实入口测试与 19 项隔离数据库复验通过；只强化测试隔离，不改变运行 Contract。

Applicable candidate: `213ed9a4e0d299f77448883c0b3c5d72341d4c67`；后续仅验收记录更新时证据仍适用。
Evidence: 见 verification.md；全量软件回归后的局部修订有受影响复验，不重复无关检查。
Documentation: docs/specs/bootstrap.md、Query API / RAG Spec、Query API Design、Architecture、README、Runbook 和 roadmap 均已同步。
Harness Feedback: runner 的失效路径已通过本目标回归检查修复；未观察到需要扩展当前目标的新增 Harness 缺口。
Next: 本地 Commit；远端发布仍未授权。
