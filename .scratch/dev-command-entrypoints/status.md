# dev分类入口与本机管理员恢复

Status: 本地实现、验证与Review完成；远端未授权
Work item: dev-command-entrypoints
Baseline: master@38e1302ce33d999dc908419067bc5d39195f86cf
Branch / Worktree: feat/dev-command-entrypoints；/home/jojo/Projects/chatbi-dev-tools

## 当前结论

用户确认完整Spec、Design Review PASS和七项Ticket拆分，授权全部本地实现、验证与Commit。七项实现完成，范围及验证见[验收记录](acceptance.md)与[Code Review](code-review.md)。精确提交及当前阶段以Git公共目录harness/work-items/dev-command-entrypoints/status.md为准。

本目标未Push、未创建PR，不接管旧Stable/Restore、不操作日常管理员或数据卷、不执行真实LLM验收。原工作区container-auto-restart@fd9be30保留为独立候选。

## 文档与历史

当前事实源同步README、Runbook、Bootstrap/开发容器/标准应用Contract与新增管理员恢复Contract；Architecture/Product Scope只补已确认恢复边界。Roadmap更新本地实现事实，没有调整优先级或声称远端完成。

[盘点](script-inventory.md)保留基线24个脚本事实，文末给最终处置；history/保留早期未确认方案及PowerShell旧实现，不作为现行推荐。

## 后续

本地提交后保留分支和工作区。若用户授权发布，按Git/PR流程说明范围、风险、验证与Auto-merge，再处理远端交付。
