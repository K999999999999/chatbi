# R5 Linux Chromium 下载名验收环境修复

Status: 根因已定位为 Linux Chromium 验收容器缺少 UTF-8 locale；仅调整浏览器测试环境，不改变 R5 产品行为。

## Goal

让 Linux Chromium 验收环境能够正确处理 R5 下载的中文文件名，使浏览器报告的建议文件名与服务端 UTF-8 `Content-Disposition` 文件名一致。

## Scope

- 在 `docker/node-dev.Dockerfile` 的 browser 阶段设置 `LANG=C.UTF-8` 和 `LC_ALL=C.UTF-8`。
- 在 `scripts/verify_container_dev.sh` 启动浏览器容器时显式传入相同 locale，避免容器运行配置覆盖镜像默认值。
- 更新 R5 验收记录，说明历史 Linux Chromium 文件名偏差来自测试环境 locale。
- 不修改前后端导出实现、授权检查、文件内容 / 格式、登录行为或 R5 Contract；不改动 R7 PR #62。

## Done When

- 构建后的 browser 镜像报告 UTF-8 locale，实际 Chromium 对 Blob `download` 与带 UTF-8 `filename*` 的 HTTP 附件均保留中文文件名。
- 现有 R5 Playwright 文件名断言继续覆盖产品下载行为；脚本语法及 `git diff --check` 通过。
- 更新 R5 Acceptance 的根因与复验说明；检查 `docs/roadmap.md`，路线状态不变时在实时工作记录中说明理由。
- 完成当前上下文 Code Review；迁移到最新 `master` 后重跑受影响验证并形成独立 PR，按仓库真实规则跟进 required checks 与自动合并。

## Evidence

- 历史隔离浏览器报告中，Linux Chromium `153.0.8010.12` 的 12 次 Blob 下载均建议保存为 `download`，但文件内容及格式解析通过；HTTP 附件预检的 ASCII 文件名通过。
- 隔离对照实验复现了空 `LANG` / `LC_ALL` 时中文名退化；设置 `C.utf8` 后 Blob 与 `filename*` 路径恢复中文名。前端已解析服务端 `filename*` 并赋给 Blob 链接 `download` 属性，服务端已提供 UTF-8 文件名。
- 根因是验收容器 locale 配置，不是 R5 文件内容或导出实现缺陷。
