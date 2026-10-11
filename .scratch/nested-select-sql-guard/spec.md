# 嵌套 SELECT 拒绝修复短 Spec

## 目标
落实 Online Query V1 已确认的“只允许单层 SELECT”约束，避免单指标 / 实体类 SQL 中的嵌套查询绕过 SQL Guard。

## 行为与范围
- SQL Guard 解析 PostgreSQL SQL 后，检查完整 AST；任意位置出现嵌套 SELECT（例如 FROM 派生表、EXISTS、标量子查询）都返回 `SQL_REJECTED`。
- 在数据库执行之前拒绝；普通顶层 SELECT 和现有合法直接 LEFT JOIN 行为不变。
- CTE、集合运算和多指标结构规则保持原有行为，不扩大 SQL 功能。

## 验收与验证
- 代码路径在单指标、实体类及多指标输入上统一执行嵌套查询拒绝。
- 检查正式 Online Query Spec 与实现一致；验证命令及结果记入本机实时状态。

## 授权
用户 2026-10-11 明确要求“开始修复”，授权该小范围实现及其必要本地文档 / 验证工作；不包含 Push / PR / Stable 操作。
