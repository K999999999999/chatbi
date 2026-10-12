# 在线查询与 SQL 安全：整理前的过程记录

来源：`docs/specs/online-query.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 整理前入口说明

# Online Query Module Spec

状态：当前 Online Query 已接入并通过 Online Retrieval V1（在线检索 V1）验收。Online Retrieval 的当前行为以 [V1 Feature Contract（V1 功能契约）](../../online-retrieval-v1/spec.md) 为准；本文继续负责 Online Query 的输入、输出、执行和错误边界。

## 实现设计阶段再决定

- 代码目录和文件落位。
- 节点 Typed Contract（类型契约）。
- LangChain 模型类、模型名称和 Provider 配置。
- SQL 解析库和 SQL Guard 的具体算法。
- 数据库连接和超时的具体实现方式。
- 单元测试文件和 Task 拆分。
