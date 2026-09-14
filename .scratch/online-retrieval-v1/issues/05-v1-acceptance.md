# 05: V1 回归、业务验收与文档状态同步

**What to build:**

完成 01～04 后，执行完整的 Software Test（软件测试）、AI Evaluation（AI 评估）和 Business Acceptance（业务验收），并同步项目文档，使文档、Spec、测试和实际实现保持一致。

**Blocked by:**

04

**Status:** open

## Acceptance criteria

- [ ] 正向场景通过：查询销售额；查询销售额和完成订单数；按客户类型分组查询销售额；按产品分组查询 2025 年销售额；查询客户名称。
- [ ] 拒答场景通过：缺少必要表、字段或指标；需要中间表或多跳 Join；日期关系不明确；指标不兼容；SQL Guard 失败。
- [ ] 技术失败场景返回正确状态：Qdrant/Embedding 失败、Asset Snapshot 版本不一致、LLM 超时、数据库超时。
- [ ] 空结果被识别为合法成功结果。
- [ ] 旧文档中与当前 Spec 冲突的行为被删除、合并修正，或改为指向当前 Spec。
- [ ] 评估报告可在本地生成，但不强制提交到 GitHub 或作为远程 Issue/PR 内容。
- [ ] 所有相关确定性测试和评估结果均有可复核证据。
- [ ] 完成 Diff Review、`git diff --check` 和 Secret 检查。
- [ ] 没有混入无关代码、文档或生成文件。

## Result

待实现。

## Comments

这是交付验收 Ticket，不提前实现新的业务能力；只有 01～04 的行为闭环完成后才执行。
