# 验证与 Code Review

## 候选与范围
基线 0e8a198b8396c6614c9e01c044e6259cc086dbab；分支 chore/remove-optional-dev-entrypoints。本报告随候选提交保存，结果适用于本次已审 Diff；原始软件报告保留执行时 HEAD 与 dirty 身份，不改称 clean 提交结果。

## 验证
- `./dev test python tests/scripts/test_database_script_line_endings.py tests/scripts/test_container_dev.py tests/scripts/test_run_database_tests.py`：64 passed，0 skip；报告 reports/tests/20261025T133549Z-0e8a198-test-python-370425d285e4.json。覆盖 Compose 配置、统一开发命令、宿主路径映射和数据库测试脚本；后续只修正文档历史链接，不影响该证据。
- `bash scripts/check_python_quality.sh`：315 files already formatted；All checks passed；按脚本使用 ruff 0.16.8，覆盖 src / evaluation / tests。
- `./dev check docs`：首次发现三个历史断链；修正后通过，报告 reports/tests/20261025T133628Z-0e8a198-check-docs-b2ac3e643b4f.json。
- `git diff --check`：通过。
- `python3 -m scripts.check_harness_state`：无 ERROR；REVIEW 为本任务未交付和本任务工作区修改，归属已核实。
- Plugin state / diff 只读可用；新记录仍为 legacy_read_only，缺 task / slice baseline；不宣称新版 closeout 通过，不迁移旧记录。
- 未运行全量软件测试、真实 LLM 评测、真实业务验收或启动/停止用户容器；本次无业务实现、模型或数据改动。

## Review
使用 engineering-workflow:workflow-code-review，在当前主 Agent 上只读检查上述基线与本次 Diff。
Review: PASS
Clean Code: PASS

验收满足：移除授权范围内两个目录与编辑服务；基础 Compose 中 PostgreSQL / Qdrant 的服务、数据卷、端口与健康检查逐行保持，开发 Compose 完全不变。静态授权实现和角色授权装配均未变更。只删除退役编辑器入口的专用测试，数据库 LF 检查迁移至独立命名文件。历史链接保留当时基线身份，无无关重构或 Secret。

动态文档：Runbook 与正式开发 Spec 已更新；项目讲解删除过期入口。Roadmap 已复核，产品目标、能力、依赖及里程碑均未变化，无需更新；AGENTS、文档规则、工作项规则、交付规则、Harness adapter 与动态清单的触发条件均不适用。旧文件内容由基线 Git 历史保留。

Harness Feedback: 未观察到符合门槛的 Harness 缺口。

## Compose 研究建议
原拆分决定见 .scratch/container-dev-environment/design.md：基础文件只启动 PostgreSQL / Qdrant，开发叠加文件承载 API / Web / 工具。移除编辑器入口后此职责划分仍成立。当前建议保留两个文件，由 ./dev 统一加载；合并可以单独评估，但本任务未授权合并。

## 已授权的 Vite CI 修复

用户确认 Vite 8.3.2 升级至 8.3.5 后，更新 package.json 与 package-lock.json。必要传递依赖为 rolldown 1.2.15（Vite 要求 ~1.2.14）、其平台 binding 与 @oxc-project/types 0.155.0、postcss 8.5.31（Vite 要求 ^8.5.30）及 nanoid 3.3.20（postcss 要求 ^3.3.20）；其他直接依赖不变。

- 使用官方 npm registry 生成锁文件；首次容器命令在写入文件后因镜像内 node_modules 的权限导致退出 243；随后在独立可写 tmpfs 工作目录运行 npm install --package-lock-only --ignore-scripts --no-audit --no-fund 成功。宿主 node_modules 未修改。
- 基于更新锁文件构建 chatbi-node-vite835:local；npm ci 成功且 found 0 vulnerabilities；安装版本实际核验为 8.3.5。
- npm audit --package-lock-only --audit-level=low：found 0 vulnerabilities。
- 在新镜像中以 network none 执行 npm run build -- --configLoader runner（含 TypeScript 检查）及 npm run build:export -- --configLoader runner：通过。
- 更新后的文档检查、git diff --check：通过。Python 源码与测试实现未再次改变，复用已通过的 Python 质量检查。
- 本地浏览器运行 reports/tests/20261025T134621Z-15a36af-test-web-943986000cd8.json 在锁文件生成完成前启动，实际使用 Vite 8.3.2，期间源身份变化；即使机器计数 83/83 也不作为升级验证。
- 升级后尝试 CHATBI_DEV_BROWSER_IMAGE=chatbi-browser-vite835:local ./dev test web；系统依赖镜像下载缓慢，主动取消构建，未执行新版浏览器测试，不作为通过证据。报告 reports/tests/20261025T134815Z-15a36af-test-web-d7b745315ba9.json。
- 新版 Chrome、开发服务器回归交由 PR 的必需 Deterministic tests CI 执行；其 workflow 明确运行 npm test 与 npm run test:dev，CI 结果待真实核验。

