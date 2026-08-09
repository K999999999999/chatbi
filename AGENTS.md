# AGENTS.md

# ChatBI AI 开发指南

本文件用于约束 Codex / AI Coding Agent 在本仓库中的开发行为。

它不是架构文档、业务需求文档，也不记录当前开发进度。

具体内容分别以对应 Source of Truth 为准。

## 1. 项目定位

ChatBI 定位：

```
ChatBI = Domain AI Engine Service
内部架构 = Modular Monolith
```

总体开发原则：

```
业务正确
↓
完整业务闭环
↓
测试与 Evaluation
↓
可维护
↓
工程化
↓
Production Readiness
↓
Platform Integration
```

始终优先完成当前 Feature 的最小正确业务闭环。

不要提前建设当前 Feature 不需要的复杂平台能力。

## 2. Source of Truth

开发时按照以下职责理解资料：

```
ARCHITECTURE
= 稳定架构骨架、边界和不变量

ENGINEERING_RULES
= 长期工程规则与演进边界

Domain / Topic
= 业务事实、业务口径和业务规则

Feature Spec
= 当前具体做什么、拒绝什么、如何验收

Code
= Feature Spec 的实现

Tests / Evaluation
= 证明实现是否正确
```

通常按照以下顺序理解约束：

```
docs/ARCHITECTURE.md
↓
docs/ENGINEERING_RULES.md
↓
相关 Domain / Topic
↓
当前 Feature Spec
↓
相关代码
↓
相关 Tests / Evaluation
```

不要使用历史代码反向修改已经确认的架构不变量或业务事实。

## 3. 开发流程

默认采用：

```
Domain
↓
Feature Spec
↓
Task Breakdown
↓
Implement One Task
↓
Tests
↓
Evaluation（适用时）
↓
Review Diff
↓
Commit
```

Feature 开发前，应先明确：

```
为什么做
做什么
不做什么
输入是什么
正常行为是什么
什么时候 Clarify / Reject / Deny
输出是什么
如何验收
```

一次只实现一个可独立验证的 Task。

不要在同一个 Task 中混入无关的新功能、重构和清理工作。

## 4. Architecture Freeze

`docs/ARCHITECTURE.md` 是稳定架构基线。

普通 Feature 开发默认不修改 Architecture。

只有真正改变以下内容时，才重新讨论架构：

```
系统定位或 Owner 边界
核心业务链
核心对象稳定含义
模块职责
分层或依赖方向
安全 / 正确性 / 状态不变量
外部 Contract 边界
```

以下变化通常不属于架构变化：

```
增加指标或维度
增加业务规则
增加 Feature
修改 Prompt
更换模型
调整 Retrieval
新增 SQL Guard Rule
增加测试
修复 Bad Case
UI 修改
配置修改
数据库物理字段变化
局部代码重构
```

如果实现与 Architecture 冲突，不要直接修改 Architecture 来迁就代码。

先检查实现是否违反了已有边界。

## 5. 分层与依赖

稳定依赖方向：

```
Interfaces
↓
Application
↓
Domain
```

外部技术实现位于系统边缘：

```
Application
↓
Port / Contract
↑
Infrastructure Adapter
```

Bootstrap 负责装配具体实现。

不要为了目录整齐提前创建大量空层、空 Interface 或空 Adapter。

目录应随着真实 Feature 自然形成。

## 6. 各层职责

### Domain

Domain 保存稳定业务含义，例如：

```
业务对象
Value Object
SemanticQuery
Metric
Dimension
Filter
TimeRange
Grain
业务规则
业务校验
领域授权规则
```

Domain 不得依赖具体技术实现，例如：

```
LLM SDK
数据库 SDK
Redis
FastAPI
Streamlit
Higress
Keycloak
Langfuse
向量数据库 SDK
平台 SDK
```

Domain 应尽可能能够在没有网络、数据库和模型服务的情况下测试。

### Application

Application 负责：

```
Use Case
Workflow
业务步骤编排
路由
分支
状态流转
调用 Domain
调用外部能力
有限恢复
```

