# 初始化入口与运行资源生命周期

## 范围和职责

`src/bootstrap/` 是应用的集中装配边界，统一运行资源生命周期和显式初始化命令。它不定义业务真相，也不改变各模块的业务职责；具体数据库迁移、索引构建和模型适配仍由所属模块实现。业务模块不依赖 bootstrap。

## 运行资源

- 导入 `src.query_api.main` 或 bootstrap 模块不加载配置、不打开外部连接、不创建模型运行资源和后台线程。
- `uvicorn src.query_api.main:app` 保持为服务启动入口。FastAPI lifespan 内加载配置并创建本轮运行资源，绑定到 HTTP Adapter；启动检查通过后才接收请求。
- 统一管理 Tracing、Control DB、模型 HTTP clients、查询服务、RAG Runtime、经营分析 engine / checkpoint pool / run store 和清理线程。
- Query Executor 保持逐查询连接与只读事务，不增加运行连接池；RAG 内部保持按需加载。
- Control DB Schema、checkpoint 和运行权限检查继续生效。production 必须启用 RAG，并通过既有来源指纹、集合与 PostgreSQL catalog 一致性检查；无法验证或不一致时拒绝启动。开发环境不额外强制预加载全部 RAG 资源。
- 资源取得后立即登记清理。局部构造失败释放已取得资源；启动失败仍保留原始原因，单个清理失败不跳过其余清理。清理诊断仅输出安全的阶段及异常类型。
- 应用关闭时按依赖逆序释放本轮持有资源，同步与异步 HTTP clients 在各自适用生命周期内关闭；重复关闭不重复释放，重复启动不复用已关闭资源或重复挂载 SQLAdmin。
- 直接注入服务的 `create_app(service, ...)` 仍可用于测试。调用者持有的 engine / recorder 不被接管；既有 analysis_service 关闭约定保留，应用自己创建的 fallback recorder 由应用关闭。
- 认证、授权、SQL Guard、Semantic、业务查询和经营分析行为遵循对应正式 Contract。

## 显式初始化命令

```text
python -m src.bootstrap migrate
python -m src.bootstrap create-admin [--username USERNAME]
python -m src.bootstrap prepare-model
python -m src.bootstrap build-rag [--structure-dir PATH] [--metrics-path PATH] [--output-dir PATH] [--build-id ID]
```

命令按操作加载依赖；帮助不初始化资源。外部环境变量优先于 `.env`，沿用各模块现有配置和参数。

| 命令 | 行为与失败边界 |
| --- | --- |
| migrate | 幂等建立 Control DB、固定 RBAC、checkpoint 和 grants；不创建管理员；成功 0、迁移失败 1 |
| create-admin | 隐藏输入密码并确认，显式创建首个管理员；已存在管理员时拒绝；成功 0、操作失败 1、两次密码不一致 2 |
| prepare-model | 下载固定 revision 的 BGE-M3 到既有缓存目录；成功且配置文件存在返回 0，失败返回 1，不输出凭据 |
| build-rag | 使用现有 builder 校验、构建、验证并原子发布；成功发布 0，未发布结果 1；构建异常仍报告失败，释放临时 Qdrant client 并保护已发布资产 |

缺少必需子命令、未知参数等解析错误返回 2，不加载运行配置。运行资源不使用迁移身份；管理员密码不进入参数、配置模板、Seed、文档或日志。

服务启动不自动运行这些命令，不重播 Seed。Compose、数据库 / Qdrant 重置与结构导出仍使用各自环境入口。

## 入口迁移

旧 `python -m src.chatbi_control`、`python -m scripts.prepare_embedding_model` 和 `python -m src.rag_offline` 命令入口已移除，不提供转发。模块业务 API 保留；当前文档、CI、测试和脚本统一使用 bootstrap。日期化 Acceptance、旧报告和历史规划保持原候选身份。

## 验证

生命周期与命令的软件测试在 `tests/bootstrap/`、Query API 及所属模块测试中；迁移、checkpoint 权限、管理员和完整 API 启动通过隔离 PostgreSQL development profile 验证。正常、局部失败、就绪失败、关闭抛错和重复启动必须有回归证据。模型 / RAG 命令测试使用替身，不隐式下载真实模型、调用 LLM 或写入开发索引。

操作步骤见 [Runbook](../runbook.md)，查询行为见 [Query API Spec](query-api.md)，索引发布规则见 [RAG Offline Build Spec](rag-offline-build.md)。
