# Ticket 04：维护规则、门禁与 Review 形成可验证闭环

Status: open
Canonical Source: [Spec](../spec.md)、[设计](../design.md)；用户已确认四项拆分与整体本地实施。

Change Profile: 持续维护工程工具与项目规则 / 中等脚本、测试、CI 和文档变更 / 漏报与误报、协作保护丢失风险 / fixture 回归和最终迁移 Review / 本地候选。
Owner: 当前主 Agent。
Blocked by: 03。

### What to build

- 在 AGENTS.md 保留短强制入口，详细文档维护规范集中在 docs/agents/documentation.md。
- 精简 domain / issue-tracker / git-pr-workflow 的重复说明；原 agent-harness 中当前要求逐项分入正确位置，独有过程归档，修复全部引用。
- 更新现有 PR 模板与 Done When / Agent Review，记录当前文档更新、历史去向或不适用理由；保持现行授权、状态恢复、Auto-merge 与收尾规则。
- 保留原链接入口和 --root；新增组合文档检查入口，使用共享最小解析检查链接、当前文档标题跳级和正文章节符号引用。
- 基于临时 Git fixture 建立有意义的回归，验证文件发现、作用范围、代码示例过滤、ATX / Setext、行号及退出码。
- 现有 Deterministic tests job 调用组合入口，不更改 job 名称和远端 required checks 设置；Runbook 同步可复现的本地命令。
- 完成整目标台账、规则覆盖、阅读走查、验证 / Review 与本机状态记录。

### Acceptance criteria

1. 从 AGENTS 能找到文档归属、更新与检查规则；唯一详细规范可达，现行关键协作与安全保护未丢失。
2. 本地和 CI 使用同一组合入口；原链接入口仍兼容，全库历史记录继续受链接保护。
3. 正式文档的跳级和章节符号引用失败，定位准确；代码块 / 行内代码 / 历史目录不误报；缺少 Git 或读取失败非零退出。
4. 回归包含新违规 fixture、正常 fixture、历史和示例边界；现有链接测试通过，新增解析没有破坏旧锚点 / 链接行为。
5. 现有 Review 可追溯文档更新 / 不适用理由；不通过关键词推断业务矛盾、不新增用户审批或第三方依赖。
6. 全部迁移条目有当前规则 / 独有历史内容的处置证据；最终当前文档脱离历史唯一 Contract，导航和运行阅读走查通过。
7. 最终验证绑定本目标候选 / 基线；不把 CI 配置已改称为远端 required gate 已核实，也不把历史 AI 结果称为当前候选新结果。

owned files: AGENTS.md；docs/agents/ 现有文件与新 documentation.md；.github/pull_request_template.md；scripts/check_markdown_links.py、新 check_documentation.py 与按需要共享的 markdown_content.py；tests/scripts/test_check_markdown_links.py 与新 test_check_documentation.py；.github/workflows/ci.yml；Runbook 检查命令；受影响引用与本工作项证据。CONTEXT / CONTEXT-MAP 仅检查现行结构，领域定义不变。

验证证据:

- `CHATBI_WEB_ORIGIN=https://example.invalid uv run --python 3.11 --locked python -m pytest -q tests/scripts/test_check_markdown_links.py tests/scripts/test_check_documentation.py`
- `uv run --python 3.11 --locked python -m scripts.check_documentation`
- `uv run --python 3.11 --locked python -m scripts.check_module_boundaries`
- `bash scripts/check_python_quality.sh`，并以该脚本固定的 Ruff 版本补充检查受影响 scripts 文件（其现有全量范围是 src / evaluation / tests）。
- `uv run --python 3.11 --locked python -m scripts.check_harness_state` 与 `git diff --check`；说明属于本目标的 REVIEW。
- 工作流调用核对、当前文档语义 Review、全目标阅读走查与历史保全台账核对；无业务代码变更时不启动真实服务或 LLM。

Migration / Rollback: 先完成正式文档清理，再激活组合门禁。解析回归失败时固定坏例子后修复，不通过排除全部正式文档绕过；恢复时同时恢复工具、CI 调用和规范入口。用户改动保留，旧历史唯一副本不删除。

Done When: 规则可发现、确定性问题可拦截、语义 Review 可追溯、全目标迁移 / 阅读 / 验证通过、本地候选完成。发布授权仍是独立边界。


## Result

待实施与验证。

## Comments

发布尚未授权；本目标按依赖连续完成。
