# 本地容器开发 Design Review

Review: PASS
Review Target: [已确认 Spec](spec.md) 与 [实现设计](design.md)
Baseline: `8c506fab07868c851d2ec8e5f8ed1b0b4fe0c295`；规划文件未提交
Owner: 当前主 Agent，2026-10-03；当前上下文只读审查，未启动独立 Agent

## Findings

无需要修订目标、行为或设计边界的发现。以下是通过判断所依据的风险检查，不是已完成实现 / 验收结果。

| 检查 | 证据及结论 |
| --- | --- |
| Use Case / Domain | 统一开发启动，不改变销售业务、查询链路、权限、SQL Guard 或模块职责；业务模块不依赖 Compose / Shell |
| Contract / 生命周期 | 已明确显式首次初始化、后台启动、手动恢复、进程会话失效、持久数据与不自动重置；启动成功和真实查询成功分别验证 |
| 网络 / 兼容 | 原 Vite 代理是宿主回环地址，设计增加 server-only 容器目标且保留默认值；新增覆盖文件不让原基础命令隐式启动应用 |
| 配置 / Secret | API 现有配置加载过滤 migration keys，但不能替代容器边界；设计使用白名单且不挂`.env`，迁移工具独立，不将真实配置送入构建上下文 |
| 初始化顺序 | PostgreSQL完整健康检查依赖migration创建的checkpoint；migrator不依赖API / 完整healthy，以基础初始化等待后显式执行，避免循环 |
| 源码 / 依赖 | Python依赖镜像内隔离，前端选择性挂载不覆盖node_modules；锁文件改变显式重建；UID / GID及可写目录不要求重写用户数据所有权 |
| State / Failure | CPU配置不更换模型或Torch来源；单worker、重载丢短期会话沿用Contract；失败非零、有界等待、不伪造ready、不杀冲突进程 |
| Evidence / Testability | Shell行为可通过假Docker验证；隔离项目验证初始化；真实浏览器新增外部Compose模式，避免既有Playwright webServer实际测到宿主入口 |
| Complexity / Alternative | Shell只封装运行编排，不复制业务；已比较基础Compose直接扩展及Dev Container方案，不建设新Framework / Service / Port / 发布平台 |
| Recovery / Delivery | 现有volume不迁移；停止应用后可回本机模式。生产流量与升级不在范围，发布与清理仍按仓库独立授权 |

## Reference

已读取本 Skill 的 Architecture Knowledge Core：生命周期成本、变化轴、依赖方向、Observable Behavior、Failure / 状态、Design Twice、迁移和 Overengineering Guard 等相关章节。新增部署形态没有新增业务架构依赖。

## Evidence Sources

- [Architecture](../../docs/architecture.md)、[产品范围](../../docs/product-scope.md)、[Bootstrap](../../docs/specs/bootstrap.md)、[Web Spec](../../docs/specs/web-dialogue-v1.md)、[Runbook](../../docs/runbook.md)。
- [基础 Compose](../../docker-compose.yml)、[Dev Container](../../.devcontainer/devcontainer.json)、[环境模板](../../.env.example)、[Vite](../../frontend/vite.config.ts)、[Python依赖](../../pyproject.toml)、[前端依赖](../../frontend/package.json)。
- [API配置加载](../../src/query_api/config.py)、[Bootstrap命令](../../src/bootstrap/commands.py)、[管理员及migration](../../src/bootstrap/control.py)、[模型准备](../../src/bootstrap/model.py)。
- [真实浏览器配置](../../frontend/playwright.real.config.ts)、[真实浏览器测试](../../frontend/tests/real.spec.ts)、[账号支持](../../tests/browser_real_support.py)、[参考值](../../tests/browser_real_reference.py)、[现有Dev Container回归](../../tests/scripts/test_devcontainer_config.py)。

本次没有构建镜像、执行真实API、下载模型或初始化数据。PASS表示设计可进入拆分，不表示运行已通过或取得实施授权。

Next: `workflow-to-tickets`，随后当前上下文执行 `workflow-ticket-readiness`。

## 实施中复核

Review: PASS（模型挂载目标修订，2026-10-03）

Signal: 原固定模型挂载目标与既有资产身份不兼容。
Evidence: `src/online_query/retrieval/rag_runtime.py`的`_validate_manifest`检查路径；现有ignored manifest记录主机模型绝对路径，真实容器查询503；隔离新建索引则通过。
Impact: 相同权重和索引在新增入口中不可复用，违反已确认Spec；静默改manifest或放宽校验会破坏来源边界。
Recommendation: 仅在运行编排中保留模型源绝对路径作为容器目标并同步环境变量，不改业务代码、来源或索引。设计已明确修订，依赖 / 生命周期 / Secret边界维持；不新增用户决定。

Next: 按修订映射继续实施，并重新验证真实旧资产复用。
