# R2 Ticket草案

Status: 草案；Design Review PASS，Ticket Readiness READY，用户已确认拆分及整体本地实施
Canonical Source: [已确认Spec](spec.md)、[已审设计](design.md)、[Design Review](design-review.md)
Owner: 当前主Agent，持续维护的代码 /测试 /文档由本目标维护者负责；本轮不需要独立Backup Owner。
Delivery: 同一feat/result-visualization-v1 /worktree连续推进，全部适用验证与Code Review后本地Commit；一个目标一个PR，发布授权独立取得。所有Ticket均在完成时同步相应正式Contract及证据，不把文档维护全部延后。

## 01 可信单值结果说明与数字展示

Change Profile: 持续维护 /中 /公共响应与业务说明中高风险；Evidence为纯认证、API与页面确定性验证；Owner当前主Agent。
Blocked by: None (can start immediately)

### What to build

- 新增Semantic展示属性与校验加载，引用现有规范指标 /维度 /物理来源，不重复公式 /过滤，不修改现有RAG来源文件或哈希。缺失 /非法属性局部不可用。
- 固化设计§4的metadata数据Contract；实现已通过Guard的SQL投影位置 /权威公式 /固定过滤 /实际范围认证基本链，独立于Guard裁决及LLM调用。
- QuerySuccess /必要QueryContext及执行结果增加末尾可选描述事实，API兼容输出；旧构造、静态替身或无metadata响应降级。
- 前端解码、统一十进制格式及可操作原值入口；无分组单行可靠指标展示卡片+表格和口径 /单位 /范围。未知列保留原值、未知单位不猜，说明异常不改变原成功状态。

### Owned files

新增`src/semantic/result_display.json`及加载校验、`src/online_query/result_metadata.py`、元数据简单Contract（可在online_query内独立文件）；必要`contracts.py`、`service_execution.py`、`service.py`、retrieval_context中只读描述事实传递、`database.py`及Query API响应序列化；frontend results /数字格式 /解码 /查询展示；相关semantic /online_query /query_api测试和Chrome用例，正式R2 /API说明与本工作记录。路径拆分可按设计局部调整，不修改Prompt或Guard行为。

### Acceptance / 验证

1. 金额、计数、毛利率和编号正确展示，支持高精度字符串 /负值 /舍入边界 /极小非零 /NULL /零 /空字符串，原始返回值可核对。
2. 列别名改变不影响正确位置认证；公式 /固定过滤不符、错维度角色、旧响应或局部无效说明不得虚标业务含义。
3. 新字段可被旧客户端忽略，旧字段 /rows /错误码 /会话保持；证明Prompt文本、Guard裁决与数据库 /LLM调用次数未改变。
4. 范围只在实际谓词可证时标confirmed，否则partial /unknown；SemanticQuery意图不冒充SQL结果范围。
5. 单值页面卡片+表格默认同显、可分别收起；API /纯函数 /桌面页面回归通过。

### Migration / Rollback / Done When

兼容附加字段，无DB迁移 /RAG重建；恢复代码可回旧展示，原用户 /资产保留。适用确定性与API /浏览器验证、当前上下文Code Review、正式Spec/API文档、Diff检查和本地逻辑提交完成。失败保留原结果并修复，不用放宽认证替代通过。

## 02 问数趋势与分类图表

Change Profile: 持续维护 /中 /依赖与绘图解释中高风险；Evidence为锁依赖、纯图表计划、Chrome及容器页面；Owner当前主Agent。
Blocked by: 01

### What to build

- 锁定ECharts6.1.0与npm lock，按需SVG渲染、安全tooltip /aria /实例生命周期，局部加载 /绘制失败隔离；不安装新表格库或React包装依赖，不升级现有框架。
- 扩展01认证支持当前月份 /季度 /年份与分类物理输出的可靠绑定及time_axis，单一逻辑时间可能对应多个物理列；无新语义 /SQL决策。
- 实现time /category图表计划、同单位series /不同单位拆图；与表格同显、分别收起，适用类型切换不重查。
- 时间排序只作用图形；NULL与缺失时段断点，单点无趋势暗示，重复键 /多业务维度 /不可安全绘图数值降级。长标签及最多100行有可读布局，截断明确部分结果。

### Owned files

frontend package /lock、图表计划 /React图形边界 /查询展示 /样式 /results解码、02需要的后端元数据时间 /分组认证增量；相关纯函数 /online_query /Chrome用例、正式R2设计 /Contract /运行说明与工作记录。

### Acceptance / 验证

1. 同一结果同时用于图表 /表格，分类与时间显示类型正确；同单位对比、不同单位分图，未认证单位不误合轴。
2. 表格顺序保留，时间图升序；同一分组重复 /OR复杂范围未知 /缺失年份身份等保守降级，不求和、不填零。
3. 100行 /跨度大缺失时段 /长标签 /恶意标签 /绘图失败可重复测试，不丢数据、不生成无限空位、不执行HTML，原始表格保持。
4. 追问后图 /表 /单位 /范围同步，退出 /换号 /迟到响应 /刷新仍符合R1。
5. npm ci、typecheck、build、audit及锁来源验证通过；桌面Chrome开发与打包入口、容器启动 /热更新适用检查通过。

