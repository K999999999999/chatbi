# R6 稳定服务恢复与文档收尾短 Spec

授权：2026-10-08 用户确认“先恢复并核验稳定服务，再补齐文档状态”，覆盖既有稳定环境启停恢复、只读核验、文档修订和本地 Commit；不包含新 PR 发布、其他项目启停、永久 IDM 设置、整机 / Docker 重启或 R7 实施。

目标：按既有 ./local up 恢复 chatbi-stable，保持 runtime 2b4a8c8、已有卷与业务数据；修正与 PR60 已合并事实冲突的当前文档描述。

范围：本短 Spec / 验证记录，docs/roadmap.md、docs/acceptance/local-deployment-v1.md、.scratch/chatbi-product-v1/spec.md、.scratch/r6-local-deployment/spec.md 与 Ticket 04 的当前状态，以及关联本机进度。保留历史阶段、报告候选身份和未执行验证限制。

验收：稳定 API / PostgreSQL / Qdrant 正常运行；API 镜像与持久卷身份不变；PostgreSQL 容器可按既有发布记录重建，必须记录实际镜像变化并核验数据指纹；启动资产 / 权限 / migration / RAG 校验通过；HTTP 网页与健康入口可访问；只读核对已有账号 / 历史 / 成果与 Seed；其他项目状态不变；文档正确区分已合并交付、运行恢复、R7 和重启 / Evaluation 限制。

验证：既有启动门禁、Docker 身份 / health、HTTP、数据库只读指纹与历史快照核验、Markdown links、Diff 和当前上下文 Code Review；不新增产品代码或重复运行完整模型 / 浏览器验收。

基线：master 9a706016504be6145e7a702536d858b2d641d957；初始 clean；branch fix/r6-runtime-document-closeout。

Done When：上述验收完成、证据归档、关联记录同步、Review PASS 并形成本地提交。路线顺序保持 R7 澄清。