Application 可以知道“需要什么能力”，但不应知道“具体供应商如何实现”。

不得写死：

```
Provider URL
API Key
数据库密码
供应商 Header
平台专属协议
```

### Interfaces

Interfaces 包括：

```
HTTP
CLI
UI
其他外部入口
```

只负责：

```
接收输入
协议转换
调用 Application
返回 / 展示结果
```

不得承载完整业务流程。

### Infrastructure

Infrastructure 负责可替换技术实现，例如：

```
模型调用
数据库访问
Retrieval
文件读取
State Storage
SQL AST
Telemetry
Audit
平台 Adapter
```

Infrastructure 不定义业务真相。

## 7. 业务语义与物理实现分离

业务世界：

```
Metric
Dimension
Filter
TimeRange
Grain
SemanticQuery
```

数据库世界：

```
Schema
Table
Column
Join
SQL
Connection
```

必须保持：

```
Natural Language
↓
Business Semantic Resolution
↓
SemanticQuery
↓
Certified Data Mapping
↓
Physical Query / SQL
```

不要直接：

```
Natural Language
↓
Database Field
```

`SemanticQuery` 不应包含：

```
数据库连接
物理表名
物理列名
SQL 字符串
```

物理数据结构变化，不应迫使业务语义和上层 Workflow 重写。

## 8. Model 与确定性规则

核心原则：

> **Model proposes, program decides.**

模型可以参与：

```
自然语言理解
结构化候选生成
语义候选生成
歧义识别
SQL Candidate 生成
有限修复
结果解释
```

模型输出始终视为不可信候选。

模型不得最终决定：

```
业务口径
业务规则
Domain Authorization
Data Scope
SQL 安全
权限放行
```

这些必须由权威业务资料和确定性代码裁决。

Prompt 不能成为权限或安全的唯一保护措施。

## 9. SQL 与数据访问

模型生成的 SQL Candidate 不得直接执行。

必须经过确定性 SQL Guard。

根据当前 Feature，SQL Guard 应落实适用的约束，例如：

```
只允许查询
禁止 DDL / DML
禁止多语句
限制认证数据源
限制字段
限制 SELECT *
限制结果行数
落实 Data Scope
只读数据库访问
```

数据库访问细节必须限制在 Infrastructure / Adapter 边界。

## 10. Authentication 与 Authorization

必须区分：

```
Authentication
≠
Domain Authorization
```

外部身份系统负责：

```
你是谁
```

ChatBI 负责：

```
你能使用什么业务能力
你能访问什么 Topic
你能访问哪些 Metric / Dimension
你能访问什么 Data Scope
你能否访问敏感或明细数据
```

外部身份通过 `PrincipalContext` 进入。

ChatBI 的业务访问边界通过 `DomainAccessContext` 表达。

不要把具体企业 Role 名称直接写死成业务规则。

保持：

```
REJECT
= 当前业务能力本身不支持

DENY
= 业务能力存在，但当前主体无权访问
```

## 11. State

不要因为架构中存在 `EngineExecutionState` 就提前建设完整状态平台。

只有当前 Feature 真正需要：

```
连续追问
跨请求上下文
Clarification Resume
Checkpoint
中断恢复
Durable Execution
```

时，再增加对应 State 能力。

如果存在可修改的跨请求 Thread State：

```
同一 Thread
→ 保持业务顺序

不同 Thread
→ 可以独立并发
```

需要跨进程、重启恢复或多实例共享的权威状态，不得只保存在单进程内存。

## 12. 抽象原则

不要为了“以后可能需要”就提前创建：

```
大量 Interface
大量 Adapter
Plugin Manager
Provider Registry
Abstract Factory
复杂 Framework Wrapper
```

通常只有以下情况才值得建立抽象：

```
已经存在多个真实实现

或

某个实现明确即将被替换

或

不建立边界会让具体技术污染业务核心
```

否则：

> **保持简单。**

Architecture 中存在 Contract，不代表现在必须全部实现为 Python `ABC`、`Protocol` 或 Interface Class。

