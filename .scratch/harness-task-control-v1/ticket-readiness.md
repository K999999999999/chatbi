# Harness V1 Ticket Readiness

Ticket Readiness: READY
Scope: [已确认Spec](spec.md)、[设计说明](design.md)及[8项Ticket草案](ticket-drafts.md)
Baseline: ChatBI `2897302038fa42167e79a0b5ad483c2b628359b9`；Plugin通用内容在源 `9d97431b0e8d3870db5d06c748a23ddae6a2d1cd` 与远端master `6681366453eedce45e36f989a082df8a78b85819` 一致

本报告记录 Ticket 起草前的只读 Readiness 审查快照；当时未写正式 issues 或实现代码。用户随后于 2026-10-19 确认拆分并授权本地实施。本文不替代当前软件验收，也不授权发布。

## Change Profile 与 Owner

长期通用工具与项目适配，8个可独立观察 / 验证的行为切片。风险为状态失真、无依据推进、预算绕过、用户改动覆盖、证据失配、迁移与跨仓假完成。Owner为当前主Agent；用户负责关键决定和额外授权。标准库Python 3.11与已有Git / 容器满足约束，不新增第三方依赖、数据库、App或服务。

## Findings 与核对

1. **目标与设计已确定。** 用户整体确认Spec；Design Review为PASS WITH MINOR FIXES，D1–D4已落实并核对。单一权威文件、旧字段兼容、类型化证据、预算区间与容器运行边界不再留给实施猜测。CLI子命令拼写、模块内部拆分等局部组织不改变Contract，可由实施收敛。
2. **纵向切片完整。** 01状态查询/拒绝转换、02Diff与证据、03预算、04收尾与维护、05接入、06阶段集成、07项目适配、08整体验收，每项含正常、失败、迁移、验证及Done When。工具与测试 / 文档不按层分成不同Ticket；没有纯“建空架构”切片。
3. **授权与强制边界明确。** 自动状态校验不冒充沙箱/监控；聊天批准不冒充独立远端审批；Spec确认不等于实施；本地候选、安装、发布、Ruleset应用及隔离实验分别记事实和授权。08仅准备可审查远端计划，不隐式执行。
4. **事实源与owned files明确。** 两仓分别拥有通用工具和项目adapter，ChatBI是主记录。旧状态工具保留原语义；通用核心不复制进ChatBI。共享文件在同仓候选顺序修改，owned-files重叠不等于并行写入授权。
5. **证据可实现。** 标准库测试、临时Git / linked worktree、可控时间、合成报告 / 远端快照及容器fixture覆盖软件行为，不需要真实模型或数据库。远端规则与跳过 / 并发的真实阻断没有被Mock替代，另列授权实验。
6. **运行与分发可恢复。** ChatBI不新增宿主运行时；旧入口/无工具/挂载权限均有测试。源、安装缓存和会话加载分开，不手改缓存。没有安装授权时可以完成本地候选验证，但不能宣称安装生效。
7. **Plugin源保护。** 当前源worktree在已存在feature分支，含用户未跟踪7z归档；另一linked worktree在旧master。实施前从核实同步的远端master建立隔离、干净的本目标候选，不切换/清理已有源目录、不夹带agent-engineering-skills未发布改动。当前engineering-workflow内容与远端master相同，通用工具无需基于未发布审计改动实现。源同步仍须另核对与授权。
8. **动态文档和反馈已覆盖。** 04提供机制，06通用规则，07项目清单，08核对当前事实与历史证据。long-task-progress-clarity保留独立生命周期，不能因本目标登记就标解决。已有规则未执行优先修正事实，不默认堆叠规则。

## Dependencies

直接依赖01→02；02→03、04；04→05；03、05→06；06→07；07→08，无循环。02的实际事实采集建立在01明确的依据Contract上，不允许01把未验证当通过。按编号实施即可满足依赖。08通过07传递依赖全部通用能力，不需要重复列出所有前置。

用户确认后，各仓一个实现候选；无逐Ticket PR、无独立Agent、无长期多线集成目标。跨仓依赖是本地可用候选，不意味着未获授权就先发布Plugin。

## Migration / Rollback

没有业务Schema或产品行为迁移。旧记录只读识别 / 按目标显式迁移、保留原件，不批量补造授权；旧check的行为和退出码保留。新版不可达明确失败 / unavailable，不冒充完整通过。回退工具保留状态与证据；远端设置回退先保留配置并按授权执行，不能自动降低保护。独立服务Rollout / Feature Flag不适用，因为第一版不是应用运行时部署。

## Evidence 与限制

实际读取：已确认Spec、Design Review和设计、8项草案；ChatBI AGENTS / Issue Tracker / Git / PR与文档规则、架构 / 产品范围 / Runbook、dev / container_tasks与旧状态实现 / 测试、现有CI / 自动合并配置；Plugin setup、manifest、README、源码布局与Git。

当前只运行文档链接 / 结构与草案一致性检查，未运行未实现工具的测试、产品回归、真实模型、托管CI或远端实验。ChatBI未提交文档归属本目标，Plugin用户归档保持不动；Harness检查的相关REVIEW按上述归属保留，不当错误清理。

Historical Next: 用户确认8项粒度 / 依赖后，创建正式 Tickets 并连续实施。该门槛已由 2026-10-19 会话确认；当前结果见[正式 Tickets](issues/)和[验收记录](acceptance.md)。不包含 Push / PR、安装更新、远端设置或实验授权。
