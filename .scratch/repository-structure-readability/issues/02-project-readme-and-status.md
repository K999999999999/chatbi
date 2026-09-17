# 02: 建立面向新开发者的 README 入口

**What to build:**

建立根目录 `README.md`，作为新开发者的第一入口，说明 ChatBI 当前版本、开发和生产状态、主链路、模块组成、工作区目录职责、模块实现状态、验证证据和下一步阅读路径。

统一项目整体定位：不使用 `MVP` 或 `POC` 概括整个 ChatBI；`POC` 只用于明确的验证入口或验证场景。版本号必须使用 Ticket 01 确认的真实来源。

**Blocked by:**

01: 建立全工作区事实地图与整理基线

**Status:** done

## Acceptance criteria

- [x] 新开发者仅通过 README 和其入口链接，可以在 5 分钟内说明项目用途、模块、主链路、当前状态和下一步阅读位置。
- [x] README 使用当前真实版本来源，不手写未经核实的具体版本号。
- [x] README 将实现状态、验证证据和生产状态分开描述。
- [x] README 明确 `Streamlit` 等 POC 范围，不把整个 ChatBI 写成 POC。
- [x] README 中的目录、模块和文档链接真实有效。
- [x] 详细启动、测试和故障排查内容仍由运行手册承担，不复制成另一份长手册。

## Result

已完成。根目录 `README.md` 已建立，作为项目定位、主链路、模块地图、工作区职责、状态和下一步阅读入口。详细启动和故障排查仍保留在 `docs/runbook.md`，README 未复制运行手册内容。

验证：README 引用的项目入口、模块目录、测试目录、文档路径和 Feature 路径均已核对存在；版本使用 `pyproject.toml` 的 `0.1.0`，并明确当前是 Git Development Snapshot，不将版本号表述为 Production Ready。

## Comments

README 是项目入口，不替代稳定架构文档、Module Spec 或详细运行手册。
