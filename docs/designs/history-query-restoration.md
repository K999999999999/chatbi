# 完整查询条件与历史恢复

Contract：[History Spec](../specs/history-results-v1.md)。本文件说明已确认的业务语义恢复和确定性认证设计。

## 1. 单一执行链与兼容入口

现有 `OnlineQueryService.execute` → Retrieval / QueryContext → Prompt → SQL Guard → Database链不复制。`QueryRequest`末尾增加内部 `require_restorable: bool=False`；仅HistoryApplication设置True，HTTP不接受客户端提交该标记。旧Bearer /旧评测 /分析内任务沿用False，原六字段Candidate parser、Prompt、Guard默认语义、请求 /响应字段与短期状态不变。

`ValidatedSemanticQuery`末尾可选 `restoration_conditions`，默认None代表旧语义Contract，不代表“全部条件为空”。新增独立不可变DTO `RestorationConditions`、`CertifiedQueryState`与严格codec。启用历史profile时必须有完整conditions与认证来源，缺失不能返回网页成功；不通过R2 result_metadata.status推断是否可恢复。

查询理解Adapter新增history profile入口（first / revision），复用同一模型调用 /受控重试 /基础六字段校验，不另建理解服务或第二次模型调用。旧understand / understand_revision默认parser不接受新字段。history profile增加下面的Candidate字段，经程序校验才能成为Validated对象；完整原问题不作为恢复真相。History请求执行仍调用现有AuthorizedQueryService，内部标记在其复制QueryRequest时必须保留，不能由wrapper丢失。

## 2. 完整状态与条件

| 字段 | 严格语义 |
| --- | --- |
| 基础语义 | query_type、subjects、metrics、dimensions、filters，沿用当前校验；time为已校验带时区绝对[start,end)和granularity，不重新解析旧相对时间 |
| order_by | 有序元组，每项target_kind为metric / dimension / entity_field / time、target为规范业务身份，direction为asc / desc、nulls为first / last；不接受物理列名 /表达式 /SQL片段。target必须来自该查询经认证的输出业务项 |
| row_limit | null或正整数；程序拒绝bool /浮点 /负数。用户业务排名数量与返回最多100行独立，例如前200项保留200条件并提示返回截断，不能把100当作原业务Top-N |
| aggregate_filters | 当前已允许单指标聚合条件的规范指标身份、既有equals / in / gt / gte / lt / lte及严格十进制字符串 /值数组；表示聚合后条件，禁止混成普通行WHERE。既有多指标不支持HAVING的约束仍拒绝，不借R3放宽 |
| selection | entity_lookup需明确主体、经认证输出实体字段与distinct布尔值；metric_analysis按规范指标 /维度 /时间分组，不允许模型增加未请求指标或改变去重 /公式 |
| provenance | state_version=1、实际发布资产的相关规范指标定义、字段类型 /映射、Join不变量、程序认证的semantic bindings；build_id只用于定位，不以全局build_id变化直接判不兼容 |

完整条件覆盖当前单条问数范围，不引入窗口排名、跨查询比较、任意算式 /新指标、OR自由过滤、任意复杂SQL规划。现有Guard拒绝的SQL仍拒绝；既有合法业务请求必须在既有能力内完整表达并通过，不得通过标“不可恢复”绕过验收。

不明确的“前几个” /缺少排序对象返回澄清，不猜数量或指标。同一规范target重复且冲突拒绝。仅“前10”且没有能唯一继承的排序对象也澄清。无业务排名请求时row_limit=null；不把数据库取数100行 /101探测等运行资源限制编码成业务条件。排序未指定nulls时采用PostgreSQL显式默认（asc last、desc first），在生成SQL前写入条件。

非排名结果的展示排序没有用户业务含义；程序可在SQL生成前按输出维度身份确定展示顺序并记录为order_by，不能在执行后把模型任意ORDER BY反推成用户要求。实体无指定排序默认按已认证实体身份字段；单值无需排序。排名有平局时以同一输出业务维度 /实体身份升序作为固定次级顺序，保证截取确定性；不引入R4 / R5全量分页。无法确定排序身份须澄清。

## 3. Business Semantic Resolution → 认证映射

由Online Query下的semantic_state认证规则拥有业务条件与QueryContext的绑定。只使用程序批准的业务名称 /实体字段 /时间粒度和当前发布的TABLE / COLUMN / METRIC /Join事实，不根据模型选择列就批准绑定。未发布metrics.json、显示别名、R2单位 /颜色 /格式不成为新的业务真相。

为现有规范维度 /实体字段建立一个小型、显式的 `src/semantic/query_bindings.json`：业务身份、类型、物理引用、允许的时间表达式，来源引用已有Domain /指标 /结构定义。不得新增未经确认业务口径；将R2显示文件里相同的维度column映射移入此权威绑定，R2 loader引用绑定而不是维护第二份映射。格式 /单位继续留在result_display.json。表 /字段 /类型 /Join同时必须存在于本次当前发布资产与QueryContext白名单；配置不是绕开认证的通行证。映射缺失 /歧义拒绝，不由LLM填充。

RetrievalContext把本次已发布MetricHit、ColumnHit、TableHit和JoinConstraint的必要只读认证事实传给QueryContext的末尾可选字段（旧构造默认None），单指标也需保留所选规范指标完整定义。只传最小结构化事实，不靠再次解析prompt_context文本恢复、不向API暴露hit metadata。

