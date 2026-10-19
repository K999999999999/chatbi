# 07 — ChatBI 容器适配与旧入口兼容

Status: done
Ticket Readiness: READY


Change Profile: ChatBI；长期项目适配，中型；风险为运行路线变化 / 缺Plugin假通过；容器挂载和fixture回归；本地候选。
Owner: 当前主 Agent
Blocked by: 06

### What to build

在ChatBI登记项目阶段、路径 / 验证 / 风险 / 动态文件清单，扩展现有dev协作入口使用Plugin工具。只读与明确状态写入分开挂载，保留旧check命令的行为与覆盖；CI使用合成Plugin fixture验证adapter，不复制通用控制核心。

### Acceptance criteria

- 不要求宿主Python/uv/Node，不读.env、不挂Docker socket，不改业务应用或服务；容器挂载源码/工具只读，写权限限所需状态位置。
- 普通clone与linked worktree均可定位公共目录；缺工具/镜像/路径不自动联网安装、不回退后声称新版通过。
- 旧 `./dev harness check` 与 `python -m scripts.check_harness_state` 的既有检查行为保留；新能力显式接入并报告范围。
- 动态文件清单链接现有权威文档，当前未授权旧工作项/用户文件保留；当前目标不伪装成已由新工具管理的历史。
- CI / 本地使用仓库内可复现fixture验证调用和失败行为；fixture不冒充已安装Plugin真实运行。

owned files: ChatBI `.harness/project.json`、`dev`、`scripts/container_tasks.sh`、必要薄adapter、`tests/scripts/test_harness_adapter.py`、旧Harness测试（仅兼容扩展）、必要fixture及CI入口、AGENTS/文档规则/Runbook/模板。

Verification evidence: 容器定向adapter测试、只读/写挂载检查、无Plugin/坏路径、Git公共目录、旧状态检查回归、文档链接/结构与模块边界；无LLM。

Migration / Rollback: 不批量迁移54份历史记录；新profile仅对显式目标启用。入口回退保留旧工具及新数据，不清理唯一证据。

Done When: 容器内正常/失败路径通过，旧入口兼容，项目Diff和文档Review通过；远端与安装状态如实报告。

Result: 完成 ChatBI `.harness/project.json` 阶段 / 路径 / 风险配置及 `.harness/dynamic-files.json` 动态文档清单；新增 `./dev harness control` 容器入口和薄适配器。仓库与 Plugin 源只读挂载；只允许显式状态写入挂载一个现存工作项目录。缺源码、坏插件标识、缺镜像、不支持的写入目标均失败关闭；不读 `.env`、不联网、不挂 Docker socket。旧 `./dev harness check` 和 `scripts.check_harness_state` 路径保持原样。

验证：ChatBI 开发容器 `./dev test python tests/scripts/test_harness_adapter.py` 12 项通过；`./dev check docs` 通过；实际运行旧 Harness 检查返回 54 条记录、0 ERROR、3 条既有 REVIEW；以只读 Plugin 候选实际运行 `state --json`，仓库适配正确且当前目标标记 `legacy_read_only: true`。宿主没有 `python` 命令；`python3 -m scripts.check_harness_state` 复核通过（54 条记录、0 ERROR、3 条既有 REVIEW）。未运行托管 GitHub CI，未安装 / 同步 Plugin，也未改远端设置。
Comments: 用户于 2026-10-19 确认 8 项拆分并授权整体本地实施、验证、Review 和 Commit；不含 Push / PR、Plugin 安装更新、远端设置或实验。
