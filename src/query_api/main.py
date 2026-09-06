"""Query API 的真实服务入口。"""

import os

from .app import create_app
from .config import load_local_environment
from src.online_query.database import PsycopgQueryExecutor
from src.online_query.llm import LangChainSQLGenerator
from src.online_query.rag_runtime import RagRuntime
from src.online_query.retrieval import OnlineRetriever
from src.online_query.service import OnlineQueryService


load_local_environment()


def build_service() -> OnlineQueryService:
    """使用现有环境配置创建真实 Online Query 服务。"""

    retrieval_provider = None
    if _rag_online_retrieval_enabled():
        retrieval_provider = OnlineRetriever(RagRuntime.from_environment())
    return OnlineQueryService(
        LangChainSQLGenerator.from_env(),
        PsycopgQueryExecutor.from_env(),
        retrieval_provider=retrieval_provider,
    )


def _rag_online_retrieval_enabled() -> bool:
    value = os.getenv("RAG_ONLINE_RETRIEVAL_ENABLED", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


app = create_app(build_service())