认证结果为 `CertifiedQueryState`：完整业务语义、规范业务身份到当前物理表达式的确定性binding、依赖定义摘要。生成SQL前完成；旧快照恢复先严格decode，再通过同一当前认证流程比较相关定义。定义比较对公式 /固定过滤 /time_field /数据源 /业务字段类型与映射 /Join基数做规范化后相等判定；名称显示文案 /检索排名 /无关资产变动不改变兼容性。不能把无关字段在新QueryContext未召回误称业务口径变了：技术性资产读取失败沿用受控CONTEXT_ERROR；实际相关定义缺失或改变才为HISTORY_CONTEXT_INCOMPATIBLE。

新追问先比较原完整状态的相关定义，兼容后做delta合并，并认证新合并条件；重查原条件直接当前认证，不再次理解旧问题、不执行旧SQL。R3官方验收必须覆盖单值、时间 /分类、实体、1至5指标、过滤、排序 /Top-N、既有合法单指标聚合筛选；不以“基础六字段即可”替代覆盖。

## 4. 语义修订

history revision candidate在基础六字段delta之外带order_operation / limit_operation / aggregate_filter_operation / selection_operation；仅允许keep / set / clear，对应set时必须给完整新值，keep / clear时不接受夹带值。首轮conditions为完整对象，不接受keep。沿用现有同槽位替换 /不同槽位叠加 /明确维度替换规则；程序合并而非把模型整份previous直接当成功state。

- 未提排序 /数量时keep；“只看前20项”明确set row_limit=20且继承唯一可用排序。
- “取消前几名限制”clear row_limit；“不再排序”clear用户排序并按非排名默认展示顺序重新认证。保留row_limit却清空唯一排名次序无法认证时澄清，不任意选指标。
- “改成毛利”替换指标：只有原排序target是被替换的唯一指标且替换结果唯一，程序将排序target同步替换，direction /limit保留；多个候选目标须澄清。
- 更换维度 /实体选择使order target不存在，返回澄清要求明确新排序或取消排名，不保留悬空物理表达式。
- 聚合条件未提则keep，同指标槽位新条件替换；取消须明确clear；指标替换造成原聚合条件含义不清则澄清，不能自动把“销售额>100”换成“毛利>100”。

失败 /澄清不推进最后成功完整状态。成功持久化的state含程序合并后的完整条件，不仅是最新短问题 /delta。

## 5. SQL Guard 与成功证书

history profile在现有SQL Guard之后、业务数据库执行之前加入同一校验会话内的语义一致性检查；使用已有SQLGlot，不引入新解析库 /执行器。AST只用于核对当前候选与事先认证条件，不反向生成业务语义。

确定性检查：投影业务项 /公式 /distinct、实体选择、GROUP BY /时间粒度、完整行过滤与固定口径、聚合过滤、ORDER BY业务target /方向 /nulls /固定次级顺序、业务LIMIT。别名 /可证明等价的规范表达式可接受，额外谓词、错公式、错数量、漏排序或未表达的结果改变操作均SQL_REJECTED且数据库调用0次。无业务limit时拒绝模型自行加入业务LIMIT；取数截断仍由原executor的有界机制负责。不能宽松跳过未识别AST节点，也不能改写用户语义来迁就SQL。

现有单 /多指标、Join与危险函数检查继续，history检查不放宽旧Guard。合法SQL形态的业务等价性有明确转换白名单和回归证据；如果需要改变已确认业务范围才能处理，返回设计 /Spec，不把历史保存成“成功但不能恢复”。

执行返回的QuerySuccess新增末尾可选restoration_state，旧API serializer忽略；HistoryApplication要求其存在，并与公开数据一起5MiB检查 /原子提交。当前认证、SQL检查或编码失败保存受控失败轮次，保持上一成功状态，绝不提交没有完整状态的网页成功快照。

## 6. 验证与迁移

本阶段是设计，无代码或运行PASS证据。实施验证必须包含：

1. 首轮“按销售额降序前10个产品”→服务重启→“改成毛利”：完整时间 /筛选 /分组 /排序 /limit正确保留，换成唯一毛利排序；显式重查不调用理解旧问题。
2. 无排名、前200但返回100行、nulls /平局、时间绝对值跨天、实体distinct、单指标聚合条件、5指标排序等往返；保存成果删来源后仍完整重查。
3. wrong ORDER /LIMIT、额外WHERE /HAVING、错DISTINCT /公式 /时间 /grouping、不可认证target拒绝，下游数据库0次，原成功context不变。
4. 旧六字段parser /Prompt /默认Guard、Bearer API /三套正式Evaluation、旧静态替身构造保持；旧持久state不存在，不从内存或checkpoint伪造V1完整历史。
5. 相关发布定义改变拒绝；无关指标 /build ID /R2格式改变不误拒；技术性RAG不可用不伪装业务不兼容；R2移到同一维度binding后展示回归。

新增字段和profile是Expand，网页迁移是Migrate，旧API长期保留，无删除旧Contract的Contract阶段。状态版本未知安全拒绝执行；代码回滚保留历史 /成果表和字节，不伪造兼容旧版。Owner为当前主Agent，涉及新的业务定义 /额外SQL能力 /其他Provider则升级到用户决定。
