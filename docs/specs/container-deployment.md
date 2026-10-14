# 标准容器运行

ChatBI以源码交付。日常开发与体验统一使用[容器开发入口](container-dev-environment.md)；根Dockerfile和`docker-compose.app.yml`提供打包应用的标准本地构建与运行能力。没有预构建镜像发布、升级、回滚、备份或恢复系统。

## 构建与初始化

- Dockerfile api target包含后端、网页、导出资源、Chromium及字体；database target包含既有演示数据初始化。标准Docker缓存可用，构建不要求Git发布登记或release文件。
- 应用Compose只包含API、PostgreSQL、Qdrant及tools/migrator。项目卷独立管理，默认不引用已有开发或旧Stable资源。
- 首次顺序为配置、构建、基础设施、基础初始化、migration、管理员、模型、RAG、只读verify、API。完整PostgreSQL健康检查依赖migration，migrator不能反过来依赖完整healthy。
- API运行不自动初始化或重建资产，不持有迁移凭据；模型和索引初始化工具写新建资产卷，API以非root身份只读挂载。
- API / PostgreSQL / Qdrant使用`unless-stopped`：Docker重启后恢复此前运行的服务，主动停止后保持停止直到再次`up`。tools / migrator保持`restart: "no"`；自动恢复不执行构建或初始化，依赖与资产仍需通过应用就绪门禁。
- verify保留至少32字符签名Key、非占位LLM配置的必要门禁，并检查数据库/管理员、固定来源模型与RAG、catalog、网页与导出资源，不管理发布兼容矩阵或部署状态。

## 数据与安全

- Sales Mart与Control DB结构、角色和grants不变；业务只读账号与控制数据账号隔离。
- Seed保留在首次空环境/显式开发重置场景；普通启动不重播。停止服务保留卷和资产。
- 仅回环HTTP，单API进程；Cookie/CSRF/Origin、权限、SQL Guard、应用运行锁与执行保护保持。
- Secret仅在本地配置或运行注入，不进入构建上下文、镜像或报告。保留Chromium sandbox与必要seccomp配置。

## 支持边界与验证

本地Windows+WSL/Linux Docker环境；不承诺公网生产、多worker/副本或容量/延迟。企业发布运维由部署方负责，本项目不集成外部发布平台。

旧Stable配置、卷、备份及密钥不自动迁移或删除。原R6/R7证据保留为历史，不作为当前操作入口。

验收包括所有保留Dockerfile target构建、独立空卷初始化、健康/就绪、实际业务闭环、持久性、失败保护、资源隔离与Secret边界。操作见[Runbook](../runbook.md)，应用保护见[就绪规则](application-readiness.md)。
