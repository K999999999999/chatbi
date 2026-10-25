# 文档修复：核实依据与处理结果

## 当前状态：10 项文档问题已处理

用户先确认保留 COLUMN 默认上限 50，随后接受保留当前顺序检索的建议，并明确授权“可以 改文档吧”。本轮从干净 a53792a 开始，将 DOC002 的正式流程 / 调度说明统一为 TABLE → 可选 METRIC → COLUMN；多指标逐个检索，实体查询跳过 METRIC。DOC001–DOC010 的文档修复现均完成。

当前规则依据本轮用户明确确认，不从代码或历史已合并提交反推授权。预算50不代表参数最优，顺序执行不代表并行没有收益；运行代码、测试和资源配置保持，无发布授权。以下逐项表保留初次核实及当时待确认状态；DOC001/002的最新处置以本节和正式检索Spec为准。

## 授权、基线与边界

用户追加指令：“可以先核实 再修复 修复文档”。继续同一工作项和 branch，修复切片从干净 `e69eb2b7817f75cfccfe7997c0cc075b6263d2f5` 开始；前次删除 / 审核提交不回退。只更新正式文档、审计后续状态及本工作项记录，不修改源码、测试、模型 / 资源配置，也不获 Push / PR 授权。

## 逐项核实与处置

| 审核项 | 核实依据 | 文档处理 | 剩余边界 |
| --- | --- | --- | --- |
| DOC001 | git log -S 追到 `df0a8536f892ccbc254ee3dac3fc279181bced24`；该提交将 RetrievalConfig 的 COLUMN 从20改50。提交正文说明“调整多表候选列检索”，但已查规划 / 决策记录未见明确50确认；原 .scratch/online-retrieval-v1/spec.md 及现行 Spec 为20，当前代码 / Contract 测试为50 | 检索 Spec 增加显著差异表，保留原 Top-20 要求及验收；Design 说明当前普通预算默认50与认证字段受限补充 | 原要求和实现冲突未解决；不能以已合并或测试50推定用户确认50 |
| DOC002 | .scratch/online-retrieval-v1/spec.md 流程写并行；旧归档亦有“可以并行”文字。当前 _retrieve_resources 先TABLE、再逐指标METRIC，无并发调度；未找到取消原要求的明确记录 | Spec 明列原并行要求与当前顺序事实；Design 删除错误的当前并行陈述，链接差异表 | 是否要求恢复并行仍待决定；不改代码、不虚报时延改善 |
| DOC003 | 正式历史 / 执行 Spec与Design；Chat.send 创建history并提交executions / revision；Store.create生成分析run UUID，旧query-api同步Contract仍有效 | Web Spec改用history / execution / operation / revision身份及受理观察、手动恢复；分析Spec区分旧同步客户端ID与网页服务端ID | 已修正文档；保留旧API兼容，不改状态协议 |
| DOC004 | 正式检索Spec按每个指标说法检索；资源阶段循环；现有测试断言三个metric.search | 观测性Spec / Design改为每次实际搜索一Span，实体不造指标Span | 文档已修；旧测试函数名仍有one_comprehensive字样，非本次源码范围 |
| DOC005 | 就绪 / API / 执行Spec；app同步问数与分析使用admit；admission调用同一reserve_owner | 执行Design说明共享默认1/4容量，保留同步响应及无持久execution兼容 | 已修正文档 |
| DOC006 | 恢复Spec；result_display loader从query_bindings.json读取维度，result_display.json仅含指标显示属性 | 可视化Spec明确绑定Owner与展示Owner，并链接正式恢复Contract | 已修正文档 |
| DOC007 | dev logs转发参数；dev_environment显式两份Compose和override；基础Compose无api | Runbook / 观测性Spec统一为 ./dev logs --since 10m | 已修正文档；该命令查看当前项目服务日志，不实际读取本机业务日志 |
| DOC008 | evaluation CLI四份默认输入，分析另加dimensions；Runner只为result_match生成reference；正式评测Spec及.gitignore规定本机报告 | Evaluation Design按实际套件输入 / 参考结果解释Hash，新报告不进源码Commit，旧报告保留身份 | 已修正文档；不修改历史报告 |
| DOC009 | 现行query-restoration Spec、历史Spec当前链接；旧指向scratch归档 | 历史Design改链正式恢复Spec | 已修正文档 |
| DOC010 | main只创建runtime_factory应用；Bootstrap lifespan装配 / cleanup；app中间件覆盖多命名空间并跳过GET/HEAD业务Root；service在线FAIL_CLOSED | 观测性Design更新装配、同步 / 后台 / 观察生命周期、序列化边界；移除失效static_fallback说明，兼容枚举标清非当前路径；Spec去掉旧20案例 / 错误回退要求 | 已修正文档；未验收真实OTLP收件或模型链路 |

检索差异的追溯采用本地 Git 历史、当前与归档 Spec、.scratch/natural-query-evaluation/、.scratch/query-*、.scratch/current-documentation/ 和相关文本检索。结论是“在这些已查证据中未找到确认”，不是断言从未发生过确认。不能仅从源码、PR 已合并、测试通过或本次用户仅授权修文档推定原 Contract 已改变。

## 验证计划与结果

- 文档：使用 ./dev check docs 检查全部适用Markdown的链接与正式文档结构。
- 事实：定向运行现有 test_contracts 和 retrieval_observability_t3a，核实当前默认预算与检索Span次数；不新建镜像业务代码的测试。
- 人工：逐项复核本文件与正式文档Diff，确认旧API和状态 / 权限边界保持、DOC001/002未伪装已解决。
- 未运行真实LLM、数据库 / 浏览器业务验收、全量回归和托管CI：仅文档更新，不改被测行为，不能报告真实运行新成绩。
- 最终实际结果、动态文档处置和当前上下文Review见 verification.md 的本轮追加记录。
