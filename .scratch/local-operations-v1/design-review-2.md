# R7 Design 复审

Review: PASS
Review Target: 用户2026-10-08整体确认的 [Spec](spec.md) 与Contract内补齐的 [Design](design.md)；baseline `0c77d80`。当前主Agent只读审查，无独立Agent。设计修订在审查前的设计阶段完成，审查阶段未修改目标。

## Findings

无剩余阻止Ticket拆分的设计问题。首轮四项问题逐项关闭：

1. 资源切换：Design第6节为既有local工具增加资源binding和journal；先停止候选和原环境writer，再附着已核验卷；保留原资源，失败显式recover。已有固定项目和卷是兼容默认，不新增发布平台。
2. 备份有效性：第4–5节限定age/PG工具镜像、私钥和临时文件权限；一致性snapshot、加密后完整解密校验、已知catalog摘要核验；新副本登记成功才清理过期。API仅挂安全public子目录，不获得keys/catalog/journal。
3. 共用额度：第3节在ExecutionRuntime共享owner/API计数，R4组合history/analysis租约，同步不创建伪history。当前execution.py明确使用429 EXECUTION_LIMIT_REACHED，设计沿用该值。真实调用结束前不释放额度。
4. 状态与Trace：第2节明确DTO、35秒调度/显示预算、超时与过期、显式浏览器来源校验及只读认证；当前middleware仅覆盖业务路径，新状态路由显式保护。第7节独立worker scope安全关联受理trace，不复用已关闭root；OTLP fail open。

Reference: 已读取Architecture Knowledge Core；使用业务/Contract、变更轴、依赖、复杂度、状态/权限、可测试性与Alternative比较原则。
Evidence Sources: docs/architecture.md、product-scope.md、roadmap.md；R4/R5/Web/R6/Observability Spec；local、docker-compose.local.yml、scripts/local_*；src/query_api/app.py、browser.py、execution.py、execution_runtime.py；authorization/auth_service.py、bootstrap/readiness.py、observability/tracing.py；现有tests/scripts、tests/query_api、tests/observability和frontend/tests；首轮Review及PG16/age官方依据。

## 限制与验证归属

PASS仅证明设计在现有边界内可实施，不证明恢复、60秒、30分钟、容量或云Trace已验收。上述结果分别由Ticket软件/隔离集成和最终真实验收建立；历史R6/云验收不重标为本候选通过。无AI业务行为/Prompt变化，不机械新增模型评测；受影响真实入口业务回归仍必需。

Next: workflow-to-tickets生成草案，当前主Agent执行只读Ticket Readiness；READY后请求一次确认拆分与本地实施范围。无实现、Commit或Push/PR授权扩展。
