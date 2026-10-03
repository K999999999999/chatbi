# R2 实现设计

Status: 已确认Spec内的设计细化，当前上下文Design Review PASS（2026-10-04）
Owner: 当前主Agent
Canonical Source: [Spec](spec.md)，发生冲突时Spec优先
Baseline: f182cf3；本文为编码前设计快照，当前实施以status.md和正式docs/designs/result-visualization-v1.md为准

## 1. 变化边界与替代方案

保留Online Query业务链、SQL Guard和授权裁决。Online Query在已校验SQL执行成功后，为本次结果构建显示事实；Query API仅序列化简单Contract；Web只负责格式、图形和交互。ECharts对象、Framework类型和数据库cursor均不穿过业务Contract。

比较三种方式：①前端按列名推断，无法证明业务含义，违反Spec；②在API重复解析SQL与读取业务来源，破坏Adapter职责；③在Online Query内组合本次QueryContext、ValidatedSemanticQuery、ValidatedSQL和执行结果，确定性认证后输出元数据。选③，不引入独立服务 /BFF /插件平台。

## 2. 显示属性来源与资产兼容

新增Semantic所属的展示属性记录（建议`src/semantic/result_display.json`及小型校验加载模块），引用现有规范指标 /维度名，存放显示类别、确认单位及维度物理绑定 /时间分组配方。它只拥有本次新增的展示属性，不复制指标公式、业务定义、过滤条件或Join规则；指标事实仍从metrics.json读取、物理字段从Structure及认证映射校验。

明确金额CNY /元、订单count计数、毛利率ratio /%，已完成销售数量没有确认计量单位，单位为未知，不猜“件”。维度绑定须使用完整物理字段身份；同名region字段及不同Join角色不可仅按名字互换。记录引用必须存在于当前权威来源与本次QueryContext，错误属性局部不可用。

为何不直接添加到metrics.json：`rag_offline/sources.py`哈希包含源文件字节，新增展示字段会引发旧资产失配，虽不变公式仍需重建RAG。本设计把新增展示属性与已有公式事实分别维护，避免无关重建；不改既有来源哈希、manifest或Guard。展示记录随当前代码维护，读取失败安全降级，测试覆盖引用有效性；metadata不声称它来自旧Qdrant payload。

已有`QueryContext.metric_constraints`保持原Guard语义。如单指标检索上下文需要携带已解析指标 /字段描述，新增独立可选描述事实，不能填入Guard专用constraints改变单指标校验路径或Prompt。已有测试替身 /静态上下文没有新增事实时允许降级。

## 3. 确定性列认证

新增模块建议`src/online_query/result_metadata.py`，隐藏AST规范化、来源校验和输出绑定复杂性。输入为已执行成功的SQL及本次语义 /上下文 /结果，不再次生成SQL或执行数据库。

认证步骤：

1. 用已有锁定SQLGlot解析已通过Guard的SQL，定位顶层SELECT投影与实际输出列，按位置对齐；SELECT *、投影数不一致、不可追踪子查询 /窗口等只让相关展示降级，不新增SQL拒绝。
2. 单 /多指标均对投影表达式与权威公式规范化匹配，解析表别名为完整物理身份，确认本次认证表列 /Join与指标必需固定过滤条件成立。使用或复用现有表达式规范化机制，禁止字符串别名猜测。不能仅凭Guard通过就认证单指标业务口径。
3. 维度采用Semantic展示绑定、实际表达式 /GROUP BY及本次认证物理闭包确认；显示分类 /标识角色依权威绑定，技术numeric类型不能把编号升级为度量。多字段年份+月份可组成一个时间维度，前提同一日期角色与粒度可证。
4. 时间范围和筛选说明以已校验语义结合实际SQL谓词证据认证：识别明确的AND比较 /BETWEEN边界与对应日期角色，规范化为半开区间；不支持的OR /复杂表达式或实际与语义不符时标未确认。未限定只在实际不存在相关限定时显示。任意无法证明的附加谓词不得被忽略后宣称范围已完整确认。
5. 每列 /范围分别给出可信状态；局部缺失不污染其他已认证列。业务或DB结果不变，只影响显示元数据。

需要的规范化 /认证可以用纯Python输入固定SQL、来源记录和简单dataclass单独测试。保留原QuerySuccess.semantic_query供会话提交；增加末尾可选metadata字段，旧构造方式保持。`QueryData`可末尾增加可选技术列类型，从Psycopg cursor.description安全提取基础类型；替身不提供则技术类型unknown，技术信息从不替代业务认证。

## 4. 公共响应结构

查询成功新增可选`result_metadata`；旧字段 /rows /sql完全保持，旧响应不含该字段时Web原始表格降级。应用内部使用不可变dataclass /枚举，API转换为JSON；不泄露AST、Schema对象、凭据或内部文件路径。

