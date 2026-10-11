# 嵌套 SELECT 校验修复验证

## 候选与范围

- 基线：`b7dd82386d877ccf6669bd2e02698e81da19f975`（与 `origin/master` 同步）。
- 候选：`fix/reject-nested-select` 工作区当前改动，尚未提交。
- 代码：`src/online_query/sql_guard/sql_guard.py`。
- 行为回归：`tests/online_query/test_sql_guard.py`。
- Contract：`docs/specs/online-query.md`。

## 结果

- Red：暂时移除 AST 检查后，三类实体查询（FROM 派生表、EXISTS、标量子查询）均未被拒绝；带认证单指标约束的 EXISTS 也未被拒绝。新增回归断言按预期失败。
- Green：恢复 AST 检查后，全量 `pytest -q` 通过：997 passed、41 skipped、142 subtests。
- `bash scripts/check_python_quality.sh`：PASS（307 files already formatted，all checks passed）。首次检查指出新测试的格式问题，格式化后重跑通过。
- `git diff --check`：PASS。
- SQLGlot AST 只读探针：三类子查询均包含根节点之外的 `Select` 节点。
- Review：PASS。公共解析入口统一覆盖实体、单指标和多指标；现有顶层查询及认证直接关联回归通过。没有新增数据库、LLM 或外部服务依赖。
- 不运行 AI Evaluation：本次只改变 SQL Guard 对嵌套结构的确定性拒绝行为，模型和检索行为未变化。
- 路线图不更新：不改变产品里程碑、范围、优先级、依赖或完成状态。
