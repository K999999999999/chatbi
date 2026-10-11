# 实现 Review：ChatBI 新人项目导航

Date: 2026-10-11
BASE_SHA: `b0af01e4d886df56d58433f6c34e8ec852ebaeef`
Branch: `docs/project-navigation`
Review: PASS（文档实现范围）

## Change Description

- What：新增 `docs/project-guide.md` 并加入 README 导航入口；核对当前文档状态；隔离走通新 clone 启动、健康及确定性测试步骤。
- Why：让新人能由项目全景逐层定位功能、模块、权威事实源、验证和运行入口。
- Risk：只有文档变化和一次性隔离环境运行；没有产品源码、业务行为或公共 Contract 改动。冷构建受当前 Debian 系统包源 502 阻塞，详情见 `onboarding-acceptance.md`。
- Verification：Markdown local links、Diff 检查、全量 Python 软件测试、前端类型检查、隔离 PostgreSQL 集成测试、隔离容器健康检查。

## Findings

- 未发现超出 Spec / Ticket 范围、源代码或用户运行资产变化、权威事实冲突、Secret 暴露、导航目标错误或无法回退的修改。
- README、Runbook、Product Scope、Roadmap、R7 Spec 与 R5 / R6 / R7 Acceptance 的状态差异已逐项记录在 `fact-reconciliation.md`；日期化 Acceptance 保持原样。
- `reports/` 含已提交历史报告和被忽略的新候选输出；项目导航已分别说明，并要求以每个报告的候选身份为准。

## Review Dimensions

Correctness: PASS；Comprehension: PASS；Consistency: PASS；Testability: PASS；Architecture: PASS（未改架构）；Security: PASS（生成的隔离配置已清理）。

## Tests / Evidence

- `CHATBI_WEB_ORIGIN=https://test.invalid LANGCHAIN_OPENAI_TCP_KEEPALIVE=0 uv run --python 3.11 --locked python -m pytest -q`：1035 passed、44 skipped、142 subtests passed。
- `uv run python scripts/run_database_tests.py`：5 passed。
- 隔离 Web 容器 `npm run typecheck`：通过。
- API / Web 健康检查：HTTP 200。
- `python3 scripts/check_markdown_links.py`、`git diff --check`：通过。
- 首次无 HTTPS test Origin 的全量测试有 1 项读取开发 `.env` 后失败；添加命令级 Origin 覆盖后复验通过，并已更新 Runbook / README。

## Remaining

导航作者两次模拟走读发现 README 导航入口偏后、成熟度表述混淆、Roadmap 阅读范围不清，第二遍发现“当前阶段”下的历史记录不利于新读者提炼现状；已修正并将 `python3 scripts/check_markdown_links.py`、`git diff --check` 复验为通过，过程与限制见 `onboarding-acceptance.md`。另一位新开发者尚未独立执行 `docs/project-guide.md` 的新人自查清单；Ticket 03 与整个工作项继续保持 `in-progress`，等待该走查反馈。当前系统包源对 Debian 包返回 HTTP 502，冷构建未能证明；使用本机预存镜像后的隔离初始化、启动及健康链路通过。未执行真实 LLM Evaluation 或完整浏览器业务 Acceptance。

## README 收敛复审（2026-10-12）

Review: PASS。

- What：将 README 从 122 行收敛到 61 行，保留定位 / 成熟度、首次容器开发、Hook、主链路和权威资料 / 测试入口；删除与 `docs/project-guide.md` 及专题文档重复的完整模块图、仓库地图和 R2–R5 细节。
- Why：README 已明确把新成员导向项目导航，重复展开会模糊阅读入口。
- Risk：仅 README 信息架构变化，无运行时或产品行为影响。快速开始命令与 Runbook 的环境前提、Hook 安装和初始化顺序一致。
- Review Dimensions：正确性、理解成本、事实一致性、架构、Secret 安全均 PASS。
- Verification：`python3 scripts/check_markdown_links.py` 通过；`git diff --check` 通过；核对 Hook 脚本存在以及 `.env` / 测试说明指向 Runbook 中的对应配置。未运行软件测试（纯文档变化）。
- Remaining：Ticket 03 的非作者独立新人走查仍未完成；因此工作项仍为 `in-progress`，无本地 Commit。

## 导航文件与内容适配性复核（2026-10-12）

Review: PASS（文件职责与阅读顺序）；无需移动现有正式文档。

| 文件 | 适合承担的职责 | 复核结果 |
| --- | --- | --- |
| `README.md` | 仓库首页、产品一句话说明、快速启动和权威入口 | 61 行；不再重复能力详图或逐版本功能记录；Hook / 配置 / 测试运行位置清楚 |
| `docs/project-guide.md` | 新成员全景阅读路线、能力到代码 / Contract / 验证的映射、深读路径 | 能从概览进入边界与主链路，再到能力表、专题和运行路径；表内代码路径抽查存在 |
| `docs/product-scope.md` | 当前支持边界与业务 Contract 摘要 | 与 README / Guide 的产品定位和能力边界一致；详细条款仍留在此源文档 |
| `docs/architecture.md` | 模块职责、依赖方向、系统和代码架构图 | 属于稳定架构事实源，供 Guide 链接深入，没有必要搬入项目导航 |
| `docs/roadmap.md` | 阶段顺序、项目状态及历史阶段记录 | 顶部新读者速览回答当前状态；后续长历史已标明按需阅读 |
| `docs/runbook.md` | 环境前提、配置、启动、测试及运维步骤 | Guide / README 导向第 3 节与第 8 节，未复制操作事实 |
| `.scratch/repository-structure-readability/workspace-map.md` | 保留旧结构整理工作历史 | 文首已声明为 2026-09-17 快照并指向当前入口；不属于新人推荐路径 |

README → Guide → Product Scope / Roadmap → Architecture / 能力地图 → 核心查询链路 → 专题 → Runbook / 验证 的顺序与内容职责相符。抽查 Guide 中的 inline 仓库路径均存在；`python3 scripts/check_markdown_links.py` 与 `git diff --check` 通过。未运行软件测试（文档导航复核）。仍缺非导航作者走查，不能把作者自查报告为独立新人验收。

## 独立新人走查补充复审（2026-10-12）

Reviewer: 未参与导航编写的独立审阅者；首轮只读 README、Guide 和相关事实源，未查看作者模拟记录。

- 首轮：能力到代码 / Contract / 验证 PASS；核心查询链和本地启动 / 健康 / 测试入口 PASS。发现两项理解卡点：Product Scope 将已交付的成功快照导出列在“当前明确不包含”；项目导航没有直达当前 Online Retrieval V1 Contract，容易误入历史基线文档。
- 修复：Product Scope 明确导出“已实现并作为 R5 交付”；项目导航直链 `.scratch/online-retrieval-v1/spec.md`，并将 `docs/specs/online-retrieval.md` 标成历史基线。
- 独立复核：PASS；两项卡点消除，两个链接目标存在。`python3 scripts/check_markdown_links.py` 与 `git diff --check` 再次通过。
- 该走查没有启动服务或重跑软件测试；隔离启动、全量测试和前端检查证据沿用 Ticket 03 已记录的执行结果。

## Next

独立新人走查及修订复核完成；无未解决的导航阻塞。候选以本地 Commit 交付。冷镜像构建的 Debian 系统包源 HTTP 502 限制仍须保留在交付说明中。