### Migration / Rollback / Done When

新增Web依赖，无数据库迁移 /平台发布。依赖兼容失败须定位；若需版本 /技术改变则返回设计或用户决定，不私自升级。受影响回归、安全检查、Code Review、正式Contract /设计文档及逻辑本地提交完成；保留数据卷与资产。

## 03 经营分析贡献图与任务证据

Change Profile: 持续维护 /中 /经营方向与恢复兼容风险；Evidence为确定性归因 /旧Checkpoint兼容 /Chrome；Owner当前主Agent。
Blocked by: 02（复用已完成的格式与图表边界；不重复列传递依赖01）

### What to build

- 两期金额 /差额、主要产品正负条形图、选择产品看已有因素，沿用后端effect_on_metric /分类 /对账，不重算归因。
- 省略产品明确计数，不填其他贡献或计算全量占比；new/discontinued不补造价格 /成本因素。
- 分析汇总传递查询结果可选metadata至task_results证据；不暴露SQL /内部状态，旧Checkpoint和无字段结果仍保留表格。
- 任务完成 /失败 /跳过及不完整证据提示保留；缺归因保留报告，无效 /未对账归因保持既有校验拒绝。

### Owned files

frontend Analysis /共享图形 /证据展示、business_analysis现有任务结果Contract与序列化 /checkpoint兼容传递、相关API /Business Analysis与Chrome测试，正式分析响应 /R2行为说明及本工作记录。

### Acceptance / 验证

1. 增加 /降低 /无变化方向与金额、因素和分类匹配后端；成本上升不被当毛利正贡献。
2. 产品选择不重查 /不改分析ID，省略产品 /新进入 /退出 /缺因素 /缺归因 /不完整证据用固定案例覆盖。
3. 原任务重试 /24小时Checkpoint语义不变，旧保存结果不因新增metadata失效；无额外模型调用或业务数据访问。
4. 恶意产品 /因素文本安全展示，指标 /原值格式与02一致，缺图不丢报告。

### Migration / Rollback / Done When

无DB或Checkpoint Schema迁移，新增可忽略字段且可读取旧payload。归因逻辑不变，不删历史checkpoint回滚。适用分析回归 /旧payload兼容 /Chrome、安全Review与正式响应说明完成并形成本地逻辑提交。

## 04 完整容器验收与候选交付证据

Change Profile: 持续维护 /中 /真实费用与账号清理较高风险；Evidence为最终clean代码候选、独立SQL /归因参考和资源身份；Owner当前主Agent。
Blocked by: 03

### What to build

- 扩展现有外部实际容器浏览器验收，覆盖时间 /分类 /同单位及混单位多指标问数、同会话追问、两期分析，核对元数据与图形 /表格一致。
- 使用专用验收账号，凭证不入报告；结束禁用 /撤销Session，保留原有用户、开发数据与RAG。独立SQL与既有归因参考做对照，不用LLM生成参考答案。
- 补最终受影响确定性、API /集成、浏览器、容器开发与打包检查、依赖 /安全门禁及Code Review；无新业务生成行为时明确不重跑全套Evaluation理由。
- 回填正式Spec /API /Design /Runbook /README适用变化、日期Acceptance /roadmap和工作状态，绑定clean candidate与运行资源，不覆盖旧证据身份。

### Owned files

frontend/tests容器真实用例及必要Playwright配置 /安全reporter、tests容器支持 /独立参考、scripts/verify_container_dev.sh适用扩展；docs/specs /designs /acceptance、Runbook /README /roadmap与本工作项证据。真实用例保持显式入口，与默认确定性回归隔离。

### Acceptance / 验证

1. 实际Compose网页 /API完成授权范围真实链路，图 /表 /单位 /范围及贡献对照一致；报告记录commit、git_dirty=false、模型 /数据 /RAG /镜像身份、安全结果。
2. 声明实际覆盖场景及每项结果；低概率边界由确定性故障注入证明，不以模型偶然输出替代测试。
3. 账号disabled=true /active_sessions=0、凭证移除、仅清理经标签核实的临时资源；已有资源保留。
4. 全部适用验证 /Review /Diff与事实源Done When完成；未运行项目明确列出，不声称R6 /R7或全套Evaluation完成。

### Migration / Rollback / Done When

真实资源缺失 /失败保留诊断并修复，不能换假模型宣称通过；不提高成本范围或删除既有资产。代码candidate与文档回填可分本地提交；最终工作区clean且所有Ticket完成。当前只允许本地交付，Push /PR发布独立确认。

## 依赖与授权

依赖链01→02→03→04；每项均含自己的适用测试、Review和文档，04负责实际全链与最终候选证明。已正式写入issues文件，用户已确认完整本地实施，当前实现和验证中。

用户已确认完整Spec、真实验收方向、四项拆分及全目标本地实施、适用验证、Review和本地Commit。按依赖连续完成四项，不逐项等待选择。远端发布不包含在该确认中。
