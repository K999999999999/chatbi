# T01 分类帮助、统一目标与标准应用运行

Status: done
Spec: [已确认行为](../spec.md)；[设计](../design.md)；[共用完成规则](../tickets-draft.md#共用done-when与证据要求)。
Authorization: 用户确认七项拆分及全部本地实现、验证与提交；远端未授权。

- Change Profile: 短期CLI扩展；中等切片；配置与资源选择风险；路由回归+真实Compose；本地交付。
- Owner: 当前主 Agent；长期归开发/部署工具。
- Blocked by: None (can start immediately)。
- What to build: 八类根帮助和分组帮助；共享Bash目标解析；保留现有dev根命令；app build/up/down/status/logs/infra/migrate/create-admin/prepare-model/build-rag/check，沿用标准初始化及就绪顺序。
- owned files: dev、共享scripts环境辅助文件、tests/scripts容器命令测试；docs/specs/container-dev-environment.md、container-deployment.md与Runbook所属章节。
- Acceptance Criteria: 所有帮助无.env/Docker且无副作用；错误参数先拒绝；dev/app项目/env/override/端口/UID/host路径正确且互不影响；app up不隐式初始化；down保留卷；app check只读verify；旧命令失败退出不退化。
- 验证证据: Docker替身检查参数与退出码；真实Compose config覆盖默认/定制/override；专属临时dev/app项目验证启停保留与初始化顺序，模型/LLM使用替身，不声称真实业务ready。
- Migration / Rollback: 先增入口再改推荐文档，原Compose直接调用保留；回滚CLI切片不改变卷。未知目标结构拒绝。
- Done When: 全部app操作及已有根操作完成兼容回归，目标解析成为后续唯一装配来源，正式文档说明环境选择。


## Result

八类帮助、共享目标解析与app生命周期完成；路由及实际Compose配置回归、隔离app初始化/启停/保留卷验证通过。正式容器Contract、README及Runbook已同步。

证据范围、故障修复及未运行验证见[整体验收记录](../acceptance.md)，[Code Review](../code-review.md)结论适用于本地候选；提交身份见Git公共目录实时记录。

## Comments

从草案正式写入，适用基线master@38e1302。
