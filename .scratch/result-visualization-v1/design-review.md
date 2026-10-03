# R2 Design Review

Review: PASS
Review Target: [已确认Spec](spec.md)、[实现设计](design.md)
Owner: 当前主Agent；2026-10-04，当前上下文只读审查，无独立Agent
Baseline: f182cf3及本目标规划文档，不审实现Diff

## Findings与收敛

1. Signal：当前成功结果没有业务输出绑定，单指标SQL Guard通过不等于指标公式 /筛选已认证。
   Evidence：QuerySuccess仅有列 /行 /语义状态；QueryContext.metric_constraints的既有职责是SQL Guard，单 /多指标路径不同；service_execution保有本次SQL与上下文。
   Impact：仅按别名或用户意图标单位、日期、毛利率会形成错误业务说明；把展示约束注入Guard还会改变查询拒绝范围。
   Recommendation：在Online Query内对输出位置、公式 /物理闭包 /固定筛选和实际范围独立认证；保留原Guard及成功状态，字段局部降级。设计§2–4已落实，PASS。

2. Signal：展示字段直接加入现有metrics.json会改变资产来源指纹。
   Evidence：rag_offline/sources.py读取源文件哈希；既有production Ready /manifest校验使用该来源身份。
   Impact：UI展示属性变化引起无关RAG重建、运维耦合与资产兼容风险。
   Recommendation：Semantic内新增只拥有展示属性的记录，引用既有规范名 /物理身份，不复制公式 /过滤 /Join，保留原metrics.json和来源验证。设计§2已落实，PASS。

3. Signal：Decimal字符串及JS绘图数值有不同精度和生命周期。
   Evidence：现有API保留JSON原值，归因输出十进制字符串；现有前端按String展示。
   Impact：先转Number会丢精度；绘图失败或标签HTML还可能破坏整页或安全边界。
   Recommendation：十进制字符串显示舍入、原值入口、有限绘图转换、安全tooltip、SVG /实例销毁 /失败边界及局部降级。设计§5–6已落实，PASS。

无未解决设计发现。新展示记录属于现有Semantic职责，未新增一级模块、查询链或业务公式；新metadata属于Spec已授权兼容扩展，具体字段已在设计固化。实现需遵守该Contract，不得静默换字段或修改已审边界。

## 审查维度

Business /Use Case、Contract、Change Axes、Boundaries、Dependency Direction、Repository Reality、Failure /State /Security、Complexity、Information Hiding、Testability、Optionality、Alternatives均PASS。对比前端猜测 /API复制业务 /Online Query本次认证三个方案，选最小可证明的现有模块内扩展；不新增Interface层、SDK到Domain、BFF或插件框架。

Reference：已读取Architecture Knowledge Core，重点使用业务 /变化轴、公共可观察行为、跨边界简单数据、Failure /State /可测试性、Design Twice、生命周期成本与Overengineering Guard。

Evidence Sources：Spec、Architecture、Domain Context、Query API /Web Contract、service /service_execution、QueryContext /QueryData /QuerySuccess、Psycopg执行器、SQL Guard及multi_metric表达式规范化、RAG sources、现有ResultTable /Analysis与Chrome /容器验收工具。

证据边界：只读设计与依赖元数据核对；未安装包、未运行兼容实验 /测试 /真实LLM。是否能按设计覆盖支持形状由实施测试证明，不能把PASS当运行验收。ECharts版本精确锁定及兼容性在Ticket02验证；需改已确认技术时返回确认。

Next: workflow-to-tickets草案，再当前上下文Ticket Readiness；不等于实施 /发布授权。
