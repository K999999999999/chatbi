"""保持当前环境下的确定性启动门禁。"""

from src.chatbi_control.database import verify_control_schema


def verify_startup_dependencies(
    *, control_engine, environment: str, rag_runtime, query_executor
) -> None:
    verify_control_schema(control_engine)
    if environment in {"production", "prod"}:
        if rag_runtime is None:
            raise RuntimeError("production 必须启用在线 RAG Retrieval")
        rag_runtime.verify_production_ready(query_executor.verify_structure_metadata)


def probe_dependencies() -> dict[str, str]:
    """在独立进程检查真实权限/catalog与资产；不初始化Embedding/LLM。"""
    import os
    from dataclasses import replace

    from sqlalchemy.exc import SQLAlchemyError

    from src.chatbi_control.database import ControlDatabaseConfig, create_control_engine
    from src.online_query.database import PsycopgQueryExecutor
    from src.online_query.retrieval.rag_runtime import (
        _validate_collections,
        _validate_manifest,
        _validate_provenance,
    )
    from src.rag_offline.build import PublishedAssetError, load_published_asset
    from src.rag_offline.config import OfflineBuildConfig
    from src.rag_offline.qdrant_store import QdrantAssetStore, QdrantStoreError

    checks = dict.fromkeys(
        ("control_database", "business_database", "qdrant", "assets"), "unknown"
    )
    engine = None
    try:
        engine = create_control_engine(
            ControlDatabaseConfig.from_environment(require_migrator=False)
        )
        verify_control_schema(engine)
        checks["control_database"] = "ready"
    except (OSError, RuntimeError, ValueError, SQLAlchemyError):
        checks["control_database"] = "not_ready"
    finally:
        if engine is not None:
            engine.dispose()
    try:
        PsycopgQueryExecutor.from_env().verify_structure_metadata()
        checks["business_database"] = "ready"
    except (OSError, RuntimeError, ValueError, SQLAlchemyError):
        checks["business_database"] = "not_ready"
    store = None
    try:
        if os.getenv("RAG_ONLINE_RETRIEVAL_ENABLED", "true").lower() in {
            "false",
            "0",
            "off",
            "no",
        }:
            raise RuntimeError("缺少运行资产")
        config = replace(
            OfflineBuildConfig.from_environment(), qdrant_timeout_seconds=2
        )
        published = load_published_asset(config.output_dir)
        _validate_manifest(published, config)
        _validate_provenance(published, config)
        if os.getenv("CHATBI_LOCAL_OPERATIONS_ENABLED", "false").lower() == "true":
            # 稳定镜像复用R6权威门禁；仅构造Embedding配置，不加载模型/发请求。
            import io
            from contextlib import redirect_stdout
            from scripts.local_release import verify_runtime

            with redirect_stdout(io.StringIO()):
                verify_runtime(dict(os.environ))
        checks["assets"] = "ready"
        try:
            store = QdrantAssetStore.connect(
                url=config.qdrant_url,
                path=str(config.qdrant_path) if config.qdrant_path else None,
                api_key=config.qdrant_api_key,
                timeout=2,
            )
            _validate_collections(store, published)
            checks["qdrant"] = "ready"
        except (OSError, RuntimeError, ValueError, QdrantStoreError):
            checks["qdrant"] = "not_ready"
    except (OSError, RuntimeError, ValueError, PublishedAssetError):
        checks["assets"] = "not_ready"
    finally:
        if store is not None:
            store.close()
    return checks


if __name__ == "__main__":
    import json

    print(json.dumps(probe_dependencies()))
