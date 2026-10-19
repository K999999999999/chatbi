# 06 — 将控制工具接入通用阶段 Skills 与可复现验证

Status: done
Ticket Readiness: READY


Change Profile: Plugin；长期规则集成，中型；风险为规则重复 / 自修改误判；真实CLI与临时工程流程走查；本地候选。
Owner: 当前主 Agent
Blocked by: 03, 05

### What to build

把状态查看、转换、Diff、预算、收尾和初始化接入现有阶段Skills，保持单一规则来源。增加通用工具标准库测试入口与Plugin仓库CI，使临时Git合成流程验证无需开发机缓存或业务项目。明确源版本、安装版本与会话加载的发现 / 同步流程，准备后续发布说明。

### Acceptance criteria

- 正常切片汇报后继续；关键变化/预算升级等待用户；Spec/Ticket确认不冒充实施或发布授权。
- 阶段Skills调用已定义CLI并读取项目adapter，不复制ChatBI命令 / 机器路径；工具不可达明确unavailable，不假装已执行。
- setup说明支持已确认的本地配置与另行授权远端协同，保持显式入口、安装不自动初始化。
- CI从Plugin仓库真实源码执行标准库回归；不连接LLM / 业务库，不依赖缓存或未跟踪文件；测试修改本身仍需Review。
- 文档 / 元数据版本相容；不手改安装缓存、不自动安装更新、不宣称源提交等于已加载。

owned files: Plugin现有各阶段 `skills/*/SKILL.md`、共享references、README、`.codex-plugin/plugin.json`、工具测试入口、Plugin仓库 `.github/workflows/harness-tests.yml`（若不存在则按真实仓库规则新增）。

Verification evidence: 全部标准库回归、临时项目生命周期CLI走查、Skill引用/命令校验、工具不可达、无网络测试；CI配置静态检查与后续实际run分开。

Migration / Rollback: 保留原阶段语义，替换重复规则时列明覆盖与引用；Plugin同步仅准备受支持步骤，未授权不执行；回退规则不删状态。

Done When: 通用工具与Skills形成一个候选，Review/文档通过；本地结果与托管CI未执行范围明确。

Result: 新增共享Harness工具参考并让13个阶段Skill链接，更新setup-engineering-workflow按只读发现、逐文件计划 / 用户确认 / 本地应用执行，并区分源、安装、会话加载及远端授权；同步Plugin manifest说明和Provenance数量。新增Plugin仓库标准库CI workflow，固定Action SHA、Python 3.11、只读contents权限、关闭缓存；静态检查不等于托管CI运行，也不修改required checks。Plugin全量单测 Python 3.14.4 本机与 Python 3.11.16 容器各53项PASS；CLI帮助、14个Python文件AST解析、manifest JSON、Skill引用、CI静态结构、git diff --check PASS。未Push、未安装同步、未运行托管CI。
Comments: 用户于 2026-10-19 确认 8 项拆分并授权整体本地实施、验证、Review 和 Commit；不含 Push / PR、Plugin 安装更新、远端设置或实验。
