# Observability T5（可观测性 T5）验收记录

验收日期：2026-09-14

对应规格：`docs/specs/observability.md`

对应实现设计：`docs/designs/observability.md`

实现范围：T1～T4C 已提交实现；T5 为外部验收 Gate，不新增普通实现 Commit。

## 一、验收结论

结论：PASS（阿里云 OTLP / Trace 外部验收通过）。

Observability V1 已完成从 HTTP、Online Query、RAG、LLM、SQL Guard 到 PostgreSQL 的真实 Trace 验证。该结论不代表 Production Ready（生产可用）。

## 二、验收环境

- OpenTelemetry Python SDK。
- OTLP/HTTP Exporter。
- 阿里云 Trace / OTLP 接入。
- 服务名：`chatbi-engine`。
- 运行环境：`dev`。
- Trace 内容采集：关闭。
- Endpoint 和授权 Header 仅保存在本地 `.env`，未进入仓库。

## 三、验证结果

### 1. Endpoint 接入

- 配置开关已启用。
- OTLP Endpoint 使用 HTTPS。
- 阿里云 OTLP Header 已配置。
- 独立脱敏 OTLP 探针返回 `SUCCESS`。

### 2. C05 成功链路

- 请求：按客户类型统计已完成订单数、人民币销售额和毛利率。
- HTTP 状态：200。
- 返回行数：3。
- 结果未截断。
- `X-Trace-ID`：`eb14f55bbe07d6f15bdd69d48b440430`。
- 阿里云 Trace 控制台可查询该链路，服务名为 `chatbi-engine`，入口为 `query.request`。
- 已核对 RAG、LLM、SQL Guard、数据库和响应节点，以及 Generation 映射和主要耗时节点。

### 3. 受控失败链路

- 请求：空问题。
- HTTP 状态：400。
- 错误码：`INVALID_REQUEST`。
- `X-Trace-ID`：`92d99ceb7aa39d25140b444379eba6d5`。
- 阿里云 Trace 控制台可查询该链路，并能定位到请求校验节点。
- 该失败在继续调用 LLM 或数据库之前结束。

### 4. 评测不变性

- 真实在线 RAG Evaluation：20/20。
- 全量确定性测试：230 passed、6 skipped、79 subtests。
- 接入 Trace 后，C04/C05 业务结果核对保持通过。

## 四、安全核对

- 不提交 Endpoint、授权 Header、API Key 或其他 Secret。
- 不提交原始 Prompt、候选 SQL、最终 SQL 或结果行。
- Trace 内容采集保持关闭。
- 生产环境仍只允许查看固定状态、错误码、耗时和链路编号。

## 五、后续边界

T5 完成后，仍不代表生产可用。权限、多租户、审计、限流、性能、部署、回滚和完整 Metrics / Logs / Alert 仍属于后续 Production Hardening（生产强化）范围。
