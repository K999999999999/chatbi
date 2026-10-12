# Ticket 01：当前功能行为形成唯一正式入口

Status: done
Canonical Source: [Spec](../spec.md)、[设计](../design.md)；用户已确认四项拆分与整体本地实施。

Change Profile: 持续维护文档 / 中等跨文件迁移 / 行为依据丢失风险 / 链接检查与内容覆盖 Review / 本地候选。
Owner: 当前主 Agent。
Blocked by: None。

### What to build

- 核对现有正式 Spec 与已确认的检索、多轮、经营分析来源；按能力整理当前行为、边界与验收标准。
- 用当前统一检索 Contract 替换历史 online-retrieval 正文；多指标现行规则融入同一入口，旧规格和独有决定归对应历史记录。
- 将已交付经营分析未正式固化的规则集中落入当前 Spec；将短期多轮规则整合至当前 Query API 说明，明确与持久历史的适用边界。
- 清理全部现有正式 Spec 的旧发布状态、开发任务和阶段日志；不改变输入输出、失败、授权、兼容及 SQL Guard 规则。
- 将功能阶段多轮 ADR 的独有理由 / 取舍归入对应工作记录；按迁移顺序修复所有引用。
- 建立本工作项迁移台账，逐项记录当前规则去向、历史覆盖与保存位置。

### Acceptance criteria

1. 每个当前功能规则有正式位置；查询、检索、多轮和经营分析不再将历史规划视为当前唯一 Contract。
2. 实体 / 单指标 / 多指标使用已确认的一条检索链；指标数量、直接 FK→PK、LEFT JOIN 等边界不被历史描述覆盖。
3. 短期 API 会话与长期历史续聊的状态、失败与逐轮授权边界保持正确，不把历史 ADR 限制泛化到新历史能力。
4. 所有重写 / 移除文档具备台账覆盖证据；独有理由和历史候选结论可追溯。
5. 所有 Markdown 消费者的受影响链接修复，全库链接检查通过；当前重要规则逐项 Review 通过。

owned files: docs/specs/ 全部现有文件、按覆盖需要新增经营分析当前 Spec；docs/adr/0001-multi-turn-query-v1-boundaries.md；对应 .scratch 来源的历史用途 / 归档与受影响引用；migration-ledger.md。其他当前文档只做必要引用修复，主要内容由后续切片负责。

验证证据: `uv run --python 3.11 --locked python -m scripts.check_markdown_links`；`git diff --check`；以规划基线和后续已确认扩展为依据的章节 / 规则覆盖 Review，记录候选或未提交范围。

Migration / Rollback: 先保全独有内容再提供现行说明、修复消费者、移除旧入口；覆盖不明不删除。恢复文档须同时恢复对应链接，不 reset 用户修改或删掉唯一历史副本。

Done When: 当前规则统一、台账完整、引用与语义 Review 通过、本地候选证据记录；不以历史测试结果替代本次文档核对。


## Result

当前Spec固化、旧规格/功能ADR归档与引用修复完成；全库Markdown链接和Diff检查通过。语义/边界核对见 [Review](../review-01.md)，内容去向见 [台账](../migration-ledger.md)。验证适用于基线c7f7e74到本Ticket提交的全部文档改动；未运行业务/LLM验收。

## Comments

发布尚未授权；本目标按依赖连续完成。