## 13. 配置与 Secret

`.env` 属于本地敏感配置，不得提交。

真实：

```
API Key
数据库密码
连接字符串
Provider Secret
Token
```

不得进入：

```
源码
文档
测试数据
日志
Prompt 示例
Commit
```

使用：

```
.env
→ 本地真实配置

.env.example
→ 可提交的安全模板
```

配置统一通过：

```
Settings
Environment
Config
```

进入系统。

不要在业务代码中写死运行环境配置。

## 14. 测试与 Evaluation

质量证据分为三层：

```
Software Tests
→ 证明确定性软件行为正确

AI Evaluation
→ 证明模型辅助行为正确

Business Acceptance
→ 证明真实业务需求得到满足
```

不要混淆三者。

开发行为时同步增加或调整相关测试。

适用时覆盖：

```
SUCCESS
CLARIFY
REJECT
DENY
FAILED
```

AI Feature 不能因为一个 Demo 成功就认为完成。

发现新的 Bad Case 后，应加入回归集合。

## 15. 代码原则

优先使用明确的业务命名。

例如：

```
SemanticQuery
QueryResult
DomainAccessContext
TrustedQueryUseCase
BusinessDataSource
```

避免没有明确职责的大型通用模块，例如：

```
utils.py
helpers.py
common.py
manager.py
```

除非它确实代表一个单一、清晰的职责。

保持模块小而清晰。

一个模块最好能够用一句话说明自己的职责。

不要为了面向对象而创建没有实际意义的 Class。

## 16. 注释原则

注释重点解释：

```
这个文件 / 函数负责什么
为什么这样设计
保护什么业务规则或边界
输入和输出是什么
什么情况下失败
为什么存在某个非显然判断
```

不要大量添加只是重复代码语法的注释。

业务规则应解释“为什么”，而不仅仅是“做了什么”。

## 17. 开发命令

只记录仓库中真实存在、可以执行的命令。

当项目工具链建立后，在这里维护：

```
依赖安装 / 同步
Format
Lint
Type Check
Unit Test
Acceptance Test
AI Evaluation
本地运行
```

工具链发生变化时，同步更新本节。

不要编造仓库中尚不存在的命令。

## 18. 完成任务前检查

完成一个 Task 前检查：

```
是否满足当前 Feature Spec

是否违反 Architecture

业务规则是否位于正确层

外部技术是否污染核心

是否加入必要测试

Evaluation 是否适用并完成

是否发现新的 Bad Case

是否包含无关修改

是否泄露 Secret

文档是否只修改了真正发生变化的 Source of Truth
```

只修改当前 Task 真正需要修改的内容。

## 19. Always / Ask First / Never

### Always

```
遵守当前 Feature Spec
保持 Architecture 不变量
业务语义放在正确位置
外部技术保持在系统边缘
实现行为同步测试
模型输出视为不可信候选
SQL 安全使用确定性机制
保护 Secret
优先最小正确实现
```

### Ask First

在主动改变以下内容前先确认：

```
系统边界
核心业务链
核心对象稳定语义
分层或依赖方向
业务 Source of Truth
已经稳定的公共 Contract
安全或权限不变量
```

### Never

```
为了迁就实现偷偷修改 Architecture

把核心业务规则塞进 UI / API Handler

让 Domain 依赖 Provider / Database / Platform SDK

让 LLM 绕过业务校验、权限或 SQL Guard

直接执行未经 Guard 的模型生成 SQL

提交 .env 或真实 Secret

为假设中的未来需求提前建设复杂平台

为了抽象而抽象

没有相应验证就声明 Feature 完成
```

# 最终规则

```
Architecture
= 系统不能怎么乱长

Engineering Rules
= 开发过程中必须守住什么边界

Domain
= 业务事实是什么

Feature Spec
= 当前具体做什么

Code
= 实现 Spec

Tests / Evaluation
= 证明实现正确
```

始终遵循：

> **先完成当前 Feature 的最小正确业务闭环，再根据真实需求增加复杂度。**

以及：

> **Stable Core, Replaceable Edge.**