当前上下文 engineering-workflow:workflow-code-review：PASS。检查直接依赖仅 Vite 补丁版本变化，传递依赖满足新版本要求，固定版本与完整性摘要由 npm 生成；无应用配置或行为实现改动，不调整安全门禁。Roadmap 与正式文档中未声明具体 Vite 版本，无额外同步位置；本短 Spec 已记录授权及验收调整。

## 已授权的 Python 依赖 CI 修复

用户在告警详情说明后要求先完成当前 PR。以 c0431b2 为本次依赖补丁基线，更新 pyproject.toml 的直接依赖安全下限和 uv.lock：certifi 2026.10.19、filelock 4.2.1、langgraph-checkpoint-postgres 3.1.3、langgraph-checkpoint 4.3.0、OpenTelemetry 1.45.1 / semantic-conventions 0.66b1 及两个必需 exporter transport/common 包、pypdf 6.21.2、setuptools 84.1.0。其他依赖版本与业务代码未变。

### 环境与验证

本地复用既有开发镜像的 Python / Chromium / 字体，仅以新 pyproject.toml / uv.lock 执行 uv sync --locked --no-install-project，生成 chatbi-python-security-fix:local（image digest sha256:7a58139aed36bfa69adfc9ab0cf5eb14fbb532df79b1a19d2aaa98c59d215740）。这是本地依赖回归镜像；原始完整 Dockerfile 的最终验证由本 PR CI PostgreSQL integration 中的 PDF renderer 构建执行。未重启当前开发服务。

以下 test 命令均指定 CHATBI_DEV_PYTHON_IMAGE=chatbi-python-security-fix:local，报告保留 c0431b2 + 当时稳定的工作区 Diff 身份，不改称提交后 clean 结果：

- ./dev test python：采用 scripts/container_tasks.sh 的 python_tests_for_all 相同排除项，将数据库 / renderer 分开运行，真实 LLM service integration 不运行；1120 passed、155 subtests passed、0 skip，报告 reports/tests/20261025T140744Z-c0431b2-test-python-f48f308b700a.json。
- ./dev test database：CI fixture 5 passed；development fixture 63 passed；均 0 skip，报告 reports/tests/20261025T140744Z-c0431b2-test-database-c80c0e95d9c5.json。覆盖状态、历史、会话及迁移的隔离真实 PostgreSQL 行为。
- ./dev test renderer：2 passed、0 skip，报告 reports/tests/20261025T140744Z-c0431b2-test-renderer-bbe6e9ef5565.json。
- bash scripts/check_python_quality.sh：315 files already formatted；All checks passed，覆盖 src / evaluation / tests。
- uv lock --check --python 3.11、python3 -m scripts.check_documentation、git diff --check：通过。
- docker run --rm --user 0:0 -e HOME=/tmp --entrypoint uv chatbi-python-security-fix:local run --locked --with pip-audit pip-audit：No known vulnerabilities found。工具仍无法审计非 PyPI 的 torch 2.14.1+cpu，不把该跳过解释为已验证无漏洞。临时审计容器无宿主目录挂载；前两次非 root 审计因继承缓存属主不匹配失败，未产生漏洞检查结果，随后此命令完成。

### Review 与文档

engineering-workflow:workflow-code-review 在当前主 Agent 上执行，Review: PASS；Clean Code: PASS。核对 uv 生成版本、PyPI 来源与完整性 hash，只变更已授权的 6 包及必要依赖；直接依赖安全下限与锁文件一致；没有业务 / 权限 / 数据 Contract 修改，无弱化安全门禁。既有状态持久化、追踪、PDF 测试提供回归证据，不新增镜像实现的测试。

Roadmap、Architecture、产品范围、正式行为 Spec、Runbook 的支持能力与入口没有变化；本短 Spec 和验证记录承载此次依赖修复，无需另改正式文档。前端代码与锁文件相对 c0431b2 未变化，可复用该 head 已通过的 Chrome 回归，最终完整 CI 仍在新 head 上执行。未运行真实 LLM Evaluation / 业务验收，因为未变更模型、Prompt、资源或业务实现。未观察到符合门槛的 Harness 缺口。
