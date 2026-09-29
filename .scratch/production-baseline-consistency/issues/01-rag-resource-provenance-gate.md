# RAG 资源指纹与生产就绪门禁

Status: done
Owner: ChatBI 仓库维护者
Backup Owner: None
Blocked by: None (can start immediately)

## Change Profile

- Lifetime: 长期维护的 RAG 发布资产与在线就绪校验。
- Size: M，涉及 RAG Offline Build、Online Retrieval 和 PostgreSQL Schema 校验。
- Risk: 高；不一致会导致在线 SQL 上下文与实际数据库结构或指标口径不匹配。
- Evidence: 确定性指纹测试、运行时拒绝边界、真实 PostgreSQL / Qdrant 验收。
- Delivery: 在本 Feature branch 中独立实现；最终按仓库高风险链路规则验收。

## Canonical Source

- 行为 Contract：`../spec.md`。
- RAG 输入 Contract：`docs/specs/rag-offline-build.md`。
- 在线故障边界：`docs/architecture.md`、`docs/specs/online-retrieval.md`。
- 期望 Schema：`database/` 中的 DDL；实际生效 Schema：PostgreSQL catalog；RAG 结构输入：从实际数据库导出的 `src/structure/generated/`。
- 指标事实：`src/semantic/metrics.json`。
- Qdrant manifest 和发布指针是派生资产，不是业务事实源。

## What to build

为一次 RAG 构建记录可复算的来源指纹，至少覆盖构建实际使用的 Structure Metadata、Semantic Metrics、Embedding 模型 / revision / 维度及必要配置。生产服务进入 Ready 前，比较实际 PostgreSQL catalog 结构、导出的结构 Metadata、指标输入与当前 Qdrant 发布资产的来源身份。

当来源缺失、无法核验或不匹配时，生产服务不得进入可服务状态或接受在线查询；不得使用陈旧索引或静态上下文回退。既有在线 Retrieval fail-closed 行为和显式静态测试 / Evaluation 模式保持原 Contract。Schema 变更后需先按 DDL → 数据库 → 导出 JSON 的顺序更新，再重建并验证索引。

## Acceptance criteria

- 相同规范化输入产生相同指纹；任一纳入指纹的 Schema、Metadata、Metrics 或关键 Embedding 配置变化会产生不同指纹。
- 实际 PostgreSQL catalog 与 Metadata 的结构投影可确定性比较；表、列、类型、键和关系等结构差异可以被发现。
- 指纹存在且所有来源匹配时，生产 Ready 门禁通过，在线 Retrieval 可读取当前发布资产。
- 指纹缺失、旧 manifest 无来源指纹、来源文件改变、数据库结构不匹配、Qdrant 发布资产缺失或不可验证时，生产 Ready 门禁失败且在线查询不可用；静态评测模式不因此被误判为生产可用。
- 生产错误可定位失败来源，但不泄露 Secret 或连接凭据。
- 构建新版本失败时，当前发布指针和既有完整版本保持不变。
- RAG Spec / Design 和必要的 Runbook 说明指纹范围、重建时机和失败行为；不重复维护另一份指标或 Schema 真相。

## Owned files

- `src/rag_offline/` 中的来源读取、构建 manifest 和发布校验代码。
- `src/online_query/retrieval/` 中的 RAG 资产加载与生产 Ready / 请求拒绝边界。
- `tests/rag_offline/`、`tests/online_query/` 中对应测试。
- `docs/specs/rag-offline-build.md`、`docs/designs/rag-offline-build.md`，以及必要的 `docs/architecture.md` / `docs/runbook.md`。

## Validation evidence

- 确定性测试覆盖稳定指纹和各个输入变化导致的指纹变化。
- 测试匹配、缺失、旧版本、无法读取及各类不匹配来源下的 Ready / 在线请求行为。
- 在真实本地 PostgreSQL 和 Qdrant 上，从当前输入构建索引并验证就绪；修改 Metadata 或使用不匹配 Schema 后验证服务 fail closed；重建匹配索引后恢复。
- 验证构建失败不会替换当前发布指针，静态测试路径未被生产路径误用。

## Migration / Rollback

- 旧 manifest 不含来源指纹时不能作为已验证生产资产；须构建并发布匹配当前输入的新索引后再恢复生产就绪。
- 保留旧的完整 Qdrant 版本用于人工恢复，但不能因旧指针仍存在就绕过指纹校验。
- 回滚代码不得自动切换到未经验证的旧索引；恢复服务前重新验证索引与数据库 / Metadata / Metrics 的一致性。

## Done When

生产服务只会在当前 PostgreSQL Schema、Structure Metadata、Metrics 和已发布 Qdrant 资产可验证匹配时进入 Ready；任何失配都可观察地 fail closed，并有确定性测试和真实服务验收证据。

## Result

已完成。RAG manifest 现在记录 Schema Metadata、Metrics、Embedding 配置及组合指纹；production 运行时拒绝旧 manifest 或来源不匹配的资产，并在 API 启动时以只读身份比较 PostgreSQL catalog 与结构 Metadata。新增 RAG Spec、设计文档和 Runbook 的门禁与重建说明。

验证证据：

- 针对性测试：32 passed，3 subtests passed。
- CI 规则对应的 Ruff 检查通过；`git diff --check` 通过。
- 使用本地 PostgreSQL / Qdrant 和当前 BGE-M3 输入构建并发布 `provenance-20260929`，计数 TABLE=7、COLUMN=69、METRIC=7、关系边=9。
- production 资源预检通过；manifest 含四项 SHA-256 指纹。
- 使用临时拷贝篡改表 metadata 后，以真实只读 PostgreSQL catalog 比较成功拒绝该差异；未修改仓库 metadata 或数据库。

## Comments

- 指纹编码格式、结构规范化细节和 Ready 检查的代码落点交实现设计确定，不得弱化已确认的 fail-closed Contract。
