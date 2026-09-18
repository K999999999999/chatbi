# Multi-Turn Query V1（受控多轮查询）验收记录

验收记录日期：2026-09-19
对应 Feature Spec：`.scratch/multi-turn-conversation-v1/spec.md`
对应 Ticket：`.scratch/multi-turn-conversation-v1/issues/04-multiturn-evaluation-acceptance.md`
实现 Commit：`ef1546794e61291728f14aa22816a073251863ff`
验证时 `git_dirty=true`；工作区包含本地 Feature 规划、Architecture、Spec、验收记录和工作记录修改，不包含 Secret。

## 一、分层结论

| 证据层 | 结论 | 说明 |
|---|---|---|
| Software Test（软件测试） | PASS | 多轮 API、会话生命周期、失败状态、授权、Streamlit 当前会话和新建会话均有确定性测试；全量回归通过。 |
| AI Evaluation（AI 评测） | NOT RUN | 本 Ticket 未调用真实 LLM、Qdrant 或 PostgreSQL；没有生成真实模型准确率或 Execution Accuracy 结论。 |
| Business Acceptance（业务验收） | NOT RUN | 本 Ticket 完成了可重复的确定性交互验收，但没有把 Mock/TestClient 结果冒充真实业务用户和真实数据确认。 |
| Real E2E（真实端到端） | NOT RUN | 未执行真实三轮 LLM → RAG → SQL Guard → PostgreSQL 链路；需要单独授权。 |

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

本次未执行以下真实评测命令：

```text
uv run --env-file .env python -m src.evaluation --online-retrieval
```

原因：该命令会发送测试问题以及结构和指标上下文到真实 LLM，并访问本地 RAG 资产与 PostgreSQL；按照项目边界，需要单独授权。当前没有 AI Evaluation 报告、真实 21 条案例结果或多轮真实准确率结论。

确定性 Evaluation 测试属于 Software Test，不能替代本节的真实 AI Evaluation。

## 四、Business Acceptance 证据

当前已具备可重复的交互行为证据：

1. 首轮查询建立当前会话；
2. 第二轮增加维度并保留上一轮时间条件；
3. 第三轮替换指标并保留上一轮维度和时间条件；
4. 澄清、范围拒绝和失败后仍可基于最后一次成功状态继续；
5. 会话失效后用户必须新建会话，页面不会静默复用旧会话。

上述证据来自确定性 API / Streamlit 测试替身，不是业务人员使用真实页面和真实数据完成的确认。因此真实 Business Acceptance 仍为待执行项，不能据此声称业务口径和真实数据结果已经验收。

## 五、剩余验收门槛

- 在单独授权后，执行真实三轮 E2E，并记录真实 LLM、RAG、SQL Guard 和 PostgreSQL 结果；
- 如需完整 AI Evaluation，执行 21 条标准案例，并单独记录模型、运行 Commit、`git_dirty`、结果报告和失败案例；
- 由业务方确认真实三轮场景中的指标、时间、维度继承和失败恢复行为；
- 真实验收通过后，仍需独立完成企业 Production Readiness，包括真实 SSO、持久化审计、限流、性能、部署、监控和回滚。
