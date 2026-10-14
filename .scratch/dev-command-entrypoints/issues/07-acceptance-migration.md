# T07 容器验收入口与旧操作最终归档

Status: done
Spec: [已确认行为](../spec.md)；[设计](../design.md)；[共用完成规则](../tickets-draft.md#共用done-when与证据要求)。
Authorization: 用户确认七项拆分及全部本地实现、验证与提交；远端未授权。

- Change Profile: 短期验收入口与已盘点迁移收尾；中等；错误环境/丢失验收风险；路由与断言对照；本地交付。
- Owner: 当前主 Agent；长期归验收脚本与Runbook。
- Blocked by: T01。T02–T06不是开工依赖；全目标Done需全部完成。
- What to build: verify dev默认isolated、显式real与verify app委派现有脚本；核对前端test:real断言与现行验收覆盖，处理start-dev.ps1及旧推荐引用；完成24/24台账和总帮助/README导航。
- owned files: dev、tests/scripts验收路由、frontend/package.json/real配置与断言（仅迁移需要时）、start-dev.ps1、必要验收脚本兼容点；README、Runbook、inventory与适用container Contract。成熟验收脚本不重写。
- Acceptance Criteria: 原报告/退出/clean要求/费用/专用账号清理保持；错误目标/多余参数不启动；直接脚本可用；独立SQL、追问、分析断言有明确去向，覆盖不足保留非推荐入口；内部/CI专用脚本均注明原因；不新增日常Smoke改密。
- 验证证据: 路由替身与费用说明、旧新能力逐项对照、消费者rg检索；对应确定性回归、文档/链接检查。此次不自动真实LLM验收，未运行须明确，不套用历史报告。
- Migration / Rollback: 新入口Expand→引用Migrate→证明后Contract；原断言及历史证据保留。可回滚入口和迁移引用；无日常数据操作。
- Done When: 验收命令可用、全部脚本归属与旧能力去向齐全；全部切片完成后整体Code Review与适用回归、Roadmap事实核对，形成本地候选。

## Result

verify dev默认isolated/显式real及app委派完成；退出码17传播、错误参数不启动。24/24基线脚本及外围入口处置齐全，PowerShell旧启动归档；保留未能证明等价的前端真实验收断言。真实付费LLM验收未运行。

证据范围、故障修复及未运行验证见[整体验收记录](../acceptance.md)，[Code Review](../code-review.md)结论适用于本地候选；提交身份见Git公共目录实时记录。

## Comments

从草案正式写入，适用基线master@38e1302。
