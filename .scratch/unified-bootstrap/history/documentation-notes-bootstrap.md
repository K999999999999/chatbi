# 初始化与运行资源生命周期：整理前的过程记录

来源：`docs/specs/bootstrap.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 入口迁移

旧 `python -m src.chatbi_control`、`python -m scripts.prepare_embedding_model` 和 `python -m src.rag_offline` 命令入口已移除，不提供转发。模块业务 API 保留；当前文档、CI、测试和脚本统一使用 bootstrap。日期化 Acceptance、旧报告和历史规划保持原候选身份。
