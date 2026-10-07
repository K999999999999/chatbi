# Harness 交付一致性修复：短 Spec

## 目标与授权

用户于 2026-10-07 在原因调查和修复建议后指示“开始修复”，授权当前记录收尾、工作项关联、本机只读检查、验证、Review 和本地 Commit。未授权 Push / PR 或 R6 实施。
基线：`3f24bbf2ac90da6d568053553bff67d916cfb6d0`；master 与远端一致，唯一 worktree，初始 clean。Branch：`fix/harness-delivery-consistency`。

## 范围与行为

- 补齐 R3 Ticket 06 / 状态的最终验收与 PR54 交付历史，保留 Candidate A / B 和报告身份；归档旧文档候选的工作记录，保留旧分支直到替代交付完成。旧路线图修改不直接搬入当前主干。
- 修正本机产品 V1 汇总当前字段，改为引用子工作项证据；关联 R3、R4、R5 与本修复。当前修复接手 R3 文档收尾，不扩展旧发布授权。
- 提供 `python -m scripts.check_harness_state` 本机只读入口，定位 Git common-dir（含 linked worktree），仅读取 `harness/work-items/*/status.md` 当前记录，不读取历史快照。支持文本 / JSON 输出。
- 可确定的错误：重复 / 缺失 ID 或 Status、ID 与目录不一致、非法状态、显式关联不存在、Active work item 指向已完成目标、已完成工作项显式声明的 Ticket 尚未完成、Ticket 引用越出仓库。错误退出 1。
- 待人工核对：未完成工作项、当前工作区修改、非当前 / 非 master 本地分支仍有 master 不可达提交；输出 REVIEW，不自动判为未合并（Squash 可导致不可达），不删除分支、不修改记录、不调用网络。单纯时间过期和旧文档关键词不判错。
- 正常 / 历史情况：新 clone 没有本机记录时明确报告检查范围缺失；正常历史快照忽略；明确暂缓候选仍呈现 REVIEW 及显式后续工作项，不作为 ERROR。
- 用可选的 `Related work items`、`Active work item`、`Follow-up work item`、`Ticket files` 明确同仓库关联。旧记录继续有效，不强制批量迁移。授权仍各自独立，不从关联推定授权。
- 会话恢复、交付收尾、新目标实施前执行检查；REVIEW 必须说明处置，ERROR 修复后才能宣称收尾完成。本机状态不进入 GitHub CI，工具的确定性测试进入既有测试套件。

## 验收与验证

真实临时 Git 仓库验证：R5 done / 汇总仍 active 报错；R3 待发布分支与后续引用呈现 REVIEW；done / Ticket in-progress 报错；正常关联、历史快照、linked worktree、新 clone、损坏字段与失败 Git 命令行为；检查前后内容 / Git 引用不变。
补账后真实仓库检查无 ERROR；待发布本修复与保留 R3 分支仍如实显示 REVIEW。Markdown 链接、Diff whitespace、代码格式 / lint 及当前上下文 Review。
不运行 AI Evaluation、浏览器或数据库：工具不改变产品行为 / Contract / 运行依赖。Roadmap 产品顺序 R6→R7 不变；Harness 规则和证据入口更新，不改写历史验收成绩。

Owned files：`scripts/check_harness_state.py`、`tests/scripts/test_check_harness_state.py`、`AGENTS.md`、`docs/agents/{issue-tracker,agent-harness,git-pr-workflow}.md`、`.scratch/history-results-v1/status.md`、`.scratch/history-results-v1/issues/06-runtime-acceptance.md`、本目录及本机关联记录。
Done When：补账与引用一致，工具正常 / 失败场景验证通过，旧候选证据归档，Review PASS、本地 Commit、实时进度同步；发布 / 旧分支删除另按获准交付执行。
