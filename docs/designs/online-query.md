# SQL Guard与只读执行机制

本文说明模型SQL候选从解析到执行之间的确定性边界。允许的SQL形态、指标和错误规则见 [在线查询Spec](../specs/online-query.md)，历史条件一致性见 [查询恢复](../specs/query-restoration.md)。

## 校验顺序

1. 提取单条候选，使用SQLGlot解析；无法解析或多语句直接拒绝。
2. 检查所有AST节点；任何位置的嵌套SELECT、危险语句和不允许的表达式均拒绝，不能只检查根节点。
3. 将SQL引用的表、列、别名及Join与本次QueryContext范围核对；直接关系由认证图提供。
4. 有认证metric_constraints时比较输出公式与固定顶层WHERE条件，保留单指标和多指标各自的合法形态边界。
5. 历史profile进一步比较SQL与执行前认证的完整条件；SQL不是反向恢复业务含义的来源。
6. 全部检查通过后才进入只读执行；失败不改写候选或再次请求模型。

## 物理表达式认证

指标口径与业务绑定归权威Semantic源，资产提供本次物理身份。AST比较允许认证别名、空白、大小写及无意义括号差异，不做通用数学 / 布尔等价推理。

指标固定条件必须作为顶层WHERE的必需AND子条件存在；OR、NOT不能绕过口径。完整历史条件还包括投影、实体去重、分组、行与聚合筛选、排序、平局次序及业务LIMIT。

## 有界只读执行

执行器使用专用只读身份和只读事务；数据库超时与安全失败分开返回。最多读取101行判断100行截断，运行取数上限不等同于用户业务Top-N。查询正常但没有行仍是成功。

## 代码定位

- [公共Guard](../../src/online_query/sql_guard/sql_guard.py)：编排确定性检查。
- [表列范围](../../src/online_query/sql_guard/sql_guard_scope.py)、[Join](../../src/online_query/sql_guard/sql_guard_join.py)、[指标](../../src/online_query/sql_guard/sql_guard_metrics.py)：各自认证规则。
- [只读数据库执行](../../src/online_query/database.py)：连接、事务、超时与有界取数。

校验和执行属于现有查询链，不依赖HTTP或客户端提交的SQL授权结论。
