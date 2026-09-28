# 02 查询结果统一使用千分位分组

- Status: open
- Owner: ChatBI Agent
- Blocked by: None (can start immediately)
- Change Profile: Streamlit 展示层局部行为；纯软件测试；本地交付

## What to build

普通查询和 Business Analysis Task 结果表格中的度量值采用每三位一组的半角逗号格式，例如 `12,345,678.90`。已知人民币金额列标注单位“元”，数值不换算为万元。格式只用于 Streamlit 展示，API / JSON、数据库和 SQL 结果继续保留原始数值。

## Scope

- 复用或调整 Streamlit 展示格式化逻辑，覆盖普通查询和 Business Analysis Task 表格。
- 根据已知字段语义格式化金额、计数、数量和比率，不把所有数字列推断成金额。
- 补齐正常值和边界值测试。

## Out of Scope

- 修改 API / JSON Contract、数据库列类型、SQL 执行结果或数据精度。
- 自动缩写为万元 / 亿元；推断未知指标单位；格式化数值型 ID、日期键、状态码或枚举码。

## Acceptance criteria

- 普通查询与 Business Analysis 结果表中的适用度量均以三位千分位展示，负数和小数格式正确。
- 已知人民币金额明确标注“元”，保留现有两位小数展示规则；不显示万元换算。
- ID、日期键、状态码及非数值 / 空值不被错误格式化。
- 页面格式化不改变 API 返回的原始数字值。

## Owned files

- `src/streamlit_app.py`
- `tests/streamlit/test_streamlit_app.py`
- 若单位需要通过当前权威元数据确认，可最小范围读取 / 使用 `src/structure/generated/columns.json`；不得在 Ticket 内改数据库或 API Contract。

## 验证证据

- `tests/streamlit/test_streamlit_app.py` 覆盖普通表格、Business Analysis 表格、正负数、小数、空值、单位及不应格式化的标识字段。
- 验证 API 数值仍保持数值类型，不带逗号或单位。

## Migration / Rollback

不涉及迁移。若字段语义无法从已确认元数据可靠识别，应保持原值并在 Result 记录，不猜单位。

## Done When

两个结果展示入口一致遵守 Spec，相关测试通过，原始 API 数值 Contract 不变。

## Result

待实施。

## Comments

- Canonical Source: `.scratch/chinese-business-display-and-seed/spec.md`。
