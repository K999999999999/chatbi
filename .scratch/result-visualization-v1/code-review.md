# R2 当前上下文 Code Review

Scope: 基线f182cf3 → 当前R2 owned Diff；实现、Formal Spec/Design、npm依赖和适用验证。
Mode: Main Agent；未启动独立Agent。
Review: PASS（实现与确定性验证）；真实clean候选门禁待04执行。

## What / Why / Risk

实际SQL认证显示事实，新增兼容metadata；ECharts模块化展示图表/表格/既有经营归因，十进制格式避免金额字符串转换精度损失。主要风险为范围误标、混单位、旧Checkpoint兼容、第三方文本渲染和模型行为意外变化。

## Findings与收敛

1. HAVING未计入范围：已标partial/HAVING_UNCONFIRMED，真实查询服务测试PASS。
2. 一条错误展示属性使全部说明不可用：已按记录过滤坏属性，有效指标继续认证，隔离来源测试PASS。
3. 额外JOIN谓词只读复查：实际服务证明已有Guard拒绝且executor未调用，不存在成功响应范围漏标；保留回归证明，不增加不可到达的展示分支。
4. 旧API无metadata不得额外返回null：exclude_none，旧响应精确键断言PASS。
5. 旧Checkpoint缺可选字段：实际JsonPlusSerializer加载旧字段集合构造结果，默认None；测试PASS。持久化数组形状按现有Serializer处理，不引入迁移。
6. 年/月多个物理列认证为同一逻辑时间分组，但列语义分别为年份/月；真实服务输出回归覆盖。
7. 图形init/ResizeObserver异常和失败恢复：销毁有序、保留canvas可重绘，表格独立；Chrome故障注入PASS。

## 检查维度与证据

- Correctness：位置/实际公式/固定过滤、实际日期角色、缺年份不猜、局部未知、隐藏分组、重复分组不聚合；范围未知显式降级。
- Architecture：只在执行成功后认证；API显式转换。Prompt/理解/Retrieval/SQL Guard政策/归因算法未修改；新metadata不进入报告提示。
- Security：React安全文本、richText Tooltip；图表本地加载、无CDN；登录/权限/CSRF/换号/退出/迟到响应回归保留。
- Testability：真实服务/API公共seam，外部SQL生成和数据库最小替身；默认Chrome固定响应与故障注入不调用模型。
- Compatibility：可选字段、旧响应精确键、旧任务及Checkpoint、query/analysis状态分离与原问题重试。
- Clean Code：Semantic拥有展示属性，公式来源唯一；无新表格框架、模型调用、BFF或无关抽象；删除未使用图计划方向字段。

当前证据：全软件641 passed /15 skipped /139 subtests；Chrome32 passed，Vite开发代理1 passed；锁文件/编译/Ruff/Markdown链接/模块边界/Diff PASS；npm/Python依赖审计0已知漏洞，Bandit medium/high0。

dirty实际容器诊断：问数/追问、12月三指标两单位图、四产品线同单位两指标图与独立SQL一致，热更新PASS；分析尚未完整通过。新分析对照只去掉前端解析不保留的reconciliation_passed字段，仍要求服务端通过对账及全部权威数值/方向/因素一致；正式clean运行不可省略。

本机无Gitleaks CLI，未运行完整Secret scan；对本Diff人工检查未发现真实Secret。正式全量Evaluation未运行：生成路径/Prompt/检索/Guard/归因不变，小范围真实验收单独绑定候选；不冒称历史Evaluation当前通过。未观察到符合门槛的新增Harness缺口。
