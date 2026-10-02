## 目标

<!-- 这个 PR 解决什么问题？完成后用户或系统会有什么变化？一个 PR 只写一个清晰目标。 -->

## 改动范围

<!-- 列出主要模块、文件或 Contract（契约）变化。明确说明没有包含哪些无关内容。 -->

- 

## 变更类型

- [ ] 新功能（Feature）
- [ ] Bug 修复（Bug Fix）
- [ ] 重构（Refactor）
- [ ] 测试（Test）
- [ ] 文档 / CI / 工程维护（Docs / CI / Maintenance）

## 风险与兼容性

- 影响的接口、数据、配置或行为：
- 是否涉及 Retrieval、Prompt、Semantic、RAG、Embedding、Qdrant、LLM、Evaluation cases 或 SQL 生成链路：
- 回滚方式或注意事项：

## 合并计划

- PR 类型：独立 / 依赖（依赖 PR 填写 parent PR 与最终 base）
- 自动合并：按目标仓库策略；依赖条件满足前保持 Draft
- 发布授权已在聊天中明确取得；本栏用于记录，不代替聊天授权

## 验证结果

### 代码

- [ ] Format（格式检查）
- [ ] Lint（静态规范检查）
- [ ] Type-check（类型检查；当前未配置为 blocking gate 时填写 N/A）

### 逻辑

- [ ] Unit tests（单元测试）
- [ ] Deterministic tests（确定性测试）
- [ ] SQL Guard tests（SQL 安全校验测试）
- [ ] AI Evaluation（AI 评测；仅在相关改动时执行）
- [ ] Business Acceptance（业务验收；适用时执行）
- [ ] Real E2E（真实端到端；仅在高风险改动时执行）

### 集成

- [ ] 模块链路测试
- [ ] API test（API 测试）
- [ ] PostgreSQL integration（PostgreSQL 集成测试）
- [ ] 其他外部服务集成测试：

### 运行

- [ ] Application startup smoke（应用启动 Smoke Test）
- [ ] Health check（健康检查）
- [ ] Docker build（Docker 构建；适用时）

### 安全

- [ ] Dependency audit（依赖审计）
- [ ] Secret scan（Secret 扫描）
- [ ] Static security scan（静态安全扫描）
- [ ] 未提交真实 API Key、Token、Password、Connection String 或其他 Secret

### 命令与结果

```text
# 填写实际执行的命令和关键结果，例如：
# uv run --with pytest python -m pytest -q
# 297 passed, 6 skipped
```

## 数据库、配置与文档

- [ ] 不涉及数据库 / 配置 / 文档变化
- [ ] 已同步更新数据库迁移或配置说明
- [ ] 已同步更新相关 Spec、Runbook 或 README
- [ ] 已核对 `docs/roadmap.md`，记录更新位置或不适用理由；优先级或范围变化已有用户确认

- 路线图更新位置 / 不适用理由：

## Agent Review Checklist

<!-- Agent 自检记录，不构成额外的用户 PR Review 门禁。 -->

- [ ] 这个 PR 只有一个清晰的业务或工程目标
- [ ] 相关测试已经补充或更新
- [ ] LLM 输出仍由 Contract 和确定性代码裁决
- [ ] 关键错误使用稳定的机器可读 Error Code（错误码）
- [ ] 没有混入无关重构、清理或未来功能
- [ ] 已说明未执行的验证及原因

## Agent 交付跟进

<!-- PR 创建或更新后记录真实状态。共享本机状态与聊天交接仍须同步，PR 正文不作为唯一提醒。 -->

- 最近核实时间：
- PR / head / base / commit：
- required checks 与失败原因：
- Auto-merge 状态：
- 等待条件 / 下一步：
- 聊天交接已发送：是 / 否 / 不适用

## 合并后 Harness 复盘

<!-- PR 合并后填写。检查 Agent 是否因项目背景、规则、工具或验证方式不足而误解、漏验、返工或需要用户纠正。 -->

- 复盘结论：无新增缺口 / 发现缺口
- 观察到的问题与根因：无 / 描述
- 后续 Harness 改进项：N/A / 链接
- 合并事实对路线图的影响及更新位置 / 不适用理由：
