# Repository Structure and Readability（仓库结构与可读性）

## Problem Statement

当前工作区同时包含业务源码、测试、脚本、架构与过程文档、数据库脚本、数据、模型、运行报告、IDE 配置和本地开发环境。文件和目录数量较多，但新开发者打开仓库后，不能快速判断每个区域的职责、当前项目状态、主链路以及下一步阅读入口。

当前问题还包括：

- 根目录缺少统一的项目入口；
- 代码按业务模块存在，但模块内部部分文件职责过重，阅读和定位成本较高；
- 架构规则、实际代码布局和文档入口之间不够一致；
- `MVP`、`POC`、版本号和生产状态容易被混用；
- 本地运行资产与项目源码同时出现在工作区中，视觉上容易被误认为同一类项目文件。

本 Feature 的目标是改善整个工作区的可理解性和可导航性，不改变 ChatBI 的业务行为或已有稳定 Contract（契约）。

## Solution

建立面向新开发者的 Workspace Map（工作区地图）和项目入口：

1. 保持标准工程目录和当前运行路径，明确说明每个目录的用途、维护方式和是否属于 Git 管理内容；
2. 增加简洁的 `README.md` 入口，使新开发者能够在 5 分钟内理解项目定位、当前版本、模块组成、主链路、代码位置和下一步阅读路径；
3. 以业务模块为第一层组织代码，在模块内部仅按真实职责渐进拆分过重文件；
4. 保持 `docs/specs/`、`docs/designs/`、`docs/acceptance/`、`.scratch/` 和 `docs/runbook.md` 的既定职责，通过入口和链接降低查找成本，不进行无目标迁移；
5. 使用“版本号 + 开发/生产状态 + 模块验证状态”描述当前项目，不用单一的 `MVP` 或 `POC` 概括整个 ChatBI；
6. 对非缓存文件默认保留。识别到疑似废弃、重复或无用文件时，先形成候选清单，再单独确认删除。

预期结果是：新开发者可以从根目录入口开始，依次理解“项目是什么、怎么运行、代码在哪里、证据在哪里、当前做到什么程度”，而不需要先遍历整个工作区。

## User Stories

1. As a new developer, I want to understand ChatBI's purpose, current status and main flow from one entrypoint, so that I can decide where to start reading or working.
2. As a new developer, I want each workspace area and module to have an obvious responsibility, so that I can locate source code, tests, documentation and runtime assets without guessing.
3. As a maintainer, I want large files to be split only along real responsibility boundaries, so that readability improves without changing public behavior or stable contracts.
4. As a maintainer, I want version, implementation status and validation evidence to be separate, so that project maturity is not overstated.
5. As a maintainer, I want non-cache cleanup to be reviewable through an explicit candidate list, so that historical evidence and runtime assets are not removed accidentally.

正常场景：新开发者从 `README.md` 开始，可以找到主链路、模块地图、目录说明、运行手册、Module Spec（模块规格）和测试入口。

边界场景：本地数据库、模型、虚拟环境、报告和 IDE 配置仍然存在时，它们不会被误认为业务源码；历史文档保留时，可以通过职责说明判断其用途，而不是依靠文件名猜测。

失败场景：入口文档中的路径或链接与实际目录不一致时，结构验收必须发现问题；代码拆分导致内部 import 或测试失败时，不得认为结构整理完成。

## Implementation Decisions

### Workspace boundary

- 本 Feature 覆盖整个工作区的盘点、分类和导航设计，包括源码、测试、脚本、文档、数据库脚本、数据、模型、报告、IDE 配置和本地开发环境。
- 保持 `src`、`tests`、`docs`、`scripts`、`database` 等标准工程目录。
- `data`、`models`、`.venv`、`reports`、`.idea` 等本地或运行资产保留原位置，通过项目地图解释其作用；本 Feature 不为了视觉整齐而改变它们的路径。
- 已确认的缓存清理范围包括 Python 字节码缓存、测试和 lint 缓存以及本地 `uv` 缓存。其他非缓存文件不自动删除。

### Project identity and status

- ChatBI 的整体标题使用当前版本和状态，不使用 `MVP` 作为整体定位。
- `POC` 仅用于 `Streamlit`、验证页面、测试和明确的部分评测场景。
- 入口中的项目状态至少区分：当前版本、开发/生产状态、各模块实现状态、验证证据和生产状态。
- 版本来源按以下优先级确定：Git tag、项目配置中的 `version`、Development Snapshot（开发快照）及 commit hash 和日期。
- 没有完成实际版本事实核对前，不在文档中自行编写具体版本号；版本号不代表 Production Ready（生产可用）。

### Code organization

- 代码第一层按业务模块组织，主要模块包括 `Online Query`、`RAG Offline Build`、`Query API Adapter`、`Evaluation`、`Observability` 和当前 `Streamlit` 入口。
- 模块内部只在真实职责已经形成时拆分文件或子模块，不强制每个模块都具备完整的 `Interfaces → Application → Domain ← Infrastructure` 目录。
- 可以调整内部文件、内部 import 和实现组织，但必须保持模块公开入口、公共 Contract、业务行为、异常语义和现有调用方式兼容。
- 大文件拆分属于可读性治理；如果需要改变公共 API、一级模块职责或稳定依赖方向，必须脱离本 Feature 单独进行 Architecture（架构）确认。

