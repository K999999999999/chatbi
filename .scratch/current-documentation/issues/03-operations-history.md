# Ticket 03：操作手册清楚可用，历史验收回到工作记录

Status: complete
Canonical Source: [Spec](../spec.md)、[设计](../design.md)；用户已确认四项拆分与整体本地实施。

Change Profile: 持续维护运行文档与历史证据 / 中等批量迁移 / 操作前提或证据身份遗漏风险 / 命令核对与历史保全 Review / 本地候选。
Owner: 当前主 Agent。
Blocked by: 02。

### What to build

- 按开发初始化、日常开发、宿主调试、Stable、测试 / Evaluation、排障和恢复组织 Runbook，保留环境前提与数据操作影响。
- 替换章节符号和裸编号引用为具名链接，修复旧数字锚点的全部消费者。
- 将 16 份 Acceptance 逐份核对已有工作记录后归档；保留独有环境、候选、失败 / 复验、结论与限制，不移动原始报告。
- 现行验收标准指向 Spec，验证方法指向 Runbook，必要历史证据索引简短明确其适用候选。
- Roadmap 精简为当前阶段与已确认未来方向，历史推进归所属记录；不重新排优先级或生成新承诺。

### Acceptance criteria

1. 读者可从 Runbook 独立选择容器开发、宿主调试或 Stable 路径；不会把一个环境的命令用于另一环境。
2. 测试命令的 uv / Python 版本、锁定依赖、Origin 临时覆盖原因明确；纯软件、PG 集成与真实 LLM 证据边界完整。
3. 备份 / 恢复、资源隔离、迁移 / 重置、Secret、当前配置限制等必要前提仍在对应步骤附近。
4. 16 份历史验收均有完整覆盖或归档证明，日期、候选、报告位置、结论不被当前身份替换；现行文档不再堆历次结果。
5. Roadmap 只保留当前与未来方向；所有受影响引用修复，台账和全库链接检查通过。

owned files: docs/runbook.md、roadmap.md、acceptance/ 全部 16 份；README / 其他文档中相关引用与所属 .scratch 归档；迁移台账。

验证证据: `uv run --python 3.11 --locked python -m scripts.check_markdown_links` 通过；`git diff --check` 通过；Runbook 命令与当前脚本入口只读核对；16份迁移原文、候选身份与全库引用核对；阅读走查；Review见 [review-03.md](../review-03.md)。未执行重置、部署、恢复或真实LLM调用。

Migration / Rollback: 先保全证据再迁移当前说明；锚点含义逐项匹配，不能统一替换成含义不符的入口。候选不变、原始报告不移动；恢复时同批恢复引用和历史文件。

Done When: 操作路径连贯、必要前提完整、历史验收覆盖与身份证明完整、当前 / 历史索引可达、Roadmap 核对有记录。


## Result

已完成。Runbook按环境入口、初始化、日常服务、检索资产、测试 / Evaluation、排障、Web验证和Stable保障组织；宿主纯软件回归命令、Python 3.11 / uv锁定方式与临时Origin覆盖原因保留在测试步骤。移除R1–R7过程状态与候选验收流水，明确软件测试、PG集成、真实LLM评测和运行验收的证据边界。Roadmap只列交付阶段概况、最后记录的Stable核验和“当前无已确认排期目标”；16份Acceptance完整归入所属 `.scratch` 历史并修复其引用，原始ignored报告未移动。

## Comments

发布尚未授权；本目标按依赖连续完成。
