# 本机运行保障：整理前的过程记录

来源：`docs/specs/local-operations-v1.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 整理前入口说明

# R7 本机稳定环境运行保障 Spec

Status: Contract 已确认，实施与验收完成；PR #62 已合并。最终实现和 Stable 验收证据见 [Acceptance](acceptance--local-operations-v1.md)。本文定义行为 Contract，不代表公网生产部署。

## Problem Statement

R6 已提供固定版本本机部署与兼容升级 / 回滚，但 `/health` 仅反映 HTTP 存活；稳定环境的阿里云链路输出当前关闭，备份恢复与持续依赖检查尚未提供完整 Contract。服务退出时，最后操作的部署状态记录不能独立证明当前可用性。

本轮目标是当前 Windows + WSL2 Linux x86_64 + Docker 电脑上的 `chatbi-stable`，主要自己日常使用与演示。`chatbi-engine` 继续用于开发测试；本目标不启停、覆盖或恢复开发数据。

Canonical Source: 本文件是已确认R7行为Contract；实现和验收进度见工作记录及Acceptance。既有未改变行为以原Spec为准。

事实源：[Roadmap](../../../.scratch/remove-roadmap-and-audit/history/roadmap.md)、[Architecture](../../../docs/architecture.md)、[Product Scope](../../../docs/product-scope.md)、[R6 Contract](../../deployment-simplification/history/docs--specs--local-deployment-v1.md)、[R4](../../../docs/specs/execution-streaming-v1.md)、[R5](../../../docs/specs/result-export-v1.md)、[Observability](../../../docs/specs/observability.md)、[Web](../../../docs/specs/web-dialogue-v1.md)。规划基线 master `0c77d80f35cde135160e4a8806f639397f1867ff`；稳定运行与原验收身份仍为 `2b4a8c8`，不改写历史报告身份。

## Documentation / Done When

正式运行保障Spec、Design、Architecture/API/Observability（适用处）、Runbook、Acceptance、Product Scope、roadmap及长期/实时工作记录按确认事实同步。Owner为本目标实施维护者；具体实现文件与切片由Design/Tickets确定。

完整Spec获确认、Design Review通过、Ticket草案Readiness READY及用户确认拆分/实施范围之后才能实施。本目标完成须满足所有适用Ticket、验证、正式文档、Review及获授权交付收尾；不能以clean/CI绿或部分功能完成宣称整个产品V1完成。

## Further Notes / Authorization

用户逐项确认场景、备份恢复、状态与权限、额度、阿里云方案、性能基线和恢复前提；2026-10-08确认完整备份数据范围。用户于2026-10-08整体确认本文件；完整Spec确认不等于Ticket拆分或工程实施授权。首轮Design Review的机制问题在独立实现设计中解决并复审，不改已确认行为范围。
