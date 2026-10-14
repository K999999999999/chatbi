# Deployment Simplification Design Review

Review: PASS
Review Target: [已确认Spec](spec.md)、[实现设计](design.md)
Reviewer: 当前主Agent，只读审查；未启动独立Agent。

## 前置条件与证据

用户已确认完整Spec、容器单一入口和备份API字段例外；工作区修改全部归属于本目标规划。审查基线 `f4d0693`，实际读取Architecture/Product Scope/Roadmap、Bootstrap/Container Dev/R6/R7 Contract、dev、开发/应用Dockerfile、Compose、数据库测试脚本、容器验收脚本、Playwright配置、评测入口及混合operations测试。

## Findings

### 1. 应用与运维状态耦合已明确拆分

Signal: 删除整个operations模块会放大变更并破坏应用保护。
Evidence: bootstrap runtime装配状态/监测，API admission和后台执行读取ready；R7还定义容量、模型观察和权限投影。
Impact: Coupling / Correctness；简单运维删除可改变业务受理和安全状态。
Recommendation: 设计选择保留应用状态/监测/保护，只删除backup provider和socket；API例外限定details.backup，测试保留其他行为。已落实，无待修复项。

### 2. 无宿主Python的测试链路具备完整替代路径

Signal: 仅删除宿主教程不能消除隐藏的宿主运行依赖。
Evidence: run_database_tests以sys.executable调用migration/pytest；Playwright webServer直接uv run；CI与本地有不同执行环境。
Impact: Testability / Cognitive Load；容器开发无法覆盖全部验收，易遗漏被skip的集成测试。
Recommendation: 设计采用Bash管理临时Docker资源、Python/Node容器执行测试和fixture；保留CI默认配置兼容。明确两个PG profile、真实renderer开关和浏览器渠道。已落实。

### 3. 初始化时序和运行校验不能随发布系统删除

Signal: 健康检查、migration和Stable verify-runtime存在隐藏时序依赖。
Evidence: database healthcheck检查checkpoint；dev migrate先wait_for_base_initialization；local_release还检查web/export/model/RAG/catalog/admin。
Impact: Runtime Failure / Unknown Unknowns；空卷部署可能互相等待或丢失必要检查。
Recommendation: 设计规定基础初始化后显式migration，再完整健康；必要检查逐项映射既有应用/验收，不复制release兼容矩阵。已落实，验收要求空卷及安全失败。

### 4. 旧资源与标准容器隔离

Signal: 固定Stable卷、restore binding和当前开发资源可能被新流程误用。
Evidence: local Compose使用external卷；本机旧Stable/restore容器存在，开发PG/Qdrant运行。
Impact: State / Security / Maintainability；删除代码不能推定可删除或接管真实数据。
Recommendation: 设计保留旧资源，独立验收project及标签核验，保持日常dev卷身份；无Schema变更或真实流量切换。已落实。

### 5. 最小设计及迁移闭包

Signal: 复制发布预检或将Docker socket交给业务API会保留/增加运维复杂性。
Evidence: 原release状态与备份工具跨CLI/文件/socket；标准应用仍需Dockerfile及必要运行校验。
Impact: Change Amplification / Information Hiding。
Recommendation: 不新增依赖/框架/一级模块；先迁移应用保护和测试，再删除旧系统。应用Dockerfile使用普通build，CI不全面重写；历史文档和消费者闭包在最终Ticket核对。已落实。

## 总体判断

Use Case与业务真相保持；Interfaces → Application → Domain方向不变；无Provider/数据库细节迁入Domain。主要状态、故障、权限、锁和数据边界已明确，可用现有测试seam验证。替代方案已比较，选择降低入口认知成本且不引入发布替代系统。

Reference: 已读取Architecture Knowledge Core；采用复杂度、变化轴、依赖方向、可观察行为、失败/状态、Testability、Migration和Overengineering相关章节。

验证边界：本结论为编码前设计审查，未运行软件测试、构建或业务验收，不构成实施或Commit/发布授权。遇到新依赖、扩大API例外、数据/模型/权限变化时返回Spec及Design Review。

Next: workflow-to-tickets形成草案，当前主Agent只读Readiness后请用户确认拆分及完整本地实施范围。
