# 缺失挂载失败与 Plugin 兼容

Status: done
Owner: 当前主 Agent
Blocked by: None (can start immediately)
What to build: 源 bind mount 缺失时失败；使用官方入口更新真实 Plugin 安装包并验证取消记录。
Acceptance criteria: 缺失源不会生成目录；相关容器入口测试通过；取消记录读取成功；源码 / 安装摘要核对，不宣称当前会话重载。
Owned files: docker-compose.yml、scripts/container_tasks.sh、scripts/dev_environment.sh、scripts/dev_maintenance.sh、scripts/verify_container_dev.sh、adapter 与相应测试 / Runbook；安装动作不入 Git。
Result: 宿主源预校验与--mount完成；真实缺失源退出2且没有建目录；官方更新Plugin后48文件摘要一致，取消记录可读。
Comments: 用户已确认四步方案的第三项；不修改外部源码工作分支。
