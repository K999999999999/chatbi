# 工作树收尾与 Harness 事实核验修复

## 授权与范围

用户已确认上一轮四步处理方案，并明确“可以 开始处理”。本记录固化该范围，四个切片沿用已确认顺序：本机收尾、归属与完成检查、Docker / Plugin 兼容、历史事实纠正。授权覆盖连续本地实现、验证、Review、Commit、本机 Plugin 更新和 PR #100 正文纠正；本目标的新 Push / PR 仍需发布授权。文档候选 `docs/remove-roadmap-and-audit@e598533` 完整保留，独立等待发布。

基线：ChatBI `master@6ca342c`，新分支 `fix/harness-worktree-closeout`。产品范围、Domain、业务 API、模型、数据库和付费评测均不变。

## 已确认问题

- CI 工作已在远端合并，临时 worktree 切回 master 后仍留在本机，完成报告没有说明目录去向。
- PR #100 错称其 master 不存在 `docs/roadmap.md`；该文件实际存在，只有未发布文档分支删除了它。
- 旧检查不遍历 linked worktree，也不核验记录的任务与 checkout 归属。
- Plugin state 可将任意当前 checkout 包装成指定工作项的 candidate；旧格式记录缺少新版完成依据。
- Docker `-v` 对缺失的源码路径可创建空目录；已删除的审计目录曾留下文件名形式的空目录，具体历史触发命令未确认。
- 已安装 Plugin 落后于同版本已发布源码，读取取消记录失败。

## 行为 Contract

1. 归档并逐文件校验 CI 本机测试报告，清理已授权临时目录，主目录同步远端 master；保留未发布文档分支及共享工作记录。
2. 新任务增加本机结构化字段 `Branch`、`Worktree`、`Worktree disposition`（active / parked / removed / retained）；收尾增加 `Return worktree`、`Merge commit`、`Cleanup evidence`，retained 必须有 `Retention reason`。旧的复数自由文本字段继续作人类说明。
3. 普通 `harness check` 仍只读、不访问网络、不清理任何对象；检查所有登记 worktree 的状态和新字段，旧格式历史记录不批量迁移。没有 ERROR 的退出码仍为 0，REVIEW 不代表整体完成。
4. 增加显式 `--work-item ID` checkout 核验和 `--closeout ID` 本机收尾核验。后者要求字段完整、合并提交已进入本地 master、master 与已获取的 origin/master 相同、Feature branch 已清理、目标目录已移除或有明确保留原因、返回目录在干净 master。它只核对本机 Git 事实，不能证明远端快照新鲜或 PR / CI / 正文正确。
5. Plugin adapter 在创建 / 消费 candidate 前核验任务、branch、worktree。state 允许跨目录发现记录；归属不匹配或历史记录未绑定时只返回记录信息，移除 candidate 及依赖当前 checkout 的派生结论。diff、baseline、证据、阶段转换和完成等候选操作必须明确匹配，失败不得执行 Plugin 状态写入。合并后返回 master 的归属只能由完整本机收尾核验建立，并显式标记 post-merge；总体完成写入额外要求本机收尾通过，Plugin 原有证据门禁仍须满足。
6. 源码、配置、Plugin 和 Git 的 bind mount 使用 Docker `--mount`，并在调用前验证宿主源存在；当前调用环境不可核实的映射明确失败。真实 smoke 已证明本机 Docker Desktop 不能仅靠 `--mount` 防止建目录。报告等显式创建的输出目录保留原用途，不得自动重建缺失源码目录。
7. 使用 `codex plugin add engineering-workflow@harness-task-control-v1` 更新真实安装包，对照已发布源码校验，并验证取消记录可读；不手改安装缓存，不将 CLI 可用声称为当前会话已重新加载。

归属检查仅约束候选相关操作；迁移、取消、运行 / 诊断记录和 adapter 明确不需要 candidate 的早期阶段转换保留原语义，不为纯记录操作强制创建开发分支。
8. 更正 PR #100 的错误事实和复盘，读回完整正文；本机相关记录注明修复项、归档位置和文档候选去向。新任务本地候选完成后主目录可回 master，任务在分支上 parked 等待发布，不标记整个目标 done。

## 验收与验证

- 真实 Git fixture 覆盖：另一 worktree 的修改、checkout 不匹配、parked 候选保留、done 但目录 / branch 遗留、缺失或不匹配的返回目录、有效收尾、旧记录兼容与只读性。
- 真实入口测试 state 的 record-only 输出和候选操作拒绝，包含未绑定 legacy、正确绑定、错误绑定和 Plugin 失败。
- Adapter / 容器脚本回归验证只读挂载及指定状态目录写入边界；真实 Docker smoke 证明缺失源码不会被创建。
- 受影响确定性测试、统一 Python quality、文档组合检查、模块边界、`bash -n`、Diff Review；不运行无关业务集成或收费 AI 评测。
- 适用事实源：AGENTS、issue-tracker、git-pr-workflow、Runbook、动态文档清单逐项复核；产品范围和业务 Spec 无变化。

## 回退与交付

代码通过普通 Git 提交回退；必要报告位于 Git common-dir 的归档中；文档候选分支继续保留。Plugin 使用官方安装入口刷新，源仓库和原有工作分支保持各自身份。本机进度不入 Git，历史错误更正保留前后快照，不伪造历史验证。
