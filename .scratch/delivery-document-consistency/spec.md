# 交付文档一致性修复：短 Spec

## 目标与授权

用户核实 R2 交付文档与 Harness 漏检后指示“开始修复”，授权当前事实与交付一致性检查修复、验证、Review 和本地 Commit。未授权 Push / PR；不实施 R3 或缓存优化。
基线：`1f57c9b4468d282e015299479cccc70fa07455a2`；开始时 master 与 origin/master 一致、唯一 worktree、工作区干净。Branch：`docs/delivery-document-consistency`。

## 范围与预期结果

Owned files：`docs/roadmap.md`、`docs/product-scope.md`、`docs/agents/agent-harness.md`、`docs/agents/git-pr-workflow.md`、`.github/pull_request_template.md`、本文件。
本机实时记录：Git 公共目录中本工作项及 `chatbi-product-v1`、`result-visualization-v1` 的 status.md，不纳入 Commit；更新前读取并保存旧记录到同目录历史文件。

- 路线图明确 R1 / R2 已合并、R3 待澄清；当前能力与不包含范围不再把已交付图表写成未来能力。
- 产品范围与正式 R2 Spec 一致，保留同步 HTTP、无长期历史 / 流式 / 导出等边界。
- 交付检查覆盖需求状态、当前能力、不包含 / 后续范围的一致性；合并后同步主记录及关联实时记录顶部当前字段。
- PR 模板记录具体核对位置与结果；链接检查不能代替语义一致性验证。
- 日期化验收与 Evaluation 身份保持不变，不将旧候选证据重标为 merge commit 结果。

## 验收与验证

核实相关 PR 合并身份；人工对照路线图、产品范围、R2 Spec 和实时记录；运行 Markdown 本地链接检查与 git diff --check；按 workflow-code-review 在当前上下文只读 Review。
纯文档，无行为、依赖、数据或权限变化，不运行 Software Test、AI Evaluation 或真实 E2E。
Done When：受影响文档和实时字段一致，检查与 Review PASS，形成本地 Commit；远端发布另需授权。

## Harness 缺口与修复

类别：事实源 / 反馈。证据：PR51 已勾选 roadmap 同步，但 roadmap 当前能力与 product-scope 不包含清单仍排除图表；主实时记录顶部仍称 R2 未授权发布，末尾却称已合并。新增完成事实与追加收尾没有替换旧的当前描述，Review / 合并复盘漏检。
机制：在 Harness 维护说明、候选 / 合并检查与 PR 模板列明核对位置和当前字段更新要求。本工作项就是该缺口的改进记录，不重复创建远端 Issue。

## 验证与 Review 结果

适用基线：`1f57c9b4468d282e015299479cccc70fa07455a2`；范围为本短 Spec 的六个文件及三份 Git 公共目录实时记录。

| 核对位置 | 结果 |
| --- | --- |
| roadmap 当前阶段、阶段表及 R1 / R2 / R3 需求行 | PR49 / PR51 已合并，R3 待澄清；与本轮 GitHub 只读查询和本地基线一致 |
| roadmap 当前 MVP 能力边界 | R2 图表 / 可信说明列入已支持；SSE / 历史 / 导出仍属后续 |
| product-scope 当前不包含与 R2 结果展示 | 已移除图表排除项，与正式 R2 Spec 一致；不改变同步 HTTP / 数据范围 |
| Harness 路线图维护、候选 / 合并检查、PR 模板 | 都要求核对当前描述及具体结果；明确链接检查不能代替语义检查 |
| chatbi-product-v1 / result-visualization-v1 实时记录 | 顶部阶段、PR、授权引用、停点、下一步与交付一致；旧记录保存为历史快照，R2 Status 修正为规定的 done |

`uv run --locked python -m scripts.check_markdown_links`：PASS。
`git diff --check`：PASS。
当前上下文 `workflow-code-review`：PASS；Diff 范围、正确性、可理解性、状态一致性、授权与证据边界均通过；无待修复发现。
本次不修改正式业务 Spec / Design、Runbook 或日期化 Acceptance：产品行为及运行方式未变；验收证据由本记录承担，不改写历史报告。路线图已同步完成事实与当前边界，未重排优先级。
Software Test / AI Evaluation / Real E2E 未运行：纯文档改动，无相应行为变化。未执行远端发布或 CI。
本次已修复有证据的事实源 / 反馈缺口；未观察到其他符合门槛的新 Harness 缺口。
