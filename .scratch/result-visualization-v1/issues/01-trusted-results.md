# 01 可信单值结果说明与数字展示

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


Status: in-progress
Canonical Source: ../spec.md、../design.md
Authorization: 用户已确认四项拆分及全目标本地实现、验证、Review和Commit；未授权发布

## Result

实现与确定性验证完成，Code Review PASS；待本地代码候选及04实际容器clean验收绑定。

证据：软件641 passed /15 skipped /139 subtests，Chrome32 passed / Vite1 passed；R2公共Contract、Design、Query API、Runbook、README及roadmap已同步。

## Comments

按01→02→03→04连续完成。
