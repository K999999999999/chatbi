# 本地源码运行边界

ChatBI 当前以源码方式开发和体验。唯一受支持的本机运行入口是容器开发环境 `./dev`；仓库提供的 Python / Node 镜像用于开发依赖、测试和构建工具，不构建独立业务 APP 镜像。

日常初始化、运行、Software Test、AI Evaluation 和按需业务验收入口见 [Runbook](../runbook.md)。API、认证、授权、SQL Guard、数据角色、应用就绪与请求保护仍按各自 Contract 工作；移除 APP 镜像路线不改变这些运行时行为。

已存在的 APP 容器、镜像、卷、配置和资产不会被仓库命令自动删除或迁移。开发维护入口拒绝将旧 APP Compose 资源当作当前 dev 目标。旧打包运行 Contract 保存在[历史归档](../../.scratch/test-reliability/history/container-deployment-app.md)，不构成当前支持入口。
