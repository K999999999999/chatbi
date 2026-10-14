# 常驻容器自动恢复短 Spec

## 目标与授权

用户在本会话确认采用 `unless-stopped`：常驻服务首次启动后随 Docker 恢复，主动停止后保持停止；构建和初始化仍通过命令显式执行。该稳定小范围指令同时授权本地实现、适用验证及本地 Commit，未授权 Push / PR。

## 范围与行为

- 开发环境 API / Web / PostgreSQL / Qdrant，以及标准应用 API / PostgreSQL / Qdrant 使用 `unless-stopped`。
- tools / migrator 等一次性工具保持 `restart: "no"`；不自动构建、迁移、创建管理员或重建模型 / 索引。
- `./dev up` / `./dev down` 保留启动就绪检查、显式停止与数据保留语义。
- 验证依赖晚启动后的 API / Web 恢复，必要时在容器启动边界补齐等待；保留热重载、身份、SQL Guard、历史与业务执行规则。
- 开发API使用有界控制库等待入口，随后以exec启动既有Uvicorn热重载命令；不在Domain/Application引入重试或运维逻辑。
- 应用当前开发容器配置并启动本项目完整服务；不重启整机 / Docker daemon，不修改 Docker Desktop 开机设置，不操作旧 Stable / Restore 数据。

## 验收

- 两种 Compose 实际解析后的常驻 / 一次性服务策略符合上述规则。
- 已有开发入口回归通过；覆盖停止保留数据与失败传播。
- 当前开发环境启动成功，HTTP /ready 与网页可用；依赖延后启动时可恢复，不要求人工修改源码触发重载。
- 有隔离容器运行证据检查正常退出自动恢复、主动停止保持停止；整机 / Docker daemon 重启未执行时明确记录。
- README / Runbook / 正式容器 Spec 同步当前行为，检查文档链接、Diff 和当前上下文 Code Review。

## 基线

BASE: `38e1302ce33d999dc908419067bc5d39195f86cf`；初始 master / origin/master 一致、工作区干净，唯一 worktree。工作分支 `fix/container-auto-restart`。

## 验证边界

不调用真实 LLM、不重跑业务 AI Evaluation；此次只改变容器生命周期。Docker Desktop 自动启动是本机独立设置，本次不修改。

当前开发环境的既有RAG资产记录`devices=null`，与容器固定`devices=cpu`不一致；为恢复真实就绪，本次显式执行`./dev build-rag`发布匹配CPU配置的新资产。旧资产保留，不改Semantic、Metadata或业务数据；这不是自动恢复流程的一部分。
