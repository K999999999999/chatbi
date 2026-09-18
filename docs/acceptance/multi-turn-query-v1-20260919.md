# Multi-Turn Query V1（受控多轮查询）验收记录

验收记录日期：2026-09-19
对应 Feature Spec：`.scratch/multi-turn-conversation-v1/spec.md`
对应 Ticket：`.scratch/multi-turn-conversation-v1/issues/04-multiturn-evaluation-acceptance.md`
实现 Commit：`ef1546794e61291728f14aa22816a073251863ff`
真实 AI Evaluation 测试 Commit：`a8356109c6b353b79f2827dfaa9059a79bb1d60d`，报告记录 `git_dirty=false`。
验收完成后恢复了本地 Feature 规划、Architecture、Spec 和工作记录修改；这些本地修改不属于真实评测 Commit，且不包含 Secret。

## 一、分层结论

| 证据层 | 结论 | 说明 |
|---|---|---|
| Software Test（软件测试） | PASS | 多轮 API、会话生命周期、失败状态、授权、Streamlit 当前会话和新建会话均有确定性测试；全量回归通过。 |
| AI Evaluation（AI 评测） | PASS | 真实 21 条标准案例通过，Execution Accuracy 为 `100.00%`；报告记录 `21/21`、`git_dirty=false`。 |
| Business Acceptance（业务验收） | NOT ACCEPTED | 确定性测试通过，但真实三轮场景第二轮失败，尚不能由业务方确认多轮维度继承和真实数据结果。 |
| Real E2E（真实端到端） | FAIL | 真实三轮已执行：第一轮 `200`，第二轮 `422 CANNOT_ANSWER`，第三轮虽为 `200`，但实际基于第一轮状态，不能算完整三轮通过。 |

本记录证明的是当前 Commit 的确定性软件行为，不代表 Multi-Turn Query V1 已达到面向所有企业用户的 Production Ready（生产可用）状态。

## 二、Software Test 证据

### 2.1 关键多轮回归

命令：

```text
uv run --with pytest python -m pytest -q tests/query_api/test_multi_turn_revision.py tests/query_api/test_conversation.py tests/query_api/test_app.py tests/streamlit/test_streamlit_app.py
```

结果：`47 passed, 21 subtests passed`。

覆盖范围：

- 首轮成功创建会话，后续连续三轮增加维度并替换指标；
- 澄清和超出范围请求不执行查询、不修改最后一次成功状态；
- 下游失败后保留最后一次成功状态；
- 每一轮重新执行当前授权，权限变化后不能继续越权查询；
- 会话状态提交、失败回滚、30 分钟 TTL、服务重启失效、用户隔离和并发冲突；
- Streamlit 三轮连续请求只携带新问题和不透明 `conversation_id`；
- 会话失效后清理旧 ID，在点击“新建会话”前不会静默再次调用 API；
- 新建会话后不再复用旧 ID，新增响应字段不破坏原有结果展示。

### 2.2 全量回归与工程门禁

命令：

```text
uv run --with pytest python -m pytest -q
```

结果：`356 passed, 6 skipped, 118 subtests passed`。

其他门禁：

- `uv run --with ruff==0.16.8 ruff format --check src tests`：通过；
- `uv run --with ruff==0.16.8 ruff check --select E4,E7,E9,F src tests`：通过；
- `python -m compileall -q src tests`：通过；
- `git diff --check`：通过，只有既有 Windows 换行符提示。

### 2.3 Streamlit 运行时烟测

使用 `uv run streamlit run src/streamlit_app.py --server.headless true --server.port 8502` 启动页面，访问 `http://127.0.0.1:8502/_stcore/health` 返回 `ok`。临时进程已停止，端口已释放。

该烟测只证明页面可以启动，不证明真实查询链路、模型准确率或数据库业务结果。

## 三、AI Evaluation 证据

本次已执行以下真实评测命令：

```text
uv run --env-file .env python -m src.evaluation --online-retrieval
```

结果：`PASS`，`Execution Accuracy: 100.00%`，`PASS: 21, FAIL: 0, INVALID_CASE: 0`。

报告：

- JSON：`reports/evaluation/20260918T163056Z-a835610.json`；
- Summary：`reports/evaluation/20260918T163056Z-a835610.md`；
- 报告 Commit：`a8356109c6b353b79f2827dfaa9059a79bb1d60d`；
- 报告 `git_dirty`：`false`；
- 真实链路：LLM、已发布 RAG 资产、SQL Guard 和本地 PostgreSQL。

确定性 Evaluation 测试属于 Software Test，不能替代本节的真实 AI Evaluation。

## 四、Real E2E 证据

真实 HTTP 三轮场景使用的问题为：

1. `2025 年第一季度的人民币销售额是多少？`；
2. `按销售区域拆开`；
3. `改看毛利率`。

结果：

- 第一轮返回 `200`，创建了 `conversation_id`；
- 第二轮返回 `422`，公开错误码为 `CANNOT_ANSWER`；
- 由于第二轮失败，会话状态按 Contract 保留上一轮成功状态；第三轮返回 `200`，但它不是“已按销售区域分组后再替换指标”，因此不能计入三轮业务通过。

只读定位显示，第二轮的确定性 Retrieval 重放返回 `PARTIAL_UNREACHABLE`：带有时间条件和“销售区域”维度时，默认 `table_top_k=5` 的 TABLE 候选没有包含指标 `time_field` 所需的 `mart_sales.dim_date`。临时将 `table_top_k` 提高到 `7` 后，同一结构化查询返回 `SUCCESS`，Join 路径完整。该对照只证明了当前失败机制，不代表已经批准或完成参数修复。

本次 HTTP 验收启动时发现本地 `.env` 没有显式身份配置；运行期间只注入了进程级非 Secret 配置 `CHATBI_ENV=development`、`CHATBI_IDENTITY_PROVIDER=test`、`CHATBI_IDENTITY_SUBJECT_ID=analyst-1` 和示例授权策略路径，未修改 `.env`。服务已停止，端口已释放。

## 五、Business Acceptance 证据

当前已具备可重复的交互行为证据：

1. 首轮查询建立当前会话；
2. 第二轮增加维度并保留上一轮时间条件；
3. 第三轮替换指标并保留上一轮维度和时间条件；
4. 澄清、范围拒绝和失败后仍可基于最后一次成功状态继续；
5. 会话失效后用户必须新建会话，页面不会静默复用旧会话。

上述证据来自确定性 API / Streamlit 测试替身，不是业务人员使用真实页面和真实数据完成的确认；而真实三轮 E2E 当前也未通过。因此真实 Business Acceptance 仍未完成，不能据此声称业务口径和真实数据结果已经验收。

## 六、剩余验收门槛

- 针对 `table_top_k` 导致的必需时间维度表丢失问题完成最小修复，并补充“时间条件 + 销售区域维度”的确定性回归；
- 修复后重新执行真实三轮 E2E，确认第二轮成功提交新语义状态，再确认第三轮基于该状态替换指标；
- 由业务方确认真实三轮场景中的指标、时间、维度继承和失败恢复行为；
- 真实验收通过后，仍需独立完成企业 Production Readiness，包括真实 SSO、持久化审计、限流、性能、部署、监控和回滚。
