# Harness V1 设计审查

Review: PASS WITH MINOR FIXES
Review Target: 用户已整体确认的 [Spec](spec.md)
Baseline: ChatBI `2897302038fa42167e79a0b5ad483c2b628359b9`；Plugin源 `9d97431b0e8d3870db5d06c748a23ddae6a2d1cd`

本审查由当前主 Agent 只读执行，没有独立 Agent，没有实施产品或工具代码。下述修订由审查结束后的主 Agent 落实，不属于审查过程的写入。

## 结论依据

用户需要可核实的状态、改动、预算与恢复，不需要外部调度平台。文件 / Git 工具加项目适配能够覆盖第一版；可用临时仓库、可控时间和合成证据验证，不依赖模型、业务数据库或真实环境失败注入。通用工具不导入 ChatBI 应用模块，ChatBI 只提供路径、命令入口和项目规则。

## Findings

### D1 单一状态文件与兼容行为

Signal: 若机器 JSON 和现有 status.md 分别写入，中断时可能出现两种当前状态；旧工具又只解析少量顶层字段。

Evidence: Spec 要求单一权威来源与原子更新；现有 scripts.check_harness_state.fields 忽略代码块并读取顶层 ID / Status 等字段。

Impact: 状态失真、迁移失败与跨会话恢复错误，增加重复检查成本。

Recommendation: V1 复用项目适配指定的单一 Markdown 状态文件。保留旧字段权威，新结构化扩展只保存旧字段没有的数据；同文件原子替换、整文件版本核对与互斥写入。旧记录只读识别，不自动补造新版门禁。禁止另建可独立写入的当前状态副本。

### D2 证据来源与批准边界

Signal: 存在引用不代表引用为真；新工具可能把人工填入的“通过”当成机器强制证明。

Evidence: Spec 明确人工批准是流程约束；当前检查只检查字段非空。Git / PR / 原报告具有不同权威边界。

Impact: 不可信候选或旧证据错误放行，用户误以为完成独立审批。

Recommendation: 对每份依据记录机器核实、人工声明或未验证，以及来源、版本和覆盖。人工决定允许有来源的声明，机器可核实项不能以声明替代。实质变化使候选依据待复核，范围授权单独保存；同范围 CI 修复不自动扩大授权，也不机械新增逐提交批准。

### D3 诊断时间、等待与恢复

Signal: “30分钟无证据”与“正常等待不计诊断”若没有记录起止，跨会话可能被误重置或无限延长。

Evidence: Spec 的3轮 / 30分钟预算跨会话保留，同时排除正常等待；现有状态没有结构化诊断计时。

Impact: 长任务无法及时升级，或正常构建被误停止；无法确定性测试。

Recommendation: 持久化问题身份、无进展轮数、最近有效证据时间和有界等待区间，计算累计有效诊断时长。等待必须有开始 / 截止 / 原因；超时、时钟倒退或区间无法核实则返回待核实，不能获得新预算。使用可控时间测试精确边界，不通过真实等待验证。

### D4 工具分发与 ChatBI 运行边界

Signal: Plugin 目前只提供 Skills；若临时假定工具已安装或要求宿主 Python，将改变 ChatBI 已确认的容器路线。

Evidence: Plugin manifest / setup Skill 无工具安装器；Runbook 明确宿主只需 Git、Docker、Compose；dev harness 当前在容器执行旧检查。

Impact: 工具不可达、两套逻辑漂移，或额外环境依赖导致接入失败。

Recommendation: 通用 CLI 使用 Python 3.11 标准库，无第三方依赖 / 新服务；代码随 Plugin 分发，项目只保存 adapter / 薄入口。ChatBI 通过已有容器挂载已核实工具路径，不自动安装或联网。缓存 / 路径缺失显式报 unavailable；旧只读检查保留明确范围，不能冒充新门禁。源 / 安装 / 当前会话版本分别核验。

## 修订核对

主 Agent 在审查结束后形成[设计说明](design.md)，落实 D1–D4，并更新 Spec 的确认和授权状态。逐项核对：无新第三方依赖、服务、审批身份、产品行为、外部写入或实施授权；四项为已确认需求内的实现约束。

Reference: 已读取 Architecture Knowledge Core，使用变化轴、依赖方向、Observable Behavior、Failure / State、Design Twice、兼容迁移及 Overengineering Guard。

Evidence Sources: Spec；ChatBI AGENTS、Architecture、Product Scope、Runbook、Issue Tracker、Git / PR规则、旧状态检查实现与测试、dev容器入口；Plugin manifest、README、setup和交付Skill；两仓库Git与源目录状态。

Next: 修订已核对，可准备 Ticket 草案和当前上下文 Readiness。通过不代表实施、Commit、发布、安装或远端配置授权。
