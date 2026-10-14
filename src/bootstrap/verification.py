"""只读检查标准容器初始化结果，不管理发布版本或修改运行数据。"""

import os
import sys
from contextlib import ExitStack
from pathlib import Path


def verify() -> int:
    stage = "运行配置"
    try:
        if len(os.environ.get("CHATBI_ADMIN_SECRET_KEY", "").strip()) < 32:
            raise RuntimeError("签名Key必须至少32个字符")
        key = os.environ.get("LLM_API_KEY", "").strip()
        if not key or key.lower() in {"replace-me", "change-me", "your-api-key"}:
            raise RuntimeError("LLM配置尚未完成")
        if not os.environ.get("LLM_MODEL", "").strip():
            raise RuntimeError("LLM型号尚未配置")
        stage = "模型与检索资产"
        model = Path(os.environ.get("RAG_MODEL_DIR", ""))
        if not (model / "config.json").is_file():
            raise RuntimeError("模型尚未准备")
        from src.online_query.database import PsycopgQueryExecutor
        from src.online_query.retrieval.rag_runtime import RagRuntime
        from src.rag_offline.config import OfflineBuildConfig

        with ExitStack() as resources:
            rag = RagRuntime(
                OfflineBuildConfig.from_environment(), production_mode=True
            )
            resources.callback(rag.close)
            rag.verify_production_ready(
                PsycopgQueryExecutor.from_env().verify_structure_metadata
            )
            stage = "应用库与管理员"
            from sqlalchemy import select
            from sqlalchemy.orm import Session

            from src.chatbi_control.database import (
                ControlDatabaseConfig,
                create_control_engine,
                verify_control_schema,
            )
            from src.chatbi_control.models import Role, User

            engine = create_control_engine(
                ControlDatabaseConfig.from_environment(require_migrator=False)
            )
            resources.callback(engine.dispose)
            verify_control_schema(engine)
            with Session(engine) as session:
                administrator = session.scalar(
                    select(User.id)
                    .join(User.roles)
                    .where(User.is_active.is_(True), Role.name == "admin")
                    .limit(1)
                )
                if administrator is None:
                    raise RuntimeError("首个管理员尚未创建")
            stage = "网页与导出资产"
            web = Path(os.environ.get("CHATBI_WEB_DIST_DIR", "/opt/chatbi-web"))
            if not (web / "index.html").is_file() or not (web / "assets").is_dir():
                raise RuntimeError("网页构建未完成")
            from src.query_api.export_assets import verify_runtime_manifest

            verify_runtime_manifest(
                Path(os.environ.get("CHATBI_EXPORT_ROOT", "/opt/chatbi-export"))
            )
    except Exception as error:  # noqa: BLE001 - 配置和连接异常不得输出敏感文本
        print(
            f"初始化验证失败：{stage}（{type(error).__name__}）；"
            "请检查必要配置、migration、管理员、模型、索引和镜像构建。",
            file=sys.stderr,
        )
        return 1
    print("初始化验证通过：数据库、管理员、模型、RAG、网页与导出资产。")
    return 0
