# 检索快照、候选范围与直接关系

本文说明当前统一检索机制；业务限制和失败结果见 [检索Spec](../specs/online-retrieval.md)。旧BFS、多跳与独立多指标设计已归工作记录。

## 请求级资产身份

一次请求固定同一AssetSnapshot，TABLE、COLUMN、METRIC、关系图和Embedding身份不能混版。新发布指针在后续请求加载，本轮上下文不切换版本；加载失败不回退到静态全量Schema。

## 候选与必需资源

TABLE与可选METRIC检索并行，COLUMN随后限定在已召回表范围内；资源选择与组合由一条流水线处理。指标公式、固定条件、时间关系与明确分组所需字段只在候选范围内受限恢复。

TABLE候选池不意味着所有候选都必须连接。Join Key作为结构事实单独提供，不占普通COLUMN候选预算；不补入中间表扩大范围。

## 直接关系与上下文

指标数据源确定anchor_table；实体查询从列命中表与表分数确定主表。关系图只提供认证直接FK→PK；多日期关系按指标time_field或明确语义选择。无法唯一认证时拒答，不让模型发明连接。

上下文同时携带最小Prompt内容与程序可用的认证指标 / 字段 / Join事实。程序不从Prompt文本恢复认证身份，模型不接收完整Schema、关系图或行数据。

## 代码定位

- [检索入口](../../src/online_query/retrieval/retrieval.py)、[流水线](../../src/online_query/retrieval/retrieval_pipeline.py)：统一编排。
- [资产运行时](../../src/online_query/retrieval/rag_runtime.py)：发布版本加载与校验。
- [资源召回](../../src/online_query/retrieval/resource_retrieval.py)、[关系图](../../src/online_query/retrieval/relationship_graph.py)：候选范围与直接关系。
- [上下文](../../src/online_query/retrieval/retrieval_context.py)：认证事实与最小生成上下文。

技术失败与业务候选不足按Spec分别返回，任何失败都不能触发未经认证的SQL执行。
