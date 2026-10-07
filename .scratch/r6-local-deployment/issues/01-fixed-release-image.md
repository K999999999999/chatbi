# Ticket 01：固定版本镜像承载完整应用

Status: done
Owner: 当前主Agent
Blocked by: None
Result: 完成并于 `4d4732b7896a46b231a4a3437c703e74b5ae513f` 重新构建；API 与 PostgreSQL 镜像均记录该 clean source commit，镜像身份及定向运行检查通过。
Comments: 本地实施授权于2026-10-07取得；发布授权未取得。


Change Profile: 持续维护 / 中 / 构建与运行资产风险 / 构建检查+容器浏览器导出证据 / 本地Commit。
Owner: 当前主Agent；后续Docker构建/导出资产维护者。
Blocked by: None。
What to build: 多阶段本地交付Dockerfile，打包网页、Python源码/事实资产、R5导出bundle/Chromium/字体和数据库初始化镜像；固定CPU PyTorch wheel来源且锁定哈希、排除CUDA依赖；基础digest/依赖锁定；非root、单worker、无reload；发布描述记录commit和实际image ID及初始兼容声明。
Owned files: docker/local.Dockerfile、.dockerignore、发布描述格式及构建支持（scripts/local_release.py相关部分）、必要构建配置、安全模板骨架；对应测试与镜像说明文档。不得混入业务改动或锁文件无关升级。
Acceptance Criteria:
- clean指定版本容器构建成功，镜像包含有效网页与导出manifest、所需初始化/迁移文件；无.env/真实凭据/开发挂载依赖。
- 内嵌源commit与发布描述一致，镜像实际ID记录；不依赖可变标签识别版本。
- Linux锁文件选中CPU torch wheel，不包含CUDA/NVIDIA/Triton包；`uv lock --check`和锁文件依赖树可验证。
- API默认非root、单worker且没有reload；字体/Chromium既有验证机制可运行，导出不依赖宿主源码。
Evidence: uv lock check与torch依赖树、构建定义确定性检查、镜像内容/启动命令检查、导出资产校验及受影响R5回归；容器帮助入口运行不需要宿主Python/Node。
Migration / Rollback: 不修改DB Schema；不替换开发镜像或开发入口。失败只保留本目标构建诊断，不自动prune镜像。
Done When: 构建证据关联clean候选与image ID，软件/资产检查和Code Review完成；Runbook打包入口说明同步，未执行项如实记录。

Verification: `docker build --check` PASS；API与PostgreSQL database目标均真实构建成功；Web `npm run build`（含typecheck）PASS；`uv lock --check` PASS，锁定CPU torch且CUDA/NVIDIA/Triton依赖移除。最终 clean source commit `4d4732b7896a46b231a4a3437c703e74b5ae513f`：API image ID `sha256:dfe36e7aa5927bd2334f2fd406a257837e7079ef8e07f168dd2ffca9aa01961b`（1,909,212,440 bytes）；PostgreSQL image ID `sha256:e9605804df9016d702ee575220cd27ab7a40441a07f44846931fe9ca952fdbfc`（116,049,593 bytes）。两镜像OCI revision label与`/opt/chatbi-release.json`均等于该commit。严格 smoke 确认API非root、单worker、无reload，网页/R5 bundle/Chromium/font manifest有效，CPU torch可导入且CUDA不可用，pytest/ruff未安装，R5 export runtime manifest校验PASS；PostgreSQL镜像含PostgreSQL 16.14、`/docker-entrypoint-initdb.d/10_chatbi_dev_environment.sh`、迁移DDL和合成Seed。未运行模型Embedding Evaluation、完整API/浏览器E2E；Ticket02/04负责相应运行闭环。

实现补充：PostgreSQL目标同样要求40位commit输入，并写入`/opt/chatbi-release.json`及OCI revision label，确保两镜像源提交可核验。检查：改后`docker build --check`无告警。
