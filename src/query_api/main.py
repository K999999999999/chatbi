"""Query API 的真实服务入口。"""

import os

from sqlalchemy.orm import sessionmaker

from src.authorization import (
    AuthService,
    LocalSessionIdentityProvider,
    PersistentAuditSink,
    RoleAuthorizationPolicyStore,
)
from src.chatbi_control.database import (
    ControlDatabaseConfig,
    ControlDatabaseMigrationError,
    create_control_engine,
    verify_control_schema,
)
from src.observability.tracing import create_trace_recorder
from src.online_query.database import PsycopgQueryExecutor
from src.online_query.llm import LangChainSQLGenerator
from src.online_query.query_understanding_llm import LangChainQueryUnderstanding
from src.online_query.retrieval import OnlineRetriever
from src.online_query.retrieval.rag_runtime import RagRuntime
from src.online_query.service import OnlineQueryService

from .app import create_app
from .config import (
    load_local_environment,
    validate_runtime_configuration,
)

load_local_environment()
_runtime_environment = validate_runtime_configuration()


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


_control_config = ControlDatabaseConfig.from_environment(require_migrator=False)
_control_engine = create_control_engine(_control_config)
_control_session_factory = sessionmaker(_control_engine, expire_on_commit=False)
_audit_sink = PersistentAuditSink(_control_session_factory)
_auth_service = AuthService(_control_session_factory, audit_sink=_audit_sink)
_identity_provider = LocalSessionIdentityProvider(_auth_service)
_policy_store = RoleAuthorizationPolicyStore()
_admin_secret_key = os.getenv("CHATBI_ADMIN_SECRET_KEY", "").strip()
if not _admin_secret_key:
    raise RuntimeError("CHATBI_ADMIN_SECRET_KEY 必须显式设置")
if _runtime_environment in {"production", "prod"} and len(_admin_secret_key) < 32:
    raise RuntimeError("production 的 CHATBI_ADMIN_SECRET_KEY 至少需要 32 个字符")

_service = build_service()
app = create_app(
    _service,
    audit_sink=_audit_sink,
    identity_provider=_identity_provider,
    policy_store=_policy_store,
    auth_service=_auth_service,
    admin_engine=_control_engine,
    admin_secret_key=_admin_secret_key,
    admin_session_factory=_control_session_factory,
    query_understanding=_service.query_understanding,
)


@app.on_event("startup")
def verify_startup_dependencies() -> None:
    """Schema 未完整迁移时阻止认证、管理和查询入口启动。"""

    try:
        verify_control_schema(_control_engine)
    except ControlDatabaseMigrationError:
        _control_engine.dispose()
        raise
