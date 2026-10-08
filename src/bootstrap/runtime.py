"""在服务启动期间集中装配运行资源，并持有其完整生命周期。"""

import os
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from openai import DefaultAsyncHttpxClient, DefaultHttpxClient
from sqlalchemy.orm import sessionmaker

from src.authorization import (
    AuthService,
    LocalSessionIdentityProvider,
    PersistentAuditSink,
    RoleAuthorizationPolicyStore,
)
from src.chatbi_control.database import ControlDatabaseConfig, create_control_engine
from src.chatbi_control.history import PostgresHistoryStore
from src.observability.tracing import create_trace_recorder
from src.online_query.database import PsycopgQueryExecutor
from src.online_query.llm import LangChainSQLGenerator
from src.online_query.query_understanding_llm import LangChainQueryUnderstanding
from src.online_query.retrieval import OnlineRetriever
from src.online_query.retrieval.rag_runtime import RagRuntime
from src.online_query.service import OnlineQueryService
from src.query_api.browser import BrowserSettings
from src.query_api.config import load_local_environment, validate_runtime_configuration
from src.query_api.history_runtime import HistoryRuntime
from src.query_api.operations import OperationsState
from src.query_api.runtime import RuntimeDependencies

from .analysis import build_analysis_application
from .backup_status import read_backup_status
from .lifecycle import register_async_cleanup, register_cleanup
from .operations import ObservedModel, OperationsMonitor
from .operations_socket import OperationsSocket
from .readiness import verify_startup_dependencies


@asynccontextmanager
async def create_runtime() -> AsyncIterator[RuntimeDependencies]:
    """每次启动获取新资源，失败或结束时释放；不运行离线初始化。"""

    load_local_environment()
    environment = validate_runtime_configuration()
    secret_key = os.getenv("CHATBI_ADMIN_SECRET_KEY", "").strip()
    if not secret_key:
        raise RuntimeError("CHATBI_ADMIN_SECRET_KEY 必须显式设置")
    if environment in {"production", "prod"} and len(secret_key) < 32:
        raise RuntimeError("production 的 CHATBI_ADMIN_SECRET_KEY 至少需要 32 个字符")

    async with AsyncExitStack() as resources:
        operations = OperationsState(backup_provider=read_backup_status)

        def observe_model(model):
            return ObservedModel(model, operations.record_model)

        recorder = create_trace_recorder()
        register_cleanup(resources, "tracing", recorder.shutdown)
        config = ControlDatabaseConfig.from_environment(require_migrator=False)
        engine = create_control_engine(config)
        register_cleanup(resources, "control_database", engine.dispose)
        sessions = sessionmaker(engine, expire_on_commit=False)
        audit = PersistentAuditSink(sessions)
        auth = AuthService(sessions, audit_sink=audit)
        http_client = DefaultHttpxClient()
        register_cleanup(resources, "llm_http", http_client.close)
        http_async_client = DefaultAsyncHttpxClient()
        register_async_cleanup(resources, "llm_async_http", http_async_client.aclose)
        executor = PsycopgQueryExecutor.from_env()
        rag = None
        retriever = None
        understanding = None
        retrieval_enabled = os.getenv(
            "RAG_ONLINE_RETRIEVAL_ENABLED", "true"
        ).strip().lower() not in {"0", "false", "no", "off"}
        if retrieval_enabled:
            rag = RagRuntime.from_environment()
            register_cleanup(resources, "rag", rag.close)
            retriever = OnlineRetriever(rag, trace_recorder=recorder)
            understanding = LangChainQueryUnderstanding.from_env(
                trace_recorder=recorder,
                http_client=http_client,
                http_async_client=http_async_client,
                model_wrapper=observe_model,
            )
        service = OnlineQueryService(
            LangChainSQLGenerator.from_env(
                trace_recorder=recorder,
                http_client=http_client,
                http_async_client=http_async_client,
                model_wrapper=observe_model,
            ),
            executor,
            retrieval_provider=retriever,
            query_understanding=understanding,
            trace_recorder=recorder,
        )
        verify_startup_dependencies(
            control_engine=engine,
            environment=environment,
            rag_runtime=rag,
            query_executor=executor,
        )

        monitor = OperationsMonitor(operations)
        register_cleanup(resources, "operations_monitor", monitor.close)
        monitor.start()
        status_socket = OperationsSocket(lambda: operations.snapshot(detailed=True))
        register_cleanup(resources, "operations_socket", status_socket.close)
        status_socket.start()

        history_store = PostgresHistoryStore(engine)
        history_runtime = HistoryRuntime(engine, config.app_connection_kwargs())
        register_cleanup(resources, "history", history_runtime.close)

        def analysis_factory(authorized_service):
            analysis = build_analysis_application(
                authorized_service,
                http_client=http_client,
                http_async_client=http_async_client,
                model_wrapper=observe_model,
            )
            register_cleanup(resources, "business_analysis", analysis.close)
            register_cleanup(resources, "history_drain", history_runtime.drain)
            return analysis

        yield RuntimeDependencies(
            service=service,
            operations=operations,
            history_store=history_store,
            history_runtime=history_runtime,
            browser_settings=BrowserSettings.from_environment(os.environ),
            audit_sink=audit,
            auth_service=auth,
            identity_provider=LocalSessionIdentityProvider(auth),
            policy_store=RoleAuthorizationPolicyStore(),
            trace_recorder=recorder,
            query_understanding=understanding,
            analysis_service_factory=analysis_factory,
            admin_engine=engine,
            admin_session_factory=sessions,
            admin_secret_key=secret_key,
        )
