# 05 — 显式项目接入与 CI / 远端配置核验计划

Status: done
Ticket Readiness: READY


Change Profile: Plugin；长期接入行为，中型；风险为覆盖用户配置 / 隐式远端写入；新旧项目fixture和远端安全快照验证；本地候选。
Owner: 当前主 Agent
Blocked by: 04

### What to build

提供只读发现、适配与差异计划、已确认文件的本地写入和接入核验。识别真实测试入口与CI覆盖，输出远端目标、检查来源、严格base等变化与回退计划。远端授权、应用、读回由阶段Skill协同现有工具，核心只读查询不执行远端修改。

### Acceptance criteria

- Plugin安装 / 只读检查不修改项目；新项目显式接入，已有项目复用规则并展示逐文件差异。
- 未确认文件、用户已有变动、路径越界、未知栈 / 测试命令、无权限或无法核验远端，均不覆盖、不生成空绿色job或报告完整接入。
- 本地应用前重新核对原文件身份；并发变化拒绝覆盖，重复应用安全且不会重复追加规则。
- GitHub快照区分实际required checks与其他成功job、来源、base策略及未验证项；真实应用需独立授权和读回。
- 其他托管平台 / 技术栈不虚构真实适配；输出待确认项目，而非硬编码ChatBI的8项检查。

owned files: Plugin工具接入部分、CLI、`tests/test_harness_onboarding.py`、接入 / CI配置文档；不改实际远端规则。

Verification evidence: 新旧项目fixture、冲突与重复应用、越界路径、缺命令、过期 / 错仓库快照；模拟应用前变化；全程无业务服务 / 真实远端写入。

Migration / Rollback: 写入前保留已核实原件与清单；只回退本次明确文件，不移除用户新增内容；远端回退仅计划，未经授权不执行。

Done When: 能生成具体接入Diff并证明拒绝路径；未知平台 / 权限限制可见，Review通过。

Result: 新增只读项目发现、单文件 Diff 计划与显式确认后原子应用；对不可信 / 嵌套路径、敏感文件、已有未提交或未跟踪文件、Git ignored 目标、应用前身份变化均拒绝覆盖。GitHub快照单独核对 required checks、来源 App、head/base、strict 与非必需成功Job；不访问网络或声称实时远端完成。Plugin全量单测 Python 3.14.4 本机与 Python 3.11.16 容器各49项PASS；CLI帮助、Python AST语法解析、git diff --check PASS。
Comments: 用户于 2026-10-19 确认 8 项拆分并授权整体本地实施、验证、Review 和 Commit；不含 Push / PR、Plugin 安装更新、远端设置或实验。
