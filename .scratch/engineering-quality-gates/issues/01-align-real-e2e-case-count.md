# Ticket 01：对齐 Real E2E 案例集与验收数量

Status: done

## Owner

ChatBI 仓库维护者负责验收；当前实施 Agent 负责实现。

## Blocked by

None (can start immediately)

## Change Profile

- Lifetime: 长期维护的手动 Real E2E 门禁。
- Size: 小范围 workflow / 验收逻辑修改。
- Risk: 中；workflow 会调用真实 LLM，但本 Ticket 不授权触发真实评测。
- Evidence: 确定性验收逻辑测试和 CI workflow 检查。
- Delivery: 与同一 Feature 的其他 Ticket 使用同一 branch 和 PR。

## What to build

修正 `.github/workflows/real-e2e.yml` 中运行范围和报告案例数断言不一致的问题。Workflow 保持手动触发和当前默认完整单轮 Golden Set 范围；验收数量以实际加载的当前案例集为准。当前单轮集有 29 个案例，不能继续要求 21 个。

不得通过删改 Golden Case 来迁就旧数量；如果报告的案例数与本次加载的数据不符，workflow 必须失败并说明预期来源。

## Acceptance criteria

- Workflow 仍只运行默认单轮在线评测，不把 Multi-Turn 或 Business Analysis 加入本 Ticket。
- 验收逻辑核对报告案例数与当前单轮案例集一致，不保留独立且过期的 `21` 硬编码期望值。
- 成功时所有加载案例有效且通过，`FAIL=0`、`INVALID_CASE=0`，并保留现有 `execution_accuracy=1.0` 验收。
- 案例数不一致、失败或无效案例均使 workflow 失败，并给出可定位的错误信息。
- 确定性测试验证验收逻辑；普通 CI 不调用真实 LLM，也不自动触发 Real E2E。

## Owned files

- `.github/workflows/real-e2e.yml`
- `evaluation/common/real_e2e_acceptance.py`
- `tests/evaluation/common/test_real_e2e_acceptance.py`

## Verification evidence

- 运行对应确定性测试。
- 静态检查 workflow 仍为 `workflow_dispatch`，且测试范围、报告数和验收语义一致。
- 不运行手动 Real E2E；真实 LLM 执行需按仓库授权流程另行确认。

## Migration / Rollback

无运行时 Migration。若新门禁误拒绝合法报告，可回退本 Ticket 的 workflow / 验收逻辑修改；不得放宽为接受 FAIL 或 INVALID_CASE。

## Done When

确定性验证通过，workflow 的运行范围与报告验收一致，且没有过期的 21-case 断言。

## Result

已将 workflow 的验收数改为读取本次传入的案例文件长度，并校验总数、有效数、通过数、失败数、无效数和 Execution Accuracy。覆盖 21 / 29 案例计数、过期数量、失败 / 无效及 CLI 文件读取的测试通过（对应测试 4 项，含 2 个 subtests）。普通 CI 不触发真实 LLM。

## Comments

None.
