# ChatBI 项目路线图

具体范围、Contract（契约）、技术选择和验收标准在进入对应阶段时再讨论确认。

## 当前状态

- Online Query、Online Retrieval V1 和 RAG Offline Build 已实现；实体类、单指标和离线资产链路已完成相应软件测试与验收。
- 基础 Multi-Metric Retrieval（多指标在线检索）已按当前 V1 统一为 `metrics=0/1/N` 流程，支持最多 5 个指标，完成软件实现和确定性验收；当前分支最近一次真实在线 RAG Evaluation（评测）为 20/21，唯一失败为一次受控的 Query Understanding LLM_ERROR。
- Observability V1 已完成 T1～T5；阿里云 OTLP / Trace 外部验收已通过。当前仍不能称为 Production Ready（生产可用）。
- 当前全量确定性测试数量以本次验证输出为准；最近一次真实在线 RAG Evaluation 为当前分支 20/21。三类证据仍分别记录，不互相替代。

## 后续路线

1. **Quality Automation（质量自动化）**：自动执行软件测试、AI Evaluation（AI 评测）入口、安全检查和构建验证。
2. **User & Data Authorization（用户与数据权限）**：完成用户身份、角色、数据范围、审计以及按真实需求启用的租户隔离。
3. **Multi-Turn Conversation（多轮对话）**：实现用户隔离的结构化对话状态、上下文继承和每轮重新授权查询。
4. **Business Analysis（经营分析）**：实现受控任务拆解、多查询执行、证据汇总和可继续追问的分析闭环。
5. **Production Hardening（生产强化）**：补齐性能与负载验证、资源治理、Secret、安全发布、监控、部署和回滚。
6. **Platform Evolution（平台演进）**：仅根据真实规模和需求扩展多租户、AI Gateway（AI 网关）、集群和平台治理能力。
