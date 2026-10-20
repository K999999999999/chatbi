# 项目全景详解短 Spec

## 目标与授权

用户在本会话明确要求一份全面、详细、可独立阅读的项目讲解文档，解释整个项目思路，并建立业务、系统架构模块与目录文件之间的关系。该指令构成本次纯文档工作的实施授权；不包含 Push / PR 授权。

基线：`baseline-20261020` / `fa5dd6edbace8b866ddacbf1a9a50133d77d3468`。开始时 `master == origin/master`，工作区干净，57 条本机工作记录无 Harness findings；55 项 done、2 项 cancelled。

## 范围与预期结果

- 新增 `docs/project-explained.md`，从业务目标与具体问题讲起，覆盖产品能力、设计原则、逻辑架构、数据与语义、在线问数、RAG 在线 / 离线、多轮与恢复、经营分析、身份权限、历史成果、执行与取消、展示导出、Bootstrap / 诊断、物理目录、代码阅读路径、运行和验证、当前边界与术语。
- 同一篇文档内提供连贯解释、示例、图示和职责 / 路径映射；外链用于核对和深入，不作为理解主线的必要条件。
- 讲解内容以当前 Architecture、Product Scope、正式 Specs / Designs 与核实后的关键源码为依据；概括行为并解释目的，不另立或逐条复制完整 Contract，不承诺新能力。
- README 增加长文入口；文档维护规则登记其教学说明职责和事实源关系。
- 保留现有正式文档和所有历史资料；已冻结 Git tag 保持原指向。

Owned files：`docs/project-explained.md`、`README.md`、`docs/agents/documentation.md`、`.scratch/project-explained/spec.md`、`.scratch/project-explained/status.md`。

## 验收与验证

1. 单篇可从“为什么做”读到“怎样实现和验证”，说明目录、逻辑职责、调用链与部署组件的区别。
2. 当前一级能力和工程子系统均有解释、主要代码入口与对应事实源；包含完整问数及经营分析示例，说明失败、权限和状态边界。
3. 所有关键代码路径存在，术语和主要流程与当前事实源一致；正文清楚区分教学示例、当前能力与范围外事项。
4. 执行 Markdown 链接 / 结构组合检查、`git diff --check`、当前上下文的文档 Code Review 和本机 Harness 核对。
5. 纯文档改动不运行业务软件测试、真实 LLM 评测或部署验收；历史结果不冒称本次候选的新结果。
6. 复核动态文档清单与 Roadmap，记录更新位置或不适用理由；验证与 Review 通过后只创建本地中文 Commit。

## 文档归属

此前 `docs/project-guide.md` 已在文档整理目标中并入 README；本次不恢复第二个导航总入口，而是按用户新授权新增一份系统教学长文。README 仍是总入口，Architecture / Product Scope / Specs / Runbook 仍分别定义结构、范围、行为与操作；本长文负责解释它们如何组成一个完整项目。
