# 检索模型首次加载与安全故障诊断


- Change Profile: 中高风险；模型资源与第三方错误边界；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD010、AUD018。
- Blocked by: None (can start immediately)
- owned files: src/rag_offline/embedding.py；src/rag_offline/qdrant_store.py；src/online_query/retrieval/retrieval_resource_stage.py；src/online_query/service.py（仅必要错误传播收口）；tests/rag_offline/test_embedding.py；tests/rag_offline/test_qdrant_store.py；相关retrieval/service测试；docs/designs/rag-offline-build.md（同步本地快照规则）。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

在provider内保护首次加载并保留重试能力；Qdrant异常输出只含安全阶段/类型，不拼接原URL或敏感异常。

### Acceptance criteria

1. 同provider多线程同步首次调用只构造一个成功实例，已加载路径复用；构造失败释放锁，后续调用可恢复。
2. 不对所有推理强加全局串行锁，不改变模型配置、revision或RAG身份。
3. 带合成userinfo、敏感查询参数、API Key和异常canary的故障在最终服务日志和公开错误中均不含canary；安全诊断仍可识别阶段/类别。

### 验证证据

Barrier/Event控制构造并发计数及失败恢复；捕获最终日志链核对合成canary；真实BGE加载由后续隔离评测验证。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

Status: completed
Result: `BgeM3EmbeddingProvider` 现在以实例级双重检查锁保护首次模型构造；失败会释放锁供后续重试，已加载模型的推理不受该锁串行化。Qdrant 连接、集合读写、检索（含旧版 `search` 回退）和关闭失败只暴露静态阶段与异常类型，并抑制第三方异常链。在线检索服务日志和公开错误通过 canary 集成测试验证未泄漏 URL userinfo、查询参数、API Key 或原异常正文。设计文档同步为仅加载 `prepare-model` 准备的本地固定 revision 快照，缺失时 fail-closed。
Comments: 实现Commit `066e2b2 fix(rag): 串行化BGE首次加载并脱敏Qdrant异常`；候选定向 Python 测试 32 passed / 0 skipped（`20261016T190428Z-066e2b2-test-python-fdc989378278`）；完整 Python 测试步骤 1052 passed / 57 条件性 skipped / 0 failed（`20261016T190445Z-066e2b2-test-python-1e82a5932aae`，报告因 skip 标为 incomplete）；`./dev check python`（`20261016T190456Z-066e2b2-check-python-709e21ef4410`）、`./dev check docs`（`20261016T190456Z-066e2b2-check-docs-f40baad43b90`）、Diff 检查和Review均通过，报告 provenance stable。真实 BGE 模型加载由后续隔离评测验证；仅完成Ticket 06，不代表整体审计修复目标完成。
