# 02 — 查看本轮 / 累计 Diff 并核实候选依据

Status: done
Ticket Readiness: READY


Change Profile: Plugin；长期事实采集，中型；风险为漏报改动 / 旧证据放行 / 内容泄漏；Git与报告合成回归；本地候选。
Owner: 当前主 Agent
Blocked by: 01

### What to build

采集任务起点、切片和当前commit/index/worktree身份；输出本轮及累计安全Diff清单。记录机器核实、人工声明、未验证的区别，核对报告 / Git / 远端安全快照身份，分离范围授权与具体候选批准，接入转换依据判断和敏感路径分类。

### Acceptance criteria

- 已提交、staged、unstaged和未跟踪变更均按边界列明，不能只统计commit；默认不输出敏感配置内容。
- 新增依赖、公共接口 / 权限 / 数据 / 验收敏感路径提示需Review；未知语义不能自动称安全，分类规则改动也被标明。
- 源码、base、报告 / 输入身份变化后，受影响依据失效或明确待复核；复用必须有来源、覆盖和理由，原报告身份不改。
- 人工声明不冒充机器核实；同范围CI修复保留范围授权但刷新候选依据，关键范围变化要求新决定。
- 不可读取Git / 报告或缺少实时核对不能产生完整通过。

owned files: Plugin工具事实采集/依据模块、CLI、`tests/test_harness_evidence.py`、工具使用文档。

Verification evidence: 临时Git提交与四类修改、合成报告 / 远端快照、base移动、相容 / 不相容证据、敏感路径与canary输出检查。

Migration / Rollback: 新证据增量登记，不将旧结果重标新候选；回退采集功能保留原报告和引用。

Done When: 正反例证明Diff边界和依据失效；风险限制说明与用户可读摘要完整，Review通过。

Result: Done。Plugin CLI 提供不可重置的任务起点与可更新切片基线；安全 Diff 汇总 committed、staged、unstaged、untracked 与 base 移动，输出候选 / 报告指纹、路径风险和完整性边界。候选依据绑定当前候选和可选报告摘要；旧候选、base / 分类器变化、外部输入身份均会标 stale 或待复核。增加敏感路径裁剪、分类规则变更识别、Git 快照身份比对；远端快照必须与当前仓库 / HEAD / base 一致且本地工作树干净，工具不替远端来源背书。验证：Python 3.11.16 ChatBI 容器中及 Python 3.14.4 本机均运行完整Plugin unittest 19项 PASS；覆盖四类Git变更、mode-only、base移动、classifier变化、候选 / 报告 / 快照身份失效与敏感 canary；`py_compile` 与 `git diff --check` PASS。测试使用临时Git仓库；无网络 / 业务服务 / 真实远端写入。
Comments: 用户于 2026-10-19 确认 8 项拆分并授权整体本地实施、验证、Review 和 Commit；不含 Push / PR、Plugin 安装更新、远端设置或实验。
