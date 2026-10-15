# 04 修正无序结果的容差匹配

Status: done
Canonical Source: [Spec](../spec.md)、[Design](../design.md)、[草案](../tickets-draft.md#04-修正无序结果的容差匹配)
Owner: 当前主 Agent
Change Profile: 小范围确定性评测算法修复；评分影响中等；不调用模型 / 数据库。
Blocked by: None (can start immediately)

## What to build

复用现有值比较，以多项式增广路径判断无序结果是否存在完整的一一配对。保持有序模式、原数值容差、NULL、列顺序、重复行和截断规则。

Owned files: `evaluation/suites/single_turn/evaluator.py`、受影响的 single-turn / multi-turn evaluator 测试、`docs/specs/evaluation.md` 比较规则。

Out of Scope: 修改评测题集、标准 SQL、模型答案、误差门槛或有序比较语义。

## Acceptance criteria

- 重叠容差反例及行置换得到正确结果；存在完整配对时通过，不存在时失败。
- 覆盖重复行不足、NULL 与零、多列、容差边界、数字字符串归一化、截断和有序比较。
- 接近有界最大行数的稠密候选图确定性完成，不枚举全排列、不使用脆弱的计时断言；相关确定性 Evaluation 测试通过。

Migration / Rollback: 不回算旧报告；切片可独立恢复，评分结果关联其候选版本。

## Result

TDD: Red 阶段新增的容差重叠反例在旧贪心实现上失败：第一行先占用共享候选，导致实际存在完整配对的结果被误判。改为确定性增广路径匹配后，原顺序及行置换都通过。

Code Review: PASS；审查基线为 Ticket 03 提交 `dbb948c81f5bcbc02d39c8dd22b3452a868b9d58`，范围限于评测比较器、对应测试和评测 Contract。匹配图基于原 `_rows_match` 语义构建，增广路径寻找完整一一配对；有序分支、容差和值类型语义不变。未发现需修改问题。

Verification: `uv run --locked pytest -q tests/evaluation/single_turn tests/evaluation/multi_turn`（30 passed）；`uv run --locked pytest -q tests/evaluation`（92 passed、1 skipped、22 subtests passed）；`uv run --locked ruff check evaluation/suites/single_turn/evaluator.py tests/evaluation/single_turn/test_evaluator.py`、`python3 -m scripts.check_documentation`、`git diff --check` 均通过。新增 100 行稠密候选测试无计时断言，不调用模型或数据库。

Commit: `9654f2d83a46b869c0f98a64f3f80e574cc1eb33`（本地）；没有 Push / PR。

## Comments

调查确认现有贪心匹配对相同多重集合的判断受实际行顺序影响。
