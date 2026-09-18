"""Query API 的真实服务入口。"""

import os

from src.authorization import InMemoryAuditSink
from src.observability.tracing import create_trace_recorder
from src.online_query.database import PsycopgQueryExecutor
from src.online_query.llm import LangChainSQLGenerator
from src.online_query.query_understanding_llm import LangChainQueryUnderstanding
from src.online_query.retrieval import OnlineRetriever
from src.online_query.retrieval.rag_runtime import RagRuntime
from src.online_query.service import OnlineQueryService

from .app import create_app
from .config import (
    build_identity_provider,
    build_policy_store,
    load_local_environment,
)

load_local_environment()


def build_service() -> OnlineQueryService:
    """使用现有环境配置创建真实 Online Query 服务。"""

    trace_recorder = create_trace_recorder()
    retrieval_provider = None
    query_understanding = None
    if _rag_online_retrieval_enabled():
        retrieval_provider = OnlineRetriever(
            RagRuntime.from_environment(),
            trace_recorder=trace_recorder,
        )
        query_understanding = LangChainQueryUnderstanding.from_env(
            trace_recorder=trace_recorder,
        )
    return OnlineQueryService(
        LangChainSQLGenerator.from_env(trace_recorder=trace_recorder),
        PsycopgQueryExecutor.from_env(),
        retrieval_provider=retrieval_provider,
        query_understanding=query_understanding,
        trace_recorder=trace_recorder,
    )


def _rag_online_retrieval_enabled() -> bool:
    value = os.getenv("RAG_ONLINE_RETRIEVAL_ENABLED", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


_identity_provider = build_identity_provider()
_policy_store = build_policy_store()
app = create_app(
    build_service(),
    audit_sink=InMemoryAuditSink(),
    identity_provider=_identity_provider,
    policy_store=_policy_store,
)
