# 删除 Roadmap 与正式文档一致性审核

## 目标与授权

用户明确要求删除已无用途的 Roadmap，随后审核 docs/ 和根目录文档的正确性及其与项目实现的一致性；该指令构成本次小范围文档改动和只读审核的授权。不包含 Push / PR 授权。

## 范围与结果

- 删除 docs/roadmap.md，将原文原样保存在本工作项 history/roadmap.md，修复现行入口、规则、动态清单和历史 Markdown 链接；历史文本中的原路径保留其当时语义。
- 逐份审核根目录 Markdown 与 docs/**/*.md，对照源代码、配置、脚本和测试；报告文档错误、实现与已确认 Contract 的冲突及未验证项，不借审核改变产品 Contract 或实现。
- 修正删除 Roadmap 必需的规则；其他发现形成可追溯报告，不默认扩展为业务代码修复。

## 验收与验证

- 正式入口不再要求读取或更新 Roadmap；本地 Markdown 链接、结构和动态清单有效。
- docs/audits/documentation-audit-20261025.md 给出基线、每份文档的审核结论、发现证据与验证限制。
- 运行文档组合检查、git diff --check、动态清单相关确定性测试及本机状态检查；当前上下文执行 workflow-code-review 后本地 Commit。

## 基线与归属

BASE_SHA: 64d2eae；master 与 origin/master 同步，初始工作区干净。branch: docs/remove-roadmap-and-audit。初始 59 份本机记录检查无 ERROR / REVIEW；不涉及其他仓库状态写入。不修改运行时代码或用户配置。
