# Domain 文档

本文档只记录本仓库的领域文档位置和读取边界；领域术语的澄清、Glossary 维护和 ADR 判断由 `domain-modeling` 负责。

## 读取顺序

处理领域相关任务前，读取与当前主题相关的：

1. `AGENTS.md`；
2. `CONTEXT-MAP.md`（如果存在）；
3. 对应的 `CONTEXT.md`（如果存在）；
4. `docs/adr/` 下的相关 ADR（如果存在）；
5. `docs/product-scope.md`、`docs/architecture.md`、相关 Spec、Design、测试和验收记录。

文件或目录不存在时静默继续，不要为了补齐结构而创建空的 `CONTEXT.md`、`CONTEXT-MAP.md` 或 ADR。只有在真实领域术语被确认，或不可逆且存在实际权衡的决策被确认时，才按 `domain-modeling` 的规则按需创建。

## 领域文档边界

- `CONTEXT.md` 只记录 ChatBI 已确认的领域词汇、定义、同义词和边界，不记录实现细节、数据库表、接口路径、测试步骤或临时讨论。
- `docs/adr/` 只记录已确认的、难以逆转且存在真实取舍的长期决策，重点说明决定和原因。
- `docs/specs/` 记录功能行为和验收 Contract；不要把 Feature Spec 写进 `CONTEXT.md`。
- `docs/designs/` 记录如何实现已确认的 Contract；不要用 Implementation Design 反向改写领域事实。

## 术语冲突

如果用户说法、代码、文档或已有领域定义不一致，先明确区分：

- 已确认的领域事实；
- 当前实现事实；
- 用户希望实现的目标；
- 尚未确认的假设。

不得默默用同义词替换已确认术语，也不得把旧代码或模型推测当成业务真相。发现与 ADR 冲突时，明确指出冲突及其影响，等待重新确认。
