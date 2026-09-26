# 统一 Dev Container 与 WSL / Linux 开发入口

Status: done
Owner: ChatBI 仓库维护者
Backup Owner: None
Blocked by: 01-local-postgres-test-isolation, 02-postgres-development-environment, 03-qdrant-index-rebuild, 04-evaluation-data-fingerprint

## Change Profile

- Lifetime: 短期，新 clone Onboarding 和双入口验收。
- Size: M。
- Risk: 中；涉及 Dev Container 生命周期、Docker Compose 项目身份和持久 volume 使用方式。
- Evidence: 两种入口的干净 clone 验收、Dev Container rebuild 前后数据保持验证。
- Delivery: 当前 Feature branch 上的最后集成切片；不改变生产运行逻辑。

## Canonical Source

- 行为基线：`../spec.md`。
- 开发命令和恢复方式：`docs/runbook.md`。
- Dev Container 配置：`.devcontainer/devcontainer.json` 及其 lock 文件。

## What to build

以 Dev Container 作为推荐标准入口，并支持 WSL / Linux 本地开发。两者共用 `uv`、`.env`、Docker Compose、PostgreSQL 初始化、自动测试和显式 RAG 索引构建流程；只在必要的路径或容器 / 宿主机连接端点处记录差异。

明确 Rebuild Dev Container 只重建开发工作区容器，不能删除或重置 PostgreSQL / Qdrant named volume。更新 Runbook，说明从干净 clone、日常启动、管理员创建、测试、索引构建、数据库重置和索引重建的完整操作路径。

## Acceptance criteria

- Dev Container 和 WSL / Linux 本地环境均可从干净 clone 按同一套依赖、配置、Compose 和 PostgreSQL 初始化流程建立环境。
- 两种入口有明确且一致的 PostgreSQL、Qdrant、应用和 `.env` 连接配置说明。
- Rebuild Dev Container 后 PostgreSQL 与 Qdrant named volume 中的数据 / 索引仍然可用。
- PostgreSQL 重置和 Qdrant 清除仍为独立操作，普通启动、关闭或重建 Dev Container 不会调用删除数据卷的操作。
- Runbook 清楚区分首次初始化、日常启动、自动测试、黄金评测和显式重建 / 重置；不依赖 W11 路径或手工运行大量 SQL。
- 全流程不把 `.env`、真实 Secret、PostgreSQL / Qdrant 物理数据或 Embedding 权重加入 Git。

## Owned files

- `.devcontainer/devcontainer.json`
- `.devcontainer/devcontainer-lock.json`（如配置变化需要更新锁定 Feature）
- `docs/runbook.md`（新 clone 总流程和两种入口）
- 与 02、03 配置集成所需的最小入口配置；具体改动仍限定在已确认的 Spec。

## Validation evidence

- Dev Container 新 clone：准备本地 `.env`、`uv sync`、`docker compose up`、数据库自动初始化、显式 RAG build、确定性测试和应用启动检查。
- WSL / Linux 新 clone：使用同一流程完成对应基础设施和应用启动检查。
- 在 Dev Container rebuild 前后分别验证 PostgreSQL 和 Qdrant 数据仍可访问；单独 PG reset / Qdrant clear 时验证只删除目标 volume。
- 真实 LLM Evaluation 不自动运行；如需作为最终业务验收，遵循仓库独立授权流程。

## Migration / Rollback

- 不迁移、复制或删除 W11 旧项目的 PostgreSQL / Qdrant 目录。
- 回滚 Dev Container / Runbook 配置不删除 named volume；任何数据删除仅通过各自明确的重置流程执行。

## Done When

新开发者能够使用 Dev Container 或 WSL / Linux 从干净 clone 恢复完整开发环境；两种入口的开发流程清晰一致，重建 Dev Container 不造成数据丢失。

## Result

Dev Container Compose profile 和 WSL/Linux 宿主入口均完成 `uv sync` / 数据库与 Qdrant 启动、开发初始化、隔离测试、索引构建及应用健康检查。另从最终 Feature 提交实际创建 clean clone；其 `.env`、旧 `data/postgres` / `data/qdrant` 和模型缓存均缺席。按 `.env.example` 准备本地配置后，PostgreSQL、Qdrant、Git 源资产索引、Query API 和 Streamlit 均通过健康检查。Force-recreate 专用 `devcontainer` 服务后，PostgreSQL 数据指纹和 Qdrant 已发布索引继续可用；PG 与 Qdrant 的独立 reset 边界也分别实测。环境中没有 `devcontainer` CLI，因此通过 Compose 对同一 Dev Container 服务执行 force-recreate 验证重建的数据卷边界；未单独通过 VS Code 命令面板触发 Rebuild。最终确定性回归 `489 passed, 12 skipped, 123 subtests passed`，格式与 CI lint 检查通过。

## Comments

- 当前 Dev Container 的 `postCreateCommand` 会安装锁定版本 `uv` 并执行 `uv sync --locked`；当前 Compose 服务仍单独启动。此 Ticket 负责把二者组织成 Spec 确认的共同开发入口，不重复实现数据库或 RAG 初始化逻辑。
