# 浏览器镜像缓存定向验收

## 身份与边界

基线：`acf747fc5ef8783a5faea47642e69647ca1a795b`；证据对应本目标提交前的 Dockerfile 改动，以原始 manifest 中的 Dockerfile SHA-256 关联最终本地候选（候选 SHA 记入本机实时记录）。验证使用独立临时 context / 专属镜像 tag，不改仓库业务源码或依赖文件，不连接业务服务或调用 LLM。
Docker Engine 29.5.3，default builder（BuildKit v0.30.0），linux/amd64；Node v24.21.0、Playwright 1.63.0、Chromium 153.0.8010.12。

## 构建场景

实际命令为 `docker build --progress=plain --target <target> -f docker/node-dev.Dockerfile -t <专属 tag> .`，在各临时 context 内执行。context 只包含 Dockerfile 与其 COPY 的前端配置、依赖清单、锁文件和源码。

| 场景 | 改动 | 耗时 | 结果 |
| --- | --- | --- | --- |
| browser 首次构建 | 优化后的原始 context | 443.77 秒 | PASS；npm 已缓存，Chromium / 系统依赖重新安装 |
| dev 构建 | 同一原始 context | 1.36 秒 | PASS；npm 命中缓存 |
| 源码变化 | 只在 main.tsx 末尾追加注释 | 1.47 秒 | PASS；npm 与 Chromium 层均 CACHED |
| 配置变化 | 只在 vite.config.ts 末尾追加注释 | 1.33 秒 | PASS；npm 与 Chromium 层均 CACHED |
| 依赖清单 / 锁文件变化 | 根包 version 0.1.0 → 0.1.1，并同步 lock 顶层及 packages[""] 的 version；实际依赖版本不变 | 695.55 秒（含共享缓存等待） | PASS；npm 与 Chromium 层均重新执行，镜像导出成功 |

耗时是本机本轮结果，包含镜像导出；首次构建仍受网络和下载影响。来源 Issue #52 的 220–253 秒是历史构建记录，不是本轮同环境前后对照。依赖变化构建与首次构建并行，包含共享 apt cache 的等待，不用它衡量优化后的性能。

## 运行和静态验证

- 原 dev / browser 镜像与新镜像的 User、WorkingDir、Cmd、Entrypoint 和 Env 值一致；browser 保留 UTF-8 locale、HOME=/tmp 和 /opt/browsers。
- 源码与配置对照镜像实际包含新增内容；依赖变化镜像包含更新后的根包 version 与可用 Chromium，Playwright 版本仍为 1.63.0。
- 新 browser 镜像以 node（UID 1000）启动 Chromium，中文页面文本读取与按钮点击通过。
- 新 dev 镜像按默认启动命令运行，使用 Compose 对应的 CHATBI_DEV_API_TARGET 配置；Vite 首页和 /src/main.tsx 均 HTTP 200，容器已清理。
- 现有 playwright.container.config.ts / container-real.spec.ts 经实际 Playwright runner 发现 3 个用例；仅发现用例，未执行真实模型业务验收。
- 现有 chart-plan、helpers、number-format 三组用例在新 browser 镜像内执行：8 passed。
- Docker build --check：无警告；Markdown local links 与 git diff --check：通过。
- 未运行全量 Python 测试、AI Evaluation 或完整业务 Real E2E：本改动只调整前端验收镜像构建层，Python / 模型 / 业务源码未变化。

## 事实源与收尾

Runbook §3 已说明 dev / browser target、源码缓存复用和依赖变化失效边界。路线图的当前阶段、当前能力、后续扩展和产品范围已核对；不改变产品 V1 能力、验收身份或优先级，无需更新路线图。Issue #52 未关闭，Push / PR 仍待用户发布授权。

原始日志及 JSON 汇总：`reports/browser-real-artifacts/browser-image-cache/chatbi-browser-cache-y9p_acfn`（ignored，不纳入 Commit，不保证新 clone 中存在）。

Dockerfile SHA-256：`61c18578a7b93eca18f66888d0f05acf4a28901cdcb077f06468ce0eea975921`。本机 manifest 记录适用基线、构建 context、镜像身份；构建日志保存依赖层 CACHED / DONE 的原始证据。
