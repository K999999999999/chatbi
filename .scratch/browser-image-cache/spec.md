# 浏览器验收镜像构建缓存优化（短 Spec）

## 目标与授权
用户于 2026-10-11 指示“可以进行优化”，授权本地实施与验证此前说明的浏览器镜像重复依赖安装问题。来源为工程维护 Issue #52；未授权 Push / PR 或关闭远端 Issue。

## 预期结果与范围
调整 docker/node-dev.Dockerfile 的构建阶段：npm 依赖作为共享稳定阶段，Chromium / 系统依赖安装在复制前端源码之前；dev 与 browser 分别在依赖阶段之上复制前端源码。
保留锁定的 Node 镜像摘要和 Playwright 版本、dev / browser target 名称、工作目录、HOME、启动命令、非 root 用户、browser 的 UTF-8 locale 与 PLAYWRIGHT_BROWSERS_PATH。不修改依赖清单、业务源码、Stable 服务或验收覆盖。

## 验收与验证
1. 实际构建 dev / browser 镜像成功；浏览器以 node 用户启动 Chromium 并渲染中文；现有容器验收 Playwright 配置和用例可发现，dev 启动命令可服务页面。
2. 在独立临时构建 context 仅修改前端源码，再构建 browser，Chromium 安装层与 npm 安装层均为 CACHED，记录耗时。
3. 在独立 context 修改依赖清单及锁文件的一致版本元数据，确认 npm / Chromium 安装层均重新执行；不改仓库依赖文件。
4. 保存构建日志、Dockerfile 指纹、适用基线和结果；缓存通过不等于完整业务验收通过。更新 Runbook 对构建缓存的说明。
5. 当前上下文 Code Review、Markdown 链接及 git diff --check 通过后创建本地 Commit。

## 路线图适用性
此目标是已完成产品 V1 的独立工程维护，不改变产品能力、验收身份、依赖或优先级；核对 docs/roadmap.md 与 product-scope.md，无需改写产品路线图。
