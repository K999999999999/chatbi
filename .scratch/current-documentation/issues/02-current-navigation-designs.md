# Ticket 02：README、架构与实现说明形成连贯阅读路径

Status: open
Canonical Source: [Spec](../spec.md)、[设计](../design.md)；用户已确认四项拆分与整体本地实施。

Change Profile: 持续维护导航与机制文档 / 中等批量迁移 / 导航与重要机制遗漏风险 / 阅读走查与引用 / 本地候选。
Owner: 当前主 Agent。
Blocked by: 01。

### What to build

- README 承接项目简介、开始入口、简短代码地图和当前文档导航，合并 project-guide 有效定位能力。
- 当前架构集中描述模块、依赖、链路、数据归属和关键约束；产品范围按能力描述支持与限制。
- 按处置清单逐份核对 15 份 Design；仅保留独有重要机制，重复说明引用正式 Spec，开发方案和历史结果归工作记录。
- 将历史检索设计、多指标独立设计和无独立价值的细碎说明归档；保留事务、worker / SSE、备份恢复、SQL Guard、Trace 与资产发布的必要当前机制。
- 原 guide 独立入口移除前提供完整替代导航，修复全库当前及历史消费者，更新台账。

### Acceptance criteria

1. README 直接定位当前产品、架构、主要模块、核心能力、运行和验证入口，没有独立 project-guide 阅读入口。
2. 架构和产品范围不重复功能细则和开发日志；系统定位、依赖方向、业务语义链路与支持边界完整。
3. 每个 Design 的保留 / 合并 / 归档都有内容依据；没有重要机制仅留在未说明用途的历史文件。
4. 所有当前内容层级连贯、章节具名引用；正文补充已融入相应主题，不在尾部堆阶段追加。
5. README → 能力 / 模块 → 当前规则 / 机制的阅读走查通过，全库链接检查通过。

owned files: README.md；docs/project-guide.md、architecture.md、product-scope.md；docs/designs/ 现有 15 份；必要受影响引用与所属 .scratch 归档；迁移台账。Spec 仅在核对中发现需要落位已有规则时做一致性补充并复核前项证据。

验证证据: 全库 Markdown 链接检查；`git diff --check`；导航与核心链路只读走查；当前重要机制覆盖 Review。代码入口以存在的路径和符号核对，不执行业务命令。

Migration / Rollback: 先提供新的当前入口与机制说明，再修复链接并移除旧稿；恢复时同时恢复当前 / 历史引用。无代码、模型、数据或运行资源迁移。

Done When: 导航唯一且可达、产品 / 架构职责清晰、15 份设计逐项核对完成、台账和验证更新。


## Result

待实施与验证。

## Comments

发布尚未授权；本目标按依赖连续完成。