### Documentation organization

- `README.md` 是面向新开发者的简洁项目入口，负责项目身份、主链路、模块地图、目录地图、状态和下一步阅读入口。
- `docs/architecture.md` 负责稳定架构和代码地图；它必须与实际目录和模块职责保持一致。
- `docs/runbook.md` 负责详细启动、测试、配置和故障排查，不复制成另一份 README。
- `docs/specs/` 负责稳定 Module Contract；`docs/designs/` 负责已确认 Contract 的实现设计；`docs/acceptance/` 负责验收证据；`.scratch/` 负责当前 Feature 的 Spec、Ticket 和过程规划。
- 不把历史 Feature 的 Feature Contract、验收证据或实现设计随意迁移到另一类文档中。

### Deletion and preservation

- 可重建缓存和已确认的空缓存残留目录可以清理；这些清理已经作为前置工作完成。
- 非缓存文件默认保留，包括历史文档、验收证据、数据库、模型、数据、报告和本地配置。
- 后续发现的疑似废弃或重复文件必须列出路径、用途判断、保留风险和删除影响，获得单独确认后才能删除。

## Testing Decisions

本 Feature 的最高验证边界是“仓库结构、入口导航和内部代码兼容性”，不是业务 AI 结果验收。

### Navigation and documentation evidence

- 检查 `README.md` 是否能覆盖 5 分钟理解目标：项目定位、版本和状态、主链路、模块地图、目录职责、当前状态和下一步入口。
- 检查 README、架构地图、目录说明和实际文件路径是否一致。
- 检查 Markdown 相对链接和文档入口是否有效。
- 抽查新开发者从入口进入架构、运行、规格、测试和验收证据的路径，不要求阅读过程文档才能理解主链路。

### Code structure evidence

- 对发生移动或拆分的模块执行 Python import / compile 检查。
- 执行受影响模块的 targeted tests（针对性测试）。
- 结构调整完成后执行完整 deterministic tests（确定性测试），证明公共行为没有因内部重组而回归。
- 测试外部可观察行为、公共 Contract 和模块入口，不测试偶然的内部文件布局。

### Validation boundary

- 本 Feature 不改变业务逻辑、数据库、模型、Qdrant 资产、LLM 配置或 Retrieval 行为，因此不把真实 PostgreSQL、Qdrant、BGE-M3、LLM 或 Business Acceptance 作为本 Feature 的必需验收项。
- 如果实施过程中实际改变了上述行为或稳定 Contract，必须停止当前结构整理，重新确认范围并追加对应验证。

### Acceptance criteria

1. 新开发者仅从项目入口和链接进入，能够在 5 分钟内说明 ChatBI 的用途、模块、主链路、当前状态和下一步阅读位置。
2. 工作区所有主要目录都有明确分类，源码、测试、文档、运行资产、生成资产和本地工具之间的边界可解释。
3. 版本、开发/生产状态、模块实现状态和验证证据没有被混写成单一成熟度标签。
4. 大文件拆分后，相关 import、targeted tests 和完整 deterministic tests 通过。
5. README、架构地图和实际目录没有已知断链或明显过时的职责描述。
6. 除已确认缓存和空目录外，没有未经确认的非缓存删除；Git diff 只包含本 Feature 允许的结构和文档变化。

## Out of Scope

- 修改 Online Query、RAG Offline Build、Query API、Evaluation、Observability 或 Streamlit 的业务行为。
- 改变公共 API、模块公开入口、稳定 Contract、权限边界、SQL 安全边界或数据库内容。
- 移动或重建 `data`、`models`、`.venv`、`reports`、`.idea` 等本地运行资产。
- 强制把所有模块改造成完整的四层 Architecture。
- 新增业务 Feature、正式前端、API Gateway、登录、限流、审计、多租户或生产运维能力。
- 直接删除历史文档、验收证据、报告、数据、模型或其他非缓存文件。
- 创建外部 Issue、PR、Push 或自动发布。
- 通过本 Feature 重新定义版本号、创建 Git tag 或宣称 Production Ready。

## Further Notes

- 当前仓库事实、版本具体值和最终文件清单需要在正式实施前重新只读核对；本 Spec 不把未核对的版本号写成事实。
- 当前已有架构文档、产品范围文档、设计文档、规格文档和验收文档，后续需要做职责与链接一致性审查；审查不等于无目标内容瘦身。
- 当前没有适用的领域 Glossary（术语表）变更；本 Feature 主要是仓库结构和工程导航，不创建 `CONTEXT.md`。
- 当前方案不改变不可逆的业务或公共架构决策，因此不创建 ADR。若后续决定强制正式分层、移动运行资产或改变公共模块边界，应先单独记录 ADR 并重新确认。
- 该 Spec 可以交给 `to-tickets` 进行实现切片，但必须先获得用户对 Spec 的确认；本 Skill 不自动创建 Ticket 或进入实现。
