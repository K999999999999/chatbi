# ChatBI 项目路线图

具体范围、Contract（契约）、技术选择和验收标准在进入对应阶段时再讨论确认。

## 当前状态

- Online Query、Online Retrieval V1 和 RAG Offline Build 已实现；实体类、单指标和离线资产链路已完成相应软件测试与验收。
- 基础 Multi-Metric Retrieval（多指标在线检索）已完成 T1～T4 软件实现与确定性测试，修复 M08 后真实在线 RAG Evaluation（评测）达到 20/20；C05 和 M08 通过，但正式 Business Acceptance（业务验收）仍待确认。
- Observability V1 已完成 T1～T4C 和本地验收；T5 Langfuse / Business Acceptance Gate（业务验收门禁）因未配置外部 Endpoint（端点）待补，当前不能称为 Production Ready（生产可用）。
- 当前全量确定性测试为 230 passed、6 skipped、79 subtests；真实在线 RAG Evaluation 为 20/20。三类证据仍分别记录，不互相替代。

## 后续路线

1. **完成当前验收门槛**：确认基础 Multi-Metric Retrieval 的 Business Acceptance，并在具备外部配置后完成 Observability T5 Gate。
2. **Quality Automation（质量自动化）**：自动执行软件测试、AI Evaluation（AI 评测）入口、安全检查和构建验证。
3. **User & Data Authorization（用户与数据权限）**：完成用户身份、角色、数据范围、审计以及按真实需求启用的租户隔离。
4. **Multi-Turn Conversation（多轮对话）**：实现用户隔离的结构化对话状态、上下文继承和每轮重新授权查询。
5. **Business Analysis（经营分析）**：实现受控任务拆解、多查询执行、证据汇总和可继续追问的分析闭环。
6. **Production Hardening（生产强化）**：补齐性能与负载验证、资源治理、Secret、安全发布、监控、部署和回滚。
7. **Platform Evolution（平台演进）**：仅根据真实规模和需求扩展多租户、AI Gateway（AI 网关）、集群和平台治理能力。
