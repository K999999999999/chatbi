# 文档整理与门禁设计审查

Review: PASS。
首轮为 PASS WITH MINOR FIXES；下列实施细化已落实并核对，复核后可进入 Ticket 草案。
Review Target: [已确认 Spec](spec.md)、[处置清单](file-plan.md)、[实施设计](design.md)。
规划基线: `c7f7e74`；只读审查由当前主 Agent 执行，没有启动独立 Agent。

## 发现与处置

### F1：批量迁移需要逐项内容覆盖证据

Signal: 存在 Unknown Unknowns；仅列文件处置方向不能证明独有行为和历史取舍已保存。

Evidence: 57 份正式文档中，检索 Spec / Design 明确 Historical Record；当前唯一规则在 `.scratch/online-retrieval-v1/spec.md`。历史 ADR 与新历史能力的适用范围不同；Spec 要求不改变规则并保全独有证据。

Impact: 只修复链接可能让旧锚点指向含义不同的新章节，或删除仍有价值的约束，造成维护和验收依据丢失。

Recommendation: 以规划基线和本工作项迁移台账记录原章节、当前去向、独有历史内容与引用核对。每批闭环后才移除原入口。

处置: design.md 的“迁移依据与内容保全”明确了台账、顺序、停止条件和历史引用修复；不引入新的业务或全局注册表。

### F2：门禁解析与扫描范围需可测试

Signal: 结构规则与链接规则可能在代码围栏、行内代码及历史目录上出现不同解析行为。

Evidence: scripts/check_markdown_links.py 已独立处理围栏和 Setext 锚点，扫描 Git tracked / untracked 非 ignored Markdown；Spec 要求代码示例与历史记录不误报，CI 使用同一规则。

Impact: 两套解析或模糊的例外会造成误报 / 漏报，迫使提交者绕过门禁；替换旧入口还可能损坏既有脚本调用。

Recommendation: 保留旧链接入口，新增组合入口并共享最小解析；限定结构扫描的当前文件范围，固定退出码 / 行号 / fixture，迁移完成后接入原 CI job。

处置: design.md 明确 CLI 兼容、扫描范围、ATX / Setext、代码过滤、真实 Git fixture 和激活顺序；未增加依赖或改变 required check 名称。

## 总体判断

- 使用场景围绕当前规则可查、历史可追溯和持续维护，方案不改变业务模块或授权不变量。
- 当前 Spec 与历史来源边界清楚；代码与测试用于核对实现，不能反向改写已确认 Contract。
- 迁移影响包含全库 Markdown 消费者；每个切片包含引用修复与检查，无需修改运行服务、数据库或外部 PR 正文。
- 现有 Deterministic tests job 已调用 Markdown 检查，工具回归 seam 在 tests/scripts/，方案可离线验证。
- 结构门禁只承担可确定判断，语义与阅读质量纳入现有 Review，无额外用户审批流程。
- 依赖方向、Domain、SQL Safety 与产品支持范围不变；不会为文档维护建设平台、供应商或复杂抽象。

Reference: 已读 Architecture Knowledge Core，重点 §2 复杂度、§5 可观察行为、§7 可测试性、§8 迁移与选择、§9 防过度设计；已读 Migration and Large-Scale Change 的消费者发现、分批迁移、失败与恢复规则。此审查记录属于历史工作区，不受正式文档结构门禁约束。

Evidence Sources: AGENTS.md、Architecture / Product Scope / Roadmap、agents/issue-tracker.md、已确认 Spec 与处置清单、历史检索和多轮 / 经营分析规划位置、scripts/check_markdown_links.py、tests/scripts/ 现有检查测试入口、.github/workflows/ci.yml、PR 模板、当前 Git / 本机记录。

未执行业务测试、真实 LLM 或运行验收；本结论属于方案可实施性审查。

Next: 形成四项 Ticket 草案，当前上下文执行 Readiness，随后确认拆分与整体实施范围。
