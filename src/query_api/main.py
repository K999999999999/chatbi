"""Query API 的真实服务入口。"""

from src.online_query.database import PsycopgQueryExecutor
from src.online_query.llm import LangChainSQLGenerator
from src.online_query.service import OnlineQueryService

from .app import create_app


def build_service() -> OnlineQueryService:
    """使用现有环境配置创建真实 Online Query 服务。"""

    return OnlineQueryService(
        LangChainSQLGenerator.from_env(),
        PsycopgQueryExecutor.from_env(),
    )


app = create_app(build_service())
