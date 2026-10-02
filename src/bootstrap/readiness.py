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
