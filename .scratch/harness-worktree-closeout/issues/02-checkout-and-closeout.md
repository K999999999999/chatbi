# 任务归属与收尾核验

Status: done
Owner: 当前主 Agent
Blocked by: 01-local-cleanup
What to build: 检查全部 worktree；结构化归属和显式本机收尾 gate；Plugin 候选 preflight 与 record-only state；更新对应规则。
Acceptance criteria: 不匹配时不生成任务候选且不写状态；另一目录修改可见；done 但 branch / 目录遗留会失败；有效收尾通过；旧记录只读发现兼容。
Owned files: scripts/check_harness_state.py、scripts/harness_control.py、scripts/harness_container_adapter.sh、相关测试、AGENTS、docs/agents、Runbook。
Result: 归属 / 严格本机收尾、跨分支Ticket、record-only与相关规则完成；脚本回归268项通过，最终state模块9项定向通过；详见../verification.md。
Comments: 用户已确认四步方案的第二项；纯恢复查询允许跨 checkout。
