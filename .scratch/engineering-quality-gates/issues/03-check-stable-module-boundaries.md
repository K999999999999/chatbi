# Ticket 03：在 CI 检查已声明的模块依赖边界

Status: done

## Owner

ChatBI 仓库维护者负责验收；当前实施 Agent 负责实现。

## Blocked by

None (can start immediately)

## Change Profile

- Lifetime: 长期维护的架构回归门禁。
- Size: 中等，新增有限的确定性依赖检查并接入 CI。
- Risk: 中；误编码边界可能拒绝当前合法的模块组装方式。
- Evidence: 依赖违规正反例测试和 CI 结果。
- Delivery: 与同一 Feature 的其他 Ticket 使用同一 branch 和 PR；与 Ticket 02 共用 CI workflow 文件，顺序实施以减少冲突。

## What to build

把 `AGENTS.md` 和 `docs/architecture.md` 已明确、且可从 Python 模块依赖关系客观判断的少量边界加入确定性 CI 检查。首批范围限定为：

- Streamlit 页面只通过 HTTP 调用 Query API，不直接依赖在线查询、LLM、SQL Guard 或数据库实现。
- `src/query_api/app.py` 不直接装配 LLM、Query Executor、SQL Guard 或数据库执行器；`src/query_api/main.py` 是合法的 Composition Root（组装入口），不得被误判。
- `src/rag_offline/` 不依赖 PostgreSQL、Query API 或在线查询运行时实现。

该检查只守护源码依赖边界。业务逻辑是否重复、运行时是否经过授权链路等行为继续由现有测试和 Review 验证，不宣称由静态依赖检查覆盖。

## Acceptance criteria

- 上述禁止依赖在测试中被明确列出；合法组装入口有明确例外。
- 加入受禁止的 import 时检查失败，并指出发起模块和被依赖模块。
- 现有合法模块布局通过检查；没有新增 Clean Architecture 分层、通用 Plugin、架构检查框架或其他未来抽象。
- 规则来源可追溯至 `AGENTS.md` / `docs/architecture.md`；检查不创造新的业务或公共架构 Contract。
- 正反例测试通过，检查在普通 CI 的 Push / Pull Request 路径运行。

## Owned files

- `.github/workflows/ci.yml`
- `scripts/check_module_boundaries.py`
- `tests/architecture/` 中的模块依赖边界测试。

## Verification evidence

- 对允许与禁止的模块依赖分别提供确定性验证。
- 确认 `src/query_api/main.py` 合法装配没有被规则误报。
- 在普通 CI 中执行边界检查；不运行真实 LLM 或数据库。

## Migration / Rollback

无运行时 Migration。若发现现有 Contract 与检查规则冲突，停止并返回 Spec / Design Review；不得为让检查通过而静默改变模块职责。可回退该 CI 检查，不改变运行时行为。

## Done When

静态依赖检查只覆盖上述可判定边界，合法代码通过、反例失败且提示清楚，并由普通 CI 执行。

## Result

已实现来源受 `AGENTS.md` / `docs/architecture.md` 约束的 AST import 检查，只覆盖 Streamlit、Query API Adapter、RAG Offline Build 已确认的直接依赖边界；`query_api/main.py` 组装入口明确豁免。当前源码检查和允许 / 禁止依赖测试通过，错误会报告发起文件及被禁止模块。

## Comments

None.
