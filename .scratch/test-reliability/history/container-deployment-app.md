# 历史：标准 APP 容器 Contract

> 历史快照：本规范记录独立业务 APP 镜像路线仍受支持时的行为。用户于 2026-10-15 确认移除此路线；当前本地源码运行边界见[正式 Spec](../../../docs/specs/container-deployment.md)。以下保留原 Contract 事实，不是现行操作说明。

ChatBI以源码交付。日常开发与体验统一使用容器开发入口；当时根Dockerfile和`docker-compose.app.yml`提供打包应用的标准本地构建与运行能力。没有预构建镜像发布、升级、回滚、备份或恢复系统。

当时统一使用`./dev app build/up/down/status/logs/infra/migrate/create-admin/prepare-model/build-rag/check`。app是打包运行方式，默认.env，CHATBI_APP_ENV_FILE/CHATBI_APP_COMPOSE_OVERRIDE可选配置，资源与dev独立。build显式构建；up不隐式构建或初始化；down停止保留卷；migrate先基础初始化、后迁移及完整健康。app check委派Bootstrap只读verify；verify app委派空卷真实验收，包含LLM费用 / 报告 / 清理。

- Dockerfile api target包含后端、网页、导出资源、Chromium及字体；database target包含既有演示数据初始化。标准Docker缓存可用，构建不要求Git发布登记或release文件。
- 应用Compose只包含API、PostgreSQL、Qdrant及tools/migrator。项目卷独立管理，默认不引用已有开发或旧Stable资源。
- 首次顺序为配置、构建、基础设施、基础初始化、migration、管理员、模型、RAG、只读verify、API。完整PostgreSQL健康检查依赖migration，migrator不能反过来依赖完整healthy。
- API运行不自动初始化或重建资产，不持有迁移凭据；模型和RAG工具写入资产卷，API以非root身份只读挂载。
- API / PostgreSQL / Qdrant使用`unless-stopped`：Docker重启后恢复此前运行的服务，主动停止后保持停止直到再次`up`。tools / migrator保持`restart: "no"`。
- verify检查签名Key、LLM配置、数据库 / 管理员、模型与RAG来源、catalog、网页及导出资源。

Sales Mart与Control DB结构、角色和grants不变；业务只读账号与控制数据账号隔离。Seed仅在首次空环境 / 显式开发重置场景创建。仅回环HTTP，单API进程；Cookie / CSRF / Origin、权限、SQL Guard、应用运行锁与执行保护保持。Secret不进入构建上下文、镜像或报告；保留Chromium sandbox与seccomp。

当时的支持边界为本地Windows+WSL/Linux Docker环境；不承诺公网生产、多worker / 副本或容量 / 延迟。企业发布运维由部署方负责，项目不集成外部发布平台。旧Stable配置、卷、备份及密钥不自动迁移或删除。

当时验收范围包括保留Dockerfile targets构建、独立空卷初始化、健康 / 就绪、实际业务闭环、持久性、失败保护、资源隔离与Secret边界。历史 Runbook 与候选验收仍保存在各自工作项记录中。
