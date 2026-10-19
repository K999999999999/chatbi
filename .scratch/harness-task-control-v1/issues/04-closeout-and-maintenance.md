# 04 — 动态文件收尾、恢复与 Harness 改进闭环

Status: done
Ticket Readiness: READY


Change Profile: Plugin；长期生命周期闭环，中型；风险为假完成 / 证据丢失；合成项目文档和follow-up验证；本地候选。
Owner: 当前主 Agent
Blocked by: 02

### What to build

工具消费项目动态文件清单，登记适用 / 不适用、更新位置、核实版本和未决项；区分本地、远端和总体完成。恢复时核对主关联记录、候选及唯一证据。复用复盘/follow-up记录缺口分类、有效性证据和例外复查。

### Acceptance criteria

- 缺适用核对、未完成Ticket / 子工作项、未证实合并 / 复盘 / 清理时不能误标整体完成。
- 不适用必须有理由；工具校验结构与引用，语义Review独立声明，不声称能自动理解任意文档。
- 换worktree / 主记录不可用 / 记录损坏保留未知与原件，关联不继承授权；存在用户改动不清理。
- 缺口有归属、授权、验收、处置和实际效果证据；登记或多写一条规则不足以解决，旧机制退出有替代覆盖与历史去向。
- 本地目标未获发布授权可准确结束本地范围，包含交付的目标不因此被标done；唯一证据未处置前拒绝报告已安全清理。

owned files: Plugin工具收尾/恢复/维护部分、CLI、`tests/test_harness_closeout.py`、动态文件清单与复盘使用文档。

Verification evidence: 合成Spec/Ticket/文档/PR正文、缺引用/未完成/不适用/损坏状态、关联循环或缺失、效果未验证与退出覆盖回归。

Migration / Rollback: 不批量改旧done，不删除旧跟踪；恢复工具回退保留当前状态和原始证据。

Done When: 有效生命周期及拒绝假完成均可验证；语义与结构边界清楚，Review通过。

Result: Plugin全量单测：Python 3.14.4 本机 36 项 PASS，Python 3.11.16 容器 36 项 PASS；CLI帮助、Python AST语法解析、git diff --check PASS。完成记录绑定候选、Manifest、文件核对、Ticket、关联工作项、诊断、维护记录及相关证据；关联工作项状态变化会使旧完成记录失效。
Comments: 用户于 2026-10-19 确认 8 项拆分并授权整体本地实施、验证、Review 和 Commit；不含 Push / PR、Plugin 安装更新、远端设置或实验。
