# 06 — 真实执行生命周期与阿里云Trace安全接入

Status: done
Authorization: 用户2026-10-08确认七项拆分与全部本地实施、验证、Review和Commit；无Push/PR或实际stable切换授权。
Canonical Source: [Spec](../spec.md)、[Design](../design.md)；共同约束见 [已确认拆分](../tickets-draft.md)。


Change Profile: 持续维护 / 各入口的同一诊断闭环 / 高风险（内容泄露、fail open）/ Software+OTel集成+实际云验收 / 本地Commit。
Owner: 当前目标实施维护者。
Blocked by: 02。
What to build: 复用TraceRecorder/OTLP，HTTP受理与实际worker独立scope安全关联，覆盖问数追问、分析、XLSX/PNG/PDF及同步Query；stable受限配置白名单与有界batch exporter；仅阶段/耗时/安全分类，内容采集硬关闭。
Acceptance Criteria:
- HTTP结束不结束后台真实业务span；禁止跨线程复用已关闭root，关联使用批准carrier/Link/ID；导出worker实际步骤及回收有真实证据。
- 不采集问题/SQL/结果/Secret/raw exception；身份/请求属性受白名单保护；稳定配置不继承dev端点/headers。
- 云断连/队列满/超时不阻断业务、不耗无界内存；停机有界，错误只安全分类；状态探测不产生LLM或高频业务trace噪声。
- 本机诊断仍可用；实际用户配置的阿里云可查询当前候选trace才能记cloud PASS，缺凭据/运行授权或出口条件写未验收，不以历史证据替代。
owned files: src/observability/{tracing,contracts,config,tracing_export,tracing_safety}.py；src/query_api执行/导出入口与实际worker；bootstrap装配；local/compose受限配置；tests/observability、tests/query_api和受影响业务Trace测试。
验证证据: in-memory exporter span生命周期/安全属性/故障注入；实际OTLP有界行为；各入口当前候选trace ID/安全截图证据（脱敏）；云不可用仍完成业务。
Migration / Rollback: OTel SDK在Infrastructure Adapter；保留既有TraceRecorder正常接口；开关仅控制输出，业务就绪不依赖云；新增稳定配置白名单可关闭云输出且不影响本地状态。
Done When: Trace软件/集成证据与Review完成；Observability/Runbook白名单与fail-open说明更新；真实云结果归07最终报告，缺证据不得宣称目标完成。


Result: 本地实现、软件与OTLP集成测试、Runbook/Observability Contract更新及Code Review完成。云端实际Trace查询属于Ticket 07当前候选最终验收；稳定配置未启用OTLP，因此不报告云接入PASS。
Comments: 本地候选提交及验证记录见 `.scratch/local-operations-v1/review-06.md`；未修改或重启stable/dev服务，未读取或记录Secret值。
