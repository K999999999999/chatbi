# Deployment Simplification Ticket Readiness

Ticket Readiness: READY
Scope: [已确认Spec](spec.md)、[四项Ticket草案](tickets-draft.md)、[实现设计](design.md)、[Design Review PASS](design-review.md)
Reviewer: 当前主Agent；只读核对，不启动独立Agent。
Change Profile: 持续维护的开发/容器入口与跨模块旧系统删除；总体较大，中至高风险；软件、PG集成、浏览器、renderer、构建及隔离Business Acceptance；默认本地交付。
Owner: 当前实施Agent。无跨团队交付；遇到数据/权限/AI/API例外扩大或新依赖返回用户确认及Design Review。

## Findings / 核对结果

- Scope明确：每项提供可观察行为与owned files；01保护应用状态，02形成完整容器验证能力，03完成标准运行和删除闭包，04完成使用入口和交付验收。无业务链路或Schema改动混入。
- Spec是本目标范围权威，Design是实现选择，正式当前应用规则在交付时更新；Ticket不另定义权限/指标/恢复真相。
- 01和02无技术前置，可依次由同一Owner实施；03直接依赖01、02，04直接依赖03，无循环或虚假全链依赖。
- 共享dev/验收/文档文件有明确阶段归属，单Agent按编号实施；混合operations和local测试逐条保留必要应用覆盖。
- 正常、未知配置/参数、资产缺失、超时、端口冲突、重复初始化、故障恢复、退出/失败清理均有验收入口；不以容器liveness替代readiness或真实业务。
- 用户已确认details.backup删除，其他HTTP/权限/无保活不变；保留应用锁/epoch/generation、业务只读和Control DB身份边界。无需额外架构决策。
- 软件与模型证据区分；PG两profile、实际renderer开关、浏览器渠道和skip处理明确。评测案例不改，历史结果不得重标。
- 构建继续使用已锁定版本与现有浏览器/字体；不新增库。Secret与迁移凭据不进API/构建上下文/报告，Docker socket不进业务API。
- 已发现旧消费者（CLI/脚本/Compose/应用装配/网页/测试/当前及历史文档）；删除前迁移必要校验，最终搜索消费者并记录历史白名单，防止新代码继续依赖Stable。
- Done When可客观验证：行为、适用测试、Review、正式文档、证据和资源清理均须完成。检查失败不得仅凭git clean或CI绿标done。
- 发布和旧真实资源操作未授权；确认Tickets/本地实施不扩大到Push/PR、数据清理或生产切换。

Dependencies: 01、02 → 03 → 04；同一Owner顺序执行。
Migration / Rollback: 先迁移必要应用/验证能力，再删除旧系统；任一失败暂停后续删除，以修复提交恢复源码，不回退用户改动。无Schema变更，无真实资源切换。专用测试资源按标签清理；旧资源保持。
Evidence: 审查基线f4d0693，真实代码/配置读取、Design Review及Ticket验收计划；此处不是运行验证结果，软件/构建/首次部署尚未执行。
Next: 用户确认四项拆分，并明确是否授权完整本地实施、验证和相关Commit；之后写入正式issues，按依赖连续执行。
