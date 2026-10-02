"""经营分析生产资源装配；业务与语义实现由所属模块提供。"""

from collections.abc import Mapping
from contextlib import ExitStack
from pathlib import Path

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.business_analysis.application import (
    AuthorizedQueryEntry,
    BusinessAnalysisApplication,
)
from src.business_analysis.decomposer import LangChainAnalysisRequestExtractor
from src.business_analysis.reporting import LangChainAnalysisSummarizer
from src.business_analysis.run_store import PostgresAnalysisRunStore
from src.business_analysis.runtime import (
    DEFAULT_DIMENSIONS_PATH,
    DEFAULT_METRICS_PATH,
    _build_chat_model,
    _checkpoint_allowed_types,
    load_analysis_context,
)
from src.chatbi_control.database import ControlDatabaseConfig, create_control_engine

from .lifecycle import register_cleanup


def build_analysis_application(
    authorized_query_service: AuthorizedQueryEntry,
    *,
    environ: Mapping[str, str] | None = None,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    dimensions_path: Path = DEFAULT_DIMENSIONS_PATH,
    http_client: object | None = None,
    http_async_client: object | None = None,
) -> BusinessAnalysisApplication:
    """装配真实 LLM 边缘和当前语义事实。"""

    model = _build_chat_model(
        environ, http_client=http_client, http_async_client=http_async_client
    )
    control_config = ControlDatabaseConfig.from_environment(
        None if environ is None else dict(environ),
        require_migrator=False,
    )
    with ExitStack() as pending:
        control_engine = create_control_engine(control_config)
        register_cleanup(pending, "analysis_database", control_engine.dispose)
        checkpoint_pool = ConnectionPool(
            make_conninfo(**control_config.app_connection_kwargs()),
            kwargs={"autocommit": True, "row_factory": dict_row},
            min_size=1,
            max_size=10,
            open=False,
        )
        register_cleanup(pending, "checkpoint_pool", checkpoint_pool.close)
        checkpoint_pool.open()
        checkpointer = PostgresSaver(
            checkpoint_pool,
            serde=JsonPlusSerializer(
                allowed_msgpack_modules=_checkpoint_allowed_types()
            ),
        )
        application = BusinessAnalysisApplication(
            authorized_query_service,
            decomposer=LangChainAnalysisRequestExtractor(model),
            summarizer=LangChainAnalysisSummarizer(model),
            context_provider=lambda: load_analysis_context(
                metrics_path=metrics_path,
                dimensions_path=dimensions_path,
            ),
            checkpointer=checkpointer,
            run_store=PostgresAnalysisRunStore(control_engine),
        )
        pending.pop_all()
        return application
