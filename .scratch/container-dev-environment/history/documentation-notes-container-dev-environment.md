# 容器开发环境：整理前的过程记录

来源：`docs/specs/container-dev-environment.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 整理前入口说明

# 本地容器开发运行 Contract

适用入口：WSL / Linux 的 Git、Bash、Docker Engine / Compose。容器安装 Python / uv / Node 与仓库锁定依赖；推荐开发入口为根目录 `./dev`，原宿主开发入口继续支持。此文档由开发运行配置的维护者同步维护，生产部署属于 R6。