```text
result_metadata:
  version: 1
  status: complete | partial | unavailable
  columns: 每个输出位置一项
    index / name: 与columns严格对齐
    data_type: number | string | boolean | date | unknown
    role: metric | dimension | identifier | unknown
    semantic_name / definition / unit: 已认证内容，否则null
    format: money | count | ratio | number | raw
    certified: boolean
    reason_code: 未认证原因的安全枚举，否则null
  scope:
    status: complete | partial | unavailable
    time: {start, end_exclusive, time_basis} | null
    time_status: confirmed | unbounded | unknown
    filters: 已认证筛选的结构化文字和值
    grouping: [{semantic_name, kind: time|category, column_indices}]
    warnings: 安全公开reason_code列表
  time_axis: {granularity, keys: 与rows一一对应的规范时间键} | null
```

unit为`{key: string, label: string}`或null，包含稳定同单位比较键与显示文字；money为CNY /元，ratio为ratio /%，计数按订单与明细行分别标识，unknown为null，不能仅同叫number就认为同单位。filters元素为`{label: string, operator: string, values: string[]}`，仅包含安全公开的认证条件；时间边界为ISO8601字符串、time_basis为已认证业务日期口径文字，grouping.column_indices为非负整数数组。time_axis.keys为规范日期 /期间起点ISO字符串，granularity为day /week /month /quarter /year之一；没有可靠键则整个time_axis为null，不输出猜测键。scope部分未知时不声称filters已完整；元数据status与列 /范围状态一致。keys只描述已有结果，不增加结果行或客户端查询参数。

前端按version及index/name/长度/角色/格式一致性校验，不接受自定义代码、ECharts option或HTML。未知版本整个说明降级；列局部无效只降级该列。API若元数据构建失败，返回成功结果及unavailable元数据或兼容省略，不能吞掉原数据库错误。

经营分析贡献以已有report.attribution为权威，不新增第二份贡献计算。任务证据可兼容增加同结构result_metadata：在任务结果汇总边界传递QuerySuccess的metadata，不把整个SQL或语义状态公开。旧Checkpoint /无字段任务仍显示原表格，不改变恢复协议或数据库Schema。

## 5. 前端与精度

结果说明解码、数字格式和图表计划为独立纯函数；ResultTable与新卡片 /图表统一使用已校验的显示信息。字符串Decimal不先转JS Number再做格式化：采用十进制字符串算法，money及ratio采用确定性四舍五入（半值向远离零），百分比用十进制移位；原始返回值独立保留。极小非零舍入到0时显示舍入提示。number来源保留传输值，不承诺恢复传输前未知精度。

计数只接受合法整数；认证与值不匹配局部raw降级，不截去小数。NaN /Infinity /过大不可绘图数不送ECharts，原值仍可核对。原始值查看采用可键盘操作的按钮 /展开内容，不只靠鼠标title。

图表计划按业务维度分为single /time /category /unsupported。单位不同拆图；无分组多行不取首行；同一逻辑分组出现重复键则受影响图表降级，不聚合。表格保留原顺序，time图按规范键排序；缺失段采用null图形占位与connectNulls=false，不改rows。只为100行内已返回数据的区间分段 /有限空位，跨度过大可用分段序列避免生成无限时间点。

ECharts `6.1.0`精确锁定，仅按需注册LineChart /BarChart及必要轴 /提示 /legend /renderer组件，不新增React包装依赖。渲染器使用SVG便于桌面浏览器断言和有限数据展示；tooltip使用安全文本 /richText方式，不插入返回HTML。aria与文字方向标签 /表格提供读图入口；图实例创建 /更新 /resize /dispose与React生命周期一致。模块加载与绘制错误在图表边界隔离，不使整页崩溃。

图例和说明明确series单位；分类长标签允许滚动 /有限视窗及完整名称提示，不丢已返回分类。默认同显、分别收起；时间图line /bar切换，分类图bar。新查询各自拥有展示状态，不改变会话；refresh /logout行为沿用R1。

产品正负贡献图保留后端顺序与effect_on_metric；选产品显示其现有因素。new/discontinued不伪造价格 /成本因素；缺归因保留报告，非法 /未对账归因保持现有拒绝。省略产品只显示数量提示，不绘制推算other。

## 6. 验证与交付

独立认证seam、API兼容、精度及图表计划、既有Guard /Prompt /查询执行调用次数回归；桌面Chrome开发 /打包两入口与SVG /键盘 /攻击标签 /失败隔离。npm ci /typecheck /build /audit与lock来源记录验证兼容，ECharts版本无需升级现有React等依赖。

扩展既有容器真实验收的外部服务模式，覆盖时间 /分类 /同单位与混单位多指标、同会话追问和两期分析。独立SQL核对金额与分组，既有归因参考核对方向 /因素，记录实际绘图类型、格式和范围。故障 /NULL /复杂形状用确定性案例覆盖，不要求模型偶然生成边界。专用账号禁用、Session0、安全报告及clean候选要求沿用现有入口。

因不改模型 /Prompt /Retrieval决策 /SQL Guard业务裁决，预计无需全套AI Evaluation，实施Diff若触及这些行为则重新评估。源码 /API /Contract不变后的文档回填可复用证据，日志不输出凭据。正式Spec、API Contract、Design、Runbook与Acceptance、roadmap作为Done When同步。

无线上迁移 /部署，不增加Feature Flag。展示回滚可恢复代码与锁依赖，不删除持久卷、用户、Checkpoint或RAG；旧客户端与旧Checkpoint可降级消费。当前仅设计，不安装依赖或运行实验。
