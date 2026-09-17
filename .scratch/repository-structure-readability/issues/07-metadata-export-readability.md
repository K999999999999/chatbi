# 07: 整理 Metadata Export 脚本内部职责

**What to build:**

在不改变数据库读取边界和生成结果的前提下，整理 Metadata Export 工具的配置读取、数据库访问、结构转换、文件生成和命令行入口职责。

该 Ticket 只改善脚本可读性和定位方式，不修改数据库内容、不改变结构事实语义。

**Blocked by:**

01: 建立全工作区事实地图与整理基线

**Status:** done

## Acceptance criteria

- [x] 脚本入口和核心生成流程容易定位。
- [x] 不修改数据库内容。
- [x] 不改变生成结构事实的语义和输出 Contract。
- [x] 脚本测试通过。
- [x] Python import / compile 检查通过。
- [x] 完整 deterministic tests（确定性测试）通过。

## Result

已完成。`export_schema.py` 保留 CLI 和 `export_schema()` 总编排；模型与常量位于 `export_schema_models.py`，本地配置和字段值示例位于 `export_schema_input.py`，只读 PostgreSQL 读取位于 `export_schema_database.py`，结构投影和 JSON 文件生成位于 `export_schema_output.py`。原有导入入口和输出文件 Contract 保持兼容。

验证：

- `tests/metadata/test_export_schema.py`：`2 passed`；
- `uv run python -m compileall -q scripts/metadata` 通过；
- CLI 模块导入、`ROOT`、`TARGET_SCHEMA` 和 `OUTPUT_FILES` 入口核对通过；
- 未连接数据库，未修改数据库内容；
- Ticket 08 最终验收的完整 deterministic tests：`255 passed, 6 skipped, 85 subtests passed`。

## Comments

如果 Ticket 01 证明该脚本不需要拆分，则可以将本 Ticket 调整为只做导航说明，不能为了文件数量强行重构。
